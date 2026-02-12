import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V66-终极全指标版", layout="wide")

# 2. 侧边栏
st.sidebar.header("🛡️ 深度财务诊断 (V66 Core)")
time_frame = st.sidebar.radio("分析维度：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])
stock_list = {
    "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "英伟达 (NVDA)": "NVDA",
    "特斯拉 (TSLA)": "TSLA"
}
selected_stock = st.sidebar.selectbox("快速选择：", list(stock_list.keys()))
symbol = st.sidebar.text_input("手动输入代码：", stock_list[selected_stock]).upper()

# --- 核心辅助函数：索引对齐提取 ---
def get_aligned_data(df, tags):
    if df is None or df.empty: return pd.Series(dtype=float)
    df.index = df.index.map(str).str.strip()
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag]
            if isinstance(res, pd.DataFrame): res = res.iloc[0]
            return res.replace('-', np.nan).astype(float).fillna(0.0)
    return pd.Series(0.0, index=df.columns)

# --- 主引擎 ---
def run_v66_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        # 兼容年度和季度
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty or bs_raw.empty:
            st.error("数据拉取失败，请检查网络或代码。")
            return

        # 统一正序，取最新8个周期
        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        years = [d.strftime('%Y-%m') for d in is_df.columns]

        # --- 全量指标提取 (基于 V43 标签库) ---
        rev = get_aligned_data(is_df, ['Total Revenue', 'Revenue', 'Operating Revenue'])
        ni = get_aligned_data(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_aligned_data(is_df, ['EBIT', 'Operating Income'])
        interest = get_aligned_data(is_df, ['Interest Expense', 'Interest Expense Non Operating']).abs()
        
        assets = get_aligned_data(bs_df, ['Total Assets'])
        equity = get_aligned_data(bs_df, ['Stockholders Equity', 'Total Equity'])
        ca = get_aligned_data(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_aligned_data(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        liab = get_aligned_data(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        
        cash = get_aligned_data(bs_df, ['Cash And Cash Equivalents'])
        st_debt = get_aligned_data(bs_df, ['Short Term Debt', 'Current Debt'])
        ar = get_aligned_data(bs_df, ['Net Receivables'])
        inv = get_aligned_data(bs_df, ['Inventory'])
        ap = get_aligned_data(bs_df, ['Accounts Payable'])
        
        ocf = get_aligned_data(cf_df, ['Operating Cash Flow'])
        div = get_aligned_data(cf_df, ['Cash Dividends Paid', 'Dividends Paid']).abs()

        # --- 核心比率计算 (强制对齐) ---
        calc_df = pd.DataFrame({
            'ca': ca, 'cl': cl, 'rev': rev, 'ni': ni, 'assets': assets, 
            'equity': equity, 'liab': liab, 'cash': cash, 'st_debt': st_debt
        }).fillna(0)

        growth = calc_df['rev'].pct_change().fillna(0) * 100
        roe = (calc_df['ni'] / calc_df['equity'] * 100).fillna(0)
        debt_ratio = (calc_df['liab'] / calc_df['assets'] * 100).fillna(0)
        curr_ratio = (calc_df['ca'] / calc_df['cl'].replace(0, 1.0)).fillna(0)
        # OWC 公式校准
        owc = (calc_df['ca'] - calc_df['cash']) - (calc_df['cl'] - calc_df['st_debt'])
        # 利息保障倍数
        int_cover = (ebit / interest.replace(0, 0.001)).clip(-5, 50)
        # C2C 周期
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)

        # --- UI 渲染 ---
        st.title(f"🏛️ 财务全图谱 V66 (V29灵魂复刻版)：{ticker}")
        
        # 评分系统
        score = sum([roe.iloc[-1]>15, (ocf.iloc[-1]/ni.iloc[-1] if ni.iloc[-1]!=0 else 0)>1, 
                     debt_ratio.iloc[-1]<50, growth.iloc[-1]>10, c2c.iloc[-1]<60]) * 2
        st.metric("综合健康分", f"{score} / 10")
        st.divider()

        # 1. 营收与效率
        st.header("1️⃣ 营收成长与 OWC 变动")
        col1, col2 = st.columns(2)
        with col1:
            f1 = make_subplots(specs=[[{"secondary_y": True}]])
            f1.add_trace(go.Bar(x=years, y=rev, name="营收"), secondary_y=False)
            f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", line=dict(color='red')), secondary_y=True)
            f1.update_layout(height=400, xaxis_type='category'); st.plotly_chart(f1, use_container_width=True)
        with col2:
            st.write("**营运资本 OWC 趋势**")
            st.bar_chart(pd.Series(owc.values, index=years))

        # 2. 财务安全 A (拆分：负债率 & 流动比率)
        st.header("2️⃣ 财务安全 A：杠杆与短期流动性")
        
        f2 = make_subplots(specs=[[{"secondary_y": True}]])
        f2.add_trace(go.Scatter(x=years, y=debt_ratio, name="资产负债率 %", line=dict(color='orange', width=4)), secondary_y=False)
        f2.add_trace(go.Bar(x=years, y=curr_ratio, name="流动比率 (倍)", opacity=0.3), secondary_y=True)
        f2.update_yaxes(title_text="负债率 %", range=[0, 100], secondary_y=False)
        f2.update_yaxes(title_text="流动比率 (倍)", secondary_y=True)
        f2.update_layout(height=400, xaxis_type='category'); st.plotly_chart(f2, use_container_width=True)

        # 3. 财务安全 B (拆分：利息保障倍数)
        st.header("3️⃣ 财务安全 B：偿债保障 (利息保障倍数)")
        
        f3 = go.Figure(go.Scatter(x=years, y=int_cover, mode='lines+markers+text', 
                                  text=[f"{x:.1f}" for x in int_cover], name="利息保障倍数", line=dict(color='blue')))
        f3.update_layout(height=400, yaxis_title="倍数 (EBIT/利息)", xaxis_type='category')
        st.plotly_chart(f3, use_container_width=True)

        # 4. 盈利驱动与周转
        st.header("4️⃣ 盈利效率 (ROE 杜邦拆解)")
        
        f4 = go.Figure()
        f4.add_trace(go.Scatter(x=years, y=roe, name="ROE%", line=dict(width=5, color='green')))
        f4.add_trace(go.Scatter(x=years, y=ni/rev*100, name="净利率%"))
        f4.add_trace(go.Scatter(x=years, y=rev/assets*10, name="周转率x10"))
        f4.update_layout(height=400, xaxis_type='category'); st.plotly_chart(f4, use_container_width=True)

        # 5. 利润质量与分红
        st.header("5️⃣ 利润质量与分红 (净利/现金流/分红)")
        
        f5 = go.Figure()
        f5.add_trace(go.Bar(x=years, y=ni, name="净利润", marker_color='royalblue'))
        f5.add_trace(go.Bar(x=years, y=ocf, name="经营现金流", marker_color='seagreen'))
        f5.add_trace(go.Bar(x=years, y=div, name="现金分红", marker_color='gold'))
        f5.update_layout(height=450, barmode='group', xaxis_type='category')
        st.plotly_chart(f5, use_container_width=True)

    except Exception as e:
        st.error(f"引擎故障: {e}")

if st.sidebar.button("启动 V66 终极版诊断"):
    run_v66_engine(symbol, time_frame == "年度趋势 (Annual)")
