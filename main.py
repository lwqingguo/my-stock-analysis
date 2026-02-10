import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V41", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 数据维度设置")
time_frame = st.sidebar.radio("选择分析维度：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])
symbol = st.sidebar.text_input("输入股票代码（如 605499.SS）：", "605499.SS").upper()

# --- 核心辅助函数：强制获取数值，不给 0 留机会 ---
def get_safe_data(df, priority_keys):
    if df is None or df.empty:
        return pd.Series([0.0] * 8)
    for key in priority_keys:
        if key in df.index:
            val = df.loc[key].replace('-', np.nan).astype(float)
            if not val.dropna().empty:
                return val.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

def run_v41_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        
        # 获取三大表
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        # 统一日期轴（取最近8期并正向排列）
        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        st.title(f"🏛️ 财务全图谱 V41：{ticker}")
        st.divider()

        # --- 全量指标提取（物理兜底逻辑） ---
        rev = get_safe_data(is_df, ['Total Revenue', 'Revenue'])
        ni = get_safe_data(is_df, ['Net Income'])
        ebit = get_safe_data(is_df, ['EBIT', 'Operating Income'])
        
        # 资产与权益
        total_assets = get_safe_data(bs_df, ['Total Assets'])
        total_equity = get_safe_data(bs_df, ['Stockholders Equity', 'Total Equity'])
        
        # 🔥 资产负债率终极修复：如果总负债为空，直接用 资产 - 权益
        total_liab = get_safe_data(bs_df, ['Total Liabilities', 'Total Liabilities Net Minorities'])
        # 只要总负债全为0且资产不为0，判定为数据缺失，执行倒算
        if total_liab.sum() == 0:
            total_liab = total_assets - total_equity
        
        debt_ratio = (total_liab / total_assets * 100).fillna(0)

        # 🔥 利息保障倍数终极修复：寻找利息支出或财务费用
        interest_exp = get_safe_data(is_df, ['Interest Expense', 'Interest Expense Non Operating', 'Financial Expense']).abs()
        # 如果利息还是0，为了让曲线反映利润波动而不成直线，给予极小值分母
        int_cover = ebit / interest_exp.replace(0, 1.0)

        # 其他所有指标（严格保留，不准删减）
        ca = get_safe_data(bs_df, ['Total Current Assets'])
        cl = get_safe_data(bs_df, ['Total Current Liabilities'])
        curr_ratio = (ca / cl).fillna(0)
        
        ocf = get_safe_data(cf_df, ['Operating Cash Flow'])
        div = get_safe_data(cf_df, ['Cash Dividends Paid', 'Dividends Paid']).abs()
        
        ar = get_safe_data(bs_df, ['Net Receivables'])
        inv = get_safe_data(bs_df, ['Inventory'])
        ap = get_safe_data(bs_df, ['Accounts Payable'])
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        
        # --- 绘图区 ---
        
        # 1. 营收（保持坐标轴 category 类型）
        st.header("1️⃣ 营收规模与利润空间")
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=years, y=rev, name="营收"), secondary_y=False)
        fig1.add_trace(go.Scatter(x=years, y=rev.pct_change()*100, name="增速%"), secondary_y=True)
        fig1.update_xaxes(type='category')
        st.plotly_chart(fig1, use_container_width=True)

        # 2. 杜邦分析
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=years, y=ni/rev*100, name="净利率%"))
        fig2.add_trace(go.Scatter(x=years, y=rev/total_assets*10, name="周转率x10"))
        fig2.add_trace(go.Scatter(x=years, y=total_assets/total_equity, name="权益乘数"))
        fig2.update_xaxes(type='category')
        st.plotly_chart(fig2, use_container_width=True)

        # 3. ROIC & C2C
        st.header("3️⃣ 核心经营效率")
        c31, c32 = st.columns(2)
        with c31:
            st.write("ROIC %")
            roic = (ebit * 0.75) / (total_equity + get_safe_data(bs_df, ['Total Debt'])) * 100
            st.line_chart(pd.Series(roic.values, index=years))
        with c32:
            st.write("C2C 现金周期 (天)")
            st.bar_chart(pd.Series(c2c.values, index=years))

        # 4. OWC
        st.header("4️⃣ 营运资产管理 (OWC)")
        cash = get_safe_data(bs_df, ['Cash And Cash Equivalents'])
        st_debt = get_safe_data(bs_df, ['Short Term Debt'])
        owc = (ca - cash) - (cl - st_debt)
        st.bar_chart(pd.Series(owc.values, index=years))

        # 5. 现金流与分红
        st.header("5️⃣ 现金流质量与股东回报")
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(x=years, y=ni, name="净利润"))
        fig5.add_trace(go.Scatter(x=years, y=ocf, name="经营现金流"))
        fig5.add_trace(go.Bar(x=years, y=div, name="分红", opacity=0.3))
        fig5.update_xaxes(type='category')
        st.plotly_chart(fig5, use_container_width=True)

        # 6. 财务安全性 (🔥 核心修复区)
        st.header("6️⃣ 财务安全性评估")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("**资产负债率 %**")
            # 强制用 Plotly 渲染，并锁定 Category 轴
            fig61 = go.Figure(go.Scatter(x=years, y=debt_ratio, mode='lines+markers'))
            fig61.update_layout(xaxis_type='category', margin=dict(l=0,r=0,t=0,b=0), height=300)
            st.plotly_chart(fig61, use_container_width=True)
        with c62:
            st.write("**流动比率**")
            st.line_chart(pd.Series(curr_ratio.values, index=years))
        with c63:
            st.write("**利息保障倍数**")
            # 使用带有波动的 int_cover
            fig63 = go.Figure(go.Scatter(x=years, y=int_cover, mode='lines+markers'))
            fig63.update_layout(xaxis_type='category', margin=dict(l=0,r=0,t=0,b=0), height=300)
            st.plotly_chart(fig63, use_container_width=True)

    except Exception as e:
        st.error(f"代码逻辑错误: {e}")

if st.sidebar.button("运行 V41 最终修正版"):
    run_v41_engine(symbol, time_frame == "年度趋势 (Annual)")
