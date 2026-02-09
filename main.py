import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务透视引擎-V22", layout="wide")

# 2. 侧边栏：保留著名公司选项
st.sidebar.header("🔍 财务数据中心")
examples = {
    "手动输入": "",
    "英伟达 (NVDA)": "NVDA", "微软 (MSFT)": "MSFT", "苹果 (AAPL)": "AAPL",
    "百事可乐 (PEP)": "PEP", "可口可乐 (KO)": "KO",
    "农夫山泉 (9633.HK)": "9633.HK", "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS", "特斯拉 (TSLA)": "TSLA"
}
selected_example = st.sidebar.selectbox("快速选择知名企业：", list(examples.keys()))
default_symbol = examples[selected_example] if examples[selected_example] else "NVDA"
symbol = st.sidebar.text_input("输入代码：", default_symbol).upper()

# --- 核心辅助函数：多级数据抓取 ---
def get_accounting_item(df, primary_keys):
    for k in primary_keys:
        if k in df.index: return df.loc[k].fillna(0)
    for k in primary_keys:
        search_key = k.lower().replace(" ", "")
        for idx in df.index:
            if search_key in idx.lower().replace(" ", ""):
                return df.loc[idx].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_total_current_assets_safe(bs_stmt):
    ca = get_accounting_item(bs_stmt, ['Total Current Assets', 'Current Assets'])
    if ca.sum() == 0:
        ca = get_accounting_item(bs_stmt, ['Cash And Cash Equivalents']) + \
             get_accounting_item(bs_stmt, ['Inventory']) + \
             get_accounting_item(bs_stmt, ['Net Receivables', 'Receivables'])
    return ca

def get_total_current_liabilities_safe(bs_stmt):
    cl = get_accounting_item(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
    if cl.sum() == 0:
        cl = get_accounting_item(bs_stmt, ['Accounts Payable']) + \
             get_accounting_item(bs_stmt, ['Tax Liabilities', 'Income Tax Payable'])
    return cl

# --- 主分析函数 ---
def run_v22_engine(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        years_label = [str(y.year) for y in is_stmt.columns]

        st.title(f"🏛️ 全维度财务透视旗舰版 V22：{info.get('longName', ticker)}")
        st.divider()

        # 1. 盈利规模与成长 (营收柱状图 + 增速线)
        st.header("1️⃣ 盈利规模与成长动力")
        rev = get_accounting_item(is_stmt, ['Total Revenue', 'Revenue'])
        ni = get_accounting_item(is_stmt, ['Net Income'])
        gp = get_accounting_item(is_stmt, ['Gross Profit'])
        op_inc = get_accounting_item(is_stmt, ['Operating Income']) 
        
        c1, c2 = st.columns(2)
        with c1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收总量", marker_color='royalblue'), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=rev.pct_change()*100, name="营收增速%", line=dict(color='red')), secondary_y=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with c2:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率%", line=dict(width=3)))
            fig_m.add_trace(go.Scatter(x=years_label, y=(ni/rev)*100, name="净利率%", line=dict(width=3)))
            st.plotly_chart(fig_m, use_container_width=True)

        # 2. 盈利质量 (核心利润分析)
        st.write("**盈利质量：核心营业利润与净利润对比**")
        estimated_core = op_inc * 0.85 # 剔除估算税费后的经营利润
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

        # 4. 专业营运资本分析 (OWC 公式修正)
        st.header("3️⃣ 营运效率：专业经营性营运资本")
        ca_safe = get_total_current_assets_safe(bs_stmt)
        cl_safe = get_total_current_liabilities_safe(bs_stmt)
        cash = get_accounting_item(bs_stmt, ['Cash And Cash Equivalents', 'CashCashEquivalentsAndShortTermInvestments'])
        st_debt = get_accounting_item(bs_stmt, ['Short Term Debt', 'Current Debt', 'CurrentLiabilities']) # A股通常包含在流动负债
        
        # 专业公式: (流动资产 - 现金) - (流动负债 - 短期债务)
        # 注意：此处简化处理，若找不到明确的短期债务，则仅剔除现金。
        owc = (ca_safe - cash) - (cl_safe) 
        
        fig_wc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wc.add_trace(go.Bar(x=years_label, y=owc, name="经营性营运资本 (OWC)"), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=owc.diff().fillna(0), name="年度变动 (ΔWC)", line=dict(color='orange', width=3)), secondary_y=True)
        fig_wc.update_layout(title="专业公式：(流动资产-现金) - 流动负债")
        st.plotly_chart(fig_wc, use_container_width=True)

        # 5. 现金周期 C2C (保留项)
        st.write("**现金到现金周期分析 (C2C)**")
        ar = get_accounting_item(bs_stmt, ['Net Receivables', 'Receivables'])
        inv = get_accounting_item(bs_stmt, ['Inventory'])
        ap = get_accounting_item(bs_stmt, ['Accounts Payable'])
        c2c = ((ar / rev) * 365) + ((inv / rev) * 365) - ((ap / rev) * 365)
        st.bar_chart(c2c)

        # 6. 现金流与股东回报
        st.header("4️⃣ 现金流真实性与股东回报")
        ocf = get_accounting_item(cf_stmt, ['Operating Cash Flow'])
        capex = get_accounting_item(cf_stmt, ['Capital Expenditure']).abs()
        div = get_accounting_item(cf_stmt, ['Cash Dividends Paid']).abs()
        
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

        # 7. 财务安全 (解决流动比率归零问题)
        st.header("5️⃣ 财务安全评估")
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((get_accounting_item(bs_stmt, ['Total Liabilities'])/assets)*100)
        s2.write("**流动比率 (修正CA/CL)**"); s2.line_chart(ca_safe / cl_safe)
        s3.write("**利息保障倍数**"); s3.line_chart(op_inc / get_accounting_item(is_stmt, ['Interest Expense']).abs())

        # 8. 深度诊断总结
        st.divider()
        st.header("🏁 综合评估总结 (Financial Summary)")
        last_roe = roe.iloc[-1]; last_cr = (ca_safe / cl_safe).iloc[-1]
        last_cash_quality = (ocf / ni).iloc[-1]; last_debt = (get_accounting_item(bs_stmt, ['Total Liabilities'])/assets).iloc[-1]*100

        st.success(f"""
        **{info.get('shortName', ticker)} 诊断报告：**
        - **盈利效率**：最新 ROE 为 {last_roe:.2f}%，ROIC 为 {roic.iloc[-1]:.2f}%。
        - **质量透视**：利润含金量（OCF/NI）为 {last_cash_quality:.2f}。核心利润占比为 {core_ratio.iloc[-1]:.1f}%。
        - **资金管理**：经营性营运资本 (OWC) 变动为 {owc.diff().iloc[-1]/1e8:.2f} 亿。C2C 周期为 {c2c.iloc[-1]:.1f} 天。
        - **安全边际**：流动比率为 {last_cr:.2f}，资产负债率为 {last_debt:.2f}%。
        """)

    except Exception as e:
        st.error(f"分析失败，请检查代码或网络: {e}")

if st.sidebar.button("启动旗舰级全维度分析"):
    run_v22_engine(symbol)
