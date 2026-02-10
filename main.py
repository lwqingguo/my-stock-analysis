import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V43", layout="wide")

# 2. 侧边栏常驻逻辑
st.sidebar.header("🔍 数据维度设置")
time_frame = st.sidebar.radio("分析维度：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])
stock_list = {
    "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "英伟达 (NVDA)": "NVDA",
    "特斯拉 (TSLA)": "TSLA"
}
selected_stock = st.sidebar.selectbox("快速选择：", list(stock_list.keys()))
symbol = st.sidebar.text_input("手动输入代码：", stock_list[selected_stock]).upper()

# --- 核心辅助函数：多标签暴力匹配 ---
def get_any(df, tags):
    if df is None or df.empty: return pd.Series([0.0] * 8)
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty: return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主分析引擎 ---
def run_v43_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty or bs_raw.empty:
            st.error("无法获取财务报表数据，请检查代码或网络。")
            return

        # 统一正序与日期轴
        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        # --- 全量指标提取 ---
        rev = get_any(is_df, ['Total Revenue', 'Revenue', 'Operating Revenue'])
        ni = get_any(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_any(is_df, ['EBIT', 'Operating Income'])
        assets = get_any(bs_df, ['Total Assets'])
        equity = get_any(bs_df, ['Stockholders Equity', 'Total Equity'])
        ca = get_any(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_any(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        liab = get_any(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        cash = get_any(bs_df, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'])
        st_debt = get_any(bs_df, ['Short Term Debt', 'Current Debt'])
        ar = get_any(bs_df, ['Net Receivables', 'Receivables'])
        inv = get_any(bs_df, ['Inventory'])
        ap = get_any(bs_df, ['Accounts Payable'])
        ocf = get_any(cf_df, ['Operating Cash Flow'])
        div = get_any(cf_df, ['Cash Dividends Paid', 'Dividends Paid']).abs()
        interest = get_any(is_df, ['Interest Expense', 'Interest Expense Non Operating', 'Financial Expense']).abs()

        # --- 核心比率计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        owc = (ca - cash) - (cl - st_debt)
        roic = ((ebit * 0.75) / (equity + 1).values * 100).fillna(0)

        # --- 新增：打分系统逻辑 ---
        score = 0
        latest_roe = roe.iloc[-1]
        latest_cash_quality = (ocf.iloc[-1] / ni.iloc[-1]) if ni.iloc[-1] != 0 else 0
        latest_debt = debt_ratio.iloc[-1]
        latest_growth = growth.iloc[-1]

        if latest_roe > 15: score += 2
        if latest_cash_quality > 1: score += 2
        if latest_debt < 50: score += 2
        if latest_growth > 10: score += 2
        if c2c.iloc[-1] < 60: score += 2

        # --- 头部诊断展示 ---
        st.title(f"🏛️ 财务全图谱 V43：{stock.info.get('longName', ticker)}")
        col_s, col_t = st.columns([1, 2])
        with col_s:
            color = "#2E7D32" if score >= 8 else "#FFA000" if score >= 6 else "#D32F2F"
            st.markdown(f'''<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;">
                <h1 style="font-size:70px; color:{color}; margin:0;">{score}</h1>
                <p style="color:{color}; font-weight:bold;">综合健康评分</p></div>''', unsafe_allow_html=True)
        with col_t:
            st.subheader("📝 核心诊断总结")
            st.write(f"**盈利能力**：最新 ROE 为 {latest_roe:.2f}%，{'表现优秀' if latest_roe > 15 else '需关注回报率'}。")
            st.write(f"**现金含金量**：经营现金流/净利润为 {latest_cash_quality:.2f}，{'回款极强' if latest_cash_quality > 1 else '现金转化一般'}。")
            st.write(f"**财务杠杆**：资产负债率为 {latest_debt:.1f}%，{'结构稳健' if latest_debt < 60 else '负债偏高'}。")
        st.divider()

        # --- 1-6 全量指标板块 (Plotly 渲染) ---
        # 1. 营收
        st.header("1️⃣ 营收规模与利润空间")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", line=dict(color='red')), secondary_y=True)
        f1.update_xaxes(type='category'); st.plotly_chart(f1, use_container_width=True)

        # 2. 杜邦
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=years, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=years, y=rev/assets*10, name="周转率x10"))
        f2.add_trace(go.Scatter(x=years, y=assets/equity, name="权益乘数"))
        f2.update_xaxes(type='category'); st.plotly_chart(f2, use_container_width=True)

        # 3. ROIC & C2C
        st.header("3️⃣ 经营效率 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("**ROIC %**"); st.line_chart(pd.Series(roic.values, index=years))
        with c32: st.write("**C2C 周期 (天)**"); st.bar_chart(pd.Series(c2c.values, index=years))

        # 4. OWC
        st.header("4️⃣ 营运资产管理 (OWC)")
        st.bar_chart(pd.Series(owc.values, index=years))

        # 5. 现金流与分红
        st.header("5️⃣ 现金流质量与股东回报")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=years, y=ni, name="净利润"))
        f5.add_trace(go.Scatter(x=years, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=years, y=div, name="分红", opacity=0.3))
        f5.update_xaxes(type='category'); st.plotly_chart(f5, use_container_width=True)

        # 6. 安全性
        st.header("6️⃣ 财务安全性评估")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("**资产负债率 %**")
            f61 = go.Figure(go.Scatter(x=years, y=debt_ratio, mode='lines+markers+text', 
                                      text=[f"{x:.1f}%" for x in debt_ratio], textposition="top center"))
            f61.update_layout(xaxis_type='category', height=300); st.plotly_chart(f61, use_container_width=True)
        with c62:
            st.write("**流动比率**")
            f62 = go.Figure(go.Scatter(x=years, y=curr_ratio, mode='lines+markers'))
            f62.update_layout(xaxis_type='category', height=300); st.plotly_chart(f62, use_container_width=True)
        with c63:
            st.write("**利息保障倍数**")
            f63 = go.Figure(go.Scatter(x=years, y=int_cover, mode='lines+markers'))
            f63.update_layout(xaxis_type='category', height=300); st.plotly_chart(f63, use_container_width=True)

    except Exception as e:
        st.error(f"分析引擎发生错误: {e}")

# 启动按钮
if st.sidebar.button("启动 V43 全量诊断版"):
    run_v43_engine(symbol, time_frame == "年度趋势 (Annual)")
