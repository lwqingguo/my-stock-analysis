import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V39", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 数据维度设置")
time_frame = st.sidebar.radio("选择分析维度：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])

examples = {
    "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "英伟达 (NVDA)": "NVDA"
}
selected_example = st.sidebar.selectbox("快速选择：", list(examples.keys()))
symbol = st.sidebar.text_input("代码：", examples[selected_example]).upper()

# --- 核心数据抓取函数 ---
def get_item(df, keys):
    if df is None or df.empty: return pd.Series([0.0] * 8)
    for k in keys:
        if k in df.index:
            return df.loc[k].astype(float).fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v39_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        
        # 1. 获取报表
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow
        
        # 2. 统一截取最近8期并格式化坐标轴
        is_stmt = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_stmt = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_stmt = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        
        years_label = [d.strftime('%Y-%m') for d in is_stmt.columns]
        is_stmt.columns = bs_stmt.columns = cf_stmt.columns = years_label

        st.title(f"🏛️ 财务全图谱 V39：{ticker}")
        st.divider()

        # --- 全量指标提取（一个不删） ---
        rev = get_item(is_stmt, ['Total Revenue', 'Revenue'])
        ni = get_item(is_stmt, ['Net Income'])
        op_inc = get_item(is_stmt, ['Operating Income'])
        gp = get_item(is_stmt, ['Gross Profit'])
        
        assets = get_item(bs_stmt, ['Total Assets'])
        equity = get_item(bs_stmt, ['Stockholders Equity', 'Total Equity'])
        # 🔥 关键修复：如果 Total Liabilities 是 0，则用 资产 - 权益 补位
        liab_raw = get_item(bs_stmt, ['Total Liabilities', 'Total Liabilities Net Minorities'])
        liab = liab_raw.where(liab_raw != 0, assets - equity) 
        
        ca = get_item(bs_stmt, ['Total Current Assets', 'Current Assets'])
        cl = get_item(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
        cash = get_item(bs_stmt, ['Cash And Cash Equivalents'])
        st_debt = get_item(bs_stmt, ['Short Term Debt'])
        ar = get_item(bs_stmt, ['Net Receivables'])
        inv = get_item(bs_stmt, ['Inventory'])
        ap = get_item(bs_stmt, ['Accounts Payable'])
        
        ocf = get_item(cf_stmt, ['Operating Cash Flow'])
        div = get_item(cf_stmt, ['Cash Dividends Paid']).abs()
        capex = get_item(cf_stmt, ['Capital Expenditure']).abs()
        interest = get_item(is_stmt, ['Interest Expense']).abs()

        # --- 计算逻辑 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0)
        # 利息倍数补 1 规避除以 0
        int_cover = (op_inc / (interest + 1.0)).clip(-100, 100)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        debt_val = get_item(bs_stmt, ['Total Debt'])
        roic = ((op_inc * 0.75) / (equity + debt_val) * 100).fillna(0)
        owc = (ca - cash) - (cl - st_debt)

        # --- 绘图区（全指标严格展示） ---
        
        # 1. 营收与增长
        st.header("1️⃣ 营收规模与利润空间")
        f1 = make_subplots(specs=[[{"secondary_y": True}]]); f1.update_xaxes(type='category')
        f1.add_trace(go.Bar(x=years_label, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years_label, y=growth, name="增速%"), secondary_y=True)
        st.plotly_chart(f1, use_container_width=True)

        # 2. 杜邦分析
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        f2 = go.Figure(); f2.update_xaxes(type='category')
        f2.add_trace(go.Scatter(x=years_label, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=years_label, y=rev/assets*10, name="周转率x10"))
        f2.add_trace(go.Scatter(x=years_label, y=assets/equity, name="权益乘数"))
        st.plotly_chart(f2, use_container_width=True)

        # 3. ROIC & C2C
        st.header("3️⃣ 经营效率 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("ROIC %"); st.line_chart(pd.DataFrame(roic.values, index=years_label))
        with c32: st.write("C2C 周期 (天)"); st.bar_chart(pd.DataFrame(c2c.values, index=years_label))

        # 4. OWC
        st.header("4️⃣ 营运资产管理 (OWC)")
        f4 = go.Figure(go.Bar(x=years_label, y=owc)); f4.update_xaxes(type='category')
        st.plotly_chart(f4, use_container_width=True)

        # 5. 现金流
        st.header("5️⃣ 现金流质量与分红")
        f5 = go.Figure(); f5.update_xaxes(type='category')
        f5.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
        f5.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=years_label, y=div, name="分红", opacity=0.3))
        st.plotly_chart(f5, use_container_width=True)

        # 6. 财务安全（🔥 核心修复区）
        st.header("6️⃣ 财务安全性评估")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("**资产负债率 %**")
            f61 = go.Figure(go.Scatter(x=years_label, y=debt_ratio, mode='lines+markers+text', 
                                      text=[f"{x:.1f}%" for x in debt_ratio], textposition="top center"))
            f61.update_layout(xaxis_type='category', height=300); st.plotly_chart(f61, use_container_width=True)
        with c62:
            st.write("**流动比率**"); st.line_chart(pd.DataFrame(curr_ratio.values, index=years_label))
        with c63:
            st.write("**利息保障倍数**"); st.line_chart(pd.DataFrame(int_cover.values, index=years_label))

    except Exception as e:
        st.error(f"代码运行异常: {e}")

if st.sidebar.button("启动 V39 全量诊断"):
    run_v39_engine(symbol, time_frame == "年度趋势 (Annual)")
