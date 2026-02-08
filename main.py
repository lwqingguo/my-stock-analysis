import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="全维度股票透视系统", layout="wide")
st.title("🛡️ 全维度财务综合分析与趋势平台")

# 侧边栏
st.sidebar.header("分析配置")
symbol = st.sidebar.text_input("股票代码 (美股:AAPL, A股:600519.SS)", "AAPL").upper()

def get_pro_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 获取报表 (注意：这里使用了兼容性更好的新版接口)
        is_stmt = stock.income_stmt
        bs_stmt = stock.balance_sheet
        cf_stmt = stock.cashflow
        info = stock.info

        if is_stmt.empty:
            st.error("无法获取财务报表。提示：美股AAPL，沪市600519.SS，深市000001.SZ")
            return

        # --- 核心指标看板 ---
        st.header(f"📊 {info.get('longName', ticker)} 核心透视")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("ROE (净资产收益率)", f"{info.get('returnOnEquity', 0)*100:.2f}%")
        m2.metric("净利率", f"{info.get('netIncomeToCommon', 0)/info.get('totalRevenue', 1)*100:.2f}%")
        m3.metric("资产负债率", f"{info.get('debtToEquity', 0):.2f}%")
        m4.metric("总资产周转率", f"{info.get('totalRevenue', 0)/info.get('totalAssets', 1):.2f}")

        # --- 维度一：盈利与成长 (多维度趋势) ---
        st.subheader("1️⃣ 盈利能力与规模增长 (5年趋势)")
        # 整理数据
        rev = is_stmt.loc['Total Revenue'].sort_index()
        net = is_stmt.loc['Net Income'].sort_index()
        
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=rev.index, y=rev, name="总营收"), secondary_y=False)
        fig1.add_trace(go.Scatter(x=net.index, y=net, name="净利润", line=dict(color='red', width=3)), secondary_y=True)
        fig1.update_layout(title="营收与利润增长同步性分析")
        st.plotly_chart(fig1, use_container_width=True)

        # --- 维度二：现金流质量 (真金白银分析) ---
        st.subheader("2️⃣ 现金流结构与盈利含金量")
        ocf = cf_stmt.loc['Operating Cash Flow'].sort_index()
        capex = cf_stmt.loc['Capital Expenditure'].sort_index()
        fcf = ocf + capex
        
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=net.index, y=net, name="账面利润", fill='tonexty'))
        fig2.add_trace(go.Scatter(x=ocf.index, y=ocf, name="经营现金流", line=dict(dash='dot')))
        fig2.add_trace(go.Bar(x=fcf.index, y=fcf, name="自由现金流 (FCF)"))
        fig2.update_layout(title="利润 vs 现金流 (判断利润是否有水分)")
        st.plotly_chart(fig2, use_container_width=True)

        # --- 维度三：营运能力与资产效率 ---
        st.subheader("3️⃣ 营运能力指标趋势")
        c1, c2 = st.columns(2)
        with c1:
            # 杜邦分析核心：资产效率
            assets = bs_stmt.loc['Total Assets'].sort_index()
            asset_turnover = rev / assets
            st.write("**总资产周转率趋势**")
            st.line_chart(asset_turnover)
        with c2:
            # 毛利率走势
            gp = is_stmt.loc['Gross Profit'].sort_index()
            g_margin = (gp / rev) * 100
            st.write("**产品毛利率趋势 (%)**")
            st.area_chart(g_margin)

        # --- 维度四：综合五角雷达图 (终极综合分析) ---
        st.markdown("---")
        st.subheader("🎯 综合基本面雷达图 (全维度体检)")
        
        # 简单的评分逻辑映射到 0-100
        score_roe = min(info.get('returnOnEquity', 0) * 400, 100) # ROE 25%满分
        score_margin = min((info.get('netIncomeToCommon', 0)/info.get('totalRevenue', 1)) * 400, 100)
        score_cash = 100 if ocf.iloc[-1] > net.iloc[-1] else 50
        score_safety = max(100 - info.get('debtToEquity', 100), 0)
        score_growth = 100 if net.iloc[-1] > net.iloc[0] else 30

        categories = ['盈利能力(ROE)', '产品利润率', '现金流质量', '财务安全性', '历史成长性']
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=[score_roe, score_margin, score_cash, score_safety, score_growth],
            theta=categories,
            fill='toself',
            name='综合评分'
        ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
        st.plotly_chart(fig_radar)

    except Exception as e:
        st.error(f"分析失败，由于: {e}")
        st.info("提示：请确保安装了最新版 yfinance (pip install yfinance --upgrade)")

if st.sidebar.button("生成全维度深度分析"):
    get_pro_analysis(symbol)
