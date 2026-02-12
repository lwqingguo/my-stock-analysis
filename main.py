import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V49", layout="wide")

# 2. 侧边栏精进优化
st.sidebar.header("📊 诊断模式配置")
mode = st.sidebar.selectbox("1. 报表频率", ["年度 (Annual)", "季度 (Quarterly)"], index=1)

q_pivot_month = None
if "季度" in mode:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 By Q 趋势透视")
    q_target = st.sidebar.radio("选择要回溯的特定季度：", ["Q1 (3月)", "Q2 (6月)", "Q3 (9月)", "Q4 (12月)"], index=0)
    q_map = {"Q1 (3月)": "-03", "Q2 (6月)": "-06", "Q3 (9月)": "-09", "Q4 (12月)": "-12"}
    q_pivot_month = q_map[q_target]
    st.sidebar.caption(f"系统将为您展示历年所有 {q_target} 的成长趋势（5-10年）。")

st.sidebar.markdown("---")
stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA"}
selected_stock = st.sidebar.selectbox("2. 快捷选择公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("3. 股票代码", stock_list[selected_stock]).upper()

# --- 核心辅助：多层标签备选机制 ---
def get_advanced_metric(df, tag_list):
    if df is None or df.empty: return pd.Series(dtype=float)
    # 转换为小写并去空格进行模糊匹配
    df.index = df.index.str.strip()
    for tag in tag_list:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty: return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v49_engine(ticker, is_annual, q_month):
    try:
        stock = yf.Ticker(ticker)
        
        # 核心修复：强制获取所有历史数据 (不限 4 期)
        is_df = stock.get_income_stmt(freq='annual' if is_annual else 'quarterly').sort_index(axis=1, ascending=True)
        bs_df = stock.get_balance_sheet(freq='annual' if is_annual else 'quarterly').sort_index(axis=1, ascending=True)
        cf_df = stock.get_cashflow(freq='annual' if is_annual else 'quarterly').sort_index(axis=1, ascending=True)

        if is_df.empty:
            st.warning("数据获取延迟，请重新点击按钮或检查网络。")
            return

        # 🔥 By Q 趋势切片逻辑
        if not is_annual and q_month:
            # 扫描所有历史年份，只要月份匹配就抽出来
            mask = is_df.columns.map(lambda x: q_month in x.strftime('%Y-%m'))
            is_df, bs_df, cf_df = is_df.loc[:, mask], bs_df.loc[:, mask], cf_df.loc[:, mask]
        
        labels = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = labels

        # --- 指标抓取 (全量字典) ---
        rev = get_advanced_metric(is_df, ['Total Revenue', 'Revenue', 'Operating Revenue', 'TotalRevenue'])
        ni = get_advanced_metric(is_df, ['Net Income', 'NetIncome', 'Net Income Common Stockholders'])
        ebit = get_advanced_metric(is_df, ['EBIT', 'Operating Income', 'OperatingIncome'])
        
        assets = get_advanced_metric(bs_df, ['Total Assets', 'TotalAssets'])
        equity = get_advanced_metric(bs_df, ['Stockholders Equity', 'Total Equity', 'Common Stock Equity'])
        # 负债修复：三重保障
        liab = get_advanced_metric(bs_df, ['Total Liabilities', 'TotalLiabilities'])
        if liab.sum() == 0: liab = (assets - equity).clip(lower=0)
        
        ca = get_advanced_metric(bs_df, ['Total Current Assets', 'Current Assets', 'CurrentAssets'])
        cl = get_advanced_metric(bs_df, ['Total Current Liabilities', 'Current Liabilities', 'CurrentLiabilities'])
        ar = get_advanced_metric(bs_df, ['Net Receivables', 'Receivables'])
        inv = get_advanced_metric(bs_df, ['Inventory', 'Inventories'])
        ap = get_advanced_metric(bs_df, ['Accounts Payable', 'AccountsPayable'])
        
        ocf = get_advanced_metric(cf_df, ['Operating Cash Flow', 'Cash Flow From Operating Activities'])
        div = get_advanced_metric(cf_df, ['Cash Dividends Paid', 'Dividends Paid']).abs()
        interest = get_advanced_metric(is_df, ['Interest Expense', 'Financial Expense', 'InterestExpense']).abs()

        # --- 比率计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        curr_ratio = (ca / cl.replace(0, 1.0)).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        owc = (ca - cl)

        # --- 打分与展示 ---
        st.title(f"🏛️ 财务 By Q 深度透视 V49：{ticker}")
        
        score = 0
        if not roe.empty:
            if roe.iloc[-1] > 15: score += 2
            if (ocf.iloc[-1]/ni.iloc[-1] if ni.iloc[-1]!=0 else 0) > 1: score += 2
            if debt_ratio.iloc[-1] < 50: score += 2
            if growth.iloc[-1] > 10: score += 2
            if c2c.iloc[-1] < 60: score += 2

        c1, c2 = st.columns([1, 2])
        with c1:
            color = "#2E7D32" if score >= 8 else "#FFA000"
            st.markdown(f'<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;"><h1 style="font-size:70px; color:{color};">{score}</h1><p>综合健康分</p></div>', unsafe_allow_html=True)
        with c2:
            st.subheader("📝 深度诊断总结")
            st.write(f"**趋势分析**：基于历年 {q_target if q_month else '连续'} 周期，共提取 {len(labels)} 期数据。")
            st.write(f"**核心点**：最新 ROE {roe.iloc[-1]:.2f}%，资产负债率 {debt_ratio.iloc[-1]:.1f}%。")
        st.divider()

        # --- 6 大板块 ---
        st.header("1️⃣ 历年同期营收与增速对比 (趋势分析)")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=labels, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=labels, y=growth, name="同比增速%", line=dict(color='red', width=3)), secondary_y=True)
        f1.update_xaxes(type='category'); st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 盈利效率 (ROE 杜邦分析)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=labels, y=rev/assets*10, name="周转率x10"))
        f2.update_xaxes(type='category'); st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 经营细节 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("ROIC %"); st.line_chart(pd.Series((ebit*0.75)/(equity+1).values, index=labels))
        with c32: st.write("C2C 周期 (天)"); st.bar_chart(pd.Series(c2c.values, index=labels))

        st.header("4️⃣ 营运资产管理 (OWC)")
        st.bar_chart(pd.Series(owc.values, index=labels))

        st.header("5️⃣ 现金流质量与分红")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=labels, y=ni, name="净利润"))
        f5.add_trace(go.Scatter(x=labels, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=labels, y=div, name="分红", opacity=0.3))
        f5.update_xaxes(type='category'); st.plotly_chart(f5, use_container_width=True)

        st.header("6️⃣ 财务安全性评估 (深度回溯)")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("**资产负债率 %**")
            f61 = go.Figure(go.Scatter(x=labels, y=debt_ratio, mode='lines+markers+text', text=[f"{x:.1f}" for x in debt_ratio]))
            f61.update_layout(xaxis_type='category', height=300); st.plotly_chart(f61, use_container_width=True)
        with c62:
            st.write("**流动比率**")
            st.line_chart(pd.Series(curr_ratio.values, index=labels))
        with c63:
            st.write("**利息保障倍数**")
            st.line_chart(pd.Series(int_cover.values, index=labels))

    except Exception as e:
        st.error(f"引擎运行失败: {e}")

if st.sidebar.button("🚀 启动旗舰版深度诊断"):
    run_v49_engine(symbol, "年度" in mode, q_pivot_month)
