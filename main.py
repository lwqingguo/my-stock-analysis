import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="十年深度财务透视", layout="wide")
st.title("🏛️ 十年多维财务分析平台 (专业增强版)")

# 侧边栏
st.sidebar.header("数据控制台")
symbol = st.sidebar.text_input("股票代码 (如: AAPL, 600519.SS)", "AAPL").upper()

def analysis_v3(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 显式抓取年度报表
        is_stmt = stock.income_stmt  # 损益表
        cf_stmt = stock.cashflow     # 现金流表
        bs_stmt = stock.balance_sheet  # 资产负债表
        
        if is_stmt.empty:
            st.error("无法获取报表数据，请检查网络或代码后缀。")
            return

        # 1. 营收与盈利性分析 (营收柱状图 + 营收增长率折线图)
        st.header("1️⃣ 营收规模与成长速度")
        # 整理数据并按年份正序排列
        rev = is_stmt.loc['Total Revenue'].sort_index()
        rev_growth = rev.pct_change() * 100  # 计算环比增长率
        
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=rev.index, y=rev, name="营业收入 (柱状)", marker_color='#4169E1'), secondary_y=False)
        fig1.add_trace(go.Scatter(x=rev.index, y=rev_growth, name="营收增长率 % (折线)", line=dict(color='#FF4500', width=3)), secondary_y=True)
        fig1.update_layout(title="历年营收与增长率趋势 (Revenue & Growth Rate)", hovermode="x unified")
        fig1.update_yaxes(title_text="营收规模", secondary_y=False)
        fig1.update_yaxes(title_text="增长率 %", secondary_y=True)
        st.plotly_chart(fig1, use_container_width=True)

        # 2. 利润率对比 (毛利率 + 净利率折线图)
        st.header("2️⃣ 利润率趋势对比")
        net_income = is_stmt.loc['Net Income'].sort_index()
        gp = is_stmt.loc['Gross Profit'].sort_index()
        
        gross_margin = (gp / rev) * 100
        net_margin = (net_income / rev) * 100
        
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=rev.index, y=gross_margin, name="毛利率 %", line=dict(color='#228B22', width=2), fill='tonexty'))
        fig2.add_trace(go.Scatter(x=rev.index, y=net_margin, name="净利率 %", line=dict(color='#8B0000', width=3)))
        fig2.update_layout(title="盈利质量：毛利与净利双线走势 (Margins Analysis)", hovermode="x unified")
        st.plotly_chart(fig2, use_container_width=True)
        
        

        # 3. 营运能力指标 (应收账款与周转效率)
        st.header("3️⃣ 营运与周转能力")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            try:
                receivables = bs_stmt.loc['Net Receivables'].sort_index()
                dso = (receivables / rev) * 365
                st.write("**应收账款周转天数 (DSO)**")
                st.line_chart(dso)
            except: st.info("暂无应收账款数据")
        with col_c2:
            assets = bs_stmt.loc['Total Assets'].sort_index()
            turnover = rev / assets
            st.write("**总资产周转率**")
            st.area_chart(turnover)

        # 4. 现金流深度体检 (收现比与 FCF)
        st.header("4️⃣ 现金流健康度")
        ocf = cf_stmt.loc['Operating Cash Flow'].sort_index()
        capex = cf_stmt.loc['Capital Expenditure'].sort_index()
        fcf = ocf + capex
        
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(x=rev.index, y=ocf, name="经营现金流"))
        fig4.add_trace(go.Bar(x=rev.index, y=fcf, name="自由现金流"))
        fig4.add_trace(go.Scatter(x=rev.index, y=(ocf/rev)*100, name="收现比 %", line=dict(color='purple')))
        fig4.update_layout(title="经营现金流、自由现金流与收现比趋势")
        st.plotly_chart(fig4, use_container_width=True)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成十年全维度报告"):
    analysis_v3(symbol)
