
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V68-ROE强化版", layout="wide")

# 2. 侧边栏常驻逻辑 (保持原版)
st.sidebar.header("🔍 数据维度设置")
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

def get_any(df, tags):
    if df is None or df.empty: return pd.Series([0.0] * 8)
    df.index = df.index.map(str).str.strip()
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty: return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主分析引擎 ---
def run_v68_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty or bs_raw.empty:
            st.error("无法获取财务报表数据。")
            return

        # 统一正序与日期轴
        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        # --- 全量指标提取 (保持 V43 标签) ---
        rev = get_any(is_df, ['Total Revenue', 'Revenue'])
        ni = get_any(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_any(is_df, ['EBIT', 'Operating Income'])
        assets = get_any(bs_df, ['Total Assets'])
        equity = get_any(bs_df, ['Stockholders Equity', 'Total Equity'])
        ca = get_any(bs_df, ['Total Current Assets'])
        cl = get_any(bs_df, ['Total Current Liabilities'])
        liab = get_any(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        cash = get_any(bs_df, ['Cash And Cash Equivalents'])
        st_debt = get_any(bs_df, ['Short Term Debt', 'Current Debt'])
        ar = get_any(bs_df, ['Net Receivables'])
        inv = get_any(bs_df, ['Inventory'])
        ap = get_any(bs_df, ['Accounts Payable'])
        ocf = get_any(cf_df, ['Operating Cash Flow'])
        div = get_any(cf_df, ['Cash Dividends Paid']).abs()
        interest = get_any(is_df, ['Interest Expense', 'Financial Expense']).abs()

        # --- 核心比率计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        # OWC 校准：强制索引对齐计算
        align_df = pd.DataFrame({'ca': ca, 'cash': cash, 'cl': cl, 'st_debt': st_debt}).fillna(0)
        owc = (align_df['ca'] - align_df['cash']) - (align_df['cl'] - align_df['st_debt'])
        
        # 杜邦三因子指标
        net_margin = (ni / rev * 100).fillna(0)
        asset_turnover = (rev / assets).fillna(0)
        equity_multiplier = (assets / equity).fillna(0)

        # --- 头部展示 ---
        st.title(f"🏛️ 财务全图谱 V68：{ticker}")
        st.divider()

        # 1. 营收规模 (保持)
        st.header("1️⃣ 营收规模与利润空间")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", line=dict(color='red')), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        # 2. ROE 深度拆解 (重磅修改：3图并列)
        st.header("2️⃣ 核心回报：ROE 杜邦三因子拆解")
        
        st.subheader(f"最新 ROE: {roe.iloc[-1]:.2f}%")
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            st.write("**因子 1：净利率 (%)**")
            st.line_chart(net_margin)
        with rc2:
            st.write("**因子 2：总资产周转率 (次)**")
            st.line_chart(asset_turnover)
        with rc3:
            st.write("**因子 3：权益乘数 (杠杆倍数)**")
            st.line_chart(equity_multiplier)

        # 3. 经营效率
        st.header("3️⃣ 经营效率 (C2C & OWC)")
        c31, c32 = st.columns(2)
        with c31: st.write("**C2C 周期 (天)**"); st.bar_chart(pd.Series(c2c.values, index=years))
        with c32: st.write("**营运资本 OWC (对齐校准版)**"); st.bar_chart(pd.Series(owc.values, index=years))

        # 4. 利润质量与分红
        st.header("4️⃣ 利润质量与股东回报")
        f5 = go.Figure()
        f5.add_trace(go.Bar(x=years, y=ni, name="净利润"))
        f5.add_trace(go.Bar(x=years, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=years, y=div, name="分红", opacity=0.5))
        f5.update_layout(barmode='group'); st.plotly_chart(f5, use_container_width=True)

        # 5. 财务安全性评估 (拆分逻辑)
        st.header("5️⃣ 财务安全性评估")
        c61, c62 = st.columns([2, 1])
        with c61:
            st.write("**资产负债率 % (左轴) vs 流动比率 (右轴)**")
            f6 = make_subplots(specs=[[{"secondary_y": True}]])
            f6.add_trace(go.Scatter(x=years, y=debt_ratio, name="负债率%", line=dict(color='orange', width=3)), secondary_y=False)
            f6.add_trace(go.Bar(x=years, y=curr_ratio, name="流动比率", opacity=0.3), secondary_y=True)
            f6.update_yaxes(range=[0, 100], secondary_y=False)
            st.plotly_chart(f6, use_container_width=True)
        with c62:
            st.write("**利息保障倍数**")
            st.line_chart(pd.Series(int_cover.values, index=years))

    except Exception as e:
        st.error(f"分析引擎发生错误: {e}")

if st.sidebar.button("启动 V68 强化诊断版"):
    run_v68_engine(symbol, time_frame == "年度趋势 (Annual)")
