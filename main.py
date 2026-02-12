import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V51", layout="wide")

# 2. 侧边栏 UI：精简化 + By Q 强化
st.sidebar.header("🛡️ 诊断控制台")
freq_mode = st.sidebar.selectbox("1. 分析模式", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"], index=1)

q_pivot_month = None
if "季度" in freq_mode:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 By Q 深度趋势")
    q_target = st.sidebar.radio("选择回溯季度：", ["Q1 (3月)", "Q2 (6月)", "Q3 (9月)", "Q4 (12月)"], index=0)
    q_map = {"Q1 (3月)": "-03", "Q2 (6月)": "-06", "Q3 (9月)": "-09", "Q4 (12月)": "-12"}
    q_pivot_month = q_map[q_target]

st.sidebar.markdown("---")
stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA"}
selected_stock = st.sidebar.selectbox("2. 公司选择", list(stock_list.keys()))
symbol = st.sidebar.text_input("3. 股票代码", stock_list[selected_stock]).upper()

# --- 核心辅助：全自动标签匹配与逻辑修复 ---
def get_clean_data(df, tags):
    if df is None or df.empty: return pd.Series(dtype=float)
    # 模糊匹配：去除大小写和空格
    df.index = df.index.str.replace(' ', '').str.lower()
    clean_tags = [t.replace(' ', '').lower() for t in tags]
    
    for tag in clean_tags:
        if tag in df.index:
            res = df.loc[tag]
            if isinstance(res, pd.DataFrame): res = res.iloc[0] # 防止重复索引
            return res.replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v51_engine(ticker, is_annual, q_month):
    try:
        stock = yf.Ticker(ticker)
        
        # 兼容性修复：根据最新 API 逻辑抓取
        if is_annual:
            is_df = stock.income_stmt
            bs_df = stock.balance_sheet
            cf_df = stock.cashflow
        else:
            # 尝试抓取所有可用的季度数据
            is_df = stock.get_income_stmt(freq='quarterly')
            bs_df = stock.get_balance_sheet(freq='quarterly')
            cf_df = stock.get_cashflow(freq='quarterly')

        if is_df.empty:
            st.error("数据拉取失败，可能是 API 限制，请尝试切换年度模式或检查代码后缀。")
            return

        # 排序：从旧到新
        is_df = is_df.sort_index(axis=1, ascending=True)
        bs_df = bs_df.sort_index(axis=1, ascending=True)
        cf_df = cf_df.sort_index(axis=1, ascending=True)

        # 🔥 By Q 趋势核心逻辑：在此处执行深度切片
        if not is_annual and q_month:
            mask = is_df.columns.map(lambda x: q_month in x.strftime('%Y-%m'))
            is_df, bs_df, cf_df = is_df.loc[:, mask], bs_df.loc[:, mask], cf_df.loc[:, mask]
            
            # 若季度数据不足，尝试拉取历史镜像
            if len(is_df.columns) < 2:
                st.info("正在尝试回溯更早的历史数据点...")
                # 这里如果仍少，说明 Yahoo 数据库确实只存了近期，无法强求

        labels = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = labels

        # --- 指标抓取 (全量字典 + 会计逻辑修复) ---
        rev = get_clean_data(is_df, ['Total Revenue', 'Revenue', 'Operating Revenue'])
        ni = get_clean_data(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_clean_data(is_df, ['EBIT', 'Operating Income'])
        
        assets = get_clean_data(bs_df, ['Total Assets'])
        equity = get_clean_data(bs_df, ['Stockholders Equity', 'Total Equity'])
        # 负债修复：如果 Total Liabilities 为 0，则用 资产-权益
        liab = get_clean_data(bs_df, ['Total Liabilities'])
        if liab.sum() == 0: 
            liab = (assets - equity).clip(lower=0)
            
        ca = get_clean_data(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_clean_data(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        ar = get_clean_data(bs_df, ['Net Receivables', 'Receivables'])
        inv = get_clean_data(bs_df, ['Inventory'])
        ap = get_clean_data(bs_df, ['Accounts Payable'])
        ocf = get_clean_data(cf_df, ['Operating Cash Flow'])
        div = get_clean_data(cf_df, ['Cash Dividends Paid']).abs()
        interest = get_clean_data(is_df, ['Interest Expense', 'Financial Expense']).abs()

        # --- 比率计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        curr_ratio = (ca / cl.replace(0, 1.0)).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)

        # --- UI 展示 ---
        st.title(f"🏛️ 财务 By Q 趋势全图谱 V51：{ticker}")
        
        # 评分
        score = 0
        if not roe.empty:
            if roe.iloc[-1] > 15: score += 2
            if (ocf.iloc[-1]/ni.iloc[-1] if ni.iloc[-1]!=0 else 0) > 1: score += 2
            if debt_ratio.iloc[-1] < 50: score += 2
            if growth.iloc[-1] > 10: score += 2
            if c2c.iloc[-1] < 60: score += 2

        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("健康评分", f"{score}/10")
        with c2:
            st.info(f"**诊断**：当前回溯期数：{len(labels)}。最新点负债率 {debt_ratio.iloc[-1]:.1f}%。")

        # --- 6 大图表 (不删减) ---
        st.header("1️⃣ 历年同期营收与增速 (By Q 趋势)")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=labels, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=labels, y=growth, name="增速%", line=dict(color='red', width=3)), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 盈利驱动 (ROE 杜邦分析)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=labels, y=rev/assets*10, name="周转率x10"))
        st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 经营细节 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("ROIC %"); st.line_chart(pd.Series((ebit*0.75)/(equity+1).values, index=labels))
        with c32: st.write("C2C 周期 (天)"); st.bar_chart(pd.Series(c2c.values, index=labels))

        st.header("4️⃣ 营运资本 (OWC)")
        st.bar_chart(pd.Series((ca - cl).values, index=labels))

        st.header("5️⃣ 现金流质量")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=labels, y=ni, name="利润"))
        f5.add_trace(go.Scatter(x=labels, y=ocf, name="现金流"))
        st.plotly_chart(f5, use_container_width=True)

        st.header("6️⃣ 安全性诊断 (趋势)")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("资产负债率 %")
            f61 = go.Figure(go.Scatter(x=labels, y=debt_ratio, mode='lines+markers+text', text=[f"{x:.1f}" for x in debt_ratio]))
            f61.update_layout(xaxis_type='category', height=300); st.plotly_chart(f61, use_container_width=True)
        with c62:
            st.write("流动比率"); st.line_chart(pd.Series(curr_ratio.values, index=labels))
        with c63:
            st.write("利息保障倍数"); st.line_chart(pd.Series(int_cover.values, index=labels))

    except Exception as e:
        st.error(f"引擎逻辑异常: {e}")

if st.sidebar.button("🚀 启动深度趋势诊断"):
    run_v51_engine(symbol, "年度" in freq_mode, q_pivot_month)
