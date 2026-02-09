import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V29", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 核心数据源")
examples = {
    "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "英伟达 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA"
}
selected_example = st.sidebar.selectbox("快速选择知名企业：", list(examples.keys()))
symbol = st.sidebar.text_input("或手动输入代码：", examples[selected_example]).upper()

# --- 核心辅助函数 (保留所有修复逻辑) ---
def get_item_safe(df, keys):
    if df is None or df.empty: return pd.Series([0.0])
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    for k in keys:
        search = k.lower().replace(" ", "")
        for idx in df.index:
            if search in str(idx).lower().replace(" ", ""): return df.loc[idx].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_ca_cl_robust(bs_stmt):
    ca = get_item_safe(bs_stmt, ['Total Current Assets', 'Current Assets', 'CurrentAssets'])
    if ca.sum() == 0:
        cash = get_item_safe(bs_stmt, ['Cash And Cash Equivalents', 'CashAndCashEquivalents'])
        inv = get_item_safe(bs_stmt, ['Inventory'])
        rec = get_item_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        ca = cash + inv + rec
    cl = get_item_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities', 'CurrentLiabilities'])
    if cl.sum() == 0:
        ap = get_item_safe(bs_stmt, ['Accounts Payable', 'Payables'])
        tax = get_item_safe(bs_stmt, ['Tax Liabilities', 'Income Tax Payable'])
        cl = ap + tax
    return ca, cl

# --- 主分析引擎 ---
def run_v29_engine(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        years_label = [str(y.year) for y in is_stmt.columns]

        st.title(f"🏛️ 旗舰级财务全图谱 V29：{info.get('longName', ticker)}")
        st.divider()

        # --- 预计算所有评分所需的 KPI ---
        rev = get_item_safe(is_stmt, ['Total Revenue', 'Revenue'])
        ni = get_item_safe(is_stmt, ['Net Income'])
        gp = get_item_safe(is_stmt, ['Gross Profit'])
        equity = get_item_safe(bs_stmt, ['Stockholders Equity', 'Total Equity'])
        assets = get_item_safe(bs_stmt, ['Total Assets'])
        ocf = get_item_safe(cf_stmt, ['Operating Cash Flow'])
        ca, cl = get_ca_cl_robust(bs_stmt)
        ar = get_item_safe(bs_stmt, ['Net Receivables'])
        inv = get_item_safe(bs_stmt, ['Inventory'])
        ap = get_item_safe(bs_stmt, ['Accounts Payable'])
        
        roe = (ni / equity) * 100
        curr_ratio = ca / cl
        c2c = ((ar/rev)*365) + ((inv/rev)*365) - ((ap/rev)*365)
        growth = rev.pct_change()
        cash_q = ocf / ni

        # --- [重点] 评分逻辑与大字展示 ---
        score = 0
        details = []
        if roe.iloc[-1] > 15: score += 2; details.append("✅ **盈利能力**：ROE > 15%，属顶级水平")
        else: details.append("❌ **盈利能力**：ROE 未达 15%")
        if cash_q.iloc[-1] > 1: score += 2; details.append("✅ **利润质量**：经营现金流 > 净利润，钱真到手了")
        else: details.append("❌ **利润质量**：现金含金量不足")
        if curr_ratio.iloc[-1] > 1.2: score += 2; details.append("✅ **财务安全**：流动比率健康")
        else: details.append("❌ **财务安全**：流动比率偏低")
        if c2c.iloc[-1] < 60: score += 2; details.append("✅ **营运效率**：C2C 周期极短，资金周转快")
        else: details.append("❌ **营运效率**：周转周期偏长")
        if growth.iloc[-1] > 0.1: score += 2; details.append("✅ **成长速度**：营收增长 > 10%，在扩张")
        else: details.append("❌ **成长速度**：增速放缓")

        # 视觉渲染
        c_score, c_desc = st.columns([1, 2])
        with c_score:
            color = "#2E7D32" if score >= 8 else "#FFA000" if score >= 6 else "#D32F2F"
            st.markdown(f"""
                <div style="text-align: center; border: 5px solid {color}; border-radius: 15px; padding: 20px; background-color: #f9f9f9;">
                    <p style="margin: 0; font-size: 22px; color: #666;">综合财务健康分</p>
                    <h1 style="margin: 0; font-size: 100px; color: {color}; font-weight: bold;">{score}</h1>
                    <p style="margin: 0; font-size: 20px; color: {color};">Total Score / 10</p>
                </div>
            """, unsafe_allow_html=True)
        with c_desc:
            st.subheader("📊 诊断报告明细")
            for d in details: st.write(d)
            st.info("💡 提示：点击下方各板块可查看详细 KPI 数据支撑。")

        st.divider()

        # --- 以下保留所有之前的专业指标板块 ---
        
        # 1. 营收与盈利
        st.header("1️⃣ 盈利规模与利润空间")
        col1, col2 = st.columns(2)
        with col1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收总量"), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=growth*100, name="增速%", line=dict(color='red')), secondary_y=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with col2:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率%"))
            fig_m.add_trace(go.Scatter(x=years_label, y=(ni/rev)*100, name="净利率%"))
            st.plotly_chart(fig_m, use_container_width=True)

        # 2. 核心利润质量
        st.write("**核心盈利质量分析**")
        op_inc = get_item_safe(is_stmt, ['Operating Income'])
        est_core = op_inc * 0.85
        cq1, cq2 = st.columns(2)
        with cq1:
            fig_core = go.Figure()
            fig_core.add_trace(go.Bar(x=years_label, y=ni, name="净利润"))
            fig_core.add_trace(go.Bar(x=years_label, y=est_core, name="核心利润"))
            st.plotly_chart(fig_core, use_container_width=True)
        with cq2:
            st.write("核心利润占比 (%)"); st.line_chart(((est_core/ni).clip(0,2))*100)

        # 3. 杜邦动因 (三要素)
        st.header("2️⃣ 效率驱动：ROE 增长动因拆解")
        net_margin = (ni / rev) * 100
        asset_turnover = rev / assets
        equity_multiplier = assets / equity
        d_c1, d_c2, d_c3, d_c4 = st.columns(4)
        d_c1.metric("ROE %", f"{roe.iloc[-1]:.2f}%")
        d_c2.metric("销售净利率", f"{net_margin.iloc[-1]:.2f}%")
        d_c3.metric("资产周转率", f"{asset_turnover.iloc[-1]:.2f}")
        d_c4.metric("权益乘数", f"{equity_multiplier.iloc[-1]:.2f}")
        fig_dupont = go.Figure()
        fig_dupont.add_trace(go.Scatter(x=years_label, y=net_margin, name="1.净利率"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=asset_turnover*10, name="2.周转率x10"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=equity_multiplier, name="3.权益乘数"))
        st.plotly_chart(fig_dupont, use_container_width=True)

        # 4. ROIC 与 C2C
        st.header("3️⃣ 核心经营效率")
        debt = get_item_safe(bs_stmt, ['Total Debt'])
        roic = (op_inc * 0.75) / (equity + debt) * 100
        r1, r2 = st.columns(2)
        with r1:
            st.write("**ROIC % (投入资本回报率)**"); st.line_chart(roic)
        with r2:
            st.write("**C2C 现金周期 (天)**"); st.bar_chart(c2c)

        # 5. OWC (经营性营运资本)
        st.header("4️⃣ 营运资产管理：OWC")
        cash = get_item_safe(bs_stmt, ['Cash And Cash Equivalents'])
        st_debt = get_item_safe(bs_stmt, ['Short Term Debt', 'Current Debt'])
        owc = (ca - cash) - (cl - st_debt)
        fig_owc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_owc.add_trace(go.Bar(x=years_label, y=owc, name="OWC总量"), secondary_y=False)
        fig_owc.add_trace(go.Scatter(x=years_label, y=owc.diff(), name="变动ΔOWC", line=dict(color='orange')), secondary_y=True)
        st.plotly_chart(fig_owc, use_container_width=True)
        st.info("💡 OWC 负值或下降通常代表公司在‘白嫖’上下游资金，是非常强势的信号。")

        # 6. 现金流真实性
        st.header("5️⃣ 现金流真实性与股东回报")
        capex = get_item_safe(cf_stmt, ['Capital Expenditure']).abs()
        div = get_item_safe(cf_stmt, ['Cash Dividends Paid']).abs()
        h1, h2 = st.columns(2)
        with h1:
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf-capex, name="自由现金流"))
            st.plotly_chart(fig_cf, use_container_width=True)
        with h2:
            st.write("**分红比例 %**"); st.bar_chart((div/ni)*100)

        # 7. 财务安全
        st.header("6️⃣ 财务安全性评估")
        liab = get_item_safe(bs_stmt, ['Total Liabilities'])
        interest = get_item_safe(is_stmt, ['Interest Expense']).abs()
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((liab/assets)*100)
        s2.write("**流动比率 (CA/CL)**"); s2.line_chart(curr_ratio)
        s3.write("**利息保障倍数**"); s3.line_chart(op_inc/interest)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("一键启动旗舰诊断引擎"):
    run_v29_engine(symbol)
