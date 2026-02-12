import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V56-年度版", layout="wide")

# 2. 侧边栏：公司快捷选择与代码输入
st.sidebar.header("🛡️ 财务诊断中心 (年度版)")
stock_list = {
    "东鹏饮料": "605499.SS", 
    "贵州茅台": "600519.SS", 
    "英伟达": "NVDA", 
    "腾讯控股": "0700.HK",
    "苹果": "AAPL",
    "特斯拉": "TSLA"
}
selected_stock = st.sidebar.selectbox("1. 快捷选择公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("2. 或手动输入代码", stock_list[selected_stock]).upper()

# --- 核心辅助：稳健取数函数 ---
def get_data(df, tags):
    if df is None or df.empty: return pd.Series(dtype=float)
    df.index = df.index.str.strip()
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag]
            if isinstance(res, pd.DataFrame): res = res.iloc[0] # 防止重复索引
            return res.replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v56_annual():
    try:
        stock = yf.Ticker(symbol)
        # 强制抓取年度报表 (Annual)
        is_df = stock.get_income_stmt(freq='annual').sort_index(axis=1)
        bs_df = stock.get_balance_sheet(freq='annual').sort_index(axis=1)
        cf_df = stock.get_cashflow(freq='annual').sort_index(axis=1)

        if is_df.empty:
            st.error("数据拉取失败，请检查代码后缀（A股需加 .SS 或 .SZ）。")
            return

        labels = [d.strftime('%Y') for d in is_df.columns]
        
        # --- 全量核心指标提取 ---
        rev = get_data(is_df, ['Total Revenue', 'Revenue'])
        ni = get_data(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_data(is_df, ['EBIT', 'Operating Income'])
        
        assets = get_data(bs_df, ['Total Assets'])
        equity = get_data(bs_df, ['Stockholders Equity', 'Total Equity'])
        liab = get_data(bs_df, ['Total Liabilities'])
        # 负债率兜底修复逻辑
        if liab.sum() == 0: liab = (assets - equity).clip(lower=0)
        
        ca = get_data(bs_df, ['Total Current Assets'])
        cl = get_data(bs_df, ['Total Current Liabilities'])
        ar = get_data(bs_df, ['Net Receivables', 'Accounts Receivable'])
        inv = get_data(bs_df, ['Inventory'])
        ap = get_data(bs_df, ['Accounts Payable'])
        
        ocf = get_data(cf_df, ['Operating Cash Flow'])
        
        # --- 核心比率计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        owc = ca - cl

        # --- 评分与总结逻辑 ---
        score = 0
        diagnostics = []
        if roe.iloc[-1] > 15: 
            score += 2
            diagnostics.append("✅ 盈利能力强劲：最新ROE超过15%。")
        if ocf.iloc[-1] > ni.iloc[-1]: 
            score += 2
            diagnostics.append("✅ 利润含金量高：经营现金流大于净利润。")
        if debt_ratio.iloc[-1] < 50: 
            score += 2
            diagnostics.append("✅ 财务稳健：资产负债率处于50%安全线以下。")
        if growth.iloc[-1] > 10: 
            score += 2
            diagnostics.append("✅ 成长性好：年度营收增长率超过10%。")
        if c2c.iloc[-1] < 60: 
            score += 2
            diagnostics.append("✅ 运营效率高：现金循环周期表现优秀。")

        # --- UI 展示：评分与总结 ---
        st.title(f"🏛️ {symbol} 年度财务全谱分析")
        
        c1, c2 = st.columns([1, 2])
        with c1:
            color = "#2E7D32" if score >= 8 else "#FFA000" if score >= 6 else "#D32F2F"
            st.markdown(f'''
                <div style="text-align:center; border:5px solid {color}; border-radius:20px; padding:30px;">
                    <h1 style="font-size:80px; color:{color}; margin:0;">{score}</h1>
                    <p style="font-size:20px;">综合健康评分</p>
                </div>
            ''', unsafe_allow_html=True)
        with c2:
            st.subheader("📝 核心财务总结")
            for d in diagnostics:
                st.write(d)
            if not diagnostics: st.write("⚠️ 多项财务指标异常，建议审慎评估其偿债及盈利持续性。")

        st.divider()

        # --- 六大核心图表 (零删减) ---
        st.header("1️⃣ 营收规模与年度同比增速趋势")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=labels, y=rev, name="营业收入"), secondary_y=False)
        f1.add_trace(go.Scatter(x=labels, y=growth, name="同比增速%", line=dict(color='red', width=3)), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 盈利驱动分析 (ROE 杜邦拆解)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=labels, y=roe, name="ROE % (股东回报率)", line=dict(width=4, color='green')))
        f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率 %", line=dict(dash='dash')))
        f2.add_trace(go.Scatter(x=labels, y=rev/assets*10, name="总资产周转率 x10"))
        st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 经营效率与营运资本 (OWC & C2C)")
        c31, c32 = st.columns(2)
        with c31:
            st.write("**C2C 现金循环周期 (天)**")
            st.bar_chart(pd.Series(c2c.values, index=labels))
        with c32:
            st.write("**营运资本变动 (OWC)**")
            st.line_chart(pd.Series(owc.values, index=labels))

        st.header("4️⃣ 财务安全评估 (资产负债率趋势)")
        f4 = go.Figure(go.Scatter(x=labels, y=debt_ratio, mode='lines+markers+text', 
                                   text=[f"{x:.1f}%" for x in debt_ratio], textposition="top center",
                                   line=dict(color='orange', width=3)))
        f4.update_layout(yaxis=dict(range=[0, 100], title="负债率 %"))
        st.plotly_chart(f4, use_container_width=True)

        st.header("5️⃣ 利润质量监测 (净利润 vs 经营现金流)")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=labels, y=ni, name="归母净利润"))
        f5.add_trace(go.Scatter(x=labels, y=ocf, name="经营现金流净额"))
        st.plotly_chart(f5, use_container_width=True)

    except Exception as e:
        st.error(f"分析引擎故障: {e}")

if st.sidebar.button("🚀 启动年度深度诊断"):
    run_v56_annual()
