import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="终极财务透视-V24", layout="wide")

# 2. 侧边栏：集成名股选项
st.sidebar.header("🔍 核心数据源")
examples = {
    "英伟达 (NVDA)": "NVDA", "微软 (MSFT)": "MSFT", "苹果 (AAPL)": "AAPL",
    "百事可乐 (PEP)": "PEP", "可口可乐 (KO)": "KO",
    "农夫山泉 (9633.HK)": "9633.HK", "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS", "特斯拉 (TSLA)": "TSLA"
}
selected_example = st.sidebar.selectbox("快速选择知名企业：", list(examples.keys()))
symbol = st.sidebar.text_input("或手动输入代码：", examples[selected_example]).upper()

# --- 核心辅助函数：解决 A 股/美股兼容与归零问题 ---
def get_item(df, keys):
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    for k in keys:
        search = k.lower().replace(" ", "")
        for idx in df.index:
            if search in idx.lower().replace(" ", ""): return df.loc[idx].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

# --- 主分析引擎 ---
def run_v24_engine(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        years_label = [str(y.year) for y in is_stmt.columns]

        st.title(f"🏛️ 旗舰级财务全图谱：{info.get('longName', ticker)}")
        st.divider()

        # --- KPI 1: 营收与成长 ---
        st.header("1️⃣ 营收规模与利润空间")
        rev = get_item(is_stmt, ['Total Revenue', 'Revenue'])
        ni = get_item(is_stmt, ['Net Income'])
        gp = get_item(is_stmt, ['Gross Profit'])
        
        c1, c2 = st.columns(2)
        with c1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收总量"), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=rev.pct_change()*100, name="增速%", line=dict(color='red')), secondary_y=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with c2:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率%", line=dict(width=3)))
            fig_m.add_trace(go.Scatter(x=years_label, y=(ni/rev)*100, name="净利率%", line=dict(width=3)))
            fig_m.update_layout(title="盈利水平趋势")
            st.plotly_chart(fig_m, use_container_width=True)

        # --- KPI 2: 盈利质量 (核心利润) ---
        st.write("**盈利质量分析**")
        op_inc = get_item(is_stmt, ['Operating Income'])
        est_core = op_inc * 0.85
        cq1, cq2 = st.columns(2)
        with cq1:
            fig_core = go.Figure()
            fig_core.add_trace(go.Bar(x=years_label, y=ni, name="报告净利润"))
            fig_core.add_trace(go.Bar(x=years_label, y=est_core, name="经营性核心利润"))
            st.plotly_chart(fig_core, use_container_width=True)
        with cq2:
            st.write("核心净利润 / 净利润 (%)")
            st.line_chart(((est_core / ni).clip(0, 2)) * 100)

        # --- KPI 3: 杜邦分析与 ROIC ---
        st.header("2️⃣ 效率驱动：杜邦分析与 ROIC")
        equity = get_item(bs_stmt, ['Stockholders Equity', 'Total Equity'])
        assets = get_item(bs_stmt, ['Total Assets'])
        debt = get_item(bs_stmt, ['Total Debt'])
        roe = (ni / equity) * 100
        roic = (op_inc * 0.75) / (equity + debt) * 100
        
        d1, d2, d3 = st.columns(3)
        d1.write("**ROE %**"); d1.line_chart(roe)
        d2.write("**ROIC %**"); d2.line_chart(roic)
        d3.write("**权益乘数 (杠杆)**"); d3.line_chart(assets / equity)

        # --- KPI 4 & 5: 营运效率与经营性营运资本 (OWC修正) ---
        st.header("3️⃣ 营运资产管理：C2C 与 OWC")
        ar = get_item(bs_stmt, ['Net Receivables', 'Receivables'])
        inv = get_item(bs_stmt, ['Inventory'])
        ap = get_item(bs_stmt, ['Accounts Payable'])
        c2c = ((ar / rev) * 365) + ((inv / rev) * 365) - ((ap / rev) * 365)
        
        ca = get_item(bs_stmt, ['Total Current Assets'])
        cl = get_item(bs_stmt, ['Total Current Liabilities'])
        cash = get_item(bs_stmt, ['Cash And Cash Equivalents'])
        st_debt = get_item(bs_stmt, ['Short Term Debt', 'Current Debt'])
        # 专业 OWC 公式: (流动资产 - 现金) - (流动负债 - 短期债务)
        owc = (ca - cash) - (cl - st_debt)
        
        e1, e2 = st.columns(2)
        with e1:
            st.write("**现金到现金周期 (天)**")
            st.bar_chart(c2c)
        with e2:
            fig_owc = make_subplots(specs=[[{"secondary_y": True}]])
            fig_owc.add_trace(go.Bar(x=years_label, y=owc, name="经营性营运资本 (OWC)"), secondary_y=False)
            fig_owc.add_trace(go.Scatter(x=years_label, y=owc.diff(), name="变动 ΔOWC", line=dict(color='orange')), secondary_y=True)
            st.plotly_chart(fig_owc, use_container_width=True)

        # --- KPI 6: 现金流与分红 ---
        st.header("4️⃣ 现金流真实性与股东回报")
        ocf = get_item(cf_stmt, ['Operating Cash Flow'])
        capex = get_item(cf_stmt, ['Capital Expenditure']).abs()
        div = get_item(cf_stmt, ['Cash Dividends Paid', 'Dividend Paid']).abs()
        
        h1, h2 = st.columns(2)
        with h1:
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf-capex, name="自由现金流"))
            st.plotly_chart(fig_cf, use_container_width=True)
        with h2:
            st.write("**分红比例 (Payout Ratio) %**")
            st.bar_chart((div / ni) * 100)

        # --- KPI 7: 财务安全 ---
        st.header("5️⃣ 财务安全性评估")
        liab = get_item(bs_stmt, ['Total Liabilities'])
        interest = get_item(is_stmt, ['Interest Expense']).abs()
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((liab / assets) * 100)
        s2.write("**流动比率 (CA/CL)**"); s2.line_chart(ca / cl)
        s3.write("**利息保障倍数**"); s3.line_chart(op_inc / interest)

        # --- 最终总结 ---
        st.divider()
        st.header("🏁 综合诊断总结")
        last_roe = roe.iloc[-1]; last_c2c = c2c.iloc[-1]
        st.success(f"""
        **{info.get('shortName', ticker)} 核心结论：**
        - **盈利能力**：ROE 为 {last_roe:.2f}%，核心利润占比稳定，盈利含金量(OCF/NI)为 {(ocf/ni).iloc[-1]:.2f}。
        - **效率效率**：C2C 周期为 {last_c2c:.1f} 天。经营性营运资本 (OWC) 最新值为 {owc.iloc[-1]/1e8:.2f} 亿。
        - **风险控制**：流动比率为 {(ca/cl).iloc[-1]:.2f}，资产负债率 {(liab/assets).iloc[-1]*100:.2f}%。
        """)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("启动终极分析报告"):
    run_v24_engine(symbol)
