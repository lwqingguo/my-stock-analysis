import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="旗舰级财务透视系统-V17", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 全球数据中心")
examples = {"手动输入": "", "英伟达 (NVDA)": "NVDA", "苹果 (AAPL)": "AAPL", "可口可乐 (KO)": "KO", "贵州茅台 (600519.SS)": "600519.SS", "农夫山泉 (9633.HK)": "9633.HK"}
selected = st.sidebar.selectbox("选择示例股票：", list(examples.keys()))
symbol = st.sidebar.text_input("输入代码：", examples[selected] if examples[selected] else "NVDA").upper()

# --- 核心数据抓取函数 (增强版：解决数据归零问题) ---
def get_data_safe(df, keys):
    """
    具备多重搜索逻辑的抓取函数：
    1. 优先尝试完全匹配 keys 中的键名
    2. 如果没找到，尝试在 df.index 中模糊搜索包含关键字的项
    """
    for k in keys:
        if k in df.index:
            return df.loc[k].fillna(0)
    
    # 模糊搜索备选方案 (针对 A 股和港股键名不一致问题)
    for k in keys:
        matches = [idx for idx in df.index if k.lower().replace(" ", "") in idx.lower().replace(" ", "")]
        if matches:
            return df.loc[matches[0]].fillna(0)
            
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_working_capital_safe(bs_stmt):
    ca = get_data_safe(bs_stmt, ['Total Current Assets', 'Current Assets', 'CurrentAssets'])
    cl = get_data_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities', 'CurrentLiabilities'])
    # 极致补偿逻辑
    if ca.sum() == 0:
        ca = get_data_safe(bs_stmt, ['CashAndCashEquivalents', 'Cash And Cash Equivalents']) + \
             get_data_safe(bs_stmt, ['Inventory']) + \
             get_data_safe(bs_stmt, ['Receivables', 'Net Receivables'])
    if cl.sum() == 0:
        cl = get_data_safe(bs_stmt, ['AccountsPayable', 'Accounts Payable'])
    return ca - cl

# --- 主分析函数 ---
def run_ultimate_v17(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        years = is_stmt.columns
        years_label = [str(y.year) for y in years]
        
        # 股价处理
        history = stock.history(period="10y")
        annual_price = history['Close'].resample('YE').last()
        annual_price.index = annual_price.index.year

        st.title(f"🏛️ 全维度财务透视旗舰版：{info.get('longName', ticker)}")
        st.divider()

        # --- 1. 估值水平 ---
        st.header("1️⃣ 估值水平 (Valuation)")
        eps = get_data_safe(is_stmt, ['Diluted EPS', 'Basic EPS', 'EPS'])
        pe_list = [annual_price[y.year] / eps[y] if y.year in annual_price.index and eps[y] != 0 else None for y in years]
        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=years_label, y=annual_price.values[-len(years):], name="年末股价", line=dict(color='black', width=3)), secondary_y=False)
        fig_val.add_trace(go.Scatter(x=years_label, y=pe_list, name="静态PE", line=dict(color='orange', dash='dot')), secondary_y=True)
        st.plotly_chart(fig_val, use_container_width=True)

        # --- 2. 盈利质量与成长分析 (增强修正) ---
        st.header("2️⃣ 盈利质量与成长分析 (Growth & Quality)")
        rev = get_data_safe(is_stmt, ['Total Revenue', 'Revenue'])
        rev_growth = rev.pct_change() * 100
        net_income = get_data_safe(is_stmt, ['Net Income', 'NetIncome'])
        gp = get_data_safe(is_stmt, ['Gross Profit', 'GrossProfit'])
        core_income = get_data_safe(is_stmt, ['Net Income From Continuing Operation Net Of Non-Controlling Interest', 'NetIncomeFromContinuingOperationNetOfNonControllingInterest'])
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            # 营收规模与增速
            fig_g = make_subplots(specs=[[{"secondary_y": True}]])
            fig_g.add_trace(go.Bar(x=years_label, y=rev, name="营收总量", marker_color='royalblue'), secondary_y=False)
            fig_g.add_trace(go.Scatter(x=years_label, y=rev_growth, name="营收增速 %", line=dict(color='red', width=2)), secondary_y=True)
            fig_g.update_layout(title="营收规模与增速趋势")
            st.plotly_chart(fig_g, use_container_width=True)
        with col_p2:
            # 利润率对比
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率 %", line=dict(width=3)))
            fig_m.add_trace(go.Scatter(x=years_label, y=(net_income/rev)*100, name="净利率 %", line=dict(width=3)))
            fig_m.update_layout(title="毛利与净利空间趋势")
            st.plotly_chart(fig_m, use_container_width=True)

        st.write("**核心盈利“深度卸妆”**")
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            fig_core = go.Figure()
            fig_core.add_trace(go.Bar(x=years_label, y=net_income, name="报告净利润"))
            fig_core.add_trace(go.Bar(x=years_label, y=core_income, name="核心持续性利润"))
            fig_core.update_layout(barmode='group', title="利润构成真实性对比")
            st.plotly_chart(fig_core, use_container_width=True)
        with c_p2:
            st.write("**核心净利润 / 净利润 (%)**")
            st.line_chart((core_income / net_income) * 100)

        # --- 3. 杜邦分析与 ROIC ---
        st.header("3️⃣ 杜邦分析与 ROIC 驱动")
        assets = get_data_safe(bs_stmt, ['Total Assets', 'TotalAssets'])
        equity = get_data_safe(bs_stmt, ['Stockholders Equity', 'StockholdersEquity'])
        debt = get_data_safe(bs_stmt, ['Total Debt', 'TotalDebt'])
        ebit = get_data_safe(is_stmt, ['EBIT'])
        
        roe = (net_income / equity) * 100
        roic = (ebit * 0.75) / (equity + debt) * 100
        
        d1, d2, d3 = st.columns(3)
        d1.write("**ROE %**"); d1.line_chart(roe)
        d2.write("**ROIC %**"); d2.line_chart(roic)
        d3.write("**权益乘数 (杠杆)**"); d3.line_chart(assets / equity)

        # --- 4. 营运效率 (保留全部指标) ---
        st.header("4️⃣ 营运效率与营运资本")
        receivables = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        payables = get_data_safe(bs_stmt, ['Accounts Payable'])
        
        e1, e2, e3 = st.columns(3)
        with e1:
            st.write("**现金到现金周期 (C2C)**")
            c2c = ((receivables/rev)*365) + ((inventory/rev)*365) - ((payables/rev)*365)
            st.bar_chart(c2c)
        with e2:
            st.write("**营收/存货 (周转率)**")
            st.line_chart(rev / inventory)
        with e3:
            st.write("**营收/应收账款**")
            st.line_chart(rev / receivables)

        wc = get_working_capital_safe(bs_stmt)
        fig_wc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wc.add_trace(go.Bar(x=years_label, y=wc, name="营运资本总量"), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=wc.diff(), name="营运资本变动"), secondary_y=True)
        st.plotly_chart(fig_wc, use_container_width=True)

        # --- 5. 现金流真实性与股东回报 ---
        st.header("5️⃣ 现金流真实性与股东回报")
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow', 'OperatingCashFlow'])
        capex = get_data_safe(cf_stmt, ['Capital Expenditure', 'CapitalExpenditure']).abs()
        div_paid = get_data_safe(cf_stmt, ['Cash Dividends Paid', 'CashDividendsPaid', 'DividendPaid']).abs()
        
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Bar(x=years_label, y=net_income, name="净利润"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流", line=dict(color='blue')))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf - capex, name="自由现金流", line=dict(color='green')))
            st.plotly_chart(fig_cf, use_container_width=True)
        with c_f2:
            st.write("**分红比例 (Payout Ratio) %**")
            st.bar_chart((div_paid / net_income) * 100)

        # --- 6. 财务安全性 (解决归零问题) ---
        st.header("6️⃣ 财务安全性分析")
        liab = get_data_safe(bs_stmt, ['Total Liabilities', 'TotalLiabilities'])
        ca = get_data_safe(bs_stmt, ['Total Current Assets', 'Current Assets'])
        cl = get_data_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
        interest_exp = get_data_safe(is_stmt, ['Interest Expense', 'InterestExpense']).abs()

        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((liab/assets)*100)
        s2.write("**流动比率 (倍)**"); s2.line_chart(ca/cl)
        s3.write("**利息保障倍数**"); s3.line_chart(ebit / interest_exp if interest_exp.mean() != 0 else pd.Series([0]*len(years)))

        # --- 7. 总结评估 ---
        st.divider()
        st.success(f"**{info.get('shortName', ticker)} 综合诊断：** ROE为 {roe.iloc[-1]:.2f}%，资产负债率为 {(liab/assets).iloc[-1]*100:.2f}%。营收增速为 {rev_growth.iloc[-1]:.2f}%。")

    except Exception as e:
        st.error(f"分析失败，请检查代码或网络: {e}")

if st.sidebar.button("生成旗舰级全维度报告"):
    run_ultimate_v17(symbol)
