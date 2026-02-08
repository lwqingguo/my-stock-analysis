import streamlit as st
import yfinance as yf
import pandas as pd

# 设置页面
st.set_page_config(page_title="高级财务分析系统", layout="wide")
st.title("🛡️ 综合股票价值评估平台 (专业版)")

# 侧边栏
st.sidebar.header("数据控制台")
symbol = st.sidebar.text_input("输入代码 (例: AAPL, 600519.SS)", "AAPL").upper()

def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 获取三大报表
        is_stmt = stock.income_stmt        # 损益表
        bs_stmt = stock.balance_sheet     # 资产负债表
        cf_stmt = stock.cashflow          # 现金流量表
        info = stock.info

        # --- 1. 核心看板 ---
        st.header(f"📊 {info.get('longName', ticker)} 财务画像")
        cols = st.columns(4)
        cols[0].metric("ROE (净资产收益率)", f"{info.get('returnOnEquity', 0)*100:.2f}%")
        cols[1].metric("毛利率", f"{info.get('grossMargins', 0)*100:.2f}%")
        cols[2].metric("市盈率 (PE)", f"{info.get('trailingPE', 'N/A')}")
        cols[3].metric("总资产负债率", f"{info.get('debtToEquity', 0):.2f}")

        # --- 2. 现金流与利润含金量分析 ---
        st.subheader("🔗 现金流与盈利深度对比")
        # 提取最新两年的净利润和经营现金流
        net_income = is_stmt.loc['Net Income']
        ocf = cf_stmt.loc['Operating Cash Flow']
        
        comparison_df = pd.DataFrame({
            '净利润': net_income,
            '经营现金流': ocf
        })
        st.bar_chart(comparison_df)

        # --- 3. 智能评分逻辑 (你的目标核心) ---
        st.subheader("🏆 综合投资价值评分")
        score = 0
        reasons = []

        # 评分标准 A: 现金流
        fcf = ocf.iloc[0] + cf_stmt.loc['Capital Expenditure'].iloc[0]
        if fcf > 0:
            score += 30
            reasons.append("✅ 自由现金流为正 (30分)")
        
        # 评分标准 B: ROE
        roe = info.get('returnOnEquity', 0)
        if roe > 0.15:
            score += 30
            reasons.append("✅ ROE 大于 15%，盈利能力强 (30分)")
        
        # 评分标准 C: 负债率
        debt_ratio = info.get('debtToEquity', 200) # 默认设高
        if debt_ratio < 100:
            score += 20
            reasons.append("✅ 负债水平健康 (20分)")

        # 评分标准 D: 利润含金量
        if ocf.iloc[0] > net_income.iloc[0]:
            score += 20
            reasons.append("✅ 利润含金量高：现金 > 利润 (20分)")

        # 显示总分
        st.info(f"### 最终得分：{score} / 100")
        for r in reasons:
            st.write(r)

        if score >= 80:
            st.success("🌟 结论：该公司财务表现极佳，极具研究价值！")
        elif score >= 50:
            st.warning("⚖️ 结论：财务状况中等，建议结合行业趋势观察。")
        else:
            st.error("🚨 结论：多项财务指标异常，需谨慎对待。")

    except Exception as e:
        st.error(f"分析失败，原因：{e}")

if st.sidebar.button("一键生成深度分析"):
    analyze_stock(symbol)
