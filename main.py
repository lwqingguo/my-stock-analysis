import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="专业级财务多维分析平台", layout="wide")
st.title("⚖️ 专业级财务多维综合分析系统")

# 2. 侧边栏
st.sidebar.header("搜索配置")
symbol = st.sidebar.text_input("股票代码 (如: AAPL, NVDA, 600519.SS)", "AAPL").upper()
period = st.sidebar.slider("分析年限", 3, 5, 5)

def professional_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 预抓取所有报表
        is_stmt = stock.annual_income_stmt
        bs_stmt = stock.annual_balance_sheet
        cf_stmt = stock.annual_cashflow
        info = stock.info

        if is_stmt.empty:
            st.error("数据调取失败，请检查代码后缀是否正确（美股无后缀，A股加 .SS 或 .SZ）。")
            return

        # --- 维度一：盈利能力 (Profitability) ---
        st.header("1. 盈利能力与质量趋势")
        col1, col2 = st.columns(2)
        
        with col1:
            # 利润率趋势
            revenue = is_stmt.loc['Total Revenue'].sort_index()
            net_income = is_stmt.loc['Net Income'].sort_index()
            margin = (net_income / revenue) * 100
            
            fig_margin = go.Figure()
            fig_margin.add_trace(go.Bar(x=revenue.index, y=revenue, name='总营收', marker_color='lightgrey'))
            fig_margin.add_trace(go.Scatter(x=margin.index, y=margin, name='净利率 %', yaxis='y2', line=dict(color='orange', width=3)))
            fig_margin.update_layout(
                title="营收与净利率走势",
                yaxis2=dict(title="净利率 %", overlaying='y', side='right'),
                hovermode="x unified"
            )
            st.plotly_chart(fig_margin, use_container_width=True)

        with col2:
            # ROE 拆解
            equity = bs_stmt.loc['Stockholders Equity'].sort_index()
            roe = (net_income / equity) * 100
            st.write("**ROE (净资产收益率) 深度趋势**")
            st.line_chart(roe)
            st.info(f"当前 ROE: {roe.iloc[-1]:.2f}% (行业基准通常为 15%)")

        # --- 维度二：现金流结构 (Cash Flow Structure) ---
        st.header("2. 现金流健康度分析")
        # 经营、投资、筹资现金流对比
        ocf = cf_stmt.loc['Operating Cash Flow'].sort_index()
        icf = cf_stmt.loc['Investing Cash Flow'].sort_index()
        fcf_activity = cf_stmt.loc['Financing Cash Flow'].sort_index()
        
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Bar(x=ocf.index, y=ocf, name='经营现金流 (造血)', marker_color='green'))
        fig_cf.add_trace(go.Bar(x=icf.index, y=icf, name='投资现金流 (扩张)', marker_color='red'))
        fig_cf.add_trace(go.Bar(x=fcf_activity.index, y=fcf_activity, name='筹资现金流 (输血)', marker_color='blue'))
        fig_cf.update_layout(barmode='group', title="现金流三维度对比 (判断公司生命周期)")
        st.plotly_chart(fig_cf, use_container_width=True)
        
        # 自由现金流 FCF
        capex = cf_stmt.loc['Capital Expenditure'].sort_index()
        fcf = ocf + capex
        st.write(f"**最新自由现金流 (FCF):** ${fcf.iloc[-1]/1e9:.2f} Billion")

        # --- 维度三：营运能力与风险 (Operating & Risk) ---
        st.header("3. 营运效率与资产安全性")
        c1, c2 = st.columns(2)
        
        with c1:
            # 资产周转率 (营收 / 总资产)
            assets = bs_stmt.loc['Total Assets'].sort_index()
            turnover = revenue / assets
            st.write("**总资产周转率 (次数)**")
            st.line_chart(turnover)
            st.caption("反映管理层利用资产产生销售收入的效率")

        with c2:
            # 偿债能力：流动比率
            current_assets = bs_stmt.loc['Current Assets'].sort_index()
            current_liab = bs_stmt.loc['Current Liabilities'].sort_index()
            current_ratio = current_assets / current_liab
            st.write("**流动比率 (Current Ratio)**")
            st.area_chart(current_ratio)
            st.caption("通常 > 1.5 表示短期偿债能力较强")

        # --- 维度四：综合评分系统 ---
        st.markdown("---")
        st.subheader("🏁 最终投资结论")
        
        final_score = 0
        analysis_notes = []

        # 逻辑：五年盈利增长
        if net_income.iloc[-1] > net_income.iloc[0]:
            final_score += 25
            analysis_notes.append("✅ 盈利成长：五年净利润实现正增长。")
        
        # 逻辑：现金流真实性
        if ocf.iloc[-1] > net_income.iloc[-1]:
            final_score += 25
            analysis_notes.append("✅ 盈利质量：经营现金流 > 净利润，利润含金量高。")
            
        # 逻辑：ROE 门槛
        if roe.iloc[-1] > 15:
            final_score += 25
            analysis_notes.append("✅ 盈利效率：ROE 维持在 15% 以上，属于绩优股特征。")

        # 逻辑：负债风险
        debt_to_equity = info.get('debtToEquity', 200)
        if debt_to_equity < 100:
            final_score += 25
            analysis_notes.append("✅ 财务杠杆：负债率处于安全区间。")

        st.info(f"### 综合价值评分: {final_score} / 100")
        for note in analysis_notes:
            st.write(note)

    except Exception as e:
        st.error(f"分析失败，由于: {e}")

if st.sidebar.button("生成多维深度报告"):
    professional_analysis(symbol)
