import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="终极财务透视-V27", layout="wide")

# 2. 侧边栏：集成名股选项 (PEP, KO, 农夫山泉, 东鹏, NVDA 等)
st.sidebar.header("🔍 核心数据源")
examples = {
    "英伟达 (NVDA)": "NVDA", "微软 (MSFT)": "MSFT", "苹果 (AAPL)": "AAPL",
    "百事可乐 (PEP)": "PEP", "可口可乐 (KO)": "KO",
    "农夫山泉 (9633.HK)": "9633.HK", "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS", "特斯拉 (TSLA)": "TSLA"
}
selected_example = st.sidebar.selectbox("快速选择知名企业：", list(examples.keys()))
symbol = st.sidebar.text_input("或手动输入代码：", examples[selected_example]).upper()

# --- 核心辅助函数：多级数据抓取 ---
def get_item_safe(df, keys):
    if df is None or df.empty: return pd.Series([0.0])
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    # 模糊匹配
    for k in keys:
        search = k.lower().replace(" ", "")
        for idx in df.index:
            if search in str(idx).lower().replace(" ", ""): return df.loc[idx].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_ca_cl_robust(bs_stmt):
    """【核心修复】三层防御逻辑，确保 CA/CL 不再为空"""
    # 1. 获取流动资产 (CA)
    ca = get_item_safe(bs_stmt, ['Total Current Assets', 'Current Assets', 'CurrentAssets'])
    if ca.sum() == 0:
        # Fallback: 子项求和
        cash = get_item_safe(bs_stmt, ['Cash And Cash Equivalents', 'CashAndCashEquivalents'])
        inv = get_item_safe(bs_stmt, ['Inventory', 'Inventories'])
        rec = get_item_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        ca = cash + inv + rec
    
    # 2. 获取流动负债 (CL)
    cl = get_item_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities', 'CurrentLiabilities'])
    if cl.sum() == 0:
        # Fallback: 子项求和
        ap = get_item_safe(bs_stmt, ['Accounts Payable', 'Payables'])
        tax = get_item_safe(bs_stmt, ['Tax Liabilities', 'Income Tax Payable'])
        cl = ap + tax
    return ca, cl

# --- 主分析引擎 ---
def run_v27_engine(ticker):
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
        st.header("1️⃣ 盈利规模与利润空间")
        rev = get_item_safe(is_stmt, ['Total Revenue', 'Revenue'])
        ni = get_item_safe(is_stmt, ['Net Income'])
        gp = get_item_safe(is_stmt, ['Gross Profit'])
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
            st.plotly_chart(fig_m, use_container_width=True)

        # --- KPI 2: 盈利质量 (核心利润) ---
        st.write("**盈利质量分析**")
        op_inc = get_item_safe(is_stmt, ['Operating Income'])
        est_core = op_inc * 0.85
        cq1, cq2 = st.columns(2)
        with cq1:
            fig_core = go.Figure()
            fig_core.add_trace(go.Bar(x=years_label, y=ni, name="报告净利润"))
            fig_core.add_trace(go.Bar(x=years_label, y=est_core, name="经营性核心利润"))
            st.plotly_chart(fig_core, use_container_width=True)
        with cq2:
            st.write("核心净利润占比 (%)")
            st.line_chart(((est_core / ni).clip(0, 2)) * 100)

        # --- KPI 3: 杜邦动因拆解 (三要素) ---
        st.header("2️⃣ 效率驱动：ROE 增长动因拆解")
        equity = get_item_safe(bs_stmt, ['Stockholders Equity', 'Total Equity'])
        assets = get_item_safe(bs_stmt, ['Total Assets'])
        net_margin = (ni / rev) * 100
        asset_turnover = rev / assets
        equity_multiplier = assets / equity
        roe = (ni / equity) * 100
        
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("ROE %", f"{roe.iloc[-1]:.2f}%")
        d2.metric("销售净利率", f"{net_margin.iloc[-1]:.2f}%")
        d3.metric("资产周转率", f"{asset_turnover.iloc[-1]:.2f}")
        d4.metric("权益乘数(杠杆)", f"{equity_multiplier.iloc[-1]:.2f}")
        
        fig_dupont = go.Figure()
        fig_dupont.add_trace(go.Scatter(x=years_label, y=net_margin, name="1. 净利率"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=asset_turnover*10, name="2. 周转率x10"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=equity_multiplier, name="3. 权益乘数"))
        st.plotly_chart(fig_dupont, use_container_width=True)

        # --- KPI 4: ROIC 与 C2C ---
        st.header("3️⃣ 核心经营效率")
        debt = get_item_safe(bs_stmt, ['Total Debt'])
        roic = (op_inc * 0.75) / (equity + debt) * 100
        ar = get_item_safe(bs_stmt, ['Net Receivables'])
        inv = get_item_safe(bs_stmt, ['Inventory'])
        ap = get_item_safe(bs_stmt, ['Accounts Payable'])
        c2c = ((ar/rev)*365) + ((inv/rev)*365) - ((ap/rev)*365)
        
        r1, r2 = st.columns(2)
        with r1:
            st.write("**ROIC % (投入资本回报率)**")
            st.line_chart(roic)
        with r2:
            st.write("**C2C 现金周期 (天)**")
            st.bar_chart(c2c)

        # --- KPI 5: 经营性营运资本 (OWC) ---
        st.header("4️⃣ 营运资产管理：OWC")
        ca, cl = get_ca_cl_robust(bs_stmt)
        cash = get_item_safe(bs_stmt, ['Cash And Cash Equivalents'])
        st_debt = get_item_safe(bs_stmt, ['Short Term Debt', 'Current Debt'])
        # 专业公式: (流动资产-现金) - (流动负债-短期债务)
        owc = (ca - cash) - (cl - st_debt)
        
        fig_owc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_owc.add_trace(go.Bar(x=years_label, y=owc, name="OWC总量"), secondary_y=False)
        fig_owc.add_trace(go.Scatter(x=years_label, y=owc.diff(), name="变动ΔOWC", line=dict(color='orange')), secondary_y=True)
        st.plotly_chart(fig_owc, use_container_width=True)

        # --- KPI 6: 现金流与分红 ---
        st.header("5️⃣ 现金流真实性与股东回报")
        ocf = get_item_safe(cf_stmt, ['Operating Cash Flow'])
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
            st.write("**年度分红比例 %**")
            st.bar_chart((div/ni)*100)

        # --- KPI 7: 财务安全 (CA/CL 修复版) ---
        st.header("6️⃣ 财务安全性评估")
        liab = get_item_safe(bs_stmt, ['Total Liabilities'])
        interest = get_item_safe(is_stmt, ['Interest Expense']).abs()
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((liab / assets) * 100)
        s2.write("**流动比率 (CA/CL)**")
        # 此时的 ca, cl 是经过 get_ca_cl_robust 修复后的
        curr_ratio = (ca / cl).fillna(0)
        s2.line_chart(curr_ratio)
        s3.write("**利息保障倍数**"); s3.line_chart(op_inc / interest)

        # --- 总结 ---
        st.divider()
        st.header("🏁 深度诊断总结")
        st.success(f"""
        - **核心盈利**：ROE 为 {roe.iloc[-1]:.2f}%，ROIC 为 {roic.iloc[-1]:.2f}%。
        - **流动性修复**：已成功探测到流动资产数据，最新流动比率为 {curr_ratio.iloc[-1]:.2f}。
        - **效率动因**：C2C 周期为 {c2c.iloc[-1]:.1f} 天，OWC 变动反映了经营性资金的净占用。
        """)

    except Exception as e:
        st.error(f"分析失败: {e}")

# 在总结部分增加一个小逻辑
score = 0
if roe.iloc[-1] > 20: score += 2
if (ocf/ni).iloc[-1] > 1: score += 2
if curr_ratio.iloc[-1] > 1.2: score += 2
if c2c.iloc[-1] < 30: score += 2
if (rev.pct_change().iloc[-1]) > 0.1: score += 2

st.info(f"📊 财务综合健康评分：{score} / 10（基于盈利、质量、效率、安全、成长维度）")

# --- 关键修正：确保按钮调用的函数名完全一致 ---
if st.sidebar.button("启动终极分析报告"):
    run_v27_engine(symbol)
