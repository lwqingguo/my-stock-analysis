import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V60-全指标旗舰", layout="wide")

# 2. 侧边栏
st.sidebar.header("🛡️ 深度财务诊断 (V60)")
stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA", "腾讯控股": "0700.HK"}
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
def run_v60():
    try:
        ticker = yf.Ticker(symbol)
        is_df = ticker.income_stmt.sort_index(axis=1)
        bs_df = ticker.balance_sheet.sort_index(axis=1)
        cf_df = ticker.cashflow.sort_index(axis=1)

        if is_df.empty:
            st.error("数据拉取失败。")
            return

        years = [d.strftime('%Y') for d in is_df.columns]
        
        # --- [指标提取] ---
        rev = get_m(is_df, ['Total Revenue', 'Revenue'])
        ni = get_m(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_m(is_df, ['EBIT', 'Operating Income'])
        int_exp = get_m(is_df, ['Interest Expense', 'Interest Expense Non Operating']).abs()
        
        assets = get_m(bs_df, ['Total Assets'])
        equity = get_m(bs_df, ['Stockholders Equity', 'Total Equity'])
        liab = get_m(bs_df, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        ca = get_m(bs_df, ['Total Current Assets'])
        cl = get_m(bs_df, ['Total Current Liabilities'])
        ar, inv, ap = get_m(bs_df, ['Net Receivables']), get_m(bs_df, ['Inventory']), get_m(bs_df, ['Accounts Payable'])
        ocf = get_m(cf_df, ['Operating Cash Flow'])
        
        # --- [派生指标计算 - 补全版] ---
        # 1. 杜邦三因子 + 杠杆
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        net_margin = (ni / rev.replace(0, 1.0) * 100).fillna(0)
        asset_turnover = (rev / assets.replace(0, 1.0)).fillna(0)
        equity_multiplier = (assets / equity.replace(0, 1.0)).fillna(0) # 权益乘数 (杠杆)
        
        # 2. 财务安全补全
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        current_ratio = (ca / cl.replace(0, 1.0)).fillna(0) # 流动比率
        # 利息保障倍数 (EBIT / 利息支出)
        interest_coverage = (ebit / int_exp.replace(0, 1.0)).replace([np.inf, -np.inf], 100).clip(upper=100)
        
        # 3. 运营效率
        owc = ca - cl
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        growth = rev.pct_change().fillna(0) * 100

        # --- [UI 渲染] ---
        st.title(f"🏛️ {symbol} 全指标深度诊断 (V60)")
        
        # 评分与总结 (逻辑增强)
        score = 0
        if roe.iloc[-1] > 15: score += 2
        if ocf.iloc[-1] > ni.iloc[-1]: score += 2
        if current_ratio.iloc[-1] > 1.5: score += 2
        if interest_coverage.iloc[-1] > 3: score += 2
        if growth.iloc[-1] > 5: score += 2
        
        st.metric("综合财务健康分 (10分制)", f"{score} / 10")
        st.divider()

        # 图表 1: 营收成长
        st.header("1️⃣ 营收规模与年度同比增速")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营业收入"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", line=dict(color='red', width=3)), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        # 图表 2: 杜邦分析 (补全杠杆乘数)
        st.header("2️⃣ 杜邦分析：盈利、效率与杠杆 (ROE 拆解)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=years, y=roe, name="ROE % (股东回报)", line=dict(width=5, color='green')))
        f2.add_trace(go.Scatter(x=years, y=net_margin, name="净利率 %"))
        f2.add_trace(go.Scatter(x=years, y=asset_turnover*10, name="周转率 x10"))
        f2.add_trace(go.Scatter(x=years, y=equity_multiplier*10, name="权益乘数 (杠杆) x10", line=dict(dash='dash')))
        st.plotly_chart(f2, use_container_width=True)

        # 图表 3: 运营效率 (OWC & C2C)
        st.header("3️⃣ 经营细节 (C2C 周期 & OWC 营运资本)")
        c31, c32 = st.columns(2)
        with c31:
            st.write("**C2C 现金循环周期 (天)**")
            st.bar_chart(pd.Series(c2c.values, index=years))
        with c32:
            st.write("**营运资本 (OWC) 趋势**")
            st.line_chart(pd.Series(owc.values, index=years))

        # 图表 4: 财务安全补全 (流动比率 & 负债率)
        st.header("4️⃣ 财务安全与流动性 (负债率 & 流动比率)")
        f4 = make_subplots(specs=[[{"secondary_y": True}]])
        f4.add_trace(go.Scatter(x=years, y=debt_ratio, name="资产负债率 %", line=dict(color='orange')), secondary_y=False)
        f4.add_trace(go.Bar(x=years, y=current_ratio, name="流动比率 (倍)", opacity=0.3), secondary_y=True)
        f4.update_yaxes(range=[0, 100], secondary_y=False)
        st.plotly_chart(f4, use_container_width=True)

        # 图表 5: 偿债能力与现金流质量
        st.header("5️⃣ 偿债保障与利润质量 (利息保障倍数 & 现金流)")
        c51, c52 = st.columns(2)
        with c51:
            st.write("**利息保障倍数 (EBIT/利息)**")
            st.line_chart(pd.Series(interest_coverage.values, index=years))
        with c52:
            st.write("**净利润 vs 经营现金流**")
            f52 = go.Figure()
            f52.add_trace(go.Scatter(x=years, y=ni, name="净利润"))
            f52.add_trace(go.Scatter(x=years, y=ocf, name="现金流"))
            st.plotly_chart(f52, use_container_width=True)

    except Exception as e:
        st.error(f"分析异常: {e}")

if st.sidebar.button("🚀 启动年度全指标诊断"):
    run_v60()
