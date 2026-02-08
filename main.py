import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="综合财务分析平台", layout="wide")

# 2. 侧边栏：增加股票示例
st.sidebar.header("🔍 数据控制台")

# 知名股票示例字典
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

symbol = st.sidebar.text_input("或输入股票代码：", default_symbol).upper()

def comprehensive_analysis_v4(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 抓取年度报表并确保年份正序
        is_stmt = stock.income_stmt.sort_index(axis=1)
        cf_stmt = stock.cashflow.sort_index(axis=1)
        bs_stmt = stock.balance_sheet.sort_index(axis=1)
        info = stock.info
        
        if is_stmt.empty:
            st.error("数据调取失败，请检查代码或网络。")
            return

        # 截取最近10年
        is_stmt = is_stmt.iloc[:, -10:]
        cf_stmt = cf_stmt.iloc[:, -10:]
        bs_stmt = bs_stmt.iloc[:, -10:]
        years = is_stmt.columns

        # --- 报告头部：明确显示股票信息 ---
        stock_name = info.get('longName', ticker)
        st.title(f"📈 财务深度透视报告：{stock_name} ({ticker})")
        st.markdown(f"**业务摘要：** {info.get('sector', '未知行业')} | {info.get('industry', '未知领域')} | {info.get('totalRevenue', 0)/1e9:.2f}B {info.get('currency', 'USD')}")
        st.divider()

        # --- 维度一：盈利性与营收成长 ---
        st.header("1️⃣ 盈利能力与营收成长 (Profitability)")
        rev = is_stmt.loc['Total Revenue']
        net_income = is_stmt.loc['Net Income']
        rev_growth = rev.pct_change() * 100
        
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=years, y=rev, name="营业收入", marker_color='royalblue', opacity=0.7), secondary_y=False)
        fig1.add_trace(go.Scatter(x=years, y=rev_growth, name="营收增长率 %", line=dict(color='firebrick', width=3)), secondary_y=True)
        fig1.update_layout(title="营收规模与增长趋势 (双轴优化)", hovermode="x unified")
        fig1.update_yaxes(title_text="营收规模", secondary_y=False)
        fig1.update_yaxes(title_text="增长率 %", secondary_y=True, showgrid=False)
        st.plotly_chart(fig1, use_container_width=True)

        # 历年毛利率与净利率 (新要求：独立图表)
        gp = is_stmt.loc['Gross Profit']
        gross_margin = (gp / rev) * 100
        net_margin = (net_income / rev) * 100
        
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=years, y=gross_margin, name="毛利率 %", line=dict(color='green', width=2), fill='tonexty'))
        fig2.add_trace(go.Scatter(x=years, y=net_margin, name="净利率 %", line=dict(color='darkred', width=3)))
        fig2.update_layout(title="历年毛利率 vs 净利率趋势", yaxis_title="百分比 (%)", hovermode="x unified")
        st.plotly_chart(fig2, use_container_width=True)

        # --- 维度二：营运指标 (改进：收入/应收账款) ---
        st.header("2️⃣ 营运效率维度 (Operating Efficiency)")
        col_eff1, col_eff2 = st.columns(2)
        
        with col_eff1:
            # 兼容性处理应收账款键名
            receivable_keys = ['Receivables', 'Net Receivables', 'Accounts Receivable']
            receivables = None
            for k in receivable_keys:
                if k in bs_stmt.index:
                    receivables = bs_stmt.loc[k]
                    break
            
            if receivables is not None:
                # 按照你的建议：收入 / 应收账款 (应收账款周转率)
                rec_turnover = rev / receivables
                fig_rec = go.Figure()
                fig_rec.add_trace(go.Scatter(x=years, y=rec_turnover, name="应收账款周转率", line=dict(color='orange', width=3), mode='lines+markers'))
                fig_rec.update_layout(title="应收账款周转率 (营收 / 应收账款)", yaxis_title="周转次数", hovermode="x unified")
                st.plotly_chart(fig_rec, use_container_width=True)
                st.caption("注：该数值越高，代表公司回款效率越高，坏账风险越小。")
            else:
                st.warning("未能从报表中提取到‘应收账款’数据。")
        
        with col_eff2:
            assets = bs_stmt.loc['Total Assets']
            asset_turnover = rev / assets
            st.write("**总资产周转率 (次)**")
            st.area_chart(asset_turnover)

        # --- 维度三：现金流健康度 ---
        st.header("3️⃣ 现金流维度 (Cash Flow Health)")
        ocf = cf_stmt.loc['Operating Cash Flow']
        capex = cf_stmt.loc['Capital Expenditure']
        fcf = ocf + capex
        cash_ratio = (ocf / rev) * 100 
        
        fig3 = make_subplots(specs=[[{"secondary_y": True}]])
        fig3.add_trace(go.Bar(x=years, y=ocf, name="经营现金流"), secondary_y=False)
        fig3.add_trace(go.Bar(x=years, y=fcf, name="自由现金流"), secondary_y=False)
        fig3.add_trace(go.Scatter(x=years, y=cash_ratio, name="收现比 %", line=dict(color='purple', width=2)), secondary_y=True)
        fig3.update_layout(title="现金生成能力与收现比", barmode='group', hovermode="x unified")
        st.plotly_chart(fig3, use_container_width=True)

        # --- 维度四：财务安全与综合评分 ---
        st.header("4️⃣ 财务安全与综合体检")
        total_liab = bs_stmt.loc['Total Liabilities Net Minority Interest']
        debt_ratio = (total_liab / assets) * 100
        
        c_s1, c_s2 = st.columns([2, 1])
        with c_s1:
            st.write("**资产负债率趋势 (%)**")
            st.area_chart(debt_ratio)
        
        with c_s2:
            # 雷达图逻辑
            s_roe = min(info.get('returnOnEquity', 0) * 400, 100)
            s_growth = min(rev_growth.iloc[-1] * 2, 100) if not pd.isna(rev_growth.iloc[-1]) else 50
            s_cash = min((ocf.iloc[-1]/rev.iloc[-1])*400, 100) if rev.iloc[-1] !=0 else 0
            s_safety = max(100 - debt_ratio.iloc[-1], 0)
            
            categories = ['盈利(ROE)', '营收增长', '现金流', '财务安全']
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(r=[s_roe, s_growth, s_cash, s_safety], theta=categories, fill='toself'))
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), title="评分雷达")
            st.plotly_chart(fig_radar, use_container_width=True)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("生成全维度深度报告"):
    comprehensive_analysis_v4(symbol)
