import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="高级财务透视引擎-V18", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 财务数据中心")
symbol = st.sidebar.text_input("输入代码 (如 NVDA, 600519.SS)：", "NVDA").upper()

# --- 核心辅助函数：解决数据空值与归零问题 ---
def get_accounting_item(df, primary_keys):
    """深度扫描报表索引，确保 A 股/美股键名兼容"""
    # 1. 完全匹配
    for k in primary_keys:
        if k in df.index:
            return df.loc[k].fillna(0)
    # 2. 模糊匹配 (不分大小写，去掉空格)
    for k in primary_keys:
        search_key = k.lower().replace(" ", "")
        for idx in df.index:
            if search_key in idx.lower().replace(" ", ""):
                return df.loc[idx].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

# --- 主分析函数 ---
def run_v18_engine(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        years = is_stmt.columns
        years_label = [str(y.year) for y in years]
        
        # 1. 营收与盈利能力 (KPI 1)
        st.header("1️⃣ 盈利规模与利润空间")
        rev = get_accounting_item(is_stmt, ['Total Revenue', 'Revenue'])
        rev_growth = rev.pct_change() * 100
        gp = get_accounting_item(is_stmt, ['Gross Profit'])
        ni = get_accounting_item(is_stmt, ['Net Income'])
        op_inc = get_accounting_item(is_stmt, ['Operating Income']) # 核心营业利润
        
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

        # 2. 盈利质量 (核心净利润) (KPI 2)
        st.write("**盈利质量：核心业务利润分析**")
        # 估算核心利润 = 营业利润 * 0.85 (剔除平均税及杂项)
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

        # 3. 杜邦分析与 ROIC (KPI 3)
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

        # 4. 营运效率与 C2C (KPI 4)
        st.header("3️⃣ 营运效率：现金周期 (C2C)")
        ar = get_accounting_item(bs_stmt, ['Net Receivables', 'Receivables'])
        inv = get_accounting_item(bs_stmt, ['Inventory'])
        ap = get_accounting_item(bs_stmt, ['Accounts Payable'])
        
        # 解决 C2C 为空的问题：通过营收反算
        dso = (ar / rev) * 365
        dio = (inv / rev) * 365 
        dpo = (ap / rev) * 365
        c2c = dso + dio - dpo
        
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

        # 5. 营运资本 (KPI 5)
        st.write("**营运资本变动 (Working Capital Delta)**")
        ca = get_accounting_item(bs_stmt, ['Total Current Assets'])
        cl = get_accounting_item(bs_stmt, ['Total Current Liabilities'])
        wc = ca - cl
        fig_wc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wc.add_trace(go.Bar(x=years_label, y=wc, name="总量"), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=wc.diff(), name="年度变动", line=dict(color='red')), secondary_y=True)
        st.plotly_chart(fig_wc, use_container_width=True)

        # 6. 现金流与股东回报 (KPI 6)
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

        # 7. 财务安全 (解决 0 问题) (KPI 7)
        st.header("5️⃣ 财务安全评估")
        total_liab = get_accounting_item(bs_stmt, ['Total Liabilities'])
        interest = get_accounting_item(is_stmt, ['Interest Expense']).abs()
        
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((total_liab/assets)*100)
        s2.write("**流动比率**"); s2.line_chart(ca/cl)
        s3.write("**利息保障倍数**"); s3.line_chart(op_inc / interest)

        # 8. 综合评估总结 (新增加)
        st.divider()
        st.header("🏁 深度评估总结 (Expert Summary)")
        
        last_roe = roe.iloc[-1]
        last_c2c = c2c.iloc[-1]
        last_cash_ratio = (ocf / ni).iloc[-1]
        last_debt = (total_liab/assets).iloc[-1] * 100

        diag_p = "盈利能力极强" if last_roe > 20 else "盈利中规中矩"
        diag_c = "现金流非常健康" if last_cash_ratio > 1.1 else "利润含金量有待提高"
        diag_e = "营运极度高效（轻资产）" if last_c2c < 0 else f"营运周期为 {last_c2c:.1f} 天"
        diag_s = "财务稳健" if last_debt < 50 else "负债偏高，需关注偿债压力"

        st.success(f"""
        ### 📊 综合诊断报告：{info.get('shortName', ticker)}
        - **盈利核心**：{diag_p}。当前 ROE 为 {last_roe:.2f}%，ROIC 为 {roic.iloc[-1]:.2f}%。
        - **质量透视**：{diag_c}。当前利润含金量（OCF/NI）为 {last_cash_ratio:.2f}。核心业务利润占比约为 {core_ratio.iloc[-1]:.1f}%。
        - **效率评估**：{diag_e}。C2C 周期显示企业{"具备" if last_c2c < 0 else "缺乏"}对上下游的极强议价能力。
        - **风险底线**：{diag_s}。资产负债率 {last_debt:.2f}%，利息保障倍数为 { (op_inc / interest).iloc[-1] if interest.iloc[-1] !=0 else "无限大" }。
        """)

    except Exception as e:
        st.error(f"分析异常，请确认代码正确或数据源可用: {e}")

if st.sidebar.button("启动终极全维度分析"):
    run_v18_engine(symbol)
