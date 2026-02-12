import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# 1. 基础配置
st.set_page_config(page_title="财务全图谱-V54-旗舰版", layout="wide")

# 2. 侧边栏交互
st.sidebar.header("🛡️ 深度诊断 (AkShare 驱动)")
stock_input = st.sidebar.text_input("1. 股票代码或名称", "东鹏饮料")
q_target = st.sidebar.radio("2. 选择对比季度：", ["Q1 (3月)", "Q2 (6月)", "Q3 (9月)", "Q4 (12月)"], index=0)

q_map = {"Q1 (3月)": "03-31", "Q2 (6月)": "06-30", "Q3 (9月)": "09-30", "Q4 (12月)": "12-31"}
target_date = q_map[q_target]

# --- 核心函数：带重试机制的数据抓取 ---
@st.cache_data(ttl=3600)
def fetch_data_with_retry(name_or_code, retries=3):
    for i in range(retries):
        try:
            # 获取代码映射
            stock_info = ak.stock_info_a_code_name()
            if name_or_code.isdigit():
                code = name_or_code
                name = stock_info[stock_info['code'] == code]['name'].values[0]
            else:
                name = name_or_code
                code = stock_info[stock_info['name'] == name]['code'].values[0]

            # 获取报表 (使用新浪接口，历史深度更广)
            is_df = ak.stock_financial_report_sina(stock=code, symbol="利润表")
            bs_df = ak.stock_financial_report_sina(stock=code, symbol="资产负债表")
            cf_df = ak.stock_financial_report_sina(stock=code, symbol="现金流量表")
            return is_df, bs_df, cf_df, code, name
        except Exception as e:
            if i < retries - 1:
                time.sleep(2) # 等待后重试
                continue
            return None, None, None, str(e), ""

def run_v54():
    is_raw, bs_raw, cf_raw, code_res, name = fetch_data_with_retry(stock_input)
    
    if is_raw is None:
        st.error(f"❌ 数据获取失败。可能原因：1.海外服务器连接受阻；2.代码输入错误。报错：{code_res}")
        st.info("💡 建议：在本地环境运行此代码，连接会更稳定。")
        return

    # 数据预处理
    for df in [is_raw, bs_raw, cf_raw]:
        df['报告日期'] = pd.to_datetime(df['报告日期'])
        df.set_index('报告日期', inplace=True)
        df.sort_index(ascending=True, inplace=True)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 🔥 By Q 趋势切片 (确保 5-10 年趋势)
    mask = is_raw.index.strftime('%m-%d') == target_date
    is_q, bs_q, cf_q = is_raw[mask], bs_raw[mask], cf_raw[mask]
    
    if len(is_q) < 2:
        st.warning(f"⚠️ 历史 {q_target} 数据点不足。请尝试其他季度或切换至成熟上市公司。")
        return

    labels = is_q.index.strftime('%Y-%m').tolist()

    # --- 指标提取 (严禁删减) ---
    rev = is_q['营业收入']
    ni = is_q['净利润']
    growth = rev.pct_change().fillna(0) * 100
    
    # 安全性 (修复负债率 0 问题)
    assets = bs_q['资产总计']
    liab = bs_q['负债合计']
    equity = bs_q['所有者权益(或股东权益)合计']
    debt_ratio = (liab / assets * 100).fillna(0)
    
    # 营运效率 (C2C)
    ar = bs_q.get('应收账款净额', bs_q.get('应收账款', pd.Series(0, index=labels)))
    inv = bs_q.get('存货净额', bs_q.get('存货', pd.Series(0, index=labels)))
    ap = bs_q.get('应付账款', pd.Series(0, index=labels))
    c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
    
    # 杜邦与现金流
    roe = (ni / equity * 100).fillna(0)
    ocf = cf_q['经营活动产生的现金流量净额']
    owc = bs_q['流动资产合计'] - bs_q['流动负债合计']

    # --- UI 渲染 ---
    st.title(f"🏛️ {name} ({code_res}) - {q_target} 同期趋势图谱")
    st.success(f"成功回溯 {len(labels)} 年历史同期数据。")

    # 板块展示
    st.header("1️⃣ 营收规模与同比增速趋势")
    f1 = make_subplots(specs=[[{"secondary_y": True}]])
    f1.add_trace(go.Bar(x=labels, y=rev, name="营业收入"), secondary_y=False)
    f1.add_trace(go.Scatter(x=labels, y=growth, name="增速%", line=dict(color='red', width=3)), secondary_y=True)
    st.plotly_chart(f1, use_container_width=True)

    st.header("2️⃣ 盈利驱动 (ROE 杜邦分析)")
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=labels, y=roe, name="ROE %", line=dict(width=4, color='green')))
    f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率 %"))
    f2.update_layout(xaxis_type='category')
    st.plotly_chart(f2, use_container_width=True)

    st.header("3️⃣ 经营细节 (C2C 周期 & OWC)")
    c31, c32 = st.columns(2)
    with c31: 
        st.write("C2C 周期 (天)")
        st.bar_chart(pd.Series(c2c.values, index=labels))
    with c32: 
        st.write("营运资本 (OWC)")
        st.line_chart(pd.Series(owc.values, index=labels))

    st.header("4️⃣ 安全性与现金流质量")
    c41, c42 = st.columns(2)
    with c41:
        st.write("资产负债率趋势 %")
        f41 = go.Figure(go.Scatter(x=labels, y=debt_ratio, mode='lines+markers+text', 
                                   text=[f"{x:.1f}" for x in debt_ratio], textposition="top center"))
        st.plotly_chart(f41, use_container_width=True)
    with c42:
        st.write("净利润 vs 经营现金流")
        f42 = go.Figure()
        f42.add_trace(go.Scatter(x=labels, y=ni, name="利润"))
        f42.add_trace(go.Scatter(x=labels, y=ocf, name="现金流"))
        st.plotly_chart(f42, use_container_width=True)

run_v54()
