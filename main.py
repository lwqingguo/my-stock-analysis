import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V31", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 数据维度设置")
time_frame = st.sidebar.radio("选择分析维度：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])
st.sidebar.divider()

examples = {
    "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "英伟达 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA"
}
selected_example = st.sidebar.selectbox("快速选择知名企业：", list(examples.keys()))
symbol = st.sidebar.text_input("或手动输入代码：", examples[selected_example]).upper()

# --- 核心辅助函数 (数据清洗与安全获取) ---
def get_item_safe(df, keys):
    if df is None or df.empty: return pd.Series([0.0])
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_ca_cl_robust(bs_stmt):
    ca = get_item_safe(bs_stmt, ['Total Current Assets', 'Current Assets'])
    cl = get_item_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
    return ca, cl

# --- 主分析引擎 ---
def run_v31_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        
        # 抓取数据并强制按时间正序排列
        if is_annual:
            is_stmt = stock.income_stmt.sort_index(axis=1, ascending=True).iloc[:, -8:]
            cf_stmt = stock.cashflow.sort_index(axis=1, ascending=True).iloc[:, -8:]
            bs_stmt = stock.balance_sheet.sort_index(axis=1, ascending=True).iloc[:, -8:]
        else:
            is_stmt = stock.quarterly_income_stmt.sort_index(axis=1, ascending=True).iloc[:, -8:]
            cf_stmt = stock.quarterly_cashflow.sort_index(axis=1, ascending=True).iloc[:, -8:]
            bs_stmt = stock.quarterly_balance_sheet.sort_index(axis=1, ascending=True).iloc[:, -8:]

        if is_stmt.empty:
            st.error("数据调取失败，请检查代码或尝试切换维度。")
            return

        # 核心日期逻辑：使用报告期结束日作为标签
        years_label = [d.strftime('%Y-%m') for d in is_stmt.columns]
        last_report_date = years_label[-1]

        info = stock.info
        st.title(f"🏛️ 财务全图谱 V31：{info.get('longName', ticker)}")
        st.caption(f"分析维度：{time_frame} | 报告截止日：{last_report_date}")
        st.divider()

        # --- KPI 预计算 ---
        rev = get_item_safe(is_stmt, ['Total Revenue', 'Revenue'])
        ni = get_item_safe(is_stmt, ['Net Income'])
        gp = get_item_safe(is_stmt, ['Gross Profit'])
        op_inc = get_item_safe(is_stmt, ['Operating Income'])
        equity = get_item_safe(bs_stmt, ['Stockholders Equity', 'Total Equity'])
        assets = get_item_safe(bs_stmt, ['Total Assets'])
        ocf = get_item_safe(cf_stmt, ['Operating Cash Flow'])
        ca, cl = get_ca_cl_robust(bs_stmt)
        ar = get_item_safe(bs_stmt, ['Net Receivables'])
        inv = get_item_safe(bs_stmt, ['Inventory'])
        ap = get_item_safe(bs_stmt, ['Accounts Payable'])
        cash = get_item_safe(bs_stmt, ['Cash And Cash Equivalents'])
        st_debt = get_item_safe(bs_stmt, ['Short Term Debt', 'Current Debt'])
        liab = get_item_safe(bs_stmt, ['Total Liabilities'])
        interest = get_item_safe(is_stmt, ['Interest Expense']).abs()
        div = get_item_safe(cf_stmt, ['Cash Dividends Paid']).abs()
        capex = get_item_safe(cf_stmt, ['Capital Expenditure']).abs()

        roe = (ni / equity) * 100
        curr_ratio = ca / cl
        c2c = ((ar/rev)*365) + ((inv/rev)*365) - ((ap/rev)*365)
        growth = rev.pct_change()
        cash_q = ocf / ni

        # --- 评分模块 (大字报) ---
        score = 0
        details = []
        if roe.iloc[-1] > 15: score += 2; details.append(f"✅ **盈利能力**：ROE({roe.iloc[-1]:.1f}%) > 15%")
        else: details.append(f"❌ **盈利能力**：ROE 未达标")
        if cash_q.iloc[-1] > 1: score += 2; details.append(f"✅ **利润质量**：经营现金流覆盖净利润")
        else: details.append(f"❌ **利润质量**：现金流支撑较弱")
        if curr_ratio.iloc[-1] > 1.2: score += 2; details.append(f"✅ **财务安全**：流动比率健康")
        else: details.append(f"❌ **财务安全**：短期偿债指标扣分")
        if c2c.iloc[-1] < 60: score += 2; details.append(f"✅ **运营效率**：C2C周期极短")
        else: details.append(f"❌ **运营效率**：资金周转效率待提高")
        g_limit = 0.1 if is_annual else 0.03
        if growth.iloc[-1] > g_limit: score += 2; details.append(f"✅ **成长速度**：扩张势头良好")
        else: details.append(f"❌ **成长速度**：增速有所放缓")

        c1, c2 = st.columns([1, 2])
        with c1:
            color = "#2E7D32" if score >= 8 else "#FFA000" if score >= 6 else "#D32F2F"
            st.markdown(f'<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px; background:#F8F9FA;"><p style="color:#666; margin:0;">综合诊断评分</p><h1 style="font-size:100px; color:{color}; font-weight:bold; margin:0;">{score}</h1><p style="color:{color}; margin:0;">报告期截止: {last_report_date}</p></div>', unsafe_allow_html=True)
        with c2:
            st.subheader("📊 诊断明细表")
            for d in details: st.write(d)
        st.divider()

        # --- 板块 1: 营收与盈利空间 ---
        st.header("1️⃣ 营收规模与利润空间")
        col1, col2 = st.columns(2)
        with col1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收"), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=growth*100, name="增速%", line=dict(color='red')), secondary_y=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with col2:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率%"))
            fig_m.add_trace(go.Scatter(x=years_label, y=(ni/rev)*100, name="净利率%"))
            st.plotly_chart(fig_m, use_container_width=True)

        # --- 板块 2: 杜邦动因分析 ---
        st.header("2️⃣ 效率驱动：ROE 动因拆解 (杜邦分析)")
        
        fig_dupont = go.Figure()
        fig_dupont.add_trace(go.Scatter(x=years_label, y=(ni/rev)*100, name="1.销售净利率%"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=(rev/assets)*10, name="2.资产周转率x10"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=assets/equity, name="3.权益乘数"))
        st.plotly_chart(fig_dupont, use_container_width=True)

        # --- 板块 3: ROIC 与 C2C ---
        st.header("3️⃣ 核心经营效率 (ROIC & C2C)")
        debt = get_item_safe(bs_stmt, ['Total Debt'])
        roic = (op_inc * 0.75) / (equity + debt) * 100
        r_c1, r_c2 = st.columns(2)
        with r_c1: st.write("**ROIC % (投入资本回报率)**"); st.line_chart(roic)
        with r_c2: st.write("**C2C 现金周期 (天)**"); st.bar_chart(c2c)

        # --- 板块 4: OWC 经营性营运资本 ---
        st.header("4️⃣ 营运资产管理 (OWC)")
        owc = (ca - cash) - (cl - st_debt)
        fig_owc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_owc.add_trace(go.Bar(x=years_label, y=owc, name="OWC总量"), secondary_y=False)
        fig_owc.add_trace(go.Scatter(x=years_label, y=owc.diff(), name="变动ΔOWC", line=dict(color='orange')), secondary_y=True)
        st.plotly_chart(fig_owc, use_container_width=True)
        st.info("💡 OWC 负值代表公司在无息占用上下游资金，是商业地位强势的标志。")

        # --- 板块 5: 现金流真实性 ---
        st.header("5️⃣ 现金流质量与分红回报")
        cf_c1, cf_c2 = st.columns(2)
        with cf_c1:
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf-capex, name="自由现金流"))
            st.plotly_chart(fig_cf, use_container_width=True)
        with cf_c2:
            st.write("**股利支付率 %**"); st.bar_chart((div/ni)*100)

        # --- 板块 6: 财务安全性 ---
        st.header("6️⃣ 财务安全性评估")
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((liab/assets)*100)
        s2.write("**流动比率 (CA/CL)**"); s2.line_chart(curr_ratio)
        s3.write("**利息保障倍数**"); s3.line_chart(op_inc/interest)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("一键启动 V31 旗舰诊断"):
    run_v31_engine(symbol, time_frame == "年度趋势 (Annual)")
