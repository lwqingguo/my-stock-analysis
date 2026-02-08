import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 页面配置
st.set_page_config(page_title="高级财务趋势分析系统", layout="wide")
st.title("📈 股票历史趋势深度对比平台")

# 侧边栏
st.sidebar.header("数据控制台")
symbol = st.sidebar.text_input("输入代码 (例: AAPL, NVDA, 600519.SS)", "AAPL").upper()

def get_trend_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        # 获取年度损益表和现金流量表 (通常包含最近4-5年)
        annual_is = stock.annual_income_stmt
        annual_cf = stock.annual_cashflow
        annual_bs = stock.annual_balance_sheet
        info = stock.info

        st.header(f"核心指标五年趋势：{info.get('longName', ticker)}")

        # --- 1. 数据清洗与整理 ---
        # 提取净利润趋势
        net_income_trend = annual_is.loc['Net Income'].sort_index()
        # 提取经营现金流趋势
        ocf_trend = annual_cf.loc['Operating Cash Flow'].sort_index()
        # 计算自由现金流趋势 (OCF + CapEx)
        capex_trend = annual_cf.loc['Capital Expenditure'].sort_index()
        fcf_trend = ocf_trend + capex_trend

        # --- 2. 趋势图表展示 ---
        st.subheader("💰 盈利与现金流增长趋势")
        trend_data = pd.DataFrame({
            '净利润': net_income_trend,
            '自由现金流 (FCF)': fcf_trend
        })
        # 使用折线图清晰展示趋势
        st.line_chart(trend_data)

        # --- 3. ROE 深度挖掘 ---
        st.subheader("🎯 股东权益报酬率 (ROE) 趋势")
        try:
            # ROE = 净利润 / 股东权益
            equity = annual_bs.loc['Stockholders Equity'].sort_index()
            roe_trend = (net_income_trend / equity) * 100
            
            fig_roe = go.Figure()
            fig_roe.add_trace(go.Scatter(x=roe_trend.index, y=roe_trend.values, mode='lines+markers', name='ROE %'))
            fig_roe.update_layout(yaxis_title="百分比 (%)", hovermode="x unified")
            st.plotly_chart(fig_roe, use_container_width=True)
            
            # 趋势解读
            latest_roe = roe_trend.iloc[-1]
            prev_roe = roe_trend.iloc[-2]
            if latest_roe > prev_roe:
                st.success(f"📈 ROE 正在改善：从 {prev_roe:.2f}% 提升至 {latest_roe:.2f}%")
            else:
                st.warning(f"📉 ROE 出现下滑：从 {prev_roe:.2f}% 降至 {latest_roe:.2f}%，需警惕盈利效率下降。")
        except:
            st.info("该股票暂无足够的历史资产数据计算 ROE 趋势。")

        # --- 4. 营运指标看板 ---
        st.subheader("🧱 资产结构健康度")
        col1, col2 = st.columns(2)
        with col1:
            # 毛利率趋势
            gross_margin_trend = (annual_is.loc['Gross Profit'] / annual_is.loc['Total Revenue']) * 100
            st.write("**毛利率 (%) 趋势**")
            st.area_chart(gross_margin_trend.sort_index())
        
        with col2:
            # 负债率趋势
            debt_trend = (annual_bs.loc['Total Liabilities Net Minority Interest'] / annual_bs.loc['Total Assets']) * 100
            st.write("**资产负债率 (%) 趋势**")
            st.line_chart(debt_trend.sort_index())

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成五年趋势报告"):
    get_trend_analysis(symbol)
