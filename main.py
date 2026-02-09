import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="高级财务透视系统", layout="wide")

# 2. 侧边栏配置
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
symbol = st.sidebar.text_input("或输入股票代码：", default_symbol).upper()

def advanced_financial_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 抓取报表并确保年份正序
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        # 获取历史股价 (10年)
        history = stock.history(period="10y")
        # 提取每年的末位股价用于估值对比
        annual_price = history['Close'].resample('YE').last()
        annual_price.index = annual_price.index.year
        
        years = is_stmt.columns
        years_idx = years.year if hasattr(years, 'year') else years

        # --- 报告头部 ---
        st.title(f"🏛️ 深度财务透视报告：{info.get('longName', ticker)}")
        st.caption(f"行业: {info.get('industry', 'N/A')} | 币种: {info.get('currency', 'N/A')}")
        st.divider()

        # --- 维度一：估值水平 (股价 vs PE/PB) ---
        st.header("1️⃣ 估值水平 (Valuation Analysis)")
        # 计算年度简易 PE (股价 / 每股收益)
        eps = is_stmt.loc['Diluted EPS'] if 'Diluted EPS' in is_stmt.index else is_stmt.loc['Basic EPS']
        annual_pe = []
        for y in years:
            y_val = y.year if hasattr(y, 'year') else y
            if y_val in annual_price.index:
                annual_pe.append(annual_price[y_val] / eps[y])
            else: annual_pe.append(None)

        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=years, y=annual_price.values[-len(years):], name="历史股价 (Close)", line=dict(color='black', width=3)), secondary_y=False)
        fig_val.add_trace(go.Scatter(x=years, y=annual_pe, name="市盈率 (PE)", line=dict(color='orange', dash='dash')), secondary_y=True)
        fig_val.update_layout(title="十年股价与估值乘数趋势", hovermode="x unified")
        fig_val.update_yaxes(title_text="股价", secondary_y=False)
        fig_val.update_yaxes(title_text="PE 倍数", secondary_y=True, showgrid=False)
        st.plotly_chart(fig_val, use_container_width=True)

        # --- 维度二：盈利性与成长性 ---
        st.header("2️⃣ 盈利与成长 (Growth)")
        rev = is_stmt.loc['Total Revenue']
        net_income = is_stmt.loc['Net Income']
        rev_growth = rev.pct_change() * 100
        
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=years, y=rev, name="营业收入", marker_color='royalblue', opacity=0.6), secondary_y=False)
        fig1.add_trace(go.Scatter(x=years, y=rev_growth, name="营收增长率 %", line=dict(color='firebrick', width=2)), secondary_y=True)
        fig1.update_layout(title="营收规模与增速", hovermode="x unified")
        st.plotly_chart(fig1, use_container_width=True)

        # 利润率对比
        gp = is_stmt.loc['Gross Profit']
        st.write("**毛利率 vs 净利率趋势**")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=years, y=(gp/rev)*100, name="毛利率 %", line=dict(color='green')))
        fig2.add_trace(go.Scatter(x=years, y=(net_income/rev)*100, name="净利率 %", line=dict(color='darkred')))
        fig2.update_layout(yaxis_title="%", hovermode="x unified")
        st.plotly_chart(fig2, use_container_width=True)

        # --- 维度三：现金流三位一体 (核心改进) ---
        st.header("3️⃣ 现金流真实性对比 (Profit vs Cash)")
        ocf = cf_stmt.loc['Operating Cash Flow']
        fcf = ocf + cf_stmt.loc['Capital Expenditure']
        
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Bar(x=years, y=net_income, name="净利润 (Net Income)", marker_color='lightgrey'))
        fig_cash.add_trace(go.Scatter(x=years, y=ocf, name="经营现金流 (OCF)", line=dict(color='blue', width=3)))
        fig_cash.add_trace(go.Scatter(x=years, y=fcf, name="自由现金流 (FCF)", line=dict(color='green', width=3)))
        fig_cash.update_layout(title="净利润 vs OCF vs FCF (验证公司是否赚到真钱)", hovermode="x unified")
        st.plotly_chart(fig_cash, use_container_width=True)
        st.caption("注：经营现金流长期高于净利润是财务健康的标志；自由现金流则是公司可支配的真金白银。")

        # --- 维度四：营运与效率 ---
        st.header("4️⃣ 营运效率 (Efficiency)")
        receivable_keys = ['Receivables', 'Net Receivables', 'Accounts Receivable']
        receivables = next((bs_stmt.loc[k] for k in receivable_keys if k in bs_stmt.index), None)
        
        c_eff1, c_eff2 = st.columns(2)
        with c_eff1:
            if receivables is not None:
                st.write("**应收账款周转率 (营收/应收账款)**")
                st.line_chart(rev / receivables)
            else: st.warning("应收账款数据缺失")
        with c_eff2:
            st.write("**总资产周转率 (次)**")
            st.area_chart(rev / bs_stmt.loc['Total Assets'])

        # --- 维度五：财务安排与安全性 (核心改进) ---
        st.header("5️⃣ 财务安排与安全性 (Financial Structure)")
        assets = bs_stmt.loc['Total Assets']
        equity = bs_stmt.loc['Stockholders Equity']
        total_liab = bs_stmt.loc['Total Liabilities Net Minority Interest']
        
        # 1. 资产负债率 (折线图)
        debt_ratio = (total_liab / assets) * 100
        # 2. 权益乘数 (杠杆率)
        equity_multiplier = assets / equity
        # 3. 利息保障倍数 (如果有利息支出数据)
        interest_coverage = is_stmt.loc['EBIT'] / abs(is_stmt.loc['Interest Expense']) if 'Interest Expense' in is_stmt.index else None

        fig_debt = make_subplots(specs=[[{"secondary_y": True}]])
        fig_debt.add_trace(go.Scatter(x=years, y=debt_ratio, name="资产负债率 %", line=dict(color='black', width=3)), secondary_y=False)
        fig_debt.add_trace(go.Scatter(x=years, y=equity_multiplier, name="权益乘数 (杠杆)", line=dict(color='purple', dash='dot')), secondary_y=True)
        fig_debt.update_layout(title="财务杠杆与负债趋势", hovermode="x unified")
        fig_debt.update_yaxes(title_text="负债率 %", secondary_y=False)
        fig_debt.update_yaxes(title_text="权益乘数", secondary_y=True, showgrid=False)
        st.plotly_chart(fig_debt, use_container_width=True)

        if interest_coverage is not None:
            st.write("**利息保障倍数 (EBIT / 利息支出)**")
            st.bar_chart(interest_coverage)
            st.caption("注：倍数越高，偿债压力越小；若小于1，说明利润已不足以支付利息。")

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成全维度深度报告"):
    advanced_financial_analysis(symbol)
