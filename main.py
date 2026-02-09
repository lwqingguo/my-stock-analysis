import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="旗舰级财务透视系统-V16", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 全球数据中心")
examples = {"手动输入": "", "英伟达 (NVDA)": "NVDA", "苹果 (AAPL)": "AAPL", "可口可乐 (KO)": "KO", "贵州茅台 (600519.SS)": "600519.SS", "农夫山泉 (9633.HK)": "9633.HK"}
selected = st.sidebar.selectbox("选择示例股票：", list(examples.keys()))
symbol = st.sidebar.text_input("输入代码：", examples[selected] if examples[selected] else "NVDA").upper()

# --- 核心数据抓取函数 ---
def get_data_safe(df, keys):
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_working_capital_safe(bs_stmt):
    ca = get_data_safe(bs_stmt, ['Total Current Assets', 'Current Assets'])
    cl = get_data_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
    if ca.sum() == 0:
        ca = get_data_safe(bs_stmt, ['Cash And Cash Equivalents']) + \
             get_data_safe(bs_stmt, ['Net Receivables']) + \
             get_data_safe(bs_stmt, ['Inventory'])
    if cl.sum() == 0:
        cl = get_data_safe(bs_stmt, ['Accounts Payable']) + get_data_safe(bs_stmt, ['Tax Liabilities'])
    return ca - cl

# --- 主分析逻辑 ---
def run_ultimate_v16(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        years = is_stmt.columns
        years_label = [str(y.year) for y in years]
        history = stock.history(period="10y")
        annual_price = history['Close'].resample('YE').last()
        annual_price.index = annual_price.index.year

        st.title(f"🏛️ 全维度财务透视旗舰版：{info.get('longName', ticker)}")
        st.divider()

        # --- 1. 估值水平 (Valuation) ---
        st.header("1️⃣ 估值水平与市场表现")
        eps = get_data_safe(is_stmt, ['Diluted EPS', 'Basic EPS'])
        pe_list = [annual_price[y.year] / eps[y] if y.year in annual_price.index and eps[y] != 0 else None for y in years]
        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=years_label, y=annual_price.values[-len(years):], name="年末股价", line=dict(color='black', width=3)), secondary_y=False)
        fig_val.add_trace(go.Scatter(x=years_label, y=pe_list, name="静态PE", line=dict(color='orange', dash='dot')), secondary_y=True)
        st.plotly_chart(fig_val, use_container_width=True)

        # --- 2. 盈利质量与 ROIC 拆解 (Profitability) ---
        st.header("2️⃣ 盈利质量与 ROIC 驱动拆解")
        net_income = get_data_safe(is_stmt, ['Net Income'])
        core_income = get_data_safe(is_stmt, ['Net Income From Continuing Operation Net Of Non-Controlling Interest', 'Net Income Continuous Operations'])
        ebit = get_data_safe(is_stmt, ['EBIT'])
        equity = get_data_safe(bs_stmt, ['Stockholders Equity'])
        debt = get_data_safe(bs_stmt, ['Total Debt'])
        invested_capital = equity + debt
        nopat = ebit * 0.75 # 假设25%税率
        roic = (nopat / invested_capital) * 100
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.write("**报告利润 vs 扣非核心利润**")
            fig_p = go.Figure()
            fig_p.add_trace(go.Bar(x=years_label, y=net_income, name="净利润"))
            fig_p.add_trace(go.Bar(x=years_label, y=core_income, name="核心利润"))
            st.plotly_chart(fig_p, use_container_width=True)
        with c_p2:
            st.write("**ROIC (投资资本回报率) %**")
            st.line_chart(roic)

        # --- 3. 杜邦分析 (DuPont Analysis) ---
        st.header("3️⃣ 杜邦分析：ROE 驱动因子")
        rev = get_data_safe(is_stmt, ['Total Revenue'])
        assets = get_data_safe(bs_stmt, ['Total Assets'])
        roe = (net_income / equity) * 100
        net_margin = (net_income / rev) * 100
        asset_turnover = rev / assets
        equity_multiplier = assets / equity

        d1, d2, d3 = st.columns(3)
        d1.write("**销售净利率 %**"); d1.line_chart(net_margin)
        d2.write("**资产周转率**"); d2.line_chart(asset_turnover)
        d3.write("**权益乘数 (杠杆)**"); d3.line_chart(equity_multiplier)

        # --- 4. 营运效率深度分析 (Efficiency) ---
        st.header("4️⃣ 营运效率与营运资本")
        receivables = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        payables = get_data_safe(bs_stmt, ['Accounts Payable'])
        
        e1, e2, e3 = st.columns(3)
        with e1:
            st.write("**现金到现金周期 (C2C) - 天**")
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
        fig_wc.add_trace(go.Bar(x=years_label, y=wc, name="营运资本总量", marker_color='lightgreen'), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=wc.diff(), name="营运资本变动 (Delta)", line=dict(color='red')), secondary_y=True)
        st.plotly_chart(fig_wc, use_container_width=True)

        # --- 5. 现金流真实性与股东回报 ---
        st.header("5️⃣ 现金流真实性与股东回报")
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow'])
        capex = get_data_safe(cf_stmt, ['Capital Expenditure']).abs()
        fcf = ocf - capex
        div_paid = get_data_safe(cf_stmt, ['Cash Dividends Paid', 'Dividend Paid']).abs()
        
        c_c1, c_c2 = st.columns(2)
        with c_c1:
            fig_cash = go.Figure()
            fig_cash.add_trace(go.Bar(x=years_label, y=net_income, name="净利润"))
            fig_cash.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流", line=dict(color='blue')))
            fig_cash.add_trace(go.Scatter(x=years_label, y=fcf, name="自由现金流", line=dict(color='green')))
            st.plotly_chart(fig_cash, use_container_width=True)
        with c_c2:
            st.write("**分红比例 (Payout Ratio) %**")
            st.bar_chart((div_paid / net_income) * 100)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("盈利含金量 (OCF/NI)", f"{(ocf/net_income).iloc[-1]:.2f}")
        m2.metric("最新股息率 (Est.)", f"{(div_paid / (stock.info.get('marketCap', 1))).iloc[-1]*100:.2f}%")
        m3.metric("年度资本开支 (亿)", f"{capex.iloc[-1]/1e8:.2f}")

        # --- 6. 财务安全性 (Safety) ---
        st.header("6️⃣ 财务安全性与负债安排")
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((get_data_safe(bs_stmt, ['Total Liabilities'])/assets)*100)
        s2.write("**流动比率 (倍)**"); s2.line_chart(get_data_safe(bs_stmt, ['Total Current Assets'])/get_data_safe(bs_stmt, ['Total Current Liabilities']))
        s3.write("**利息保障倍数**"); s3.line_chart(ebit / get_data_safe(is_stmt, ['Interest Expense']).abs())

        # --- 7. 综合评估总结 ---
        st.divider()
        st.header("🏁 综合评估总结")
        score_roe = "优秀" if roe.iloc[-1] > 15 else "一般"
        score_cash = "极佳" if (ocf/net_income).iloc[-1] > 1 else "需关注"
        
        st.success(f"""
        **{info.get('shortName', ticker)} 分析结论：**
        1. **核心盈利**：ROE ({roe.iloc[-1]:.1f}%) 表现{score_roe}，主要由 {"净利率" if net_margin.diff().iloc[-1]>0 else "周转率或杠杆"} 驱动。
        2. **含金量**：利润含金量为 {(ocf/net_income).iloc[-1]:.2f}，现金流表现{score_cash}。
        3. **营运效率**：C2C 周期为 {c2c.iloc[-1]:.1f} 天，营运资本变动为 {wc.diff().iloc[-1]/1e8:.2f} 亿。
        4. **股东回报**：分红比例为 {(div_paid/net_income).iloc[-1]*100:.1f}%，具备{"强" if div_paid.iloc[-1]>0 else "弱"}分红属性。
        """)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成终极全维度报告"):
    run_ultimate_v16(symbol)
