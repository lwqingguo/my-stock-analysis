import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="综合财务透视系统-十年版", layout="wide")

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

def expert_financial_system(ticker):
    try:
        # 获取股票对象
        stock = yf.Ticker(ticker)
        
        # --- 核心改进：尝试抓取尽可能多的年度数据 (最多10年) ---
        is_stmt = stock.get_income_stmt(as_dict=False).sort_index(axis=1)
        cf_stmt = stock.get_cashflow(as_dict=False).sort_index(axis=1)
        bs_stmt = stock.get_balance_sheet(as_dict=False).sort_index(axis=1)
        info = stock.info
        
        # 获取10年股价历史
        history = stock.history(period="10y")
        annual_price = history['Close'].resample('YE').last()
        annual_price.index = annual_price.index.year

        # 截取最近10年数据
        is_stmt = is_stmt.iloc[:, -10:]
        cf_stmt = cf_stmt.iloc[:, -10:]
        bs_stmt = bs_stmt.iloc[:, -10:]
        years = is_stmt.columns
        years_label = [str(y.year) if hasattr(y, 'year') else str(y) for y in years]

        # --- 报告头部 ---
        st.title(f"🏛️ 十年多维财务透视报告：{info.get('longName', ticker)}")
        st.markdown(f"**股票代码：** `{ticker}` | **行业：** {info.get('industry', 'N/A')} | **地区：** {info.get('country', 'N/A')}")
        st.divider()

        # --- 1. 估值水平 ---
        st.header("1️⃣ 估值水平 (Valuation)")
        eps = is_stmt.loc['Diluted EPS'] if 'Diluted EPS' in is_stmt.index else is_stmt.loc['Basic EPS']
        pe_list = []
        for y in years:
            y_val = y.year if hasattr(y, 'year') else int(y)
            if y_val in annual_price.index:
                pe_list.append(annual_price[y_val] / eps[y])
            else: pe_list.append(None)

        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=years_label, y=annual_price.values[-len(years):], name="年末股价", line=dict(color='black', width=3)), secondary_y=False)
        fig_val.add_trace(go.Scatter(x=years_label, y=pe_list, name="静态PE", line=dict(color='orange', dash='dot')), secondary_y=True)
        st.plotly_chart(fig_val, use_container_width=True)
        st.info("💡 **怎么看：** 观察股价上涨是由盈利驱动(PE平稳)还是由情绪驱动(PE飙升)。PE处于历史低位通常意味着估值具备吸引力。")

        # --- 2. 盈利与成长 ---
        st.header("2️⃣ 盈利与成长 (Growth)")
        rev = is_stmt.loc['Total Revenue']
        net_income = is_stmt.loc['Net Income']
        rev_growth = rev.pct_change() * 100
        
        fig_grow = make_subplots(specs=[[{"secondary_y": True}]])
        fig_grow.add_trace(go.Bar(x=years_label, y=rev, name="营收", marker_color='royalblue', opacity=0.7), secondary_y=False)
        fig_grow.add_trace(go.Scatter(x=years_label, y=rev_growth, name="营收增速 %", line=dict(color='firebrick', width=2)), secondary_y=True)
        st.plotly_chart(fig_grow, use_container_width=True)
        
        # 利润率
        gp = is_stmt.loc['Gross Profit']
        fig_margin = go.Figure()
        fig_margin.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率 %", line=dict(color='green')))
        fig_margin.add_trace(go.Scatter(x=years_label, y=(net_income/rev)*100, name="净利率 %", line=dict(color='darkred')))
        st.plotly_chart(fig_margin, use_container_width=True)
        st.info("💡 **怎么看：** 营收持续增长且毛利率稳定代表公司有竞争护城河；若净利率下滑而毛利率稳定，说明内部费用控制出现问题。")

        # --- 3. 现金流真实性 (核心改进) ---
        st.header("3️⃣ 现金流真实性与利润含金量")
        ocf = cf_stmt.loc['Operating Cash Flow']
        fcf = ocf + cf_stmt.loc['Capital Expenditure']
        
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Bar(x=years_label, y=net_income, name="净利润", marker_color='lightgrey'))
        fig_cash.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流(OCF)", line=dict(color='blue', width=3)))
        fig_cash.add_trace(go.Scatter(x=years_label, y=fcf, name="自由现金流(FCF)", line=dict(color='green', width=3)))
        st.plotly_chart(fig_cash, use_container_width=True)
        
        # 增加数字对比 (利润含金量)
        st.markdown("**🔍 利润转换效率 (最新财年)：**")
        c_k1, c_k2, c_k3 = st.columns(3)
        quality_ratio = ocf.iloc[-1] / net_income.iloc[-1]
        fcf_ratio = fcf.iloc[-1] / net_income.iloc[-1]
        c_k1.metric("利润含金量 (OCF/Net Income)", f"{quality_ratio:.2f}")
        c_k2.metric("现金转换率 (FCF/Net Income)", f"{fcf_ratio:.2f}")
        c_k3.write("👉 *指标含义：> 1.0 代表公司赚的是‘真钱’；若 < 0.8 则需警惕‘纸面富贵’。*")
        st.info("💡 **怎么看：** 经营现金流(蓝线)长期位于净利润(灰柱)上方是最理想状态，代表利润质量极高。")

        # --- 4. 营运效率 ---
        st.header("4️⃣ 营运效率 (Operating Efficiency)")
        rec_keys = ['Receivables', 'Net Receivables', 'Accounts Receivable']
        receivables = next((bs_stmt.loc[k] for k in rec_keys if k in bs_stmt.index), None)
        
        c_e1, c_e2 = st.columns(2)
        with c_e1:
            if receivables is not None:
                st.write("**应收账款周转率 (营收/应收账款)**")
                st.line_chart(rev / receivables)
            else: st.warning("应收账款数据缺失")
        with c_e2:
            st.write("**总资产周转率 (次)**")
            st.area_chart(rev / bs_stmt.loc['Total Assets'])
        st.info("💡 **怎么看：** 周转率越高，说明资产运转越快。如果营收增加但应收账款周转率大幅下降，警惕坏账风险。")

        # --- 5. 财务安排与安全性 ---
        st.header("5️⃣ 财务安排与安全性 (Safety)")
        assets = bs_stmt.loc['Total Assets']
        liab = bs_stmt.loc['Total Liabilities Net Minority Interest']
        debt_ratio = (liab / assets) * 100
        
        fig_safety = make_subplots(specs=[[{"secondary_y": True}]])
        fig_safety.add_trace(go.Scatter(x=years_label, y=debt_ratio, name="资产负债率 %", line=dict(color='black', width=3)), secondary_y=False)
        fig_safety.add_trace(go.Scatter(x=years_label, y=(assets/bs_stmt.loc['Stockholders Equity']), name="权益乘数", line=dict(color='purple', dash='dot')), secondary_y=True)
        st.plotly_chart(fig_safety, use_container_width=True)
        st.info("💡 **怎么看：** 资产负债率应结合行业看，制造业通常在 40%-60%。权益乘数越高，代表公司杠杆越大。")

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成十年深度报告"):
    expert_financial_system(symbol)
