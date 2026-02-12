import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V58-全指标旗舰版", layout="wide")

# 2. 侧边栏：完整快捷选项
st.sidebar.header("🛡️ 深度财务诊断 (V58)")
stock_list = {
    "东鹏饮料": "605499.SS", 
    "贵州茅台": "600519.SS", 
    "英伟达": "NVDA", 
    "腾讯控股": "0700.HK",
    "苹果": "AAPL",
    "特斯拉": "TSLA"
}
selected_stock = st.sidebar.selectbox("1. 快捷选择公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("2. 手动输入代码", stock_list[selected_stock]).upper()

# --- 核心辅助：全量指标提取函数 (严禁删减) ---
def get_full_metric(df, tags):
    if df is None or df.empty: return pd.Series(0.0, index=[0])
    df.index = df.index.map(str).str.strip()
    for tag in tags:
        if tag in df.index:
            data = df.loc[tag]
            if isinstance(data, pd.DataFrame): data = data.iloc[0]
            return data.replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series(0.0, index=df.columns)

# --- 主引擎 ---
def run_v58():
    try:
        ticker = yf.Ticker(symbol)
        
        # 🔥 彻底修复报错：直接访问属性，绝不使用 timescale 参数
        is_df = ticker.income_stmt.sort_index(axis=1)
        bs_df = ticker.balance_sheet.sort_index(axis=1)
        cf_df = ticker.cashflow.sort_index(axis=1)

        if is_df.empty:
            st.error("数据拉取失败。请确认代码正确（如 A股加 .SS, 港股加 .HK）。")
            return

        years = [d.strftime('%Y') for d in is_df.columns]
        
        # --- [指标 1: 营收与利润] ---
        rev = get_full_metric(is_df, ['Total Revenue', 'Revenue'])
        ni = get_full_metric(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_full_metric(is_df, ['EBIT', 'Operating Income'])
        
        # --- [指标 2: 资产负债与安全性] ---
        assets = get_full_metric(bs_df, ['Total Assets'])
        equity = get_full_metric(bs_df, ['Stockholders Equity', 'Total Equity'])
        liab = get_full_metric(bs_df, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        if liab.sum() == 0: liab = (assets - equity).clip(lower=0) # 负债率修复逻辑
        
        ca = get_full_metric(bs_df, ['Total Current Assets'])
        cl = get_full_metric(bs_df, ['Total Current Liabilities'])
        ar = get_full_metric(bs_df, ['Net Receivables', 'Accounts Receivable'])
        inv = get_full_metric(bs_df, ['Inventory'])
        ap = get_full_metric(bs_df, ['Accounts Payable'])
        
        # --- [指标 3: 现金流] ---
        ocf = get_full_metric(cf_df, ['Operating Cash Flow'])

        # --- [核心比率计算 (找回所有丢失指标)] ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        net_margin = (ni / rev.replace(0, 1.0) * 100).fillna(0)
        asset_turnover = (rev / assets.replace(0, 1.0)).fillna(0)
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        owc = ca - cl
        # C2C 周期计算
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)

        # --- [评分系统] ---
        score = 0
        notes = []
        if roe.iloc[-1] > 15: score += 2; notes.append("✅ 盈利卓越：最新ROE超过15%")
        if ocf.iloc[-1] > ni.iloc[-1]: score += 2; notes.append("✅ 利润真实：经营现金流大于净利润")
        if debt_ratio.iloc[-1] < 50: score += 2; notes.append("✅ 财务安全：资产负债率处于健康区间")
        if growth.iloc[-1] > 10: score += 2; notes.append("✅ 持续成长：年度营收增速超10%")
        if c2c.iloc[-1] < 90: score += 2; notes.append("✅ 运营高效：上下游资金占用能力强")

        # --- UI 渲染 ---
        st.title(f"🏛️ {symbol} 年度财务全谱分析 (V58 旗舰版)")
        
        col_s, col_t = st.columns([1, 2])
        with col_s:
            st.markdown(f"""<div style="text-align:center; border:5px solid #1E88E5; border-radius:15px; padding:20px;">
                <h1 style="color:#1E88E5; font-size:60px;">{score}</h1><p>财务综合评分</p></div>""", unsafe_allow_html=True)
        with col_t:
            st.subheader("📝 核心诊断总结")
            for n in notes: st.write(n)
        
        st.divider()

        # --- [图表区: 严禁删减] ---
        
        # 1. 营收与增速
        st.header("1️⃣ 营收规模与年度增长趋势")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营业收入"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="同比增速%", line=dict(color='red', width=3)), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        # 2. 杜邦分析 (找回了周转率和净利率)
        st.header("2️⃣ 盈利效率 (ROE 杜邦拆解)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=years, y=roe, name="ROE %", line=dict(width=4, color='green')))
        f2.add_trace(go.Scatter(x=years, y=net_margin, name="净利率 %", line=dict(dash='dot')))
        f2.add_trace(go.Scatter(x=years, y=asset_turnover*10, name="总资产周转率 x10"))
        st.plotly_chart(f2, use_container_width=True)

        # 3. 经营效率细节
        st.header("3️⃣ 运营细节 (C2C 周期 & OWC)")
        c31, c32 = st.columns(2)
        with c31:
            st.write("**C2C 现金循环周期 (天)**")
            st.bar_chart(pd.Series(c2c.values, index=years))
        with c32:
            st.write("**营运资本 (OWC) 趋势**")
            st.line_chart(pd.Series(owc.values, index=years))

        # 4. 安全性与利润含金量
        st.header("4️⃣ 安全性与含金量监测")
        c41, c42 = st.columns(2)
        with c41:
            st.write("**资产负债率趋势 %**")
            f41 = go.Figure(go.Scatter(x=years, y=debt_ratio, mode='lines+markers+text', text=[f"{x:.1f}" for x in debt_ratio]))
            f41.update_layout(yaxis=dict(range=[0, 100]))
            st.plotly_chart(f41, use_container_width=True)
        with c42:
            st.write("**净利润 vs 经营现金流**")
            f42 = go.Figure()
            f42.add_trace(go.Scatter(x=years, y=ni, name="归母净利润"))
            f42.add_trace(go.Scatter(x=years, y=ocf, name="经营现金流"))
            st.plotly_chart(f42, use_container_width=True)

    except Exception as e:
        st.error(f"引擎逻辑异常: {str(e)}")

if st.sidebar.button("🚀 启动深度扫描"):
    run_v58()
