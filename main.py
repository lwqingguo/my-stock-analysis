import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 页面设置
st.set_page_config(page_title="高级价值分析系统", layout="wide")
st.title("💎 全球股票综合价值分析平台")
st.markdown("---")

# 2. 侧边栏
st.sidebar.header("配置中心")
symbol = st.sidebar.text_input("代码 (例: NVDA, AAPL, 600519.SS)", "NVDA").upper()
btn = st.sidebar.button("生成深度体检报告")

def safe_get(df, index_name):
    """安全获取数据的辅助函数"""
    try:
        return df.loc[index_name]
    except:
        return None

if btn:
    with st.spinner('正在同步全球金融数据库...'):
        try:
            stock = yf.Ticker(symbol)
            
            # 使用最新标准的属性名
            is_stmt = stock.income_stmt    # 损益表
            cf_stmt = stock.cashflow       # 现金流表
            bs_stmt = stock.balance_sheet  # 资产负债表
            info = stock.info

            if is_stmt.empty:
                st.error("暂无财务报表数据，请尝试其他代码。")
            else:
                # --- 仪表盘 ---
                st.header(f"📊 {info.get('longName', symbol)} 实时概况")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("当前股价", f"${info.get('currentPrice', 'N/A')}")
                c2.metric("市盈率(PE)", info.get('trailingPE', 'N/A'))
                c3.metric("总市值", f"${info.get('marketCap', 0)/1e9:.2f}B")
                c4.metric("股息率", f"{info.get('dividendYield', 0)*100:.2f}%")

                # --- 趋势分析 ---
                st.subheader("📈 核心盈利与现金流趋势 (5年)")
                
                # 统一日期索引
                ni = is_stmt.loc['Net Income'].sort_index()
                ocf = cf_stmt.loc['Operating Cash Flow'].sort_index()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=ni.index, y=ni, name='净利润', line=dict(color='#1f77b4', width=3)))
                fig.add_trace(go.Scatter(x=ocf.index, y=ocf, name='经营现金流', line=dict(color='#2ca02c', dash='dot')))
                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02))
                st.plotly_chart(fig, use_container_width=True)

                # --- 营运效率 ---
                st.subheader("🧩 盈利能力与杠杆监控")
                ca, cb = st.columns(2)
                with ca:
                    # ROE 计算
                    equity = bs_stmt.loc['Stockholders Equity'].sort_index()
                    roe = (ni / equity) * 100
                    st.write("**ROE (净资产收益率) %**")
                    st.line_chart(roe)
                with cb:
                    # 负债率
                    assets = bs_stmt.loc['Total Assets'].sort_index()
                    liab = bs_stmt.loc['Total Liabilities Net Minority Interest'].sort_index()
                    debt_ratio = (liab / assets) * 100
                    st.write("**资产负债率 %**")
                    st.area_chart(debt_ratio)

                # --- 智能评分系统 ---
                st.markdown("---")
                st.subheader("🎯 智能投资评估结论")
                score = 0
                tips = []
                
                # 逻辑判断
                if ocf.iloc[-1] > ni.iloc[-1]:
                    score += 40
                    tips.append("✅ 盈利含金量极高：经营现金流 > 净利润")
                if roe.iloc[-1] > 15:
                    score += 30
                    tips.append("✅ 盈利效率优秀：ROE 超过 15%")
                if debt_ratio.iloc[-1] < 50:
                    score += 30
                    tips.append("✅ 财务防线稳固：负债率低于 50%")
                
                st.info(f"### 综合健康得分：{score} / 100")
                for t in tips: st.write(t)

        except Exception as e:
            st.error(f"分析出错：{str(e)}")
