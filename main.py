import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="全维度财务深度透视系统", layout="wide")

# 2. 侧边栏：知名股票示例
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
    return pd.Series([0]*len(df.columns), index=df.columns)

def comprehensive_expert_system(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 抓取报表并截取最近10年
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        # 获取10年股价
        history = stock.history(period="10y")
        annual_price = history['Close'].resample('YE').last()
        annual_price.index = annual_price.index.year

        years = is_stmt.columns
        years_label = [str(y.year) if hasattr(y, 'year') else str(y) for y in years]

        # --- 报告头部 ---
        st.title(f"🏛️ 全维度财务深度透视：{info.get('longName', ticker)}")
        st.markdown(f"**行业：** {info.get('industry', 'N/A')} | **代码：** `{ticker}` | **币种：** {info.get('currency', 'N/A')}")
        st.divider()

        # --- 维度一：估值水平 ---
        st.header("1️⃣ 估值水平 (Valuation Analysis)")
        eps = get_data_safe(is_stmt, ['Diluted EPS', 'Basic EPS', 'EPS'])
        pe_list = [annual_price[y.year] / eps[y] if y.year in annual_price.index and eps[y] != 0 else None for y in years]
        
        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=years_label, y=annual_price.values[-len(years):], name="年末股价", line=dict(color='black', width=3)), secondary_y=False)
        fig_val.add_trace(go.Scatter(x=years_label, y=pe_list, name="静态PE", line=dict(color='orange', dash='dot')), secondary_y=True)
        st.plotly_chart(fig_val, use_container_width=True)
        st.info("💡 **怎么看：** 观察股价上涨是由盈利驱动（PE平稳）还是情绪驱动（PE飙升）。")

        # --- 维度二：盈利性与成长性 ---
        st.header("2️⃣ 盈利与成长 (Profitability & Growth)")
        rev = get_data_safe(is_stmt, ['Total Revenue'])
        net_income = get_data_safe(is_stmt, ['Net Income'])
        gp = get_data_safe(is_stmt, ['Gross Profit'])
        rev_growth = rev.pct_change() * 100
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收", marker_color='royalblue', opacity=0.7), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=rev_growth, name="营收增速 %", line=dict(color='red')), secondary_y=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with col_g2:
            fig_margin = go.Figure()
            fig_margin.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率 %", fill='tonexty'))
            fig_margin.add_trace(go.Scatter(x=years_label, y=(net_income/rev)*100, name="净利率 %"))
            st.plotly_chart(fig_margin, use_container_width=True)
        st.info("💡 **怎么看：** 营收持续增长且利润率稳定说明具备护城河；若增速放缓且利润率下滑，说明竞争加剧。")

        # --- 维度三：营运效率 (核心：C2C周期、存货周转、营运资本) ---
        st.header("3️⃣ 营运效率深度拆解 (Operating Efficiency)")
        cogs = get_data_safe(is_stmt, ['Cost Of Revenue'])
        receivables = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        payables = get_data_safe(bs_stmt, ['Accounts Payable'])
        
        # 计算核心营运指标
        dso = (receivables / rev) * 365
        dio = (inventory / (cogs if cogs.mean() != 0 else rev)) * 365
        dpo = (payables / (cogs if cogs.mean() != 0 else rev)) * 365
        c2c_cycle = dso + dio - dpo  # 现金到现金周期
        
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.write("**现金到现金周期 (C2C Cycle) 与 存货周转率**")
            fig_e1 = make_subplots(specs=[[{"secondary_y": True}]])
            fig_e1.add_trace(go.Bar(x=years_label, y=c2c_cycle, name="C2C周期(天)", marker_color='orange'), secondary_y=False)
            fig_e1.add_trace(go.Scatter(x=years_label, y=(rev/inventory), name="营收/存货 (周转率)", line=dict(color='darkblue')), secondary_y=True)
            st.plotly_chart(fig_e1, use_container_width=True)
        with col_e2:
            st.write("**营运资本 (Required Working Capital) 变动**")
            wc = get_data_safe(bs_stmt, ['Total Current Assets']) - get_data_safe(bs_stmt, ['Total Current Liabilities'])
            fig_wc = go.Figure()
            fig_wc.add_trace(go.Bar(x=years_label, y=wc, name="营运资本总量", marker_color='lightgreen'))
            fig_wc.add_trace(go.Scatter(x=years_label, y=wc.diff(), name="年度变动(Delta)", line=dict(color='red')))
            st.plotly_chart(fig_wc, use_container_width=True)
        st.info("💡 **怎么看：** C2C周期越短说明资金效率越高（苹果常为负）；营运资本变动反映了业务扩张对现金的“吞噬”程度。")

        # --- 维度四：现金流真实性对比 ---
        st.header("4️⃣ 现金流真实性与含金量 (Cash Flow Quality)")
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow'])
        capex = get_data_safe(cf_stmt, ['Capital Expenditure'])
        fcf = ocf + capex
        
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Bar(x=years_label, y=net_income, name="净利润", marker_color='silver'))
        fig_cash.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流(OCF)", line=dict(color='blue', width=3)))
        fig_cash.add_trace(go.Scatter(x=years_label, y=fcf, name="自由现金流(FCF)", line=dict(color='green', width=3)))
        st.plotly_chart(fig_cash, use_container_width=True)
        
        # 关键量化比率
        c_k1, c_k2, c_k3 = st.columns(3)
        quality = ocf.iloc[-1] / net_income.iloc[-1]
        fcf_ni = fcf.iloc[-1] / net_income.iloc[-1]
        c_k1.metric("盈利含金量 (OCF/NI)", f"{quality:.2f}", help=">1代表钱回得快")
        c_k2.metric("现金转换率 (FCF/NI)", f"{fcf_ni:.2f}", help="反映真实分红能力")
        c_k3.write("👉 *指标解读：蓝线(OCF)长期高于净利润是高质量发展的标志。*")

        # --- 维度五：财务安排与安全性 ---
        st.header("5️⃣ 财务安全性与负债安排 (Safety)")
        assets = get_data_safe(bs_stmt, ['Total Assets'])
        liab = get_data_safe(bs_stmt, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        equity = get_data_safe(bs_stmt, ['Stockholders Equity'])
        debt_ratio = (liab / assets) * 100
        equity_multiplier = assets / equity
        
        fig_safe = make_subplots(specs=[[{"secondary_y": True}]])
        fig_safe.add_trace(go.Scatter(x=years_label, y=debt_ratio, name="资产负债率 %", line=dict(color='black', width=3)), secondary_y=False)
        fig_safe.add_trace(go.Scatter(x=years_label, y=equity_multiplier, name="权益乘数 (杠杆率)", line=dict(color='purple', dash='dot')), secondary_y=True)
        st.plotly_chart(fig_safe, use_container_width=True)
        st.info("💡 **怎么看：** 关注负债率是否异常攀升，权益乘数反映了公司利用杠杆博取ROE的程度。")

    except Exception as e:
        st.error(f"分析失败，请检查代码或网络: {e}")

if st.sidebar.button("生成全维度十年深度透视"):
    comprehensive_expert_system(symbol)
