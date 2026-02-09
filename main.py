import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="全维度财务深度透视系统", layout="wide")

# 2. 侧边栏控制台
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

# --- 工具函数 ---
def get_data_safe(df, keys):
    """鲁棒性抓取：适配不同报表中的行键名，返回Series"""
    for k in keys:
        if k in df.index:
            return df.loc[k].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def get_working_capital_safe(bs_stmt):
    """深度解决营运资本数据缺失：尝试总额获取，失败则进行科目加总"""
    ca = get_data_safe(bs_stmt, ['Total Current Assets', 'Current Assets'])
    cl = get_data_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
    
    # 如果总额为0，尝试通过子科目手动加总
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

# --- 主分析函数 ---
def run_full_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 抓取报表并截取最近10年
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        # 股价历史
        history = stock.history(period="10y")
        annual_price = history['Close'].resample('YE').last()
        annual_price.index = annual_price.index.year

        years = is_stmt.columns
        years_label = [str(y.year) if hasattr(y, 'year') else str(y) for y in years]

        # 头部告知
        st.title(f"🏛️ 全维度财务深度透视：{info.get('longName', ticker)}")
        st.markdown(f"**代码：** `{ticker}` | **行业：** {info.get('industry', 'N/A')} | **币种：** {info.get('currency', 'N/A')}")
        st.divider()

        # --- 1. 估值水平 ---
        st.header("1️⃣ 估值水平 (Valuation Analysis)")
        eps = get_data_safe(is_stmt, ['Diluted EPS', 'Basic EPS'])
        pe_list = [annual_price[y.year] / eps[y] if y.year in annual_price.index and eps[y] != 0 else None for y in years]
        
        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=years_label, y=annual_price.values[-len(years):], name="年末股价", line=dict(color='black', width=3)), secondary_y=False)
        fig_val.add_trace(go.Scatter(x=years_label, y=pe_list, name="静态PE", line=dict(color='orange', dash='dot')), secondary_y=True)
        fig_val.update_layout(title="十年股价与PE趋势", hovermode="x unified")
        st.plotly_chart(fig_val, use_container_width=True)
        st.info("💡 **专家解读：** 观察股价上涨是由盈利驱动（PE平稳）还是情绪驱动（PE飙升）。")

        # --- 2. 盈利与成长性 ---
        st.header("2️⃣ 盈利与成长 (Profitability & Growth)")
        rev = get_data_safe(is_stmt, ['Total Revenue'])
        net_income = get_data_safe(is_stmt, ['Net Income'])
        gp = get_data_safe(is_stmt, ['Gross Profit'])
        rev_growth = rev.pct_change() * 100
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收规模", marker_color='royalblue', opacity=0.7), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=rev_growth, name="营收增速 %", line=dict(color='red', width=2)), secondary_y=True)
            fig_rev.update_layout(title="营收规模与增速", hovermode="x unified")
            st.plotly_chart(fig_rev, use_container_width=True)
        with col_g2:
            fig_margin = go.Figure()
            fig_margin.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率 %", fill='tonexty'))
            fig_margin.add_trace(go.Scatter(x=years_label, y=(net_income/rev)*100, name="净利率 %", line=dict(width=3)))
            fig_margin.update_layout(title="盈利质量趋势", yaxis_title="%", hovermode="x unified")
            st.plotly_chart(fig_margin, use_container_width=True)
        st.info("💡 **专家解读：** 营收增长且利润率稳定是理想状态；若利润率下滑，需警惕行业竞争加剧。")

        # --- 3. 营运效率深度拆解 (修正布局) ---
        st.header("3️⃣ 营运效率深度拆解 (Operating Efficiency)")
        cogs = get_data_safe(is_stmt, ['Cost Of Revenue'])
        receivables = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        payables = get_data_safe(bs_stmt, ['Accounts Payable'])

        dso = (receivables / rev) * 365
        dio = (inventory / (cogs if cogs.mean() != 0 else rev)) * 365
        dpo = (payables / (cogs if cogs.mean() != 0 else rev)) * 365
        c2c_cycle = dso + dio - dpo

        e1, e2, e3 = st.columns(3)
        with e1:
            st.write("**现金到现金周期 (C2C)**")
            st.bar_chart(c2c_cycle)
        with e2:
            st.write("**存货效率 (营收/存货)**")
            st.line_chart(rev / inventory)
        with e3:
            st.write("**回款效率 (营收/应收)**")
            st.line_chart(rev / receivables)
        
        # 营运资本变动图
        working_capital = get_working_capital_safe(bs_stmt)
        fig_wc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wc.add_trace(go.Bar(x=years_label, y=working_capital, name="营运资本总量", marker_color='lightgreen'), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=working_capital.diff(), name="营运资本变动", line=dict(color='red')), secondary_y=True)
        fig_wc.update_layout(title="营运资本规模与变动趋势 (Working Capital Delta)", hovermode="x unified")
        st.plotly_chart(fig_wc, use_container_width=True)
        st.info("💡 **专家解读：** C2C越短效率越高。营运资本大幅增加通常意味着钱被囤货和欠款“吃掉”了。")

        # --- 4. 现金流真实性 ---
        st.header("4️⃣ 现金流真实性对比 (Cash Flow Quality)")
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow'])
        capex = get_data_safe(cf_stmt, ['Capital Expenditure'])
        fcf = ocf + capex
        
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Bar(x=years_label, y=net_income, name="净利润", marker_color='silver'))
        fig_cash.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流(OCF)", line=dict(color='blue', width=3)))
        fig_cash.add_trace(go.Scatter(x=years_label, y=fcf, name="自由现金流(FCF)", line=dict(color='green', width=3)))
        fig_cash.update_layout(title="净利润 vs OCF vs FCF", hovermode="x unified")
        st.plotly_chart(fig_cash, use_container_width=True)
        
        m_k1, m_k2, m_k3 = st.columns(3)
        m_k1.metric("盈利含金量 (OCF/NI)", f"{ocf.iloc[-1]/net_income.iloc[-1]:.2f}")
        m_k2.metric("FCF转换率 (FCF/NI)", f"{fcf.iloc[-1]/net_income.iloc[-1]:.2f}")
        m_k3.write("👉 *指标：>1代表赚的是真钱；<0.8需警惕虚假繁荣。*")

        # --- 5. 财务安全性 (深度增强) ---
        st.header("5️⃣ 财务安全性与偿债能力 (Safety)")
        assets = get_data_safe(bs_stmt, ['Total Assets'])
        liab = get_data_safe(bs_stmt, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        equity = get_data_safe(bs_stmt, ['Stockholders Equity'])
        ebit = get_data_safe(is_stmt, ['EBIT'])
        int_exp = get_data_safe(is_stmt, ['Interest Expense']).abs()
        
        debt_ratio = (liab / assets) * 100
        equity_mult = assets / equity
        current_ratio = get_data_safe(bs_stmt, ['Total Current Assets', 'Current Assets']) / get_data_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities'])
        int_coverage = ebit / int_exp if int_exp.mean() != 0 else pd.Series([None]*len(years))

        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            fig_s = make_subplots(specs=[[{"secondary_y": True}]])
            fig_s.add_trace(go.Scatter(x=years_label, y=debt_ratio, name="资产负债率 %", line=dict(color='black', width=3)), secondary_y=False)
            fig_s.add_trace(go.Scatter(x=years_label, y=current_ratio, name="流动比率 (倍)", line=dict(color='blue', dash='dash')), secondary_y=True)
            fig_s.update_layout(title="负债率与流动性趋势", hovermode="x unified")
            st.plotly_chart(fig_s, use_container_width=True)
        with col_s2:
            st.metric("最新权益乘数 (杠杆)", f"{equity_mult.iloc[-1]:.2f}")
            if int_coverage.iloc[-1] is not None:
                st.metric("利息保障倍数", f"{int_coverage.iloc[-1]:.2f}", delta="安全" if int_coverage.iloc[-1] > 3 else "预警")
            st.metric("最新流动比率", f"{current_ratio.iloc[-1]:.2f}")
        st.info("💡 **专家解读：** 关注流动比率是否低于1，以及利润是否足够覆盖利息。")

    except Exception as e:
        st.error(f"分析失败，请检查代码或网络: {e}")

if st.sidebar.button("生成全维度十年报告"):
    run_full_analysis(symbol)
