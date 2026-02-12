import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V57-旗舰版", layout="wide")

# 2. 侧边栏
st.sidebar.header("🛡️ 财务诊断中心 (V57)")
stock_list = {
    "东鹏饮料": "605499.SS", 
    "贵州茅台": "600519.SS", 
    "英伟达": "NVDA", 
    "腾讯控股": "0700.HK",
    "特斯拉": "TSLA"
}
selected_stock = st.sidebar.selectbox("1. 快捷选择常用公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("2. 手动输入代码", stock_list[selected_stock]).upper()

# --- 核心辅助：稳健取数 (兼容新旧字段) ---
def get_val(df, tags):
    if df is None or df.empty: return pd.Series(0.0, index=[0])
    # 统一转换索引为字符串并去空格
    df.index = df.index.map(str).str.strip()
    for tag in tags:
        if tag in df.index:
            data = df.loc[tag]
            # 如果返回的是 DataFrame (多行同名)，取第一行
            if isinstance(data, pd.DataFrame): data = data.iloc[0]
            return data.replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series(0.0, index=df.columns)

# --- 主引擎 ---
def run_v57():
    try:
        ticker = yf.Ticker(symbol)
        
        # 🔥 核心修复：直接调用属性，不带参数，避开 timescale 报错
        is_df = ticker.income_stmt.sort_index(axis=1) # 利润表
        bs_df = ticker.balance_sheet.sort_index(axis=1) # 资产负债表
        cf_df = ticker.cashflow.sort_index(axis=1) # 现金流量表

        if is_df.empty:
            st.error("数据拉取为空，请检查代码后缀（如 605499.SS）。")
            return

        years = [d.strftime('%Y') for d in is_df.columns]
        
        # --- 全量指标提取 ---
        rev = get_val(is_df, ['Total Revenue', 'Revenue'])
        ni = get_val(is_df, ['Net Income', 'Net Income Common Stockholders'])
        
        assets = get_val(bs_df, ['Total Assets'])
        equity = get_val(bs_df, ['Stockholders Equity', 'Total Equity'])
        liab = get_val(bs_df, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        # 负债率修复：资产 - 权益
        if liab.sum() == 0: liab = (assets - equity).clip(lower=0)
        
        ca = get_val(bs_df, ['Total Current Assets'])
        cl = get_val(bs_df, ['Total Current Liabilities'])
        ar = get_val(bs_df, ['Net Receivables', 'Accounts Receivable'])
        inv = get_val(bs_df, ['Inventory'])
        ap = get_val(bs_df, ['Accounts Payable'])
        ocf = get_val(cf_df, ['Operating Cash Flow'])
        
        # --- 指标计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        owc = ca - cl

        # --- 评分逻辑 ---
        score = 0
        reasons = []
        if roe.iloc[-1] > 15: score += 2; reasons.append("✅ 盈利卓越：最新ROE超过15%")
        if ocf.iloc[-1] > ni.iloc[-1]: score += 2; reasons.append("✅ 利润真实：现金流大于净利润")
        if debt_ratio.iloc[-1] < 50: score += 2; reasons.append("✅ 财务安全：负债率低于50%")
        if growth.iloc[-1] > 10: score += 2; reasons.append("✅ 稳步扩张：营收增长率超10%")
        if c2c.iloc[-1] < 90: score += 2; reasons.append("✅ 效率领先：现金周期管控优秀")

        # --- UI 渲染 ---
        st.title(f"🏛️ {symbol} 年度财务全谱分析")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"""<div style="text-align:center; border:5px solid #4CAF50; border-radius:15px; padding:20px;">
                <h1 style="color:#4CAF50; font-size:60px;">{score}</h1><p>综合健康分</p></div>""", unsafe_allow_html=True)
        with col2:
            st.subheader("📝 诊断总结")
            for r in reasons: st.write(r)
            if score < 6: st.write("⚠️ 预警：该标的部分核心财务指标存在压力。")

        st.divider()

        # --- 绘图区 (零删减) ---
        st.header("1️⃣ 营收成长与同比增速")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营业收入"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", line=dict(color='red', width=3)), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 盈利效率 (ROE 杜邦分析)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=years, y=roe, name="ROE %", line=dict(width=4, color='green')))
        f2.add_trace(go.Scatter(x=years, y=ni/rev*100, name="净利率 %", line=dict(dash='dot')))
        st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 经营细节 (C2C 周期 & OWC)")
        c31, c32 = st.columns(2)
        with c31:
            st.write("C2C 现金循环周期 (天)")
            st.bar_chart(pd.Series(c2c.values, index=years))
        with c32:
            st.write("营运资本 (OWC) 变动")
            st.line_chart(pd.Series(owc.values, index=years))

        st.header("4️⃣ 财务安全与含金量")
        c41, c42 = st.columns(2)
        with c41:
            st.write("资产负债率趋势 %")
            f41 = go.Figure(go.Scatter(x=years, y=debt_ratio, mode='lines+markers+text', text=[f"{x:.1f}" for x in debt_ratio]))
            f41.update_layout(yaxis=dict(range=[0, 100]))
            st.plotly_chart(f41, use_container_width=True)
        with c42:
            st.write("利润含金量 (净利润 vs 现金流)")
            f42 = go.Figure()
            f42.add_trace(go.Scatter(x=years, y=ni, name="净利润"))
            f42.add_trace(go.Scatter(x=years, y=ocf, name="现金流"))
            st.plotly_chart(f42, use_container_width=True)

    except Exception as e:
        st.error(f"引擎运行异常: {str(e)}")

if st.sidebar.button("🚀 运行深度诊断"):
    run_v57()
