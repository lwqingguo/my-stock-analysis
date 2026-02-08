import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 网页基础配置
st.set_page_config(page_title="综合价值分析平台", layout="wide")
st.title("💎 全球股票综合价值分析平台")
st.markdown("---")

# 2. 侧边栏控制器
st.sidebar.header("控制台")
symbol = st.sidebar.text_input("代码 (例: NVDA, AAPL, 600519.SS)", "NVDA").upper()
analyze_btn = st.sidebar.button("开始全维度分析")

# 3. 核心分析函数
def full_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 获取三大报表
        annual_is = stock.annual_income_stmt
        annual_cf = stock.annual_cashflow
        annual_bs = stock.annual_balance_sheet
        info = stock.info

        if annual_is.empty:
            st.error("无法获取财务报表，请检查代码后缀是否正确。")
            return

        # --- 第一部分：实时画像 ---
        st.header(f"🏢 {info.get('longName', ticker)}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("当前股价", f"${info.get('currentPrice', 'N/A')}")
        c2.metric("市盈率 (PE)", info.get('trailingPE', 'N/A'))
        c3.metric("总市值", f"${info.get('marketCap', 0)/1e9:.2f}B")
        c4.metric("股息率", f"{info.get('dividendYield', 0)*100:.2f}%")

        # --- 第二部分：五年趋势对比 ---
        st.subheader("📈 核心财务指标五年趋势")
        
        # 数据整理
        dates = annual_is.columns
        net_income = annual_is.loc['Net Income'].sort_index()
        ocf = annual_cf.loc['Operating Cash Flow'].sort_index()
        capex = annual_cf.loc['Capital Expenditure'].sort_index()
        fcf = ocf + capex
        
        # 绘制利润与现金流对比图
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=net_income.index, y=net_income, name='净利润', line=dict(color='blue', width=4)))
        fig.add_trace(go.Scatter(x=fcf.index, y=fcf, name='自由现金流', line=dict(color='green', dash='dash')))
        fig.update_layout(title="利润 vs 现金流 (验证盈利真实性)", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # --- 第三部分：深度营运指标 ---
        st.subheader("🧩 营运效率与盈利质量")
        col_a, col_b = st.columns(2)
        
        with col_a:
            # ROE 趋势
            equity = annual_bs.loc['Stockholders Equity'].sort_index()
            roe = (net_income / equity) * 100
            st.write("**ROE (净资产收益率) 趋势 %**")
            st.line_chart(roe)
            
        with col_b:
            # 负债率趋势
            total_assets = annual_bs.loc['Total Assets'].sort_index()
            total_liab = annual_bs.loc['Total Liabilities Net Minority Interest'].sort_index()
            debt_ratio = (total_liab / total_assets) * 100
            st.write("**资产负债率 % 趋势**")
            st.area_chart(debt_ratio)

        # --- 第四部分：综合评估打分 (你的最终目标) ---
        st.markdown("---")
        st.subheader("🏆 智能综合价值评分")
        score = 0
        checks = []

        # 评分逻辑
        # 1. 现金流健康度
        if fcf.iloc[-1] > 0:
            score += 25
            checks.append("✅ 自由现金流为正 (25分)")
        # 2. 利润含金量
        if ocf.iloc[-1] > net_income.iloc[-1]:
            score += 25
            checks.append("✅ 利润含金量高：现金流 > 利润 (25分)")
        # 3. 盈利能力
        if roe.iloc[-1] > 15:
            score += 25
            checks.append("✅ ROE > 15%，具备超强盈利能力 (25分)")
        # 4. 负债安全性
        if debt_ratio.iloc[-1] < 60:
            score += 25
            checks.append("✅ 资产负债率低于 60%，财务稳健 (25分)")

        # 显示总得分
        st.info(f"### 综合得分：{score} / 100")
        for c in checks:
            st.write(c)
        
        if score >= 75:
            st.success("🌟 结论：优质品种，财务指标非常健康！")
        elif score >= 50:
            st.warning("⚖️ 结论：基本面尚可，建议关注负债或现金流变化。")
        else:
            st.error("🚨 结论：存在重大财务隐患，请谨慎投资。")

    except Exception as e:
        st.error(f"分析出错: {e}")

if analyze_btn:
    full_analysis(symbol)
