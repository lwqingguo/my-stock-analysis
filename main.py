import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V46", layout="wide")

# 2. 侧边栏常驻 (增加 By Q 过滤维度)
st.sidebar.header("🔍 数据分析维度")
time_frame = st.sidebar.radio("1. 选择频率：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])

q_filter = []
if time_frame == "季度趋势 (Quarterly)":
    st.sidebar.subheader("📅 By Q 维度筛选")
    # 默认全选，用户可以取消勾选来只看特定的 Q
    q_opts = {"Q1 (3月)": "-03", "Q2 (6月)": "-06", "Q3 (9月)": "-09", "Q4 (12月)": "-12"}
    selected_qs = st.sidebar.multiselect("只看特定季度点：", list(q_opts.keys()), default=list(q_opts.keys()))
    q_filter = [q_opts[q] for q in selected_qs]

stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA", "特斯拉": "TSLA"}
selected_stock = st.sidebar.selectbox("2. 快速选择：", list(stock_list.keys()))
symbol = st.sidebar.text_input("3. 手动代码：", stock_list[selected_stock]).upper()

# --- 核心辅助函数 ---
def get_any(df, tags):
    if df is None or df.empty: return pd.Series([0.0] * 8)
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty: return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v46_engine(ticker, is_annual, q_months):
    try:
        stock = yf.Ticker(ticker)
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        # 1. 基础数据对齐
        is_df = is_raw.sort_index(axis=1, ascending=True)
        bs_df = bs_raw.sort_index(axis=1, ascending=True)
        cf_df = cf_raw.sort_index(axis=1, ascending=True)

        # 2. 🔥 By Q 趋势过滤逻辑
        if not is_annual and q_months:
            mask = is_df.columns.map(lambda x: any(m in x.strftime('%Y-%m') for m in q_months))
            is_df, bs_df, cf_df = is_df.loc[:, mask], bs_df.loc[:, mask], cf_df.loc[:, mask]

        # 3. 截取最近8期并格式化
        is_df, bs_df, cf_df = is_df.iloc[:, -8:], bs_df.iloc[:, -8:], cf_df.iloc[:, -8:]
        labels = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = labels

        # --- 全量指标提取 (零删减) ---
        rev = get_any(is_df, ['Total Revenue', 'Revenue'])
        ni = get_any(is_df, ['Net Income'])
        ebit = get_any(is_df, ['EBIT', 'Operating Income'])
        gp = get_any(is_df, ['Gross Profit'])
        assets = get_any(bs_df, ['Total Assets'])
        equity = get_any(bs_df, ['Stockholders Equity', 'Total Equity'])
        ca = get_any(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_any(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        liab = get_any(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        cash = get_any(bs_df, ['Cash And Cash Equivalents'])
        st_debt = get_any(bs_df, ['Short Term Debt'])
        ar, inv, ap = get_any(bs_df, ['Net Receivables']), get_any(bs_df, ['Inventory']), get_any(bs_df, ['Accounts Payable'])
        ocf = get_any(cf_df, ['Operating Cash Flow'])
        div = get_any(cf_df, ['Cash Dividends Paid']).abs()
        interest = get_any(is_df, ['Interest Expense', 'Financial Expense']).abs()

        # 计算
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        roic = ((ebit * 0.75) / (equity + 1).values * 100).fillna(0)
        owc = (ca - cash) - (cl - st_debt)

        # --- 打分与诊断总结 (归位) ---
        score = 0
        if not roe.empty:
            if roe.iloc[-1] > 15: score += 2
            if (ocf.iloc[-1]/ni.iloc[-1] if ni.iloc[-1]!=0 else 0) > 1: score += 2
            if debt_ratio.iloc[-1] < 50: score += 2
            if growth.iloc[-1] > 10: score += 2
            if c2c.iloc[-1] < 60: score += 2

        st.title(f"🏛️ 财务透视 By Q 趋势版：{ticker}")
        c_score, c_diag = st.columns([1, 2])
        with c_score:
            color = "#2E7D32" if score >= 8 else "#FFA000"
            st.markdown(f'''<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;">
                <h1 style="font-size:60px; color:{color}; margin:0;">{score}</h1><p>综合评分</p></div>''', unsafe_allow_html=True)
        with c_diag:
            st.subheader("📝 核心诊断")
            st.write(f"**分析基准**：最新点为 {labels[-1]}。")
            st.write(f"**关键指标**：ROE {roe.iloc[-1]:.2f}% | 负债率 {debt_ratio.iloc[-1]:.1f}% | C2C {c2c.iloc[-1]:.0f}天")
        st.divider()

        # --- 六大板块图表 (全量保留) ---
        st.header("1️⃣ 营收规模与增长趋势")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=labels, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=labels, y=growth, name="增速%", line=dict(color='red')), secondary_y=True)
        f1.update_xaxes(type='category'); st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 盈利效率 (ROE 杜邦分析)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=labels, y=rev/assets*10, name="周转率x10"))
        f2.add_trace(go.Scatter(x=labels, y=assets/equity, name="权益乘数"))
        f2.update_xaxes(type='category'); st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 经营细节 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("**ROIC %**"); st.line_chart(pd.Series(roic.values, index=labels))
        with c32: st.write("**C2C 现金周期 (天)**"); st.bar_chart(pd.Series(c2c.values, index=labels))

        st.header("4️⃣ 营运资产管理 (OWC)")
        st.bar_chart(pd.Series(owc.values, index=labels))

        st.header("5️⃣ 现金流质量与股东回报")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=labels, y=ni, name="净利润"))
        f5.add_trace(go.Scatter(x=labels, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=labels, y=div, name="分红", opacity=0.3))
        f5.update_xaxes(type='category'); st.plotly_chart(f5, use_container_width=True)

        st.header("6️⃣ 财务安全性 (By Q 趋势)")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("**资产负债率 %**")
            f61 = go.Figure(go.Scatter(x=labels, y=debt_ratio, mode='lines+markers+text', text=[f"{x:.1f}" for x in debt_ratio]))
            f61.update_layout(xaxis_type='category', height=300); st.plotly_chart(f61, use_container_width=True)
        with c62:
            st.write("**流动比率**")
            f62 = go.Figure(go.Scatter(x=labels, y=curr_ratio, mode='lines+markers'))
            f62.update_layout(xaxis_type='category', height=300); st.plotly_chart(f62, use_container_width=True)
        with c63:
            st.write("**利息保障倍数**")
            f63 = go.Figure(go.Scatter(x=labels, y=int_cover, mode='lines+markers'))
            f63.update_layout(xaxis_type='category', height=300); st.plotly_chart(f63, use_container_width=True)

    except Exception as e:
        st.error(f"分析引擎发生错误: {e}")

if st.sidebar.button("启动 V46 全量 By Q 诊断"):
    run_v46_engine(symbol, time_frame == "年度趋势 (Annual)", q_filter)
