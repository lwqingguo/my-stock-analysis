import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V69.8", layout="wide")

# 2. 侧边栏
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

# --- 辅助函数：统一 Plotly 渲染器 (带标题 + 数字标签) ---
def st_plotly_line(x, y, name, unit="", color=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, name=name,
        mode='lines+markers+text',
        text=[f"{v:.2f}{unit}" for v in y],
        textposition="top center",
        line=dict(color=color, width=3)
    ))
    fig.update_layout(
        title={'text': name, 'x': 0.5, 'xanchor': 'center'},
        height=300, 
        margin=dict(l=10, r=10, t=50, b=10), 
        xaxis_type='category'
    )
    st.plotly_chart(fig, use_container_width=True)

def st_plotly_bar(x, y, name, color=None):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x, y=y, name=name,
        text=[f"{v:.2f}" for v in y],
        textposition='auto',
        marker_color=color
    ))
    fig.update_layout(
        title={'text': name, 'x': 0.5, 'xanchor': 'center'},
        height=300, 
        margin=dict(l=10, r=10, t=50, b=10), 
        xaxis_type='category'
    )
    st.plotly_chart(fig, use_container_width=True)

def get_any(df, tags):
    if df is None or df.empty: return pd.Series([0.0] * 8)
    df.index = df.index.map(str).str.strip()
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty: return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v69_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty or bs_raw.empty:
            st.error("数据抓取失败。")
            return

        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        # --- 核心数据提取 ---
        rev = get_any(is_df, ['Total Revenue', 'Revenue'])
        ni = get_any(is_df, ['Net Income'])
        ebit = get_any(is_df, ['EBIT', 'Operating Income'])
        assets = get_any(bs_df, ['Total Assets'])
        equity = get_any(bs_df, ['Stockholders Equity'])
        ca = get_any(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_any(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        liab = get_any(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        cash = get_any(bs_df, ['Cash And Cash Equivalents'])
        ocf = get_any(cf_df, ['Operating Cash Flow'])
        div = get_any(cf_df, ['Cash Dividends Paid']).abs()
        interest = get_any(is_df, ['Interest Expense', 'Financial Expense']).abs()

        calc_df = pd.DataFrame({'ca': ca, 'cl': cl, 'rev': rev, 'ni': ni, 'assets': assets, 'equity': equity, 'cash': cash}).fillna(0)
        growth = calc_df['rev'].pct_change().fillna(0) * 100
        roe = (calc_df['ni'] / calc_df['equity'] * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio_pct = (calc_df['ca'] / calc_df['cl'].replace(0, np.nan) * 100).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)

        # --- 1. 顶部：公司概况 ---
        st.title(f"🏛️ 财务审计图谱 V69.8：{info.get('longName', ticker)}")
        with st.expander("🏢 查看公司主营业务与商业模式", expanded=True):
            c_info1, c_info2 = st.columns([1, 2])
            with c_info1:
                st.write(f"**行业**：{info.get('industry', '未知')}")
                st.write(f"**上市地点**：{info.get('exchange', '未知')}")
            with c_info2:
                st.write("**业务摘要**：")
                st.write(info.get('longBusinessSummary', '暂无描述')[:500] + "...")

        # --- 2. 诊断总结 ---
        score = sum([roe.iloc[-1]>15, (ocf/ni).iloc[-1]>1, debt_ratio.iloc[-1]<50, growth.iloc[-1]>10]) * 2.5
        col_s, col_d = st.columns([1, 2])
        with col_s:
            color = "#2E7D32" if score >= 7.5 else "#FFA000"
            st.markdown(f'<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:15px;"><h1 style="font-size:60px; color:{color};">{score:g}</h1><b>综合评分</b></div>', unsafe_allow_html=True)
        with col_d:
            st.subheader("📝 核心诊断总结")
            st.write(f"**盈利**: {roe.iloc[-1]:.2f}% | **含金量**: {(ocf/ni).iloc[-1]:.2f} | **负债**: {debt_ratio.iloc[-1]:.1f}%")

        st.divider()

        # --- 3. 详细图表 (增加内部标题) ---
        st.header("1️⃣ 营收规模与利润空间")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营收", text=[f"{v/1e8:.1f}亿" for v in rev], textposition='auto'), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", mode='lines+markers+text', text=[f"{v:.1f}%" for v in growth], textposition="top center"), secondary_y=True)
        f1.update_layout(title={'text': "营收规模与年度增长趋势", 'x': 0.5, 'xanchor': 'center'})
        st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 核心回报：ROE 杜邦三因子拆解")
        rc1, rc2, rc3 = st.columns(3)
        with rc1: st_plotly_line(years, (ni/rev*100).fillna(0), "因子1：净利率 (%)", "%", "#FF4B4B")
        with rc2: st_plotly_line(years, (rev/assets).fillna(0), "因子2：资产周转率 (次)", "次", "#0083B8")
        with rc3: st_plotly_line(years, (assets/equity).fillna(0), "因子3：权益乘数 (杠杆)", "倍", "#2E7D32")

        st.header("3️⃣ 经营效率与营运资本")
        c31, c32 = st.columns(2)
        with c31: 
            c2c = ((get_any(bs_df,['Net Receivables'])/rev*365)+(get_any(bs_df,['Inventory'])/rev*365)-(get_any(bs_df,['Accounts Payable'])/rev*365)).fillna(0)
            st_plotly_bar(years, c2c, "C2C 现金周期 (天)", "#7D3C98")
        with c32:
            owc = (ca-cash)-(cl-get_any(bs_df,['Short Term Debt'])).fillna(0)
            st_plotly_bar(years, owc, "营运资本 OWC", "#F39C12")

        st.header("4️⃣ 利润质量与股东回报")
        f4 = go.Figure()
        f4.add_trace(go.Bar(x=years, y=ni, name="净利润", text=[f"{v/1e8:.1f}亿" for v in ni], textposition='auto'))
        f4.add_trace(go.Bar(x=years, y=ocf, name="经营现金流", text=[f"{v/1e8:.1f}亿" for v in ocf], textposition='auto'))
        f4.add_trace(go.Bar(x=years, y=div, name="现金分红", text=[f"{v/1e8:.1f}亿" if v!=0 else "" for v in div], textposition='auto'))
        f4.update_layout(title={'text': "利润 vs 现金流 vs 分红", 'x': 0.5, 'xanchor': 'center'}, barmode='group')
        st.plotly_chart(f4, use_container_width=True)

        st.header("5️⃣ 财务安全性评估")
        sc1, sc2, sc3 = st.columns(3)
        with sc1: st_plotly_line(years, debt_ratio, "指标1：资产负债率 (%)", "%", "#E67E22")
        with sc2: st_plotly_line(years, curr_ratio_pct, "指标2：流动覆盖率 (%)", "%", "#3498DB")
        with sc3: st_plotly_line(years, int_cover, "指标3：利息保障倍数 (次)", "次", "#27AE60")

    except Exception as e:
        st.error(f"分析引擎发生错误: {e}")

if st.sidebar.button("启动全量诊断"):
    run_v69_engine(symbol, time_frame == "年度趋势 (Annual)")
