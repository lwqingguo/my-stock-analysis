import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V52", layout="wide")

# 2. 侧边栏：优化 UI 与 By Q 维度筛选
st.sidebar.header("🔍 深度财务诊断 (AkShare)")
stock_input = st.sidebar.text_input("1. 股票名称或代码", "东鹏饮料")
q_target = st.sidebar.radio("2. 选择 By Q 趋势维度：", ["Q1 (3月)", "Q2 (6月)", "Q3 (9月)", "Q4 (12月)"], index=0)

q_map = {"Q1 (3月)": "03-31", "Q2 (6月)": "06-30", "Q3 (9月)": "09-30", "Q4 (12月)": "12-31"}
target_date = q_map[q_target]

# --- 核心辅助：数据抓取 ---
@st.cache_data(ttl=3600)
def fetch_full_data_ak(name_or_code):
    try:
        # 自动转换名称为代码
        if not name_or_code.isdigit():
            search_df = ak.stock_info_a_code_name()
            code = search_df[search_df['name'] == name_or_code]['code'].values[0]
        else:
            code = name_or_code

        # 获取三大报表 (由于是深度分析，我们抓取新浪/东财的长周期接口)
        is_df = ak.stock_financial_report_sina(stock=code, symbol="利润表")
        bs_df = ak.stock_financial_report_sina(stock=code, symbol="资产负债表")
        cf_df = ak.stock_financial_report_sina(stock=code, symbol="现金流量表")
        
        return is_df, bs_df, cf_df, code
    except Exception as e:
        return None, None, None, str(e)

# --- 主引擎运行 ---
def run_v52():
    is_raw, bs_raw, cf_raw, info = fetch_full_data_ak(stock_input)
    
    if is_raw is None:
        st.error(f"数据抓取失败: {info}")
        return

    # 数据预处理：统一日期索引
    for df in [is_raw, bs_raw, cf_raw]:
        df['报告日期'] = pd.to_datetime(df['报告日期'])
        df.set_index('报告日期', inplace=True)
        df.sort_index(ascending=True, inplace=True)
        # 强制转换为数值
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 🔥 By Q 核心切片：保留所有历史年份的对应季度
    mask = is_raw.index.strftime('%m-%d') == target_date
    is_q, bs_q, cf_q = is_raw[mask], bs_raw[mask], cf_raw[mask]
    
    if is_q.empty:
        st.warning("所选季度数据点不足，请尝试其他季度。")
        return

    labels = is_q.index.strftime('%Y-%m').tolist()

    # --- 核心指标全量提取 (零删减) ---
    # 1. 营收与增长
    rev = is_q['营业收入']
    ni = is_q['净利润']
    growth = rev.pct_change().fillna(0) * 100
    
    # 2. 安全性指标 (不再为0)
    assets = bs_q['资产总计']
    liab = bs_q['负债合计']
    equity = bs_q['所有者权益(或股东权益)合计']
    debt_ratio = (liab / assets * 100).fillna(0)
    ca = bs_q['流动资产合计']
    cl = bs_q['流动负债合计']
    curr_ratio = (ca / cl).fillna(0)
    
    # 3. 经营效率 (C2C 相关)
    ar = bs_q['应收账款净额'] if '应收账款净额' in bs_q.columns else bs_q['应收账款']
    inv = bs_q['存货净额'] if '存货净额' in bs_q.columns else bs_q['存货']
    ap = bs_q['应付账款']
    c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
    
    # 4. 盈利与分红
    roe = (ni / equity * 100).fillna(0)
    ocf = cf_q['经营活动产生的现金流量净额']
    owc = ca - cl

    # --- 总结与打分 ---
    score = 0
    if roe.iloc[-1] > 15: score += 2
    if ocf.iloc[-1] > ni.iloc[-1]: score += 2
    if debt_ratio.iloc[-1] < 50: score += 2
    if growth.iloc[-1] > 10: score += 2
    if c2c.iloc[-1] < 60: score += 2

    st.title(f"🏛️ {stock_input} - {q_target} 深度财务透视 (V52)")
    
    col_score, col_diag = st.columns([1, 2])
    with col_score:
        color = "#2E7D32" if score >= 8 else "#FFA000"
        st.markdown(f'<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;"><h1 style="color:{color}; margin:0;">{score}</h1><p>全量指标综合分</p></div>', unsafe_allow_html=True)
    with col_diag:
        st.subheader("📋 季度同比趋势诊断")
        st.write(f"**数据深度**：已成功回溯过去 **{len(labels)}** 年的 {q_target} 同期数据。")
        st.write(f"**关键结论**：最新负债率为 {debt_ratio.iloc[-1]:.1f}%，ROE 为 {roe.iloc[-1]:.2f}%。")
    st.divider()

    # --- 六大板块 (全量保留) ---
    # 1. 营收
    st.header("1️⃣ 营收规模与同比增速趋势")
    f1 = make_subplots(specs=[[{"secondary_y": True}]])
    f1.add_trace(go.Bar(x=labels, y=rev, name="营业收入"), secondary_y=False)
    f1.add_trace(go.Scatter(x=labels, y=growth, name="增速%", line=dict(color='red', width=3)), secondary_y=True)
    st.plotly_chart(f1, use_container_width=True)

    # 2. 杜邦分析
    st.header("2️⃣ 历年盈利效率趋势 (ROE 杜邦分析)")
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=labels, y=roe, name="ROE %", line=dict(width=4)))
    f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率 %"))
    f2.add_trace(go.Scatter(x=labels, y=rev/assets*10, name="周转率x10"))
    st.plotly_chart(f2, use_container_width=True)

    # 3. 经营细节
    st.header("3️⃣ 经营细节 (C2C 现金周期)")
    st.bar_chart(pd.Series(c2c.values, index=labels))

    # 4. OWC
    st.header("4️⃣ 营运资本 (OWC) 历年变动")
    st.line_chart(pd.Series(owc.values, index=labels))

    # 5. 现金流
    st.header("5️⃣ 利润含金量对比 (净利润 vs 经营现金流)")
    f5 = go.Figure()
    f5.add_trace(go.Scatter(x=labels, y=ni, name="净利润"))
    f5.add_trace(go.Scatter(x=labels, y=ocf, name="经营现金流"))
    st.plotly_chart(f5, use_container_width=True)

    # 6. 安全性 (修复版)
    st.header("6️⃣ 财务安全性评估 (深度趋势)")
    c61, c62 = st.columns(2)
    with c61:
        st.write("**资产负债率趋势 %**")
        f61 = go.Figure(go.Scatter(x=labels, y=debt_ratio, mode='lines+markers+text', text=[f"{x:.1f}" for x in debt_ratio]))
        st.plotly_chart(f61, use_container_width=True)
    with c62:
        st.write("**流动比率趋势**")
        st.line_chart(pd.Series(curr_ratio.values, index=labels))

run_v52()
