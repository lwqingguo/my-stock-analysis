import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V35", layout="wide")

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

def run_v35_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        
        # 抓取原始数据
        if is_annual:
            is_stmt = stock.income_stmt.sort_index(axis=1, ascending=True).iloc[:, -8:]
            cf_stmt = stock.cashflow.sort_index(axis=1, ascending=True).iloc[:, -8:]
            bs_stmt = stock.balance_sheet.sort_index(axis=1, ascending=True).iloc[:, -8:]
        else:
            is_stmt = stock.quarterly_income_stmt.sort_index(axis=1, ascending=True).iloc[:, -8:]
            cf_stmt = stock.quarterly_cashflow.sort_index(axis=1, ascending=True).iloc[:, -8:]
            bs_stmt = stock.quarterly_balance_sheet.sort_index(axis=1, ascending=True).iloc[:, -8:]

        if is_stmt.empty:
            st.error("数据调取失败。")
            return

        # 强制日期字符串化，解决进位问题
        years_label = [d.strftime('%Y-%m') for d in is_stmt.columns]
        is_stmt.columns = years_label
        cf_stmt.columns = years_label
        bs_stmt.columns = years_label
        
        last_report = years_label[-1]
        info = stock.info

        st.title(f"🏛️ 财务全图谱 V35：{info.get('longName', ticker)}")
        st.caption(f"维度：{time_frame} | 报告期截止：{last_report}")
        st.divider()

        # --- 全量指标预计算 ---
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

        # 核心比例（加入填充，防止 NaN 崩溃）
        roe = (ni / equity * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0)
        c2c = (((ar/rev)*365).fillna(0) + ((inv/rev)*365).fillna(0) - ((ap/rev)*365).fillna(0))
        growth = rev.pct_change().fillna(0)
        cash_q = (ocf / ni).replace([np.inf, -np.inf], 0).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        
        # 关键：利息倍数防崩处理
        interest_cover = (op_inc / interest.replace(0, 0.001)).replace([np.inf, -np.inf], 0).clip(-100, 100).fillna(0)
        debt_val = get_item_safe(bs_stmt, ['Total Debt'])
        roic = ((op_inc * 0.75) / (equity + debt_val) * 100).fillna(0)

        # --- 1. 营收与利润 ---
        st.header("1️⃣ 营收规模与利润空间")
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=years_label, y=rev, name="营收总量"), secondary_y=False)
        fig1.add_trace(go.Scatter(x=years_label, y=growth*100, name="营收增速%"), secondary_y=True)
        fig1.update_xaxes(type='category')
        st.plotly_chart(fig1, use_container_width=True)

        # --- 2. 杜邦动因 (全量保留) ---
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=years_label, y=(ni/rev*100).fillna(0), name="销售净利率%"))
        fig2.add_trace(go.Scatter(x=years_label, y=(rev/assets*10).fillna(0), name="资产周转率x10"))
        fig2.add_trace(go.Scatter(x=years_label, y=(assets/equity).fillna(0), name="权益乘数"))
        fig2.update_xaxes(type='category')
        st.plotly_chart(fig2, use_container_width=True)

        # --- 3. ROIC & C2C (全量保留) ---
        st.header("3️⃣ 核心经营效率")
        c3_1, c3_2 = st.columns(2)
        with c3_1:
            fig3_1 = go.Figure(go.Scatter(x=years_label, y=roic, name="ROIC%", line=dict(color='green', width=3)))
            fig3_1.update_layout(title="ROIC %", xaxis_type='category')
            st.plotly_chart(fig3_1, use_container_width=True)
        with c3_2:
            fig3_2 = go.Figure(go.Bar(x=years_label, y=c2c, name="C2C天数", marker_color='orange'))
            fig3_2.update_layout(title="C2C 现金周期 (天)", xaxis_type='category')
            st.plotly_chart(fig3_2, use_container_width=True)

        # --- 4. OWC (全量保留) ---
        st.header("4️⃣ 营运资产管理 (OWC)")
        owc = (ca - cash) - (cl - st_debt)
        fig4 = go.Figure(go.Bar(x=years_label, y=owc, name="OWC总量"))
        fig4.update_xaxes(type='category')
        st.plotly_chart(fig4, use_container_width=True)

        # --- 5. 现金流与分红 (全量保留) ---
        st.header("5️⃣ 现金流质量与股东回报")
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
        fig5.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
        fig5.add_trace(go.Bar(x=years_label, y=div, name="现金分红金额", opacity=0.4))
        fig5.update_xaxes(type='category')
        st.plotly_chart(fig5, use_container_width=True)

        # --- 6. 财务安全性 (🔥 彻底修复区) ---
        st.header("6️⃣ 财务安全性评估")
        c6_1, c6_2, c6_3 = st.columns(3)
        with c6_1:
            fig6_1 = go.Figure(go.Scatter(x=years_label, y=debt_ratio, name="负债率", line=dict(color='red')))
            fig6_1.update_layout(title="资产负债率 %", xaxis_type='category')
            st.plotly_chart(fig6_1, use_container_width=True)
        with c6_2:
            fig6_2 = go.Figure(go.Scatter(x=years_label, y=curr_ratio, name="流动比", line=dict(color='blue')))
            fig6_2.update_layout(title="流动比率", xaxis_type='category')
            st.plotly_chart(fig6_2, use_container_width=True)
        with c6_3:
            fig6_3 = go.Figure(go.Scatter(x=years_label, y=interest_cover, name="利息倍数", line=dict(color='purple')))
            fig6_3.update_layout(title="利息保障倍数", xaxis_type='category')
            st.plotly_chart(fig6_3, use_container_width=True)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("启动 V35 最终版引擎"):
    run_v33_engine(symbol, time_frame == "年度趋势 (Annual)") # 修正调用名
