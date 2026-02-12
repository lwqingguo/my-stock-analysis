import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V56-年度版", layout="wide")

# 2. 侧边栏：预设公司与手动输入
st.sidebar.header("🛡️ 财务诊断中心 (年度版)")
stock_list = {
    "东鹏饮料": "605499.SS", 
    "贵州茅台": "600519.SS", 
    "英伟达": "NVDA", 
    "腾讯控股": "0700.HK",
    "特斯拉": "TSLA"
}
selected_stock = st.sidebar.selectbox("1. 快捷选择常用公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("2. 手动输入股票代码", stock_list[selected_stock]).upper()

# --- 核心逻辑：数据提取与错误兜底 ---
def get_safe_data(df, tags):
    if df is None or df.empty: return pd.Series(dtype=float)
    df.index = df.index.str.strip()
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag]
            if isinstance(res, pd.DataFrame): res = res.iloc[0]
            return res.replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v56_engine():
    try:
        stock = yf.Ticker(symbol)
        # 强制拉取年度报表
        is_df = stock.get_income_stmt(freq='annual').sort_index(axis=1)
        bs_df = stock.get_balance_sheet(freq='annual').sort_index(axis=1)
        cf_df = stock.get_cashflow(freq='annual').sort_index(axis=1)

        if is_df.empty:
            st.error("无法获取年度报表。请检查代码后缀（如A股加 .SS, 港股加 .HK）。")
            return

        years = [d.strftime('%Y') for d in is_df.columns]
        
        # --- 全量指标提取 (零删减) ---
        rev = get_safe_data(is_df, ['Total Revenue', 'Revenue'])
        ni = get_safe_data(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_safe_data(is_df, ['EBIT', 'Operating Income'])
        
        assets = get_safe_data(bs_df, ['Total Assets'])
        equity = get_safe_data(bs_df, ['Stockholders Equity', 'Total Equity'])
        liab = get_safe_data(bs_df, ['Total Liabilities'])
        # 负债率兜底：资产 - 权益
        if liab.sum() == 0: liab = (assets - equity).clip(lower=0)
        
        ca = get_safe_data(bs_df, ['Total Current Assets'])
        cl = get_safe_data(bs_df, ['Total Current Liabilities'])
        ar = get_safe_data(bs_df, ['Net Receivables', 'Accounts Receivable'])
        inv = get_safe_data(bs_df, ['Inventory'])
        ap = get_safe_data(bs_df, ['Accounts Payable'])
        ocf = get_safe_data(cf_df, ['Operating Cash Flow'])
        
        # --- 财务比率计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        owc = ca - cl

        # --- 智能评分与文字诊断 ---
        score = 0
        summary = []
        if roe.iloc[-1] > 15: 
            score += 2; summary.append("🟢 **盈利强劲**：最新ROE超过15%，股东回报率极佳。")
        if ocf.iloc[-1] > ni.iloc[-1]: 
            score += 2; summary.append("🟢 **含金量高**：经营现金流覆盖净利润，利润真实性高。")
        if debt_ratio.iloc[-1] < 50: 
            score += 2; summary.append("🟢 **财务稳健**：负债率低于50%，无重大偿债风险。")
        if growth.iloc[-1] > 10: 
            score += 2; summary.append("🟢 **稳步成长**：年营收保持10%以上增长。")
        if c2c.iloc[-1] < 90: 
            score += 2; summary.append("🟢 **运营高效**：现金循环周期较短，上下游话语权强。")

        # --- UI 顶层渲染 ---
        st.title(f"🏛️ {symbol} 年度财务全谱分析")
        col_score, col_text = st.columns([1, 2])
        with col_score:
            st.metric("综合健康评分", f"{score} / 10")
            st.progress(score / 10)
        with col_text:
            st.subheader("📝 财务诊断报告")
            for item in summary: st.write(item)
            if not summary: st.write("🔴 该公司多项核心指标低于行业警戒线。")

        st.divider()

        # --- 六大核心图表 ---
        # 1. 营收趋势
        st.header("1️⃣ 年度营收规模与增长率")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营业收入"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", line=dict(color='red', width=3)), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        # 2. 盈利杜邦分析
        st.header("2️⃣ 盈利效率 (ROE 杜邦拆解)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=years, y=roe, name="ROE %", line=dict(width=4, color='green')))
        f2.add_trace(go.Scatter(x=years, y=ni/rev*100, name="净利率 %", line=dict(dash='dot')))
        f2.add_trace(go.Scatter(x=years, y=rev/assets*10, name="周转率 x10"))
        st.plotly_chart(f2, use_container_width=True)

        # 3. 经营效率与资本 (OWC & C2C)
        st.header("3️⃣ 经营细节 (C2C 周期 & OWC)")
        c31, c32 = st.columns(2)
        with c31:
            st.write("**C2C 现金循环周期 (天)**")
            st.bar_chart(pd.Series(c2c.values, index=years))
        with c32:
            st.write("**营运资本 (OWC) 趋势**")
            st.line_chart(pd.Series(owc.values, index=years))

        # 4. 安全性
        st.header("4️⃣ 财务安全 (资产负债率趋势)")
        f4 = go.Figure(go.Scatter(x=years, y=debt_ratio, mode='lines+markers+text', 
                                   text=[f"{x:.1f}%" for x in debt_ratio], textposition="top center"))
        f4.update_layout(yaxis=dict(range=[0, 100], title="负债率 %"))
        st.plotly_chart(f4, use_container_width=True)

        # 5. 现金流对比
        st.header("5️⃣ 利润含金量 (净利润 vs 经营现金流)")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=years, y=ni, name="归母净利润"))
        f5.add_trace(go.Scatter(x=years, y=ocf, name="经营现金流"))
        st.plotly_chart(f5, use_container_width=True)

    except Exception as e:
        st.error(f"分析引擎故障: {e}")

if st.sidebar.button("🚀 启动年度深度扫描"):
    run_v56_engine()
