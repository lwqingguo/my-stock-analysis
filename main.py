import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V70.0", layout="wide")

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

# --- 辅助函数：普通图表 ---
def st_plotly_line(x, y, name, unit="", color=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, name=name,
        mode='lines+markers+text',
        text=[f"{v:.2f}{unit}" for v in y],
        textposition="top center",
        line=dict(color=color, width=3)
    ))
    fig.update_layout(title={'text': name, 'x': 0.5, 'xanchor': 'center'}, height=300, margin=dict(l=10, r=10, t=50, b=10), xaxis_type='category')
    st.plotly_chart(fig, use_container_width=True)

# --- 核心改进：千分位符渲染器 (OWC 专用) ---
def st_plotly_bar_comma(x, y, name, color=None):
    fig = go.Figure()
    # 生成千分位标签，不带小数位
    comma_text = [f"{v:,.0f}" for v in y]
    
    fig.add_trace(go.Bar(
        x=x, y=y, name=name,
        text=comma_text,
        textposition='outside',
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
def run_v70_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty or bs_raw.empty:
            st.error("无法获取财务报表数据。")
            return

        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        # --- 指标提取 ---
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

        # 计算
        calc_df = pd.DataFrame({'ca': ca, 'cl': cl, 'rev': rev, 'ni': ni, 'assets': assets, 'equity': equity, 'cash': cash}).fillna(0)
        growth = calc_df['rev'].pct_change().fillna(0) * 100
        roe = (calc_df['ni'] / calc_df['equity'] * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio_pct = (calc_df['ca'] / calc_df['cl'].replace(0, np.nan) * 100).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)

        # --- 1. 顶部：公司业务与模式 ---
        st.title(f"🏛️ 财务审计图谱 V70.0：{info.get('longName', ticker)}")
        with st.expander("🏢 查看公司主营业务与商业模式", expanded=True):
            st.write(f"**行业**：{info.get('industry', '未知')} | **全职员工**：{info.get('fullTimeEmployees', 'N/A')}")
            st.write(f"**业务摘要**：{info.get('longBusinessSummary', '暂无描述')[:800]}...")

        # --- 2. 完整评分与诊断总结 (恢复并增强) ---
        score = 0
        l_roe, l_cq, l_debt, l_growth = roe.iloc[-1], (ocf.iloc[-1]/ni.iloc[-1] if ni.iloc[-1]!=0 else 0), debt_ratio.iloc[-1], growth.iloc[-1]
        if l_roe > 15: score += 2.5
        if l_cq > 1: score += 2.5
        if l_debt < 50: score += 2.5
        if l_growth > 10: score += 2.5

        col_score, col_diag = st.columns([1, 2])
        with col_score:
            color = "#2E7D32" if score >= 7.5 else "#FFA000" if score >= 5 else "#D32F2F"
            st.markdown(f'''<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;">
                <h1 style="font-size:80px; color:{color}; margin:0;">{score:g}</h1>
                <p style="color:{color}; font-size:20px; font-weight:bold;">综合健康评分 (10分制)</p></div>''', unsafe_allow_html=True)
        with col_diag:
            st.subheader("📝 核心财务诊断总结")
            st.write(f"✅ **盈利能力**：最新 ROE 为 **{l_roe:.2f}%** ({'回报优秀' if l_roe > 15 else '回报率一般'})")
            st.write(f"✅ **现金质量**：净现比为 **{l_cq:.2f}** ({'现金转化极强' if l_cq > 1 else '利润成色需关注'})")
            st.write(f"✅ **财务杠杆**：资产负债率为 **{l_debt:.1f}%** ({'财务结构稳健' if l_debt < 50 else '杠杆偏高'})")
            st.write(f"✅ **成长动能**：营收增速为 **{l_growth:.1f}%** ({'处于扩张期' if l_growth > 10 else '增速有所放缓'})")
        
        st.divider()

        # --- 3. 详细图表板块 ---
        st.header("1️⃣ 营收规模与利润空间")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营收", text=[f"{v/1e8:,.0f}亿" for v in rev], textposition='auto'), secondary_y=False)
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
            st_plotly_bar_comma(years, c2c, "C2C 现金周期 (天)", "#7D3C98")
        with c32:
            owc = (ca-cash)-(cl-get_any(bs_df,['Short Term Debt'])).fillna(0)
            # 这里的数字标签会带千分位符且无小数
            st_plotly_bar_comma(years, owc, "营运资本 OWC (千分位展示)", "#F39C12")

        st.header("4️⃣ 利润质量与股东回报")
        f4 = go.Figure()
        f4.add_trace(go.Bar(x=years, y=ni, name="净利润", text=[f"{v/1e8:,.0f}亿" for v in ni], textposition='auto'))
        f4.add_trace(go.Bar(x=years, y=ocf, name="经营现金流", text=[f"{v/1e8:,.0f}亿" for v in ocf], textposition='auto'))
        f4.add_trace(go.Bar(x=years, y=div, name="现金分红", text=[f"{v/1e8:,.0f}亿" if v!=0 else "" for v in div], textposition='auto'))
        f4.update_layout(title={'text': "利润 vs 现金流 vs 分红", 'x': 0.5, 'xanchor': 'center'}, barmode='group')
        st.plotly_chart(f4, use_container_width=True)

        st.header("5️⃣ 财务安全性评估")
        sc1, sc2, sc3 = st.columns(3)
        with sc1: st_plotly_line(years, debt_ratio, "指标1：资产负债率 (%)", "%", "#E67E22")
        with sc2: st_plotly_line(years, curr_ratio_pct, "指标2：流动覆盖率 (%)", "%", "#3498DB")
        with sc3: st_plotly_line(years, int_cover, "指标3：利息保障倍数 (次)", "次", "#27AE60")

    except Exception as e:
        st.error(f"分析引擎发生错误: {e}")

if st.sidebar.button("启动深度审计诊断"):
    run_v70_engine(symbol, time_frame == "年度趋势 (Annual)")
