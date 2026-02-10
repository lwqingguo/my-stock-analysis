import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V30", layout="wide")

# 2. 侧边栏：维度切换开关
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
def run_v30_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        # 根据维度调取数据
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -8:] if is_annual else stock.quarterly_income_stmt.sort_index(axis=1).iloc[:, -8:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -8:] if is_annual else stock.quarterly_cashflow.sort_index(axis=1).iloc[:, -8:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -8:] if is_annual else stock.quarterly_balance_sheet.sort_index(axis=1).iloc[:, -8:]
        
        if is_stmt.empty:
            st.error("数据调取失败，请检查代码或尝试切换维度。")
            return

        info = stock.info
        years_label = [y.strftime('%Y-%m') for y in is_stmt.columns] # 统一格式：2024-12
        last_report = years_label[-1]

        st.title(f"🏛️ 财务全图谱 V30：{info.get('longName', ticker)}")
        st.caption(f"当前分析维度：{time_frame} | 最新报告期：{last_report}")
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
        
        roe = (ni / equity) * 100
        curr_ratio = ca / cl
        c2c = ((ar/rev)*365) + ((inv/rev)*365) - ((ap/rev)*365)
        growth = rev.pct_change()
        cash_q = ocf / ni

        # --- 顶部评分模块 (大字报) ---
        score = 0
        details = []
        if roe.iloc[-1] > 15: score += 2; details.append(f"✅ **盈利能力**：ROE({roe.iloc[-1]:.1f}%) > 15%")
        else: details.append(f"❌ **盈利能力**：ROE 未达 15%")
        if cash_q.iloc[-1] > 1: score += 2; details.append(f"✅ **利润质量**：经营现金流 > 净利润")
        else: details.append(f"❌ **利润质量**：现金含金量不足")
        if curr_ratio.iloc[-1] > 1.2: score += 2; details.append(f"✅ **财务安全**：流动比率健康")
        else: details.append(f"❌ **财务安全**：流动性指标扣分")
        if c2c.iloc[-1] < 60: score += 2; details.append(f"✅ **营运效率**：C2C 周期极短")
        else: details.append(f"❌ **营运效率**：资金周转较慢")
        if (growth.iloc[-1] > 0.1 if is_annual else growth.iloc[-1] > 0.03): score += 2; details.append(f"✅ **成长速度**：扩张表现强劲")
        else: details.append(f"❌ **成长速度**：增速有所放缓")

        c_score, c_desc = st.columns([1, 2])
        with c_score:
            color = "#2E7D32" if score >= 8 else "#FFA000" if score >= 6 else "#D32F2F"
            st.markdown(f"""
                <div style="text-align: center; border: 5px solid {color}; border-radius: 15px; padding: 20px; background: #F8F9FA;">
                    <p style="margin: 0; font-size: 20px; color: #666;">最新体检评分</p>
                    <h1 style="margin: 0; font-size: 100px; color: {color}; font-weight: bold;">{score}</h1>
                    <p style="margin: 0; font-size: 18px; color: {color};">基于报告期: {last_report}</p>
                </div>
            """, unsafe_allow_html=True)
        with c_desc:
            st.subheader("📊 诊断报告明细")
            for d in details: st.write(d)
        st.divider()

        # --- 保留全量指标板块 ---
        # 1. 营收与盈利空间
        st.header("1️⃣ 营收规模与利润空间")
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

        # 2. 杜邦动因
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        net_margin = (ni / rev) * 100
        asset_turnover = rev / assets
        equity_multiplier = assets / equity
        fig_dupont = go.Figure()
        fig_dupont.add_trace(go.Scatter(x=years_label, y=net_margin, name="1.净利率"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=asset_turnover*10, name="2.周转率x10"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=equity_multiplier, name="3.权益乘数"))
        st.plotly_chart(fig_dupont, use_container_width=True)

        # 3. ROIC 与 C2C
        st.header("3️⃣ 核心经营效率 (ROIC & C2C)")
        debt = get_item_safe(bs_stmt, ['Total Debt'])
        roic = (op_inc * 0.75) / (equity + debt) * 100
        r1, r2 = st.columns(2)
        with r1: st.write("**ROIC % (投入资本回报率)**"); st.line_chart(roic)
        with r2: st.write("**C2C 现金周期 (天)**"); st.bar_chart(c2c)

        # 4. OWC (关键指标)
        st.header("4️⃣ 经营性营运资本 (OWC) 变动")
        owc = (ca - cash) - (cl - st_debt)
        fig_owc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_owc.add_trace(go.Bar(x=years_label, y=owc, name="OWC总量"), secondary_y=False)
        fig_owc.add_trace(go.Scatter(x=years_label, y=owc.diff(), name="变动ΔOWC", line=dict(color='orange')), secondary_y=True)
        st.plotly_chart(fig_owc, use_container_width=True)
        st.info("💡 OWC 负值代表公司在“无息占用”上下游资金。")

        # 5. 现金流与安全性
        st.header("5️⃣ 现金流真实性与财务安全")
        s1, s2 = st.columns(2)
        with s1:
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
            st.plotly_chart(fig_cf, use_container_width=True)
        with s2:
            st.write("**资产负债率 %**"); st.line_chart((liab/assets)*100)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("启动 V30 旗舰引擎"):
    run_v30_engine(symbol, time_frame == "年度趋势 (Annual)")
