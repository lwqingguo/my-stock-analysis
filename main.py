import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="十年多维财务透视系统", layout="wide")
st.title("🏛️ 十年多维财务深度透视与趋势平台")

# 侧边栏
st.sidebar.header("分析控制台")
symbol = st.sidebar.text_input("股票代码 (如: AAPL, MSFT, 600519.SS)", "AAPL").upper()
year_range = st.sidebar.slider("分析年限", 5, 10, 10)

def expert_analysis(ticker, years):
    try:
        stock = yf.Ticker(ticker)
        # 获取年度报表 (yfinance通常支持近4-10年数据)
        is_stmt = stock.income_stmt
        bs_stmt = stock.balance_sheet
        cf_stmt = stock.cashflow
        
        if is_stmt.empty:
            st.error("无法获取报表。请确认代码正确（美股直接输入代码，A股需后缀 .SS 或 .SZ）。")
            return

        # 1. 实时基本面看板
        info = stock.info
        st.header(f"📊 {info.get('longName', ticker)} 实时画像")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("市盈率 PE(TTM)", f"{info.get('trailingPE', 'N/A')}")
        c2.metric("市净率 PB", f"{info.get('priceToBook', 'N/A')}")
        c3.metric("总市值", f"${info.get('marketCap', 0)/1e9:.2f}B")
        c4.metric("五年平均ROE", f"{info.get('returnOnEquity', 0)*100:.2f}%")

        # --- 维度一：盈利能力 (含杜邦拆解指标) ---
        st.divider()
        st.subheader(f"💎 盈利性维度 ({years}年趋势)")
        # 整理数据 (取前n年)
        rev = is_stmt.loc['Total Revenue'].sort_index().tail(years)
        net = is_stmt.loc['Net Income'].sort_index().tail(years)
        gp = is_stmt.loc['Gross Profit'].sort_index().tail(years)
        
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=rev.index, y=rev, name="营收规模", marker_color='lightblue'))
        fig1.add_trace(go.Scatter(x=rev.index, y=(net/rev)*100, name="净利率 %", line=dict(color='orange')), secondary_y=True)
        fig1.add_trace(go.Scatter(x=rev.index, y=(gp/rev)*100, name="毛利率 %", line=dict(color='red', dash='dot')), secondary_y=True)
        fig1.update_layout(title="盈利规模与利润率变动趋势")
        st.plotly_chart(fig1, use_container_width=True)
        
        st.caption("**其他关键指标：** 销售费用率、管理费用率、研发投入占比 (R&D Ratio)")

        # --- 维度二：现金流健康度 (含收现比) ---
        st.subheader("💰 现金流维度 (质量与收现比)")
        ocf = cf_stmt.loc['Operating Cash Flow'].sort_index().tail(years)
        capex = cf_stmt.loc['Capital Expenditure'].sort_index().tail(years)
        fcf = ocf + capex
        
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=ocf.index, y=ocf, name="经营现金流"))
        fig2.add_trace(go.Scatter(x=ocf.index, y=fcf, name="自由现金流 (FCF)", fill='tonexty'))
        fig2.add_trace(go.Scatter(x=ocf.index, y=(ocf/rev)*100, name="收现比 % (OCF/Revenue)", line=dict(color='purple', width=3)))
        fig2.update_layout(title="现金流生成能力与收现比趋势")
        st.plotly_chart(fig2, use_container_width=True)

        # --- 维度三：营运能力与周转效率 ---
        st.subheader("⚙️ 营运效率维度")
        # 增加应收账款周转天数 (简化计算)
        try:
            receivables = bs_stmt.loc['Net Receivables'].sort_index().tail(years)
            turnover_days = (receivables / rev) * 365
            st.write("**应收账款周转天数 (DSO) 趋势**")
            st.line_chart(turnover_days)
            st.caption("天数越短，代表公司回款能力越强，坏账风险越低。")
        except:
            st.info("该股票应收账款数据缺失。")

        # --- 维度四：资产安全性与破产预警 ---
        st.subheader("🛡️ 偿债与安全性维度")
        assets = bs_stmt.loc['Total Assets'].sort_index().tail(years)
        liab = bs_stmt.loc['Total Liabilities Net Minority Interest'].sort_index().tail(years)
        current_assets = bs_stmt.loc['Current Assets'].sort_index().tail(years)
        current_liab = bs_stmt.loc['Current Liabilities'].sort_index().tail(years)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.write("**资产负债率趋势 (%)**")
            st.area_chart((liab/assets)*100)
        with col_s2:
            st.write("**流动比率 (Current Ratio)**")
            st.line_chart(current_assets/current_liab)
            st.caption("标准通常 > 1.5 为安全。")

        # --- 维度五：终极综合评分雷达图 ---
        st.divider()
        st.subheader("🏁 综合体检雷达图")
        
        # 指标标准化打分 (0-100)
        # 1. 盈利能力 (ROE)
        s_roe = min(info.get('returnOnEquity', 0) * 400, 100)
        # 2. 现金流 (收现比)
        s_cash = min((ocf.iloc[-1]/rev.iloc[-1]) * 400, 100) if rev.iloc[-1] !=0 else 0
        # 3. 成长性 (五年营收增长)
        s_growth = 100 if rev.iloc[-1] > rev.iloc[0] else 30
        # 4. 安全性 (负债率反转)
        s_safety = max(100 - (liab.iloc[-1]/assets.iloc[-1]*100), 0)
        # 5. 营运效率 (周转率)
        s_eff = min((rev.iloc[-1]/assets.iloc[-1]) * 100, 100)

        categories = ['盈利能力', '现金流质量', '营收成长性', '资产安全性', '营运效率']
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=[s_roe, s_cash, s_growth, s_safety, s_eff],
            theta=categories,
            fill='toself',
            marker=dict(color='gold')
        ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
        st.plotly_chart(fig_radar)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成十年深度透视"):
    expert_analysis(symbol, year_range)
