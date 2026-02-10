import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V33", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 数据维度设置")
time_frame = st.sidebar.radio("选择分析维度：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])
st.sidebar.divider()

examples = {
    "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "英伟达 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA"
}
selected_example = st.sidebar.selectbox("快速选择知名企业：", list(examples.keys()))
symbol = st.sidebar.text_input("或手动输入代码：", examples[selected_example]).upper()

# --- 核心辅助函数 ---
def get_item_safe(df, keys):
    if df is None or df.empty: return pd.Series([0.0])
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

# --- 主分析引擎 ---
def run_v33_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        
        # 1. 获取原始数据并截取最近8期
        if is_annual:
            is_raw = stock.income_stmt.sort_index(axis=1, ascending=True).iloc[:, -8:]
            cf_raw = stock.cashflow.sort_index(axis=1, ascending=True).iloc[:, -8:]
            bs_raw = stock.balance_sheet.sort_index(axis=1, ascending=True).iloc[:, -8:]
        else:
            is_raw = stock.quarterly_income_stmt.sort_index(axis=1, ascending=True).iloc[:, -8:]
            cf_raw = stock.quarterly_cashflow.sort_index(axis=1, ascending=True).iloc[:, -8:]
            bs_raw = stock.quarterly_balance_sheet.sort_index(axis=1, ascending=True).iloc[:, -8:]

        if is_raw.empty:
            st.error("数据调取失败。")
            return

        # 🔥 强制日期字符串化，解决进位问题
        years_label = [d.strftime('%Y-%m') for d in is_raw.columns]
        
        # 统一所有 DataFrame 的列标签，确保后续计算索引对齐
        is_stmt = is_raw.copy(); is_stmt.columns = years_label
        cf_stmt = cf_raw.copy(); cf_stmt.columns = years_label
        bs_stmt = bs_raw.copy(); bs_stmt.columns = years_label
        
        last_report = years_label[-1]
        info = stock.info

        st.title(f"🏛️ 财务全图谱 V33：{info.get('longName', ticker)}")
        st.caption(f"维度：{time_frame} | 报告期截止：{last_report}")
        st.divider()

        # --- 全量指标预计算 (确保所有 key 覆盖) ---
        rev = get_item_safe(is_stmt, ['Total Revenue', 'Revenue'])
        ni = get_item_safe(is_stmt, ['Net Income'])
        gp = get_item_safe(is_stmt, ['Gross Profit'])
        op_inc = get_item_safe(is_stmt, ['Operating Income'])
        equity = get_item_safe(bs_stmt, ['Stockholders Equity', 'Total Equity'])
        assets = get_item_safe(bs_stmt, ['Total Assets'])
        ocf = get_item_safe(cf_stmt, ['Operating Cash Flow'])
        
        # 资产负债细节
        ca = get_item_safe(bs_stmt, ['Total Current Assets', 'Current Assets'])
        cl = get_item_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
        ar = get_item_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inv = get_item_safe(bs_stmt, ['Inventory'])
        ap = get_item_safe(bs_stmt, ['Accounts Payable'])
        cash = get_item_safe(bs_stmt, ['Cash And Cash Equivalents'])
        st_debt = get_item_safe(bs_stmt, ['Short Term Debt', 'Current Debt'])
        liab = get_item_safe(bs_stmt, ['Total Liabilities'])
        
        # 利息与分红
        interest = get_item_safe(is_stmt, ['Interest Expense']).abs()
        div = get_item_safe(cf_stmt, ['Cash Dividends Paid']).abs()
        capex = get_item_safe(cf_stmt, ['Capital Expenditure']).abs()

        # 比例计算
        roe = (ni / equity) * 100
        curr_ratio = ca / cl
        c2c = ((ar/rev)*365) + ((inv/rev)*365) - ((ap/rev)*365)
        growth = rev.pct_change()
        cash_q = ocf / ni

        # --- 评分模块 ---
        score = 0
        if roe.iloc[-1] > 15: score += 2
        if cash_q.iloc[-1] > 1: score += 2
        if curr_ratio.iloc[-1] > 1.2: score += 2
        if c2c.iloc[-1] < 60: score += 2
        if (growth.iloc[-1] > 0.1 if is_annual else growth.iloc[-1] > 0.03): score += 2

        col_score, col_details = st.columns([1, 2])
        with col_score:
            color = "#2E7D32" if score >= 8 else "#FFA000" if score >= 6 else "#D32F2F"
            st.markdown(f'''<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;">
                <h1 style="font-size:80px; color:{color}; margin:0;">{score}</h1>
                <p style="color:{color}; font-weight:bold;">截止期: {last_report}</p></div>''', unsafe_allow_html=True)
        with col_details:
            st.subheader("📊 核心体检项")
            st.write(f"盈利指标 (ROE): {roe.iloc[-1]:.2f}%")
            st.write(f"现金含量 (OCF/NI): {cash_q.iloc[-1]:.2f}")
            st.write(f"负债水平 (资产负债率): {(liab/assets).iloc[-1]*100:.1f}%")

        st.divider()

        # --- 1. 营收与利润 ---
        st.header("1️⃣ 营收规模与利润空间")
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=years_label, y=rev, name="营收"), secondary_y=False)
        fig1.add_trace(go.Scatter(x=years_label, y=growth*100, name="增速%"), secondary_y=True)
        fig1.update_xaxes(type='category')
        st.plotly_chart(fig1, use_container_width=True)

        # --- 2. 杜邦动因分析 ---
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=years_label, y=(ni/rev)*100, name="净利率%"))
        fig2.add_trace(go.Scatter(x=years_label, y=(rev/assets)*10, name="资产周转率x10"))
        fig2.add_trace(go.Scatter(x=years_label, y=assets/equity, name="权益乘数"))
        fig2.update_xaxes(type='category')
        st.plotly_chart(fig2, use_container_width=True)

        # --- 3. ROIC & C2C (修复索引) ---
        st.header("3️⃣ 核心经营效率 (ROIC & C2C)")
        debt_val = get_item_safe(bs_stmt, ['Total Debt'])
        # ROIC = (EBIT * (1-tax)) / (Equity + Debt)
        roic = (op_inc * 0.75) / (equity + debt_val) * 100
        c3_1, c3_2 = st.columns(2)
        with c3_1: 
            st.write("**ROIC % (投入资本回报率)**")
            st.line_chart(pd.Series(roic.values, index=years_label))
        with c3_2: 
            st.write("**C2C 现金周期 (天)**")
            st.bar_chart(pd.Series(c2c.values, index=years_label))

        # --- 4. OWC 营运资本 ---
        st.header("4️⃣ 营运资产管理 (OWC)")
        owc = (ca - cash) - (cl - st_debt)
        fig4 = make_subplots(specs=[[{"secondary_y": True}]])
        fig4.add_trace(go.Bar(x=years_label, y=owc, name="OWC总量"), secondary_y=False)
        fig4.add_trace(go.Scatter(x=years_label, y=owc.diff(), name="ΔOWC变动"), secondary_y=True)
        fig4.update_xaxes(type='category')
        st.plotly_chart(fig4, use_container_width=True)

        # --- 5. 现金流与分红 ---
        st.header("5️⃣ 现金流质量与股东回报")
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
        fig5.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
        fig5.add_trace(go.Bar(x=years_label, y=div, name="分红金额", opacity=0.3))
        fig5.update_xaxes(type='category')
        st.plotly_chart(fig5, use_container_width=True)

        # --- 6. 财务安全性 (全面修复利息与负债率) ---
        st.header("6️⃣ 财务安全性评估 (负债率 & 利息倍数)")
        debt_ratio = (liab / assets) * 100
        # 避免利息支出为0导致的无穷大显示，做个clip
        interest_cover = (op_inc / interest.replace(0, 0.001)).clip(-100, 100)
        
        c6_1, c6_2, c6_3 = st.columns(3)
        with c6_1:
            st.write("**资产负债率 %**")
            st.line_chart(pd.Series(debt_ratio.values, index=years_label))
        with c6_2:
            st.write("**流动比率**")
            st.line_chart(pd.Series(curr_ratio.values, index=years_label))
        with c6_3:
            st.write("**利息保障倍数**")
            st.line_chart(pd.Series(interest_cover.values, index=years_label))

    except Exception as e:
        st.error(f"分析异常: {e}")

if st.sidebar.button("启动 V33 终极修正版"):
    run_v33_engine(symbol, time_frame == "年度趋势 (Annual)")
