import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V47", layout="wide")

# 2. 侧边栏 UI 精进优化
st.sidebar.header("🛡️ 诊断控制中心")

# 频率选择
time_frame = st.sidebar.selectbox("1. 报表频率", ["年度 (Annual)", "季度 (Quarterly)"], index=1)

# By Q 深度透视逻辑
q_filter_months = []
if time_frame == "季度 (Quarterly)":
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 By Q 深度透视设置")
    use_q_pivot = st.sidebar.toggle("开启特定季度趋势对比", value=True)
    
    if use_q_pivot:
        q_choice = st.sidebar.radio("选择要回溯的季度点：", ["Q1 (3月)", "Q2 (6月)", "Q3 (9月)", "Q4 (12月)"], index=2)
        q_map = {"Q1 (3月)": "-03", "Q2 (6月)": "-06", "Q3 (9月)": "-09", "Q4 (12月)": "-12"}
        q_filter_months = [q_map[q_choice]]
        st.sidebar.caption(f"系统将提取历年所有 {q_choice} 数据进行趋势分析")

st.sidebar.markdown("---")
stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA", "特斯拉": "TSLA"}
selected_stock = st.sidebar.selectbox("2. 快捷公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("3. 股票代码", stock_list[selected_stock]).upper()

# --- 核心辅助函数：数据抓取与补全 ---
def get_safe(df, tags):
    if df is None or df.empty: return pd.Series(dtype=float)
    for tag in tags:
        if tag in df.index:
            return df.loc[tag].replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v47_engine(ticker, is_annual, filter_q):
    try:
        stock = yf.Ticker(ticker)
        # 抓取所有可用历史（不限制数量）
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty:
            st.error("无法获取数据，请检查网络或代码。")
            return

        # 1. 初始排序
        is_df = is_raw.sort_index(axis=1, ascending=True)
        bs_df = bs_raw.sort_index(axis=1, ascending=True)
        cf_df = cf_raw.sort_index(axis=1, ascending=True)

        # 2. 🔥 By Q 深度过滤 (如果是季度模式且开启了过滤)
        if not is_annual and filter_q:
            # 筛选所有符合月份要求的列（例如所有3月报表）
            mask = is_df.columns.map(lambda x: any(m in x.strftime('%Y-%m') for m in filter_q))
            is_df = is_df.loc[:, mask]
            bs_df = bs_df.loc[:, mask]
            cf_df = cf_df.loc[:, mask]
        else:
            # 普通模式：截取最近12期
            is_df = is_df.iloc[:, -12:]
            bs_df = bs_df.iloc[:, -12:]
            cf_df = cf_df.iloc[:, -12:]

        # 3. 标签处理
        labels = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = labels

        # --- 全量指标 (一个不删) ---
        rev = get_safe(is_df, ['Total Revenue', 'Revenue'])
        ni = get_safe(is_df, ['Net Income'])
        ebit = get_safe(is_df, ['EBIT', 'Operating Income'])
        assets = get_safe(bs_df, ['Total Assets'])
        equity = get_safe(bs_df, ['Stockholders Equity', 'Total Equity'])
        ca = get_safe(bs_df, ['Total Current Assets'])
        cl = get_safe(bs_df, ['Total Current Liabilities'])
        liab = get_safe(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        ar, inv, ap = get_safe(bs_df, ['Net Receivables']), get_safe(bs_df, ['Inventory']), get_safe(bs_df, ['Accounts Payable'])
        ocf = get_safe(cf_df, ['Operating Cash Flow'])
        div = get_safe(cf_df, ['Cash Dividends Paid']).abs()
        interest = get_safe(is_df, ['Interest Expense', 'Financial Expense']).abs()

        # 计算
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)

        # --- 头部总结与打分 ---
        score = 0
        if not roe.empty:
            if roe.iloc[-1] > 15: score += 2
            if (ocf.iloc[-1]/ni.iloc[-1] if ni.iloc[-1]!=0 else 0) > 1: score += 2
            if debt_ratio.iloc[-1] < 50: score += 2
            if growth.iloc[-1] > 10: score += 2
            if c2c.iloc[-1] < 60: score += 2

        st.title(f"🏛️ 财务 By Q 深度透视 V47：{ticker}")
        st.caption(f"当前模式：{'特定季度同比趋势' if filter_q else '连续季度趋势'} | 覆盖点数：{len(labels)}")
        
        c1, c2 = st.columns([1, 2])
        with c1:
            color = "#2E7D32" if score >= 8 else "#FFA000"
            st.markdown(f'<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;"><h1 style="font-size:60px; color:{color};">{score}</h1><p>综合健康分</p></div>', unsafe_allow_html=True)
        with c2:
            st.subheader("📋 深度诊断报告")
            st.write(f"**趋势分析**：基于历年 {labels[-1][-2:]} 月数据的对比分析。")
            st.write(f"**核心提示**：{labels[-1]} 负债率为 {debt_ratio.iloc[-1]:.1f}%，较上一对比期{'上升' if debt_ratio.diff().iloc[-1]>0 else '下降'}。")
        st.divider()

        # --- 六大图表 (全量不删) ---
        st.header("1️⃣ 历年营收与增速同比趋势")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=labels, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=labels, y=growth, name="同比增速%", line=dict(color='red', width=3)), secondary_y=True)
        f1.update_xaxes(type='category'); st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 盈利效率 (ROE 杜邦分析)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=labels, y=rev/assets*10, name="资产周转x10"))
        f2.add_trace(go.Scatter(x=labels, y=assets/equity, name="权益乘数"))
        f2.update_xaxes(type='category'); st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 经营细节 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("**ROIC %**"); st.line_chart(pd.Series((ebit*0.75)/(equity+1).values, index=labels))
        with c32: st.write("**C2C 现金周期 (天)**"); st.bar_chart(pd.Series(c2c.values, index=labels))

        st.header("4️⃣ 营运资产管理 (OWC)")
        st.bar_chart(pd.Series((ca-cl).values, index=labels))

        st.header("5️⃣ 现金流质量与股东回报")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=labels, y=ni, name="净利润"))
        f5.add_trace(go.Scatter(x=labels, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=labels, y=div, name="分红", opacity=0.3))
        f5.update_xaxes(type='category'); st.plotly_chart(f5, use_container_width=True)

        st.header("6️⃣ 财务安全性评估")
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
        st.error(f"引擎运行失败: {e}")

if st.sidebar.button("🚀 执行深度 By Q 诊断"):
    run_v47_engine(symbol, time_frame == "年度 (Annual)", q_filter_months)
