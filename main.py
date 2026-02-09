import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="全维度财务深度透视系统", layout="wide")

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
selected_example = st.sidebar.selectbox("选择知名股票示例：", list(examples.keys()))
default_symbol = examples[selected_example] if examples[selected_example] else "NVDA"
symbol = st.sidebar.text_input("输入股票代码：", default_symbol).upper()

def get_data_safe(df, keys):
    """鲁棒性抓取：适配不同报表中的行键名"""
    for k in keys:
        if k in df.index:
            return df.loc[k]
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_working_capital_safe(bs_stmt):
    """深度解决营运资本数据缺失：尝试总额获取，失败则进行科目加总"""
    # 尝试直接获取总额
    ca = get_data_safe(bs_stmt, ['Total Current Assets', 'Current Assets'])
    cl = get_data_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
    
    # 如果总额为0，尝试通过子科目手动加总 (常见于部分数据缺失的报表)
    if ca.sum() == 0:
        cash = get_data_safe(bs_stmt, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'])
        rec = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inv = get_data_safe(bs_stmt, ['Inventory'])
        ca = cash + rec + inv
        
    if cl.sum() == 0:
        ap = get_data_safe(bs_stmt, ['Accounts Payable'])
        tax = get_data_safe(bs_stmt, ['Tax Liabilities', 'Income Tax Payable'])
        cl = ap + tax
        
    return ca - cl

def expert_system_v10(ticker):
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

        # --- 2. 盈利与成长 ---
        st.header("2️⃣ 盈利与成长 (Profitability)")
        rev = get_data_safe(is_stmt, ['Total Revenue'])
        net_income = get_data_safe(is_stmt, ['Net Income'])
        gp = get_data_safe(is_stmt, ['Gross Profit'])
        rev_growth = rev.pct_change() * 100
        
        c_g1, c_g2 = st.columns(2)
        with c_g1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收", marker_color='royalblue'), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=rev_growth, name="增速 %", line=dict(color='red')), secondary_y=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with c_g2:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率 %", fill='tonexty'))
            fig_m.add_trace(go.Scatter(x=years_label, y=(net_income/rev)*100, name="净利率 %"))
            st.plotly_chart(fig_m, use_container_width=True)

        # --- 3. 营运效率深度拆解 (修正布局) ---
        st.header("3️⃣ 营运效率拆解 (Operating Efficiency)")
        cogs = get_data_safe(is_stmt, ['Cost Of Revenue'])
        receivables = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        payables = get_data_safe(bs_stmt, ['Accounts Payable'])

        # 计算周转指标
        dso = (receivables / rev) * 365
        dio = (inventory / (cogs if cogs.mean() != 0 else rev)) * 365
        dpo = (payables / (cogs if cogs.mean() != 0 else rev)) * 365
        c2c_cycle = dso + dio - dpo

        e1, e2, e3 = st.columns(3)
        with e1:
            st.write("**现金到现金周期 (C2C)**")
            st.bar_chart(c2c_cycle)
        with e2:
            st.write("**存货周转效率 (营收/存货)**")
            st.line_chart(rev / inventory)
        with e3:
            st.write("**应收账款效率 (营收/应收)**")
            st.line_chart(rev / receivables)
        st.info("💡 **怎么看：** C2C周期越短资金效率越高；营收/存货与营收/应收越高，代表资产周转越快，坏账及积压风险越低。")

        # --- 4. 营运资本变动 (修正数据缺失) ---
        st.subheader("💼 营运资本变动 (Working Capital Delta)")
        working_capital = get_working_capital_safe(bs_stmt)
        fig_wc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wc.add_trace(go.Bar(x=years_label, y=working_capital, name="营运资本总量", marker_color='lightgreen'), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=working_capital.diff(), name="年度变动", line=dict(color='red')), secondary_y=True)
        st.plotly_chart(fig_wc, use_container_width=True)

        # --- 5. 现金流真实性 ---
        st.header("4️⃣ 现金流真实性对比")
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow'])
        fcf = ocf + get_data_safe(cf_stmt, ['Capital Expenditure'])
        
        fig_c = go.Figure()
        fig_c.add_trace(go.Bar(x=years_label, y=net_income, name="净利润", marker_color='silver'))
        fig_c.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流(OCF)", line=dict(color='blue', width=3)))
        fig_c.add_trace(go.Scatter(x=years_label, y=fcf, name="自由现金流(FCF)", line=dict(color='green', width=3)))
        st.plotly_chart(fig_c, use_container_width=True)
        
        mk1, mk2 = st.columns(2)
        mk1.metric("盈利含金量 (OCF/NI)", f"{ocf.iloc[-1]/net_income.iloc[-1]:.2f}")
        mk2.metric("FCF转换率 (FCF/NI)", f"{fcf.iloc[-1]/net_income.iloc[-1]:.2f}")

        # --- 6. 财务安全 ---
        st.header("5️⃣ 财务安全性 (Safety)")
        assets = get_data_safe(bs_stmt, ['Total Assets'])
        liab = get_data_safe(bs_stmt, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        st.write("**资产负债率趋势 (%)**")
        st.line_chart((liab/assets)*100)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成全维度十年报告"):
    expert_system_v10(symbol)
