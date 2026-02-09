import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="高级财务透视引擎-V19", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 财务数据中心")
symbol = st.sidebar.text_input("输入代码 (如 NVDA, 600519.SS)：", "600519.SS").upper()

# --- 核心辅助函数：深度科目扫描与补偿逻辑 ---
def get_accounting_item(df, primary_keys):
    """深度扫描报表索引，确保键名兼容"""
    # 1. 完全匹配
    for k in primary_keys:
        if k in df.index:
            return df.loc[k].fillna(0)
    # 2. 模糊匹配
    for k in primary_keys:
        search_key = k.lower().replace(" ", "")
        for idx in df.index:
            if search_key in idx.lower().replace(" ", ""):
                return df.loc[idx].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_total_current_assets_safe(bs_stmt):
    """专门修复流动资产：若总计为空，尝试子项求和"""
    ca = get_accounting_item(bs_stmt, ['Total Current Assets', 'Current Assets', 'CurrentAssets'])
    if ca.sum() == 0:
        cash = get_accounting_item(bs_stmt, ['Cash And Cash Equivalents', 'CashCashEquivalentsAndShortTermInvestments'])
        inv = get_accounting_item(bs_stmt, ['Inventory'])
        rec = get_accounting_item(bs_stmt, ['Net Receivables', 'Receivables'])
        ca = cash + inv + rec
    return ca

def get_total_current_liabilities_safe(bs_stmt):
    """专门修复流动负债：若总计为空，尝试子项求和"""
    cl = get_accounting_item(bs_stmt, ['Total Current Liabilities', 'Current Liabilities', 'CurrentLiabilities'])
    if cl.sum() == 0:
        ap = get_accounting_item(bs_stmt, ['Accounts Payable', 'Payables'])
        tax = get_accounting_item(bs_stmt, ['Tax Liabilities', 'Income Tax Payable'])
        cl = ap + tax
    return cl

# --- 主分析函数 ---
def run_v19_engine(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        years = is_stmt.columns
        years_label = [str(y.year) for y in years]
        
        # 1. 营收与盈利能力
        st.header("1️⃣ 盈利规模与利润空间")
        rev = get_accounting_item(is_stmt, ['Total Revenue', 'Revenue'])
        rev_growth = rev.pct_change() * 100
        gp = get_accounting_item(is_stmt, ['Gross Profit'])
        ni = get_accounting_item(is_stmt, ['Net Income'])
        op_inc = get_accounting_item(is_stmt, ['Operating Income']) 
        
        c1, c2 = st.columns(2)
        with c1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收总量", marker_color='royalblue'), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=rev_growth, name="增长率%", line=dict(color='red')), secondary_y=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with c2:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率%", line=dict(width=3)))
            fig_m.add_trace(go.Scatter(x=years_label, y=(ni/rev)*100, name="净利率%", line=dict(width=3)))
            st.plotly_chart(fig_m, use_container_width=True)

        # 2. 盈利质量
        st.write("**盈利质量：核心业务利润分析**")
        estimated_core = op_inc * 0.85
        c_q1, c_q2 = st.columns(2)
        with c_q1:
            fig_core = go.Figure()
            fig_core.add_trace(go.Bar(x=years_label, y=ni, name="报告净利润"))
            fig_core.add_trace(go.Bar(x=years_label, y=estimated_core, name="核心业务利润"))
            st.plotly_chart(fig_core, use_container_width=True)
        with c_q2:
            core_ratio = (estimated_core / ni).clip(0, 1.5) * 100
            st.write("核心利润占比 (%)")
            st.line_chart(core_ratio)

        # 3. 杜邦分析与 ROIC
        st.header("2️⃣ 效率驱动：杜邦分析与 ROIC")
        equity = get_accounting_item(bs_stmt, ['Stockholders Equity', 'Total Equity'])
        assets = get_accounting_item(bs_stmt, ['Total Assets'])
        debt = get_accounting_item(bs_stmt, ['Total Debt'])
        roe = (ni / equity) * 100
        roic = (op_inc * 0.75) / (equity + debt) * 100
        
        d1, d2, d3 = st.columns(3)
        d1.write("**ROE %**"); d1.line_chart(roe)
        d2.write("**ROIC %**"); d2.line_chart(roic)
        d3.write("**权益乘数 (杠杆)**"); d3.line_chart(assets / equity)

        # 4. 营运效率与 C2C
        st.header("3️⃣ 营运效率：现金周期 (C2C)")
        ar = get_accounting_item(bs_stmt, ['Net Receivables', 'Receivables'])
        inv = get_accounting_item(bs_stmt, ['Inventory'])
        ap = get_accounting_item(bs_stmt, ['Accounts Payable'])
        c2c = ((ar / rev) * 365) + ((inv / rev) * 365) - ((ap / rev) * 365)
        
        e1, e2, e3 = st.columns(3)
        with e1:
            st.write("**现金到现金周期 (天)**")
            st.bar_chart(c2c)
        with e2:
            st.write("**存货周转率**")
            st.line_chart(rev / inv)
        with e3:
            st.write("**应收周转率**")
            st.line_chart(rev / ar)

        # 5. 营运资本 (重点修正部分)
        st.write("**营运资本变动 (Working Capital Delta)**")
        # 使用修正后的资产负债获取逻辑
        ca_safe = get_total_current_assets_safe(bs_stmt)
        cl_safe = get_total_current_liabilities_safe(bs_stmt)
        wc = ca_safe - cl_safe
        
        fig_wc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wc.add_trace(go.Bar(x=years_label, y=wc, name="营运资本总量"), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=wc.diff().fillna(0), name="年度变动", line=dict(color='red', width=3)), secondary_y=True)
        fig_wc.update_layout(title="公式: 流动资产(修正) - 流动负债(修正)")
        st.plotly_chart(fig_wc, use_container_width=True)

        # 6. 现金流真实性
        st.header("4️⃣ 现金流真实性与股东回报")
        ocf = get_accounting_item(cf_stmt, ['Operating Cash Flow'])
        capex = get_accounting_item(cf_stmt, ['Capital Expenditure']).abs()
        div = get_accounting_item(cf_stmt, ['Cash Dividends Paid', 'Dividend Paid']).abs()
        
        h1, h2 = st.columns(2)
        with h1:
            fig_cash = go.Figure()
            fig_cash.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
            fig_cash.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
            fig_cash.add_trace(go.Scatter(x=years_label, y=ocf-capex, name="自由现金流"))
            st.plotly_chart(fig_cash, use_container_width=True)
        with h2:
            st.write("**分红比例 (Payout Ratio) %**")
            st.bar_chart((div / ni) * 100)

        # 7. 财务安全评估 (重点修正部分)
        st.header("5️⃣ 财务安全评估")
        total_liab = get_accounting_item(bs_stmt, ['Total Liabilities'])
        interest = get_accounting_item(is_stmt, ['Interest Expense']).abs()
        
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**")
        s1.line_chart((total_liab / assets) * 100)
        
        s2.write("**流动比率 (CA/CL)**")
        # 解决流动比率为 0 的核心：使用 ca_safe 和 cl_safe
        current_ratio = ca_safe / cl_safe
        s2.line_chart(current_ratio)
        
        s3.write("**利息保障倍数**")
        s3.line_chart(op_inc / interest)

        # 8. 综合评估总结
        st.divider()
        st.header("🏁 深度评估总结 (Expert Summary)")
        last_roe = roe.iloc[-1]; last_cash_ratio = (ocf / ni).iloc[-1]
        last_debt = (total_liab/assets).iloc[-1] * 100; last_cr = current_ratio.iloc[-1]

        st.success(f"""
        ### 📊 综合诊断报告：{info.get('shortName', ticker)}
        - **盈利核心**：ROE 为 {last_roe:.2f}%。ROIC 为 {roic.iloc[-1]:.2f}%。
        - **质量透视**：利润含金量（OCF/NI）为 {last_cash_ratio:.2f}。
        - **效率评估**：C2C 周期显示企业{"具备" if c2c.iloc[-1] < 0 else "经营"}周期约 {c2c.iloc[-1]:.1f} 天。
        - **风险底线**：资产负债率 {last_debt:.2f}%。**流动比率为 {last_cr:.2f}** (通常 >1.5 为安全)。
        """)

    except Exception as e:
        st.error(f"分析异常: {e}")

if st.sidebar.button("启动终极全维度分析"):
    run_v19_engine(symbol)
