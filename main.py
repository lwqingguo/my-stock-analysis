import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V29-年度增强版", layout="wide")

# 2. 侧边栏
st.sidebar.header("🛡️ 深度财务诊断 (V29 Core)")
stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA", "腾讯控股": "0700.HK", "特斯拉": "TSLA"}
selected_stock = st.sidebar.selectbox("1. 快捷选择公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("2. 手动输入代码", stock_list[selected_stock]).upper()

# --- 核心辅助：V29 标准取数逻辑 ---
def get_data(df, tags):
    if df is None or df.empty: return pd.Series(dtype=float)
    df.index = df.index.map(str).str.strip()
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag]
            if isinstance(res, pd.DataFrame): res = res.iloc[0]
            return res.replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series(0.0, index=df.columns)

# --- 主引擎 ---
def run_v29_core():
    try:
        ticker = yf.Ticker(symbol)
        # 强制年度化属性访问 (避开 timescale 参数)
        is_df = ticker.income_stmt.sort_index(axis=1)
        bs_df = ticker.balance_sheet.sort_index(axis=1)
        cf_df = ticker.cashflow.sort_index(axis=1)

        if is_df.empty:
            st.error("无法获取年度报表，请检查代码。")
            return

        years = [d.strftime('%Y') for d in is_df.columns]
        
        # --- 原始指标提取 ---
        rev = get_data(is_df, ['Total Revenue', 'Revenue'])
        ni = get_data(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_data(is_df, ['EBIT', 'Operating Income'])
        int_exp = get_data(is_df, ['Interest Expense']).abs()
        
        assets = get_data(bs_df, ['Total Assets'])
        equity = get_data(bs_df, ['Stockholders Equity', 'Total Equity'])
        liab = get_data(bs_df, ['Total Liabilities'])
        ca = get_data(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_data(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        
        ar = get_data(bs_df, ['Net Receivables', 'Accounts Receivable'])
        inv = get_data(bs_df, ['Inventory'])
        ap = get_data(bs_df, ['Accounts Payable'])
        
        ocf = get_data(cf_df, ['Operating Cash Flow'])
        div = get_data(cf_df, ['Cash Dividends Paid', 'Common Stock Dividend Paid']).abs()

        # --- 核心比率计算 (强制索引对齐以修复 OWC) ---
        align_df = pd.DataFrame({'ca': ca, 'cl': cl, 'rev': rev, 'ni': ni, 'assets': assets, 'equity': equity}).fillna(0)
        
        owc = align_df['ca'] - align_df['cl']
        growth = align_df['rev'].pct_change().fillna(0) * 100
        roe = (align_df['ni'] / align_df['equity'].replace(0, 1.0) * 100).fillna(0)
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        current_ratio = (align_df['ca'] / align_df['cl'].replace(0, 1.0)).fillna(0)
        interest_coverage = (ebit / int_exp.replace(0, 0.001)).clip(lower=-5, upper=100)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)

        # --- UI 渲染 ---
        st.title(f"🏛️ {symbol} 财务全谱 (V29 年度回归版)")
        
        # 1. 评分与总结 (V29 风格)
        score = 0
        if roe.iloc[-1] > 15: score += 2
        if ocf.iloc[-1] > ni.iloc[-1]: score += 2
        if current_ratio.iloc[-1] > 1.2: score += 2
        if interest_coverage.iloc[-1] > 3: score += 2
        if div.iloc[-1] > 0: score += 2

        c1, c2 = st.columns([1, 2])
        with c1: st.metric("财务健康评分", f"{score}/10")
        with c2: st.info(f"总结：ROE {roe.iloc[-1]:.1f}%，负债率 {debt_ratio.iloc[-1]:.1f}%。利息保障倍数最新为 {interest_coverage.iloc[-1]:.1f} 倍。")

        st.divider()

        # 2. 经营效率 (OWC 重点复活)
        st.header("1️⃣ 经营效率：OWC 变动与现金周期")
        c21, c22 = st.columns(2)
        with c21:
            st.write("**营运资本 OWC (流动资产 - 流动负债)**")
            st.bar_chart(pd.Series(owc.values, index=years))
        with c22:
            st.write("**C2C 现金循环周期 (天)**")
            st.bar_chart(pd.Series(c2c.values, index=years))

        # 3. 财务安全 A (资产负债率 & 流动比率)
        st.header("2️⃣ 财务安全 A：杠杆与短期流动性")
        
        f2 = make_subplots(specs=[[{"secondary_y": True}]])
        f2.add_trace(go.Scatter(x=years, y=debt_ratio, name="资产负债率 %", line=dict(color='orange', width=4)), secondary_y=False)
        f2.add_trace(go.Bar(x=years, y=current_ratio, name="流动比率 (倍)", opacity=0.3), secondary_y=True)
        f2.update_yaxes(title_text="负债率 %", range=[0, 100], secondary_y=False)
        f2.update_yaxes(title_text="流动比率 (倍)", secondary_y=True)
        st.plotly_chart(f2, use_container_width=True)

        # 4. 财务安全 B (利息保障倍数)
        st.header("3️⃣ 财务安全 B：偿债保障 (利息保障倍数)")
        
        f3 = go.Figure(go.Scatter(x=years, y=interest_coverage, mode='lines+markers+text', 
                                  text=[f"{x:.1f}" for x in interest_coverage], name="利息保障倍数", line=dict(color='blue')))
        f3.update_layout(yaxis_title="倍数 (EBIT/利息)")
        st.plotly_chart(f3, use_container_width=True)

        # 5. 盈利驱动 (杜邦分析)
        st.header("4️⃣ 盈利驱动 (ROE 杜邦分析)")
        f4 = go.Figure()
        f4.add_trace(go.Scatter(x=years, y=roe, name="ROE%", line=dict(width=5, color='green')))
        f4.add_trace(go.Scatter(x=years, y=(ni/rev*100), name="净利率%"))
        st.plotly_chart(f4, use_container_width=True)

        # 6. 利润质量与分红 (利润 vs 现金流 vs 分红)
        st.header("5️⃣ 利润质量与分红 (含金量对比)")
        f5 = go.Figure()
        f5.add_trace(go.Bar(x=years, y=ni, name="净利润", marker_color='blue'))
        f5.add_trace(go.Bar(x=years, y=ocf, name="经营现金流", marker_color='green'))
        f5.add_trace(go.Bar(x=years, y=div, name="分红金额", marker_color='gold'))
        f5.update_layout(barmode='group')
        st.plotly_chart(f5, use_container_width=True)

    except Exception as e:
        st.error(f"分析异常: {e}")

if st.sidebar.button("🚀 运行 V29 增强版"):
    run_v29_core()
