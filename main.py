import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="研报级财务深度透视系统", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 数据控制台")
examples = {
    "手动输入": "",
    "英伟达 (NVDA)": "NVDA",
    "百事可乐 (PEP)": "PEP",
    "可口可乐 (KO)": "KO",
    "东鹏饮料 (605499.SS)": "605499.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "贵州茅台 (600519.SS)": "600519.SS"
}
selected_example = st.sidebar.selectbox("快速选择示例：", list(examples.keys()))
default_symbol = examples[selected_example] if examples[selected_example] else "NVDA"
symbol = st.sidebar.text_input("输入股票代码：", default_symbol).upper()

# --- 核心辅助函数 ---
def get_data_safe(df, keys):
    for k in keys:
        if k in df.index:
            return df.loc[k].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_working_capital_safe(bs_stmt):
    ca = get_data_safe(bs_stmt, ['Total Current Assets', 'Current Assets'])
    cl = get_data_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
    if ca.sum() == 0:
        ca = get_data_safe(bs_stmt, ['Cash And Cash Equivalents']) + \
             get_data_safe(bs_stmt, ['Net Receivables', 'Receivables']) + \
             get_data_safe(bs_stmt, ['Inventory'])
    if cl.sum() == 0:
        cl = get_data_safe(bs_stmt, ['Accounts Payable']) + get_data_safe(bs_stmt, ['Tax Liabilities'])
    return ca - cl

# --- 主分析函数 ---
def run_research_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        history = stock.history(period="10y")
        annual_price = history['Close'].resample('YE').last()
        annual_price.index = annual_price.index.year

        years = is_stmt.columns
        years_label = [str(y.year) if hasattr(y, 'year') else str(y) for y in years]

        st.title(f"🏛️ 全维度财务深度透视：{info.get('longName', ticker)}")
        st.divider()

        # --- 1. 估值水平 ---
        st.header("1️⃣ 估值水平 (Valuation)")
        eps = get_data_safe(is_stmt, ['Diluted EPS', 'Basic EPS'])
        pe_list = [annual_price[y.year] / eps[y] if y.year in annual_price.index and eps[y] != 0 else None for y in years]
        
        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=years_label, y=annual_price.values[-len(years):], name="年末股价", line=dict(color='black', width=3)), secondary_y=False)
        fig_val.add_trace(go.Scatter(x=years_label, y=pe_list, name="静态PE", line=dict(color='orange', dash='dot')), secondary_y=True)
        st.plotly_chart(fig_val, use_container_width=True)

        # --- 2. 盈利质量“深度卸妆” (核心增加) ---
        st.header("2️⃣ 盈利质量与“扣非”分析 (Profit Quality)")
        net_income = get_data_safe(is_stmt, ['Net Income'])
        # 模拟扣非净利润逻辑：持续经营净利润
        core_income = get_data_safe(is_stmt, ['Net Income From Continuing Operation Net Of Non-Controlling Interest', 'Net Income Continuous Operations'])
        if core_income.sum() == 0: core_income = net_income * 0.95 # 兜底逻辑
        
        non_recurring_ratio = (core_income / net_income) * 100

        c_p1, c_p2 = st.columns(2)
        with c_p1:
            fig_p = go.Figure()
            fig_p.add_trace(go.Bar(x=years_label, y=net_income, name="报告净利润"))
            fig_p.add_trace(go.Bar(x=years_label, y=core_income, name="核心持续性利润"))
            fig_p.update_layout(title="利润构成分析", barmode='group')
            st.plotly_chart(fig_p, use_container_width=True)
        with c_p2:
            st.write("**核心利润占比 (%)**")
            st.line_chart(non_recurring_ratio)
        st.info("💡 **怎么看：** 核心利润占比长期低于80%说明公司赚钱不靠主业，靠政府补贴、卖资产或投资收益，质量堪忧。")

        # --- 3. 资本开支与 ROIC (核心增加) ---
        st.header("3️⃣ 资本开支与成长耐力 (Capital Efficiency & ROIC)")
        ebit = get_data_safe(is_stmt, ['EBIT'])
        tax_exp = get_data_safe(is_stmt, ['Tax Provision'])
        tax_rate = (tax_exp / ebit).clip(0, 0.3).fillna(0.2)
        nopat = ebit * (1 - tax_rate)
        
        invested_capital = get_data_safe(bs_stmt, ['Stockholders Equity']) + get_data_safe(bs_stmt, ['Total Debt'])
        roic = (nopat / invested_capital) * 100
        capex = get_data_safe(cf_stmt, ['Capital Expenditure']).abs()

        c_r1, c_r2 = st.columns(2)
        with c_r1:
            st.write("**ROIC (投资资本回报率) %**")
            st.line_chart(roic)
        with c_r2:
            st.write("**年度资本开支 (Capex)**")
            st.bar_chart(capex)
        st.info("💡 **怎么看：** ROIC 反映管理层分配资金的效率。ROIC > 15% 且资本开支稳健增长是典型的成长型好公司。")

        # --- 4. 营运效率 ---
        st.header("4️⃣ 营运效率拆解 (Operating Efficiency)")
        rev = get_data_safe(is_stmt, ['Total Revenue'])
        receivables = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        payables = get_data_safe(bs_stmt, ['Accounts Payable'])
        
        dso = (receivables / rev) * 365
        dio = (inventory / rev) * 365 # 简化
        dpo = (payables / rev) * 365
        c2c = dso + dio - dpo

        e1, e2, e3 = st.columns(3)
        with e1:
            st.write("**现金周期 (C2C)**")
            st.bar_chart(c2c)
        with e2:
            st.write("**存货效率 (营收/存货)**")
            st.line_chart(rev / inventory)
        with e3:
            st.write("**回款效率 (营收/应收)**")
            st.line_chart(rev / receivables)

        # --- 5. 营运资本变动 ---
        st.subheader("💼 营运资本变动 (Working Capital Delta)")
        wc = get_working_capital_safe(bs_stmt)
        fig_wc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wc.add_trace(go.Bar(x=years_label, y=wc, name="总量", marker_color='lightgreen'), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=wc.diff(), name="变动", line=dict(color='red')), secondary_y=True)
        st.plotly_chart(fig_wc, use_container_width=True)

        # --- 6. 现金流与股东回报 (核心增加) ---
        st.header("5️⃣ 现金流真实性与股东回报 (Cash Flow & Shareholder Returns)")
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow'])
        fcf = ocf - capex
        div_paid = get_data_safe(cf_stmt, ['Cash Dividends Paid', 'Dividend Paid']).abs()
        
        payout_ratio = (div_paid / net_income) * 100
        # 估算历史股息率
        div_yield = (div_paid / (get_data_safe(bs_stmt, ['Ordinary Share Number']) * annual_price.values[-len(years):])) * 100

        c_s1, c_s2 = st.columns(2)
        with c_s1:
            fig_cash = go.Figure()
            fig_cash.add_trace(go.Bar(x=years_label, y=net_income, name="净利润"))
            fig_cash.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流", line=dict(color='blue')))
            fig_cash.add_trace(go.Scatter(x=years_label, y=fcf, name="自由现金流", line=dict(color='green')))
            st.plotly_chart(fig_cash, use_container_width=True)
        with c_s2:
            st.write("**分红比例 (Payout Ratio) %**")
            st.bar_chart(payout_ratio)
        
        st.metric("最新年度股息率 (Dividend Yield)", f"{div_yield.iloc[-1]:.2f}%")
        st.info("💡 **怎么看：** 分红比例在30%-70%之间通常是稳健的。股息率越高，投资的现金防御性越强。")

        # --- 7. 财务安全性 ---
        st.header("6️⃣ 财务安全性 (Safety)")
        assets = get_data_safe(bs_stmt, ['Total Assets'])
        liab = get_data_safe(bs_stmt, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        current_ratio = get_data_safe(bs_stmt, ['Total Current Assets', 'Current Assets']) / \
                        get_data_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
        
        f1, f2 = st.columns(2)
        with f1:
            st.write("**资产负债率趋势 %**")
            st.line_chart((liab/assets)*100)
        with f2:
            st.write("**流动比率 (倍)**")
            st.line_chart(current_ratio)

    except Exception as e:
        st.error(f"分析失败，请检查代码或网络: {e}")

if st.sidebar.button("生成研报级十年深度报告"):
    run_research_analysis(symbol)
