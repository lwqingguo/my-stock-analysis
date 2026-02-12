import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V69.6", layout="wide")

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

def get_any(df, tags):
    if df is None or df.empty: return pd.Series([0.0] * 8)
    df.index = df.index.map(str).str.strip()
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty: return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

def run_v69_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty or bs_raw.empty:
            st.error("数据抓取失败，请检查。")
            return

        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        # --- 核心指标计算 ---
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
        
        # --- 1. 顶部：公司概况与商业模式 ---
        st.title(f"🏛️ 财务审计图谱 V69.6：{info.get('longName', ticker)}")
        
        with st.expander("🏢 查看公司主营业务与商业模式", expanded=True):
            c_info1, c_info2 = st.columns([1, 2])
            with c_info1:
                st.write(f"**行业领域**：{info.get('industryDisp', info.get('industry', '未知'))}")
                st.write(f"**板块分类**：{info.get('sectorDisp', info.get('sector', '未知'))}")
                st.write(f"**上市地点**：{info.get('exchange', '未知')}")
                st.write(f"**全职员工**：{info.get('fullTimeEmployees', 'N/A')}")
            with c_info2:
                st.write("**业务摘要**：")
                summary = info.get('longBusinessSummary', '暂无业务描述。')
                st.write(f"{summary[:500]}..." if len(summary) > 500 else summary)

        # --- 2. 智能打分系统 ---
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
                <p style="color:{color}; font-size:20px; font-weight:bold;">综合健康评分 (满分10)</p></div>''', unsafe_allow_html=True)
        with col_diag:
            st.subheader("📝 核心诊断总结")
            st.write(f"**1. 盈利能力**：ROE **{l_roe:.2f}%** ({'回报优秀' if l_roe > 15 else '回报率一般'})")
            st.write(f"**2. 现金含金量**：现金流/利润 **{l_cq:.2f}** ({'现金转化强' if l_cq > 1 else '利润成色一般'})")
            st.write(f"**3. 财务杠杆**：资产负债率 **{l_debt:.1f}%** ({'结构稳健' if l_debt < 50 else '负债率偏高'})")
            st.write(f"**4. 成长动能**：营收增速 **{l_growth:.1f}%** ({'扩张期' if l_growth > 10 else '增速放缓'})")
        
        st.divider()

        # --- 3. 后续图表展示 (保持之前的并列结构) ---
        # 营收
        st.header("1️⃣ 营收规模与利润空间")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", line=dict(color='red')), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        # ROE 杜邦
        st.header("2️⃣ 核心回报：ROE 杜邦三因子拆解")
        
        rc1, rc2, rc3 = st.columns(3)
        with rc1: st.write("**净利率 (%)**"); st.line_chart((ni/rev*100).fillna(0))
        with rc2: st.write("**资产周转率 (次)**"); st.line_chart((rev/assets).fillna(0))
        with rc3: st.write("**权益乘数 (杠杆)**"); st.line_chart((assets/equity).fillna(0))

        # 效率
        st.header("3️⃣ 经营效率与营运资本")
        c31, c32 = st.columns(2)
        with c31: st.write("**C2C 周期 (天)**"); st.bar_chart(((get_any(bs_df,['Net Receivables'])/rev*365)+(get_any(bs_df,['Inventory'])/rev*365)-(get_any(bs_df,['Accounts Payable'])/rev*365)).fillna(0))
        with c32: st.write("**营运资本 OWC**"); st.bar_chart((ca-cash)-(cl-get_any(bs_df,['Short Term Debt'])).fillna(0))

        # 现金流
        st.header("4️⃣ 利润质量与股东回报")
        f4 = go.Figure()
        f4.add_trace(go.Bar(x=years, y=ni, name="净利润"))
        f4.add_trace(go.Bar(x=years, y=ocf, name="经营现金流"))
        f4.add_trace(go.Bar(x=years, y=div, name="分红", opacity=0.5))
        f4.update_layout(barmode='group'); st.plotly_chart(f4, use_container_width=True)

        # 安全
        st.header("5️⃣ 财务安全性评估")
        sc1, sc2, sc3 = st.columns(3)
        with sc1: st.write("**资产负债率 (%)**"); st.line_chart(debt_ratio)
        with sc2: st.write("**流动覆盖率 (%)**"); st.line_chart(curr_ratio_pct)
        with sc3: st.write("**利息保障倍数 (次)**"); st.line_chart(int_cover)

    except Exception as e:
        st.error(f"分析引擎发生错误: {e}")

if st.sidebar.button("启动诊断"):
    run_v69_engine(symbol, time_frame == "年度趋势 (Annual)")
