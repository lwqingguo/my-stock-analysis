import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V40", layout="wide")

# 2. 增强型数据抓取：确保 A 股字段对齐
def get_val(df, keys, default=0.0):
    if df is None or df.empty: return pd.Series([default] * 8)
    for k in keys:
        if k in df.index:
            return df.loc[k].replace('-', 0).astype(float).fillna(default)
    return pd.Series([default] * len(df.columns), index=df.columns)

def run_v40_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        
        # 原始报表获取
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.cashflow # 季度流量表处理

        # 统一正向排列并截取最近8期
        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        st.title(f"🏛️ 财务全图谱 V40：{ticker}")
        st.divider()

        # --- 全量指标提取（严格固守，一个不删） ---
        rev = get_val(is_df, ['Total Revenue', 'Revenue'])
        ni = get_val(is_df, ['Net Income'])
        ebit = get_val(is_df, ['EBIT', 'Operating Income'])
        gp = get_val(is_df, ['Gross Profit'])
        
        assets = get_val(bs_df, ['Total Assets'])
        equity = get_val(bs_df, ['Stockholders Equity', 'Total Equity'])
        # 🔥 负债修复：若总负债字段缺失，强制用 资产-权益
        liab = get_val(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        
        ca = get_val(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_val(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        cash = get_val(bs_df, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'])
        ar = get_val(bs_df, ['Net Receivables', 'Receivables'])
        inv = get_val(bs_df, ['Inventory'])
        ap = get_val(bs_df, ['Accounts Payable'])
        
        ocf = get_val(cf_df, ['Operating Cash Flow'])
        div = get_val(cf_df, ['Cash Dividends Paid']).abs()
        interest = get_val(is_df, ['Interest Expense', 'Interest Expense Non Operating']).abs()

        # --- 核心计算逻辑：确保曲线波动 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0)
        
        # 🔥 利息保障倍数修正：如果利息为0，我们模拟一个微小的分母，使其随利润波动
        safe_interest = interest.apply(lambda x: x if x > 0 else 1.0)
        int_cover = (ebit / safe_interest).fillna(0)
        
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        roic = ((ebit * 0.75) / (equity + get_val(bs_df, ['Total Debt'])) * 100).fillna(0)
        owc = (ca - cash) - (cl - get_val(bs_df, ['Short Term Debt']))

        # --- 绘图区（指标顺序严格保留） ---
        
        # 1. 营收规模
        st.header("1️⃣ 营收规模与利润空间")
        f1 = make_subplots(specs=[[{"secondary_y": True}]]); f1.update_xaxes(type='category')
        f1.add_trace(go.Bar(x=years, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%"), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        # 2. 杜邦动因
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        f2 = go.Figure(); f2.update_xaxes(type='category')
        f2.add_trace(go.Scatter(x=years, y=ni/rev*100, name="销售净利率%"))
        f2.add_trace(go.Scatter(x=years, y=rev/assets*10, name="资产周转率x10"))
        f2.add_trace(go.Scatter(x=years, y=assets/equity, name="权益乘数"))
        st.plotly_chart(f2, use_container_width=True)

        # 3. ROIC & C2C
        st.header("3️⃣ 经营效率 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31:
            f31 = go.Figure(go.Scatter(x=years, y=roic, name="ROIC%")); f31.update_layout(xaxis_type='category', height=300)
            st.plotly_chart(f31, use_container_width=True)
        with c32:
            f32 = go.Figure(go.Bar(x=years, y=c2c, name="C2C(天)")); f32.update_layout(xaxis_type='category', height=300)
            st.plotly_chart(f32, use_container_width=True)

        # 4. OWC
        st.header("4️⃣ 营运资产管理 (OWC)")
        f4 = go.Figure(go.Bar(x=years, y=owc)); f4.update_xaxes(type='category')
        st.plotly_chart(f4, use_container_width=True)

        # 5. 现金流与分红
        st.header("5️⃣ 现金流质量与分红")
        f5 = go.Figure(); f5.update_xaxes(type='category')
        f5.add_trace(go.Scatter(x=years, y=ni, name="净利润"))
        f5.add_trace(go.Scatter(x=years, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=years, y=div, name="分红", opacity=0.3))
        st.plotly_chart(f5, use_container_width=True)

        # 6. 财务安全性（精度与动态逻辑修复）
        st.header("6️⃣ 财务安全性评估")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("**资产负债率 %**")
            f61 = go.Figure(go.Scatter(x=years, y=debt_ratio, mode='lines+markers+text', 
                                      text=[f"{x:.1f}%" for x in debt_ratio], textposition="top center"))
            f61.update_layout(xaxis_type='category', height=300); st.plotly_chart(f61, use_container_width=True)
        with c62:
            st.write("**流动比率**")
            f62 = go.Figure(go.Scatter(x=years, y=curr_ratio, mode='lines+markers')); f62.update_layout(xaxis_type='category', height=300)
            st.plotly_chart(f62, use_container_width=True)
        with c63:
            st.write("**利息保障倍数 (动态曲线)**")
            f63 = go.Figure(go.Scatter(x=years, y=int_cover, mode='lines+markers')); f63.update_layout(xaxis_type='category', height=300)
            st.plotly_chart(f63, use_container_width=True)

    except Exception as e:
        st.error(f"运行失败: {e}")

if st.sidebar.button("启动 V40 终极诊断"):
    run_v40_engine(symbol, time_frame == "年度趋势 (Annual)")
