import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V62-终极审计版", layout="wide")

# 2. 侧边栏
st.sidebar.header("🛡️ 深度财务诊断 (V62)")
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
def run_v62():
    try:
        ticker = yf.Ticker(symbol)
        # 获取年度原始报表
        is_df = ticker.income_stmt.sort_index(axis=1)
        bs_df = ticker.balance_sheet.sort_index(axis=1)
        cf_df = ticker.cashflow.sort_index(axis=1)

        if is_df.empty or bs_df.empty:
            st.error("数据抓取失败，请检查网络或代码后缀。")
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
        if liab.sum() == 0: liab = (assets - equity).clip(lower=0)
        
        ca = get_m(bs_df, ['Total Current Assets'])
        cl = get_m(bs_df, ['Total Current Liabilities'])
        ar = get_m(bs_df, ['Net Receivables', 'Accounts Receivable'])
        inv = get_m(bs_df, ['Inventory'])
        ap = get_m(bs_df, ['Accounts Payable'])
        
        ocf = get_m(cf_df, ['Operating Cash Flow'])
        # 提取分红 (Cash Dividends Paid，通常为负值，需取绝对值)
        div = get_m(cf_df, ['Cash Dividends Paid', 'Common Stock Dividend Paid']).abs()
        
        # --- [核心比率计算] ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        net_margin = (ni / rev.replace(0, 1.0) * 100).fillna(0)
        asset_turnover = (rev / assets.replace(0, 1.0)).fillna(0)
        equity_multiplier = (assets / equity.replace(0, 1.0)).fillna(0)
        
        # 营运资本 (OWC) 显性化计算
        owc = (ca - cl) 
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        
        # 财务安全指标
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        current_ratio = (ca / cl.replace(0, 1.0)).fillna(0)
        interest_coverage = (ebit / int_exp.replace(0, 0.001)).clip(lower=-5, upper=50)

        # --- [UI 展示] ---
        st.title(f"🏛️ {symbol} 财务审计全谱 (V62 满配版)")
        
        # 智能诊断总结
        score = 0
        if roe.iloc[-1] > 15: score += 2
        if ocf.iloc[-1] > ni.iloc[-1]: score += 2
        if current_ratio.iloc[-1] > 1.2: score += 2
        if interest_coverage.iloc[-1] > 5: score += 2
        if div.iloc[-1] > 0: score += 2
        
        c1, c2 = st.columns([1, 2])
        with c1: st.metric("综合健康分", f"{score}/10")
        with c2: st.success(f"诊断结论：最新年度 ROE 为 {roe.iloc[-1]:.2f}%，资产负债率为 {debt_ratio.iloc[-1]:.2f}%。")

        st.divider()

        # 板块 1: 成长与效率 (杜邦分析含杠杆)
        st.header("1️⃣ 成长性与杜邦分析 (含杠杆乘数)")
        f1 = make_subplots(rows=1, cols=2, subplot_titles=("营收与增速", "杜邦拆解 (ROE/净利/周转/杠杆)"))
        # 营收
        f1.add_trace(go.Bar(x=years, y=rev, name="营收"), row=1, col=1)
        # 杜邦
        f1.add_trace(go.Scatter(x=years, y=roe, name="ROE%", line=dict(width=4, color='green')), row=1, col=2)
        f1.add_trace(go.Scatter(x=years, y=net_margin, name="净利率%"), row=1, col=2)
        f1.add_trace(go.Scatter(x=years, y=asset_turnover*10, name="周转率x10"), row=1, col=2)
        f1.add_trace(go.Scatter(x=years, y=equity_multiplier*5, name="权益乘数x5", line=dict(dash='dash')), row=1, col=2)
        st.plotly_chart(f1, use_container_width=True)

        # 板块 2: 经营效率细节 (OWC 修复)
        st.header("2️⃣ 经营细节 (C2C 周期 & OWC 营运资本)")
        c31, c32 = st.columns(2)
        with c31:
            st.write("**C2C 现金循环周期 (天)**")
            st.bar_chart(pd.Series(c2c.values, index=years))
        with c32:
            st.write("**营运资本 OWC (流动资产 - 流动负债)**")
            # 确保使用柱状图展示，更直观看到正负变动
            st.bar_chart(pd.Series(owc.values, index=years))

        # 板块 3: 财务安全指数 (三剑客)
        st.header("3️⃣ 财务安全指数 (负债/比率/利息保障)")
        f4 = make_subplots(specs=[[{"secondary_y": True}]])
        f4.add_trace(go.Scatter(x=years, y=debt_ratio, name="资产负债率 %", line=dict(color='orange', width=3)), secondary_y=False)
        f4.add_trace(go.Scatter(x=years, y=interest_coverage, name="利息保障倍数", line=dict(color='blue')), secondary_y=False)
        f4.add_trace(go.Bar(x=years, y=current_ratio, name="流动比率 (倍)", opacity=0.3), secondary_y=True)
        f4.update_yaxes(title_text="百分比 / 倍数", secondary_y=False)
        f4.update_yaxes(title_text="流动比率 (倍)", secondary_y=True)
        st.plotly_chart(f4, use_container_width=True)

        # 板块 4: 利润质量与分红 (核心对比)
        st.header("4️⃣ 利润质量与股东分配 (利润 vs 现金流 vs 分红)")
        f5 = go.Figure()
        f5.add_trace(go.Bar(x=years, y=ni, name="归母净利润", marker_color='blue'))
        f5.add_trace(go.Bar(x=years, y=ocf, name="经营现金流", marker_color='green'))
        f5.add_trace(go.Bar(x=years, y=div, name="现金分红", marker_color='gold'))
        f5.update_layout(barmode='group', title="利润含金量与分红慷慨度对比")
        st.plotly_chart(f5, use_container_width=True)

    except Exception as e:
        st.error(f"分析引擎逻辑故障: {e}")

if st.sidebar.button("🚀 运行终极全指标诊断"):
    run_v62()
