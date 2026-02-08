import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="综合财务多维透视平台", layout="wide")
st.title("🏛️ 综合财务多维透视平台 (10年全维度版)")

# 侧边栏
st.sidebar.header("数据控制台")
symbol = st.sidebar.text_input("股票代码 (如: AAPL, 600519.SS)", "AAPL").upper()

def comprehensive_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 抓取全量年度报表
        is_stmt = stock.income_stmt.sort_index(axis=1)
        cf_stmt = stock.cashflow.sort_index(axis=1)
        bs_stmt = stock.balance_sheet.sort_index(axis=1)
        info = stock.info
        
        if is_stmt.empty:
            st.error("无法获取数据，请检查网络或代码后缀。")
            return

        # 数据截取：取最近10年
        is_stmt = is_stmt.iloc[:, -10:]
        cf_stmt = cf_stmt.iloc[:, -10:]
        bs_stmt = bs_stmt.iloc[:, -10:]
        years = is_stmt.columns

        # --- 维度一：盈利性与增长分析 (优化比例尺) ---
        st.header("1️⃣ 盈利性与营收成长 (Growth & Profitability)")
        rev = is_stmt.loc['Total Revenue']
        net_income = is_stmt.loc['Net Income']
        rev_growth = rev.pct_change() * 100
        
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        # 营收柱状图
        fig1.add_trace(go.Bar(x=years, y=rev, name="营业收入", marker_color='royalblue', opacity=0.7), secondary_y=False)
        # 营收增长率折线
        fig1.add_trace(go.Scatter(x=years, y=rev_growth, name="营收增长率 %", line=dict(color='firebrick', width=3)), secondary_y=True)
        
        fig1.update_layout(title="营收规模与增长率趋势 (双轴优化)", hovermode="x unified")
        fig1.update_yaxes(title_text="营收金额 (单位: 货币)", secondary_y=False)
        fig1.update_yaxes(title_text="增长率 (%)", secondary_y=True, showgrid=False)
        st.plotly_chart(fig1, use_container_width=True)

        # 利润率双线图
        gp = is_stmt.loc['Gross Profit']
        gross_margin = (gp / rev) * 100
        net_margin = (net_income / rev) * 100
        
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=years, y=gross_margin, name="毛利率 %", line=dict(color='green', width=2), fill='tonexty'))
        fig2.add_trace(go.Scatter(x=years, y=net_margin, name="净利率 %", line=dict(color='darkred', width=3)))
        fig2.update_layout(title="盈利质量：毛利与净利趋势", yaxis_title="百分比 (%)", hovermode="x unified")
        st.plotly_chart(fig2, use_container_width=True)

        

        # --- 维度二：现金流健康度 (综合指标) ---
        st.header("2️⃣ 现金流维度 (Cash Flow Health)")
        ocf = cf_stmt.loc['Operating Cash Flow']
        capex = cf_stmt.loc['Capital Expenditure']
        fcf = ocf + capex
        cash_ratio = (ocf / rev) * 100 # 收现比
        
        fig3 = make_subplots(specs=[[{"secondary_y": True}]])
        fig3.add_trace(go.Bar(x=years, y=ocf, name="经营现金流"), secondary_y=False)
        fig3.add_trace(go.Bar(x=years, y=fcf, name="自由现金流"), secondary_y=False)
        fig3.add_trace(go.Scatter(x=years, y=cash_ratio, name="收现比 %", line=dict(color='purple', width=2)), secondary_y=True)
        
        fig3.update_layout(title="现金生成能力与收现比", barmode='group', hovermode="x unified")
        fig3.update_yaxes(title_text="现金流金额", secondary_y=False)
        fig3.update_yaxes(title_text="收现比 (%)", secondary_y=True, showgrid=False)
        st.plotly_chart(fig3, use_container_width=True)

        # --- 维度三：营运能力与效率 ---
        st.header("3️⃣ 营运效率维度 (Efficiency)")
        col_eff1, col_eff2 = st.columns(2)
        with col_eff1:
            try:
                receivables = bs_stmt.loc['Net Receivables']
                dso = (receivables / rev) * 365
                st.write("**应收账款周转天数 (DSO)**")
                st.line_chart(dso)
            except: st.info("暂无应收账款数据")
        with col_eff2:
            assets = bs_stmt.loc['Total Assets']
            asset_turnover = rev / assets
            st.write("**总资产周转率 (次)**")
            st.area_chart(asset_turnover)

        # --- 维度四：安全性与负债 ---
        st.header("4️⃣ 财务安全维度 (Safety)")
        total_liab = bs_stmt.loc['Total Liabilities Net Minority Interest']
        debt_ratio = (total_liab / assets) * 100
        current_assets = bs_stmt.loc['Current Assets']
        current_liab = bs_stmt.loc['Current Liabilities']
        
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=years, y=debt_ratio, name="资产负债率 %", fill='tozeroy'))
        fig4.add_trace(go.Scatter(x=years, y=(current_assets/current_liab), name="流动比率 (倍)", yaxis="y2"))
        fig4.update_layout(title="偿债能力趋势", yaxis_title="负债率 %", 
                          yaxis2=dict(title="流动比率", overlaying="y", side="right"), hovermode="x unified")
        st.plotly_chart(fig4, use_container_width=True)

        # --- 维度五：综合评分雷达图 (综合体系核心) ---
        st.divider()
        st.subheader("🏁 综合基本面雷达评分")
        # 归一化打分逻辑
        s_roe = min(info.get('returnOnEquity', 0) * 400, 100)
        s_growth = min(rev_growth.iloc[-1] * 2, 100) if not pd.isna(rev_growth.iloc[-1]) else 50
        s_cash = min((ocf.iloc[-1]/rev.iloc[-1])*400, 100) if rev.iloc[-1] !=0 else 0
        s_safety = max(100 - debt_ratio.iloc[-1], 0)
        s_eff = min(asset_turnover.iloc[-1] * 50, 100)

        categories = ['盈利能力(ROE)', '营收增长', '现金流质量', '财务安全性', '营运效率']
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(r=[s_roe, s_growth, s_cash, s_safety, s_eff], theta=categories, fill='toself', name='评分'))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
        st.plotly_chart(fig_radar)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成全维度深度报告"):
    comprehensive_analysis(symbol)
