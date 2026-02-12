import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V63-专家版", layout="wide")

# 2. 侧边栏
st.sidebar.header("🛡️ 深度财务诊断 (V63)")
stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA", "腾讯控股": "0700.HK", "特斯拉": "TSLA"}
selected_stock = st.sidebar.selectbox("1. 快捷选择公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("2. 手动输入代码", stock_list[selected_stock]).upper()

def get_m(df, tags):
    if df is None or df.empty: return pd.Series(0.0, index=[0])
    df.index = df.index.map(str).str.strip()
    for tag in tags:
        if tag in df.index:
            data = df.loc[tag]
            if isinstance(data, pd.DataFrame): data = data.iloc[0]
            return data.replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series(0.0, index=df.columns)

# --- 主引擎 ---
def run_v63():
    try:
        ticker = yf.Ticker(symbol)
        is_df = ticker.income_stmt.sort_index(axis=1)
        bs_df = ticker.balance_sheet.sort_index(axis=1)
        cf_df = ticker.cashflow.sort_index(axis=1)

        if is_df.empty:
            st.error("数据拉取失败。")
            return

        years = [d.strftime('%Y') for d in is_df.columns]
        
        # --- [精准提取：解决 OWC 为 0 问题] ---
        rev = get_m(is_df, ['Total Revenue', 'Revenue'])
        ni = get_m(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_m(is_df, ['EBIT', 'Operating Income'])
        int_exp = get_m(is_df, ['Interest Expense', 'Interest Expense Non Operating']).abs()
        
        assets = get_m(bs_df, ['Total Assets'])
        equity = get_m(bs_df, ['Stockholders Equity', 'Total Equity'])
        # 流动资产与流动负债 (多标签匹配)
        ca = get_m(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_m(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        
        liab = get_m(bs_df, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        if liab.sum() == 0: liab = (assets - equity).clip(lower=0)
        
        ar = get_m(bs_df, ['Net Receivables', 'Accounts Receivable'])
        inv = get_m(bs_df, ['Inventory', 'Stock'])
        ap = get_m(bs_df, ['Accounts Payable'])
        
        ocf = get_m(cf_df, ['Operating Cash Flow'])
        div = get_m(cf_df, ['Cash Dividends Paid', 'Common Stock Dividend Paid']).abs()
        
        # --- [指标计算] ---
        # 1. 营运资本 (OWC) 
        owc = (ca - cl) # 修正公式
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        
        # 2. 安全指标拆分
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        current_ratio = (ca / cl.replace(0, 1.0)).fillna(0)
        # 利息保障倍数
        interest_coverage = (ebit / int_exp.replace(0, 0.001)).clip(lower=-5, upper=100)
        
        # 3. 杜邦
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        net_margin = (ni / rev.replace(0, 1.0) * 100).fillna(0)
        asset_turnover = (rev / assets.replace(0, 1.0)).fillna(0)
        equity_multiplier = (assets / equity.replace(0, 1.0)).fillna(0)

        # --- [UI 渲染] ---
        st.title(f"🏛️ {symbol} 财务全谱诊断 (V63)")
        
        st.header("1️⃣ 经营效率：OWC 与现金循环周期")
        c11, c12 = st.columns(2)
        with c11:
            st.write("**营运资本 OWC (流动资产 - 流动负债)**")
            if owc.sum() == 0: st.warning("提示：该标的原始报表中流动资产/负债项缺失")
            st.bar_chart(pd.Series(owc.values, index=years))
        with c12:
            st.write("**C2C 现金循环周期 (天)**")
            st.bar_chart(pd.Series(c2c.values, index=years))

        st.header("2️⃣ 财务安全 A：杠杆与短期流动性")
        f2 = make_subplots(specs=[[{"secondary_y": True}]])
        f2.add_trace(go.Scatter(x=years, y=debt_ratio, name="资产负债率 %", line=dict(color='orange', width=4)), secondary_y=False)
        f2.add_trace(go.Bar(x=years, y=current_ratio, name="流动比率 (倍)", opacity=0.4), secondary_y=True)
        f2.update_yaxes(title_text="负债率 (%)", secondary_y=False, range=[0, 100])
        f2.update_yaxes(title_text="流动比率 (倍)", secondary_y=True)
        st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 财务安全 B：偿债能力 (利息保障倍数)")
        f3 = go.Figure()
        f3.add_trace(go.Scatter(x=years, y=interest_coverage, name="利息保障倍数 (EBIT/利息)", line=dict(color='blue', width=3), mode='lines+markers+text', text=[f"{x:.1f}" for x in interest_coverage], textposition="top center"))
        f3.update_layout(yaxis_title="倍数")
        st.plotly_chart(f3, use_container_width=True)

        st.header("4️⃣ 盈利驱动 (杜邦分析)")
        f4 = go.Figure()
        f4.add_trace(go.Scatter(x=years, y=roe, name="ROE%", line=dict(width=5, color='green')))
        f4.add_trace(go.Scatter(x=years, y=net_margin, name="净利率%"))
        f4.add_trace(go.Scatter(x=years, y=asset_turnover*10, name="周转率x10"))
        f4.add_trace(go.Scatter(x=years, y=equity_multiplier*5, name="权益乘数x5", line=dict(dash='dash')))
        st.plotly_chart(f4, use_container_width=True)

        st.header("5️⃣ 利润质量与分红对比")
        f5 = go.Figure()
        f5.add_trace(go.Bar(x=years, y=ni, name="归母净利润", marker_color='royalblue'))
        f5.add_trace(go.Bar(x=years, y=ocf, name="经营现金流", marker_color='seagreen'))
        f5.add_trace(go.Bar(x=years, y=div, name="现金分红", marker_color='gold'))
        f5.update_layout(barmode='group')
        st.plotly_chart(f5, use_container_width=True)

    except Exception as e:
        st.error(f"分析引擎故障: {e}")

if st.sidebar.button("🚀 启动年度深度诊断"):
    run_v63()
