import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V36", layout="wide")

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

def get_item_safe(df, keys):
    if df is None or df.empty: return pd.Series([0.0])
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

# --- 主引擎 V36 ---
def run_v36_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        
        # 数据调取
        if is_annual:
            is_stmt = stock.income_stmt.sort_index(axis=1, ascending=True).iloc[:, -8:]
            cf_stmt = stock.cashflow.sort_index(axis=1, ascending=True).iloc[:, -8:]
            bs_stmt = stock.balance_sheet.sort_index(axis=1, ascending=True).iloc[:, -8:]
        else:
            is_stmt = stock.quarterly_income_stmt.sort_index(axis=1, ascending=True).iloc[:, -8:]
            cf_stmt = stock.quarterly_cashflow.sort_index(axis=1, ascending=True).iloc[:, -8:]
            bs_stmt = stock.quarterly_balance_sheet.sort_index(axis=1, ascending=True).iloc[:, -8:]

        if is_stmt.empty:
            st.error("数据调取失败，请检查网络或代码。")
            return

        # 日期字符串化锁定
        years_label = [d.strftime('%Y-%m') for d in is_stmt.columns]
        is_stmt.columns = years_label
        cf_stmt.columns = years_label
        bs_stmt.columns = years_label
        
        st.title(f"🏛️ 财务全图谱 V36：{stock.info.get('longName', ticker)}")
        st.divider()

        # --- 核心指标计算（全量不删减） ---
        rev = get_item_safe(is_stmt, ['Total Revenue', 'Revenue'])
        ni = get_item_safe(is_stmt, ['Net Income'])
        gp = get_item_safe(is_stmt, ['Gross Profit'])
        op_inc = get_item_safe(is_stmt, ['Operating Income'])
        equity = get_item_safe(bs_stmt, ['Stockholders Equity', 'Total Equity'])
        assets = get_item_safe(bs_stmt, ['Total Assets'])
        ocf = get_item_safe(cf_stmt, ['Operating Cash Flow'])
        ca = get_item_safe(bs_stmt, ['Total Current Assets', 'Current Assets'])
        cl = get_item_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
        ar = get_item_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inv = get_item_safe(bs_stmt, ['Inventory'])
        ap = get_item_safe(bs_stmt, ['Accounts Payable'])
        cash = get_item_safe(bs_stmt, ['Cash And Cash Equivalents'])
        st_debt = get_item_safe(bs_stmt, ['Short Term Debt', 'Current Debt'])
        liab = get_item_safe(bs_stmt, ['Total Liabilities'])
        interest = get_item_safe(is_stmt, ['Interest Expense']).abs()
        div = get_item_safe(cf_stmt, ['Cash Dividends Paid']).abs()
        capex = get_item_safe(cf_stmt, ['Capital Expenditure']).abs()

        # 核心比例计算并强制转为 Float 格式
        def to_f(series): return pd.to_numeric(series, errors='coerce').fillna(0)

        roe = to_f(ni / equity * 100)
        curr_ratio = to_f(ca / cl)
        c2c = to_f(((ar/rev)*365) + ((inv/rev)*365) - ((ap/rev)*365))
        growth = to_f(rev.pct_change() * 100)
        cash_q = to_f(ocf / ni).replace([np.inf, -np.inf], 0)
        debt_ratio = to_f(liab / assets * 100)
        interest_cover = to_f(op_inc / interest.replace(0, 0.001)).clip(-50, 50)
        debt_val = get_item_safe(bs_stmt, ['Total Debt'])
        roic = to_f((op_inc * 0.75) / (equity + debt_val) * 100)

        # --- 绘图区（全量指标，Plotly 强制渲染） ---
        
        # 1. 营收与增长
        st.header("1️⃣ 营收规模与利润空间")
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=years_label, y=rev, name="营收"), secondary_y=False)
        fig1.add_trace(go.Scatter(x=years_label, y=growth, name="增速%"), secondary_y=True)
        fig1.update_xaxes(type='category')
        st.plotly_chart(fig1, use_container_width=True)

        # 2. 杜邦动因
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=years_label, y=to_f(ni/rev*100), name="净利率%"))
        fig2.add_trace(go.Scatter(x=years_label, y=to_f(rev/assets*10), name="周转率x10"))
        fig2.add_trace(go.Scatter(x=years_label, y=to_f(assets/equity), name="权益乘数"))
        fig2.update_xaxes(type='category')
        st.plotly_chart(fig2, use_container_width=True)

        # 3. ROIC & C2C
        st.header("3️⃣ 核心经营效率")
        c31, c32 = st.columns(2)
        with c31:
            f31 = go.Figure(go.Scatter(x=years_label, y=roic, name="ROIC%"))
            f31.update_layout(title="ROIC %", xaxis_type='category')
            st.plotly_chart(f31, use_container_width=True)
        with c32:
            f32 = go.Figure(go.Bar(x=years_label, y=c2c, name="C2C天数"))
            f32.update_layout(title="C2C 现金周期", xaxis_type='category')
            st.plotly_chart(f32, use_container_width=True)

        # 4. OWC
        st.header("4️⃣ 营运资产管理 (OWC)")
        owc = to_f((ca - cash) - (cl - st_debt))
        fig4 = go.Figure(go.Bar(x=years_label, y=owc))
        fig4.update_xaxes(type='category')
        st.plotly_chart(fig4, use_container_width=True)

        # 5. 现金流
        st.header("5️⃣ 现金流质量与分红")
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
        fig5.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
        fig5.add_trace(go.Bar(x=years_label, y=div, name="分红金额", opacity=0.4))
        fig5.update_xaxes(type='category')
        st.plotly_chart(fig5, use_container_width=True)

        # 6. 财务安全（重点修复）
        st.header("6️⃣ 财务安全性评估")
        c61, c62, c63 = st.columns(3)
        with c61:
            f61 = go.Figure(go.Scatter(x=years_label, y=debt_ratio, name="负债率"))
            f61.update_layout(title="资产负债率 %", xaxis_type='category')
            st.plotly_chart(f61, use_container_width=True)
        with c62:
            f62 = go.Figure(go.Scatter(x=years_label, y=curr_ratio, name="流动比"))
            f62.update_layout(title="流动比率", xaxis_type='category')
            st.plotly_chart(f62, use_container_width=True)
        with c63:
            f63 = go.Figure(go.Scatter(x=years_label, y=interest_cover, name="利息倍数"))
            f63.update_layout(title="利息保障倍数", xaxis_type='category')
            st.plotly_chart(f63, use_container_width=True)

    except Exception as e:
        st.error(f"分析失败: {e}")

# 🔥 这里一定不能写错，调用最新的 V36 函数
if st.sidebar.button("启动 V36 终极引擎"):
    run_v36_engine(symbol, time_frame == "年度趋势 (Annual)")
