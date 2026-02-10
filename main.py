import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V44", layout="wide")

# 2. 侧边栏常驻逻辑
st.sidebar.header("🔍 数据维度设置")
time_frame = st.sidebar.radio("分析维度：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])

# --- 新增：季度细分过滤器 ---
selected_q_months = []
if time_frame == "季度趋势 (Quarterly)":
    st.sidebar.subheader("📅 季度过滤 (可多选)")
    q_map = {"Q1 (3月)": "-03", "Q2 (6月)": "-06", "Q3 (9月)": "-09", "Q4 (12月)": "-12"}
    # 默认全选
    selected_qs = st.sidebar.multiselect("选择显示的季度点：", list(q_map.keys()), default=list(q_map.keys()))
    selected_q_months = [q_map[q] for q in selected_qs]

stock_list = {
    "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "英伟达 (NVDA)": "NVDA",
    "特斯拉 (TSLA)": "TSLA"
}
selected_stock = st.sidebar.selectbox("快速选择：", list(stock_list.keys()))
symbol = st.sidebar.text_input("手动输入代码：", stock_list[selected_stock]).upper()

# --- 核心辅助函数 ---
def get_any(df, tags):
    if df is None or df.empty: return pd.Series([0.0] * 8)
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty: return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主分析引擎 ---
def run_v44_engine(ticker, is_annual, q_filter):
    try:
        stock = yf.Ticker(ticker)
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty or bs_raw.empty:
            st.error("无法获取财务报表数据。")
            return

        # --- 季度/年度过滤逻辑 ---
        # 1. 统一正序
        is_df = is_raw.sort_index(axis=1, ascending=True)
        bs_df = bs_raw.sort_index(axis=1, ascending=True)
        cf_df = cf_raw.sort_index(axis=1, ascending=True)

        # 2. 如果是季度且有过滤条件
        if not is_annual and q_filter:
            mask = is_df.columns.map(lambda x: any(m in x.strftime('%Y-%m') for m in q_filter))
            is_df = is_df.loc[:, mask]
            bs_df = bs_df.loc[:, mask]
            cf_df = cf_df.loc[:, mask]

        # 3. 截取最近8期并格式化坐标
        is_df = is_df.iloc[:, -8:]
        bs_df = bs_df.iloc[:, -8:]
        cf_df = cf_df.iloc[:, -8:]
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        # --- 全量指标提取 (保持 V43 的高稳定性) ---
        rev = get_any(is_df, ['Total Revenue', 'Revenue', 'Operating Revenue'])
        ni = get_any(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_any(is_df, ['EBIT', 'Operating Income'])
        assets = get_any(bs_df, ['Total Assets'])
        equity = get_any(bs_df, ['Stockholders Equity', 'Total Equity'])
        ca = get_any(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_any(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        liab = get_any(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        cash = get_any(bs_df, ['Cash And Cash Equivalents'])
        st_debt = get_any(bs_df, ['Short Term Debt', 'Current Debt'])
        ar = get_any(bs_df, ['Net Receivables'])
        inv = get_any(bs_df, ['Inventory'])
        ap = get_any(bs_df, ['Accounts Payable'])
        ocf = get_any(cf_df, ['Operating Cash Flow'])
        div = get_any(cf_df, ['Cash Dividends Paid']).abs()
        interest = get_any(is_df, ['Interest Expense', 'Financial Expense']).abs()

        # --- 核心计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        owc = (ca - cash) - (cl - st_debt)
        roic = ((ebit * 0.75) / (equity + 1).values * 100).fillna(0)

        # --- 打分系统 ---
        score = 0
        if not roe.empty:
            l_roe = roe.iloc[-1]; l_cash = (ocf.iloc[-1]/ni.iloc[-1]) if ni.iloc[-1]!=0 else 0
            if l_roe > 15: score += 2
            if l_cash > 1: score += 2
            if debt_ratio.iloc[-1] < 50: score += 2
            if growth.iloc[-1] > 10: score += 2
            if c2c.iloc[-1] < 60: score += 2

        # --- 头部展示 ---
        st.title(f"🏛️ 财务全图谱 V44：{symbol}")
        c_s, c_t = st.columns([1, 2])
        with c_s:
            color = "#2E7D32" if score >= 8 else "#FFA000"
            st.markdown(f'<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;"><h1 style="font-size:70px; color:{color};">{score}</h1><p>健康评分</p></div>', unsafe_allow_html=True)
        with c_t:
            st.subheader("📝 季度筛选诊断")
            st.write(f"当前分析包含周期：{', '.join(years)}")
            st.write(f"最新 ROE ({years[-1]}): {roe.iloc[-1]:.2f}%")

        # --- 图表区 (全量保留) ---
        st.header("1️⃣ 营收与增长")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%"), secondary_y=True)
        f1.update_xaxes(type='category'); st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 杜邦分析")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=years, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=years, y=rev/assets*10, name="周转率x10"))
        f2.update_xaxes(type='category'); st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 经营效率 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.line_chart(pd.Series(roic.values, index=years))
        with c32: st.bar_chart(pd.Series(c2c.values, index=years))

        st.header("4️⃣ 营运资产 (OWC)")
        st.bar_chart(pd.Series(owc.values, index=years))

        st.header("5️⃣ 现金流与分红")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=years, y=ni, name="利润"))
        f5.add_trace(go.Scatter(x=years, y=ocf, name="现金流"))
        f5.add_trace(go.Bar(x=years, y=div, name="分红", opacity=0.3))
        f5.update_xaxes(type='category'); st.plotly_chart(f5, use_container_width=True)

        st.header("6️⃣ 安全性评估")
        c61, c62, c63 = st.columns(3)
        with c61: st.write("负债率%"); st.line_chart(pd.Series(debt_ratio.values, index=years))
        with c62: st.write("流动比"); st.line_chart(pd.Series(curr_ratio.values, index=years))
        with c63: st.write("利息倍数"); st.line_chart(pd.Series(int_cover.values, index=years))

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("启动 V44 精准诊断"):
    run_v44_engine(symbol, time_frame == "年度趋势 (Annual)", selected_q_months)
