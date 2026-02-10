import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V48", layout="wide")

# 2. 侧边栏优化：更直观的交互
st.sidebar.header("📊 诊断模式配置")
mode = st.sidebar.selectbox("1. 分析频率", ["年度 (Annual) 深度对比", "季度 (Quarterly) 深度透视"], index=1)

q_pivot_month = None
if "季度" in mode:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 By Q 趋势透视")
    # 提供明确的 Q 选择
    q_target = st.sidebar.radio("选择要回溯的特定季度：", ["Q1 (3月)", "Q2 (6月)", "Q3 (9月)", "Q4 (12月)"], index=0)
    q_map = {"Q1 (3月)": "-03", "Q2 (6月)": "-06", "Q3 (9月)": "-09", "Q4 (12月)": "-12"}
    q_pivot_month = q_map[q_target]
    st.sidebar.info(f"开启后，图表将展示历年所有 {q_target} 的趋势对比（看 5-10 年走势）。")

st.sidebar.markdown("---")
stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA"}
selected_stock = st.sidebar.selectbox("2. 快捷选择公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("3. 股票代码", stock_list[selected_stock]).upper()

# --- 核心辅助函数：三级防撞抓取逻辑 ---
def get_safe_metric(df, primary_tags, fallback_logic=None):
    if df is None or df.empty: return pd.Series(dtype=float)
    # 1. 尝试主标签
    for tag in primary_tags:
        if tag in df.index:
            vals = df.loc[tag].replace('-', np.nan).astype(float)
            if not vals.dropna().empty: return vals.fillna(0.0)
    # 2. 尝试逻辑倒算 (如 资产 - 权益)
    if fallback_logic is not None:
        try:
            return fallback_logic().fillna(0.0)
        except:
            pass
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v48_engine(ticker, is_annual, q_month):
    try:
        stock = yf.Ticker(ticker)
        # 抓取全量历史报表
        is_df = (stock.income_stmt if is_annual else stock.quarterly_income_stmt).sort_index(axis=1, ascending=True)
        bs_df = (stock.balance_sheet if is_annual else stock.quarterly_balance_sheet).sort_index(axis=1, ascending=True)
        cf_df = (stock.cashflow if is_annual else stock.quarterly_cashflow).sort_index(axis=1, ascending=True)

        if is_df.empty:
            st.error("数据源返回为空，请检查代码后缀是否正确（如 .SS 或 .SZ）。")
            return

        # 🔥 By Q 深度趋势切片：如果是季度模式，筛选所有历史年份的对应月份
        if not is_annual and q_month:
            mask = is_df.columns.map(lambda x: q_month in x.strftime('%Y-%m'))
            is_df, bs_df, cf_df = is_df.loc[:, mask], bs_df.loc[:, mask], cf_df.loc[:, mask]
        
        # 确保至少有 3-4 年数据进行展示，不设上限以展示长趋势
        labels = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = labels

        # --- 指标提取 (强力修正版) ---
        rev = get_safe_metric(is_df, ['Total Revenue', 'Revenue', 'Operating Revenue'])
        ni = get_safe_metric(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_safe_metric(is_df, ['EBIT', 'Operating Income'])
        
        assets = get_safe_metric(bs_df, ['Total Assets'])
        equity = get_safe_metric(bs_df, ['Stockholders Equity', 'Total Equity'])
        # 负债强力修复：总负债 -> (资产-权益) -> (流动+非流动)
        liab = get_safe_metric(bs_df, ['Total Liabilities'], 
                              fallback_logic=lambda: assets - equity)
        
        ca = get_safe_metric(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_safe_metric(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        
        ar = get_safe_metric(bs_df, ['Net Receivables', 'Receivables'])
        inv = get_safe_metric(bs_df, ['Inventory'])
        ap = get_safe_metric(bs_df, ['Accounts Payable'])
        
        ocf = get_safe_metric(cf_df, ['Operating Cash Flow'])
        div = get_safe_metric(cf_df, ['Cash Dividends Paid', 'Dividends Paid']).abs()
        # 利息支出强力修复：利息支出 -> 财务费用
        interest = get_safe_metric(is_df, ['Interest Expense', 'Financial Expense']).abs()

        # --- 计算核心比率 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).replace([np.inf, -np.inf], 0).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        roic = ((ebit * 0.75) / (equity + 1).values * 100).fillna(0)

        # --- 页面展示 ---
        st.title(f"🏛️ 财务全图谱 V48 (终极 By Q 版)：{ticker}")
        
        # 打分系统
        score = 0
        if not roe.empty:
            if roe.iloc[-1] > 15: score += 2
            if (ocf.iloc[-1]/ni.iloc[-1] if ni.iloc[-1]!=0 else 0) > 1: score += 2
            if debt_ratio.iloc[-1] < 50: score += 2
            if growth.iloc[-1] > 10: score += 2
            if c2c.iloc[-1] < 60: score += 2

        col_score, col_text = st.columns([1, 2])
        with col_score:
            color = "#2E7D32" if score >= 8 else "#FFA000"
            st.markdown(f'''<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;">
                <h1 style="font-size:70px; color:{color}; margin:0;">{score}</h1><p>综合健康评分</p></div>''', unsafe_allow_html=True)
        with col_text:
            st.subheader("📝 核心诊断总结")
            st.write(f"**模式**：当前展示历年 **{q_target if q_month else '连续'}** 趋势（共 {len(labels)} 个周期）。")
            st.write(f"**诊断**：最新 ROE 为 {roe.iloc[-1]:.2f}%，资产负债率 {debt_ratio.iloc[-1]:.1f}%。")
        st.divider()

        # --- 6 大板块 ---
        # 1. 营收趋势
        st.header("1️⃣ 历年同期营收与增速对比")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=labels, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=labels, y=growth, name="同比增速%", line=dict(color='red', width=3)), secondary_y=True)
        f1.update_xaxes(type='category'); st.plotly_chart(f1, use_container_width=True)

        # 2. 杜邦分析
        st.header("2️⃣ 盈利驱动 (ROE 杜邦分析)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=labels, y=rev/assets*10, name="资产周转x10"))
        f2.update_xaxes(type='category'); st.plotly_chart(f2, use_container_width=True)

        # 3. 经营细节
        st.header("3️⃣ 经营效率 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("ROIC %"); st.line_chart(pd.Series(roic.values, index=labels))
        with c32: st.write("C2C 周期 (天)"); st.bar_chart(pd.Series(c2c.values, index=labels))

        # 4. OWC
        st.header("4️⃣ 营运资产管理 (OWC)")
        st.bar_chart(pd.Series((ca - cl).values, index=labels))

        # 5. 现金流
        st.header("5️⃣ 现金流质量与分红回报")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=labels, y=ni, name="净利润"))
        f5.add_trace(go.Scatter(x=labels, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=labels, y=div, name="分红", opacity=0.3))
        f5.update_xaxes(type='category'); st.plotly_chart(f5, use_container_width=True)

        # 6. 安全性 (🔥 重点修复区)
        st.header("6️⃣ 财务安全性深度评估")
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
        st.error(f"引擎发生逻辑错误: {e}")

if st.sidebar.button("🚀 启动旗舰版深度诊断"):
    run_v48_engine(symbol, "年度" in mode, q_pivot_month)
