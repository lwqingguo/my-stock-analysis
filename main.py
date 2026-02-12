import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="财务全图谱-V50", layout="wide")

# 2. 侧边栏 UI 精简化
st.sidebar.header("🛡️ 诊断模式控制")
freq_mode = st.sidebar.selectbox("1. 报表频率", ["年度 (Annual)", "季度 (Quarterly)"], index=1)

q_pivot_month = None
if "季度" in freq_mode:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 By Q 深度趋势对比")
    q_target = st.sidebar.radio("选择要回溯的特定季度：", ["Q1 (3月)", "Q2 (6月)", "Q3 (9月)", "Q4 (12月)"], index=0)
    q_map = {"Q1 (3月)": "-03", "Q2 (6月)": "-06", "Q3 (9月)": "-09", "Q4 (12月)": "-12"}
    q_pivot_month = q_map[q_target]
    st.sidebar.success(f"已开启：系统将强制挖掘历史所有 {q_target} 数据。")

st.sidebar.markdown("---")
stock_list = {"东鹏饮料": "605499.SS", "贵州茅台": "600519.SS", "英伟达": "NVDA"}
selected_stock = st.sidebar.selectbox("2. 快捷选择公司", list(stock_list.keys()))
symbol = st.sidebar.text_input("3. 股票代码", stock_list[selected_stock]).upper()

# --- 核心辅助函数：多层级标签匹配 ---
def get_data_robust(df, tag_list):
    if df is None or df.empty: return pd.Series(dtype=float)
    # 标准化索引名，防止空格干扰
    df.index = df.index.str.strip()
    for tag in tag_list:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty: return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主引擎 ---
def run_v50_engine(ticker, is_annual, q_month):
    try:
        stock = yf.Ticker(ticker)
        
        # 🔥 关键修复：直接调用 .history 之前的全量财务缓存
        # 我们使用 .get_income_stmt 来获取，并显式指定频率
        if is_annual:
            is_df = stock.get_income_stmt(freq='annual')
            bs_df = stock.get_balance_sheet(freq='annual')
            cf_df = stock.get_cashflow(freq='annual')
        else:
            # 季度模式：尝试获取更长的历史 (部分 A 股需要特殊处理)
            is_df = stock.quarterly_income_stmt
            bs_df = stock.quarterly_balance_sheet
            cf_df = stock.quarterly_cashflow
            
        if is_df.empty:
            st.error("数据源未响应。请检查代码后缀（如 600519.SS）并重试。")
            return

        # 排序：从旧到新
        is_df = is_df.sort_index(axis=1, ascending=True)
        bs_df = bs_df.sort_index(axis=1, ascending=True)
        cf_df = cf_df.sort_index(axis=1, ascending=True)

        # 🔥 By Q 趋势透视逻辑：不再限制期数，只要匹配就保留
        if not is_annual and q_month:
            mask = is_df.columns.map(lambda x: q_month in x.strftime('%Y-%m'))
            is_df, bs_df, cf_df = is_df.loc[:, mask], bs_df.loc[:, mask], cf_df.loc[:, mask]
            
            # 如果筛选后数据太少，尝试通过年度数据补齐 Q4 (12月) 的历史
            if len(is_df.columns) < 2 and q_month == "-12":
                st.warning("正在从年度数据库补齐长周期趋势...")
                is_df = stock.income_stmt.sort_index(axis=1, ascending=True)
                bs_df = stock.balance_sheet.sort_index(axis=1, ascending=True)
                cf_df = stock.cashflow.sort_index(axis=1, ascending=True)

        labels = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = labels

        # --- 全量指标提取 (修复空值与负债率 0 问题) ---
        rev = get_data_robust(is_df, ['Total Revenue', 'Revenue', 'Operating Revenue'])
        ni = get_data_robust(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_data_robust(is_df, ['EBIT', 'Operating Income'])
        
        assets = get_data_robust(bs_df, ['Total Assets'])
        equity = get_data_robust(bs_df, ['Stockholders Equity', 'Total Equity'])
        # 负债倒算逻辑：防止 Total Liabilities 标签缺失
        liab = get_data_robust(bs_df, ['Total Liabilities'])
        if liab.sum() == 0: 
            liab = (assets - equity).clip(lower=0) # 资产减去权益补齐
            
        ca = get_data_robust(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_data_robust(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        ar = get_data_robust(bs_df, ['Net Receivables', 'Receivables'])
        inv = get_data_robust(bs_df, ['Inventory'])
        ap = get_data_robust(bs_df, ['Accounts Payable'])
        
        ocf = get_data_robust(cf_df, ['Operating Cash Flow'])
        div = get_data_robust(cf_df, ['Cash Dividends Paid']).abs()
        # 利息修复
        interest = get_data_robust(is_df, ['Interest Expense', 'Financial Expense']).abs()

        # --- 计算核心比率 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity.replace(0, 1.0) * 100).fillna(0)
        debt_ratio = (liab / assets.replace(0, 1.0) * 100).fillna(0)
        curr_ratio = (ca / cl.replace(0, 1.0)).fillna(0)
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)

        # --- 页面展示 ---
        st.title(f"🏛️ 财务 By Q 趋势透视 V50：{ticker}")
        
        # 10分制打分
        score = 0
        if not roe.empty:
            if roe.iloc[-1] > 15: score += 2
            if (ocf.iloc[-1]/ni.iloc[-1] if ni.iloc[-1]!=0 else 0) > 1: score += 2
            if debt_ratio.iloc[-1] < 50: score += 2
            if growth.iloc[-1] > 10: score += 2
            if c2c.iloc[-1] < 60: score += 2

        c1, c2 = st.columns([1, 2])
        with c1:
            color = "#2E7D32" if score >= 8 else "#FFA000"
            st.markdown(f'<div style="text-align:center; border:5px solid {color}; border-radius:15px; padding:20px;"><h1 style="font-size:70px; color:{color};">{score}</h1><p>综合健康分</p></div>', unsafe_allow_html=True)
        with c2:
            st.subheader("📝 核心诊断")
            st.write(f"**分析周期**：共发现 {len(labels)} 个匹配的财务周期。")
            st.write(f"**结论**：{labels[-1]} 数据显示，ROE 为 {roe.iloc[-1]:.2f}%，负债率为 {debt_ratio.iloc[-1]:.1f}%。")
        st.divider()

        # --- 图表区 (全量保留) ---
        st.header("1️⃣ 营收与同比增速趋势 (By Q)")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=labels, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=labels, y=growth, name="增速%", line=dict(color='red', width=3)), secondary_y=True)
        f1.update_xaxes(type='category'); st.plotly_chart(f1, use_container_width=True)

        st.header("2️⃣ 盈利能力 (ROE 杜邦分析)")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=labels, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=labels, y=rev/assets*10, name="周转率x10"))
        f2.update_xaxes(type='category'); st.plotly_chart(f2, use_container_width=True)

        st.header("3️⃣ 经营效率 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("ROIC %"); st.line_chart(pd.Series((ebit*0.75)/(equity+1).values, index=labels))
        with c32: st.write("C2C 周期 (天)"); st.bar_chart(pd.Series(c2c.values, index=labels))

        st.header("4️⃣ 营运资本 (OWC)")
        st.bar_chart(pd.Series((ca - cl).values, index=labels))

        st.header("5️⃣ 现金流质量")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=labels, y=ni, name="利润"))
        f5.add_trace(go.Scatter(x=labels, y=ocf, name="现金流"))
        f5.update_xaxes(type='category'); st.plotly_chart(f5, use_container_width=True)

        st.header("6️⃣ 财务安全性 (趋势对比)")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("资产负债率 %")
            f61 = go.Figure(go.Scatter(x=labels, y=debt_ratio, mode='lines+markers+text', text=[f"{x:.1f}" for x in debt_ratio]))
            f61.update_layout(xaxis_type='category', height=300); st.plotly_chart(f61, use_container_width=True)
        with c62:
            st.write("流动比率")
            st.line_chart(pd.Series(curr_ratio.values, index=labels))
        with c63:
            st.write("利息保障倍数")
            st.line_chart(pd.Series(int_cover.values, index=labels))

    except Exception as e:
        st.error(f"引擎逻辑异常: {e}")

if st.sidebar.button("🚀 启动 V50 深度诊断"):
    run_v50_engine(symbol, "年度" in freq_mode, q_pivot_month)
