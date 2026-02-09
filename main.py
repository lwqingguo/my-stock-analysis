import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="综合财务透视系统-旗舰版", layout="wide")

# 2. 侧边栏：内置知名示例
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
    """安全获取报表中的行数据，适配不同命名习惯"""
    for k in keys:
        if k in df.index:
            return df.loc[k]
    return None

def analyze_v7(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 抓取年度报表 (尽可能多取)
        is_stmt = stock.income_stmt.sort_index(axis=1)
        cf_stmt = stock.cashflow.sort_index(axis=1)
        bs_stmt = stock.balance_sheet.sort_index(axis=1)
        info = stock.info
        
        # 10年股价历史用于估值
        history = stock.history(period="10y")
        annual_price = history['Close'].resample('YE').last()
        annual_price.index = annual_price.index.year

        # 截取最近10年
        is_stmt = is_stmt.iloc[:, -10:]
        cf_stmt = cf_stmt.iloc[:, -10:]
        bs_stmt = bs_stmt.iloc[:, -10:]
        years = is_stmt.columns
        years_label = [str(y.year) if hasattr(y, 'year') else str(y) for y in years]

        # --- 报告头部 ---
        st.title(f"🏛️ 综合财务透视报告：{info.get('longName', ticker)}")
        st.markdown(f"**行业：** {info.get('industry', 'N/A')} | **币种：** {info.get('currency', 'N/A')}")
        st.divider()

        # --- 1. 估值水平 ---
        st.header("1️⃣ 估值水平 (Valuation Analysis)")
        # 适配 EPS 键名防止报错
        eps = get_data_safe(is_stmt, ['Diluted EPS', 'Basic EPS', 'EPS'])
        
        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=years_label, y=annual_price.values[-len(years):], name="年末股价", line=dict(color='black', width=3)), secondary_y=False)
        
        if eps is not None:
            pe_list = [annual_price[y.year] / eps[y] if y.year in annual_price.index and eps[y] != 0 else None for y in years]
            fig_val.add_trace(go.Scatter(x=years_label, y=pe_list, name="静态PE", line=dict(color='orange', dash='dot')), secondary_y=True)
        
        fig_val.update_layout(title="十年股价与 PE 估值趋势", hovermode="x unified")
        st.plotly_chart(fig_val, use_container_width=True)
        st.info("💡 **专家解读：** 股价(黑线)反映市场情绪，PE(橘线)反映估值高低。理想状态是盈利增长带动股价上涨，而 PE 保持平稳。")

        # --- 2. 盈利与成长 ---
        st.header("2️⃣ 盈利与成长 (Growth & Margins)")
        rev = get_data_safe(is_stmt, ['Total Revenue'])
        net_income = get_data_safe(is_stmt, ['Net Income'])
        gp = get_data_safe(is_stmt, ['Gross Profit'])
        
        col1, col2 = st.columns(2)
        with col1:
            rev_growth = rev.pct_change() * 100
            fig_g = make_subplots(specs=[[{"secondary_y": True}]])
            fig_g.add_trace(go.Bar(x=years_label, y=rev, name="营收"), secondary_y=False)
            fig_g.add_trace(go.Scatter(x=years_label, y=rev_growth, name="增速 %"), secondary_y=True)
            st.plotly_chart(fig_g, use_container_width=True)
        with col2:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率 %", fill='tonexty'))
            fig_m.add_trace(go.Scatter(x=years_label, y=(net_income/rev)*100, name="净利率 %"))
            st.plotly_chart(fig_m, use_container_width=True)
        st.info("💡 **专家解读：** 营收是规模，利润率是效率。如果营收涨但毛利率跌，说明产品竞争力在下降，可能陷入价格战。")

        # --- 3. 现金流真实性 (核心重点) ---
        st.header("3️⃣ 现金流真实性对比 (Profit Quality)")
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow'])
        capex = get_data_safe(cf_stmt, ['Capital Expenditure'])
        fcf = ocf + capex
        
        fig_c = go.Figure()
        fig_c.add_trace(go.Bar(x=years_label, y=net_income, name="净利润", marker_color='lightgrey'))
        fig_c.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流", line=dict(color='blue', width=3)))
        fig_c.add_trace(go.Scatter(x=years_label, y=fcf, name="自由现金流", line=dict(color='green', width=3)))
        st.plotly_chart(fig_c, use_container_width=True)
        
        # 关键比率显化
        st.markdown("**📊 现金流含金量指标 (最新财年)：**")
        k1, k2, k3 = st.columns(3)
        quality = ocf.iloc[-1] / net_income.iloc[-1]
        fcf_to_ni = fcf.iloc[-1] / net_income.iloc[-1]
        k1.metric("盈利含金量 (OCF/NI)", f"{quality:.2f}")
        k2.metric("FCF 转换率 (FCF/NI)", f"{fcf_to_ni:.2f}")
        k3.metric("资本开支/OCF", f"{abs(capex.iloc[-1])/ocf.iloc[-1]:.2%}")
        st.info("💡 **专家解读：** 蓝线(OCF)应长期高于灰柱(净利润)，代表钱真实到账。绿线(FCF)是剔除设备更新支出后真正可分红的钱。")

        # --- 4. 营运效率 ---
        st.header("4️⃣ 营运效率 (Operating Efficiency)")
        receivables = get_data_safe(bs_stmt, ['Net Receivables', 'Receivables', 'Accounts Receivable'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        
        c_e1, c_e2 = st.columns(2)
        with c_e1:
            if receivables is not None:
                st.write("**应收账款周转率 (营收/应收)**")
                st.line_chart(rev / receivables)
        with c_e2:
            st.write("**总资产周转率 (次)**")
            st.area_chart(rev / get_data_safe(bs_stmt, ['Total Assets']))
        st.info("💡 **专家解读：** 应收账款周转率越高，回款越快。如果周转率暴跌，警惕利润只是堆积在账面上的数字。")

        # --- 5. 财务安全性 ---
        st.header("5️⃣ 财务安全性 (Financial Safety)")
        assets = get_data_safe(bs_stmt, ['Total Assets'])
        liab = get_data_safe(bs_stmt, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
        debt_ratio = (liab / assets) * 100
        
        fig_s = go.Figure()
        fig_s.add_trace(go.Scatter(x=years_label, y=debt_ratio, name="资产负债率 %", line=dict(color='black', width=3)))
        st.plotly_chart(fig_s, use_container_width=True)
        st.info("💡 **专家解读：** 资产负债率不仅要看绝对值，更要看趋势。持续攀升的负债率配合下降的现金流是极其危险的信号。")

    except Exception as e:
        st.error(f"分析出错，错误详情: {e}")

if st.sidebar.button("生成全维度十年报告"):
    analyze_v7(symbol)
