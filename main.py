import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="综合财务透视系统-营运增强版", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 数据控制台")
examples = {
    "手动输入": "",
    "英伟达 (NVDA)": "NVDA",
    "百事可乐 (PEP)": "PEP",
    "可口可乐 (KO)": "KO",
    "东鹏饮料 (605499.SS)": "605499.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "海康威视 (002415.SZ)": "002415.SZ"
}
selected_example = st.sidebar.selectbox("选择知名股票示例：", list(examples.keys()))
default_symbol = examples[selected_example] if examples[selected_example] else "NVDA"
symbol = st.sidebar.text_input("输入股票代码：", default_symbol).upper()

def get_data_safe(df, keys):
    for k in keys:
        if k in df.index:
            return df.loc[k]
    return pd.Series([0]*len(df.columns), index=df.columns)

def analyze_v8(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        years = is_stmt.columns
        years_label = [str(y.year) if hasattr(y, 'year') else str(y) for y in years]

        st.title(f"🏛️ 财务深度透视报告：{info.get('longName', ticker)}")
        st.divider()

        # --- 维度一：营运效率深度拆解 (核心升级) ---
        st.header("1️⃣ 营运效率与周转能力 (Operating Efficiency)")
        
        rev = get_data_safe(is_stmt, ['Total Revenue'])
        cogs = get_data_safe(is_stmt, ['Cost Of Revenue'])
        receivables = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        payables = get_data_safe(bs_stmt, ['Accounts Payable'])

        # 计算周转天数 (Days)
        dso = (receivables / rev) * 365
        dio = (inventory / cogs) * 365 if cogs.mean() != 0 else (inventory / rev) * 365
        dpo = (payables / cogs) * 365 if cogs.mean() != 0 else (payables / rev) * 365
        c2c_cycle = dso + dio - dpo # 现金到现金周期

        col1, col2 = st.columns(2)
        with col1:
            # 营收/存货 (存货周转率)
            st.write("**存货周转效率 (营收 / 存货)**")
            inv_turnover = rev / inventory
            fig_inv = go.Figure()
            fig_inv.add_trace(go.Scatter(x=years_label, y=inv_turnover, name="存货周转率", line=dict(color='darkblue', width=3)))
            st.plotly_chart(fig_inv, use_container_width=True)
            st.caption("注：数值越高，代表商品从入库到卖出的速度越快，资金占用少。")

        with col2:
            # 现金到现金周期 (Cash-to-Cash Cycle)
            st.write("**现金到现金周期 (C2C Cycle) - 天数**")
            fig_c2c = go.Figure()
            fig_c2c.add_trace(go.Bar(x=years_label, y=c2c_cycle, name="C2C周期(天)", marker_color='orange'))
            st.plotly_chart(fig_c2c, use_container_width=True)
            st.caption("注：计算公式：收账天数+存货天数-付账天数。数值越小（甚至为负）代表公司产业链话语权越强。")

        # --- 维度二：营运资本变动 ---
        st.subheader("💼 营运资本需求分析 (Working Capital)")
        current_assets = get_data_safe(bs_stmt, ['Total Current Assets'])
        current_liab = get_data_safe(bs_stmt, ['Total Current Liabilities'])
        working_capital = current_assets - current_liab
        wc_change = working_capital.diff()

        fig_wc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_wc.add_trace(go.Bar(x=years_label, y=working_capital, name="营运资本总量", marker_color='lightgreen'), secondary_y=False)
        fig_wc.add_trace(go.Scatter(x=years_label, y=wc_change, name="营运资本变动量", line=dict(color='red')), secondary_y=True)
        fig_wc.update_layout(title="营运资本规模与年度变动趋势")
        st.plotly_chart(fig_wc, use_container_width=True)
        st.info("💡 **怎么看：** 营运资本大幅增加通常意味着公司为了扩张投入了大量资金在存货和应收账款上。")

        # --- 维度三：现金流真实性对比 (保留原有指标) ---
        st.header("2️⃣ 现金流真实性对比")
        net_income = get_data_safe(is_stmt, ['Net Income'])
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow'])
        fcf = ocf + get_data_safe(cf_stmt, ['Capital Expenditure'])
        
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Bar(x=years_label, y=net_income, name="净利润", marker_color='silver'))
        fig_cash.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流(OCF)", line=dict(color='blue', width=3)))
        fig_cash.add_trace(go.Scatter(x=years_label, y=fcf, name="自由现金流(FCF)", line=dict(color='green', width=3)))
        st.plotly_chart(fig_cash, use_container_width=True)
        
        m1, m2 = st.columns(2)
        m1.metric("最新利润含金量 (OCF/NI)", f"{ocf.iloc[-1]/net_income.iloc[-1]:.2f}")
        m2.metric("最新FCF转换率 (FCF/NI)", f"{fcf.iloc[-1]/net_income.iloc[-1]:.2f}")

        # --- 维度四：财务安全与负债 ---
        st.header("3️⃣ 财务安全维度")
        assets = get_data_safe(bs_stmt, ['Total Assets'])
        liab = get_data_safe(bs_stmt, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        debt_ratio = (liab / assets) * 100
        st.write("**资产负债率趋势 (%)**")
        st.line_chart(debt_ratio)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成全维度深度报告"):
    analyze_v8(symbol)
