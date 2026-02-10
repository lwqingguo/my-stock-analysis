import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置 - 必须在最前面
st.set_page_config(page_title="财务全图谱-V42", layout="wide")

# 2. 侧边栏强制常驻
st.sidebar.header("🔍 数据维度设置")
time_frame = st.sidebar.radio("分析维度：", ["年度趋势 (Annual)", "季度趋势 (Quarterly)"])
# 修复侧边栏丢失：将备选列表独立出来
stock_list = {
    "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS",
    "农夫山泉 (9633.HK)": "9633.HK",
    "英伟达 (NVDA)": "NVDA",
    "特斯拉 (TSLA)": "TSLA"
}
selected_stock = st.sidebar.selectbox("快速选择：", list(stock_list.keys()))
symbol = st.sidebar.text_input("手动输入代码：", stock_list[selected_stock]).upper()

# --- 核心辅助函数：多标签暴力匹配 ---
def get_any(df, tags):
    """从多个可能的标签中抓取第一个非空的数据流"""
    if df is None or df.empty:
        return pd.Series([0.0] * 8)
    for tag in tags:
        if tag in df.index:
            res = df.loc[tag].replace('-', np.nan).astype(float)
            if not res.dropna().empty:
                return res.fillna(0.0)
    return pd.Series([0.0] * len(df.columns), index=df.columns)

# --- 主分析引擎 ---
def run_v42_engine(ticker, is_annual):
    try:
        stock = yf.Ticker(ticker)
        
        # 抓取原始报表
        is_raw = stock.income_stmt if is_annual else stock.quarterly_income_stmt
        bs_raw = stock.balance_sheet if is_annual else stock.quarterly_balance_sheet
        cf_raw = stock.cashflow if is_annual else stock.quarterly_cashflow

        if is_raw.empty or bs_raw.empty:
            st.error("无法获取财务报表数据，请检查网络或代码后缀是否正确。")
            return

        # 统一正序对齐与时间戳格式化
        is_df = is_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        bs_df = bs_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        cf_df = cf_raw.sort_index(axis=1, ascending=True).iloc[:, -8:]
        years = [d.strftime('%Y-%m') for d in is_df.columns]
        is_df.columns = bs_df.columns = cf_df.columns = years

        st.title(f"🏛️ 财务全图谱 V42：{stock.info.get('longName', ticker)}")
        st.divider()

        # --- 全量指标提取（多标签兜底，一个不删） ---
        # 1. 利润相关
        rev = get_any(is_df, ['Total Revenue', 'Revenue', 'Operating Revenue'])
        ni = get_any(is_df, ['Net Income', 'Net Income Common Stockholders'])
        ebit = get_any(is_df, ['EBIT', 'Operating Income'])
        gp = get_any(is_df, ['Gross Profit'])
        
        # 2. 资产负债相关 (重点修复)
        assets = get_any(bs_df, ['Total Assets'])
        equity = get_any(bs_df, ['Stockholders Equity', 'Total Equity', 'Total Equity Gross Minority Interest'])
        # 流动资产与负债 (修复流动比率 0 的关键)
        ca = get_any(bs_df, ['Total Current Assets', 'Current Assets'])
        cl = get_any(bs_df, ['Total Current Liabilities', 'Current Liabilities'])
        # 负债倒算法：如果 Total Liabilities 为空，则用 资产-权益
        liab = get_any(bs_df, ['Total Liabilities']).replace(0, np.nan).fillna(assets - equity)
        
        # 3. 运营效率相关
        cash = get_any(bs_df, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'])
        st_debt = get_any(bs_df, ['Short Term Debt', 'Current Debt', 'Current Provisions'])
        ar = get_any(bs_df, ['Net Receivables', 'Receivables'])
        inv = get_any(bs_df, ['Inventory'])
        ap = get_any(bs_df, ['Accounts Payable'])
        
        # 4. 现金流与利息
        ocf = get_any(cf_df, ['Operating Cash Flow'])
        div = get_any(cf_df, ['Cash Dividends Paid', 'Dividends Paid']).abs()
        interest = get_any(is_df, ['Interest Expense', 'Interest Expense Non Operating', 'Financial Expense']).abs()

        # --- 核心比率计算 ---
        growth = rev.pct_change().fillna(0) * 100
        roe = (ni / equity * 100).fillna(0)
        debt_ratio = (liab / assets * 100).fillna(0)
        curr_ratio = (ca / cl).fillna(0) # 现在 ca 和 cl 都有多标签兜底，不再是 0
        int_cover = (ebit / interest.replace(0, 1.0)).fillna(0)
        c2c = ((ar/rev*365) + (inv/rev*365) - (ap/rev*365)).fillna(0)
        owc = (ca - cash) - (cl - st_debt)

        # --- 绘图区（指标全保留） ---
        # 1. 营收规模
        st.header("1️⃣ 营收规模与利润空间")
        f1 = make_subplots(specs=[[{"secondary_y": True}]])
        f1.add_trace(go.Bar(x=years, y=rev, name="营收"), secondary_y=False)
        f1.add_trace(go.Scatter(x=years, y=growth, name="增速%", line=dict(color='red')), secondary_y=True)
        f1.update_xaxes(type='category'); st.plotly_chart(f1, use_container_width=True)

        # 2. 杜邦动因
        st.header("2️⃣ 效率驱动：ROE 动因拆解")
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=years, y=ni/rev*100, name="净利率%"))
        f2.add_trace(go.Scatter(x=years, y=rev/assets*10, name="周转率x10"))
        f2.add_trace(go.Scatter(x=years, y=assets/equity, name="权益乘数"))
        f2.update_xaxes(type='category'); st.plotly_chart(f2, use_container_width=True)

        # 3. ROIC & C2C
        st.header("3️⃣ 经营效率 (ROIC & C2C)")
        c31, c32 = st.columns(2)
        with c31: st.write("**ROIC %**"); st.line_chart(pd.Series((ebit*0.75)/(equity+1).values, index=years))
        with c32: st.write("**C2C 周期 (天)**"); st.bar_chart(pd.Series(c2c.values, index=years))

        # 4. OWC 营运资本
        st.header("4️⃣ 营运资产管理 (OWC)")
        st.bar_chart(pd.Series(owc.values, index=years))

        # 5. 现金流与分红
        st.header("5️⃣ 现金流质量与分红")
        f5 = go.Figure()
        f5.add_trace(go.Scatter(x=years, y=ni, name="净利润"))
        f5.add_trace(go.Scatter(x=years, y=ocf, name="经营现金流"))
        f5.add_trace(go.Bar(x=years, y=div, name="分红", opacity=0.3))
        f5.update_xaxes(type='category'); st.plotly_chart(f5, use_container_width=True)

        # 6. 财务安全性 (精度与波动修复)
        st.header("6️⃣ 财务安全性评估")
        c61, c62, c63 = st.columns(3)
        with c61:
            st.write("**资产负债率 %**")
            f61 = go.Figure(go.Scatter(x=years, y=debt_ratio, mode='lines+markers+text', 
                                      text=[f"{x:.1f}%" for x in debt_ratio], textposition="top center"))
            f61.update_layout(xaxis_type='category', height=300); st.plotly_chart(f61, use_container_width=True)
        with c62:
            st.write("**流动比率 (校准)**")
            f62 = go.Figure(go.Scatter(x=years, y=curr_ratio, mode='lines+markers'))
            f62.update_layout(xaxis_type='category', height=300); st.plotly_chart(f62, use_container_width=True)
        with c63:
            st.write("**利息保障倍数 (随利润波动)**")
            f63 = go.Figure(go.Scatter(x=years, y=int_cover, mode='lines+markers'))
            f63.update_layout(xaxis_type='category', height=300); st.plotly_chart(f63, use_container_width=True)

    except Exception as e:
        st.error(f"分析引擎发生错误: {e}")

# 启动按钮
if st.sidebar.button("启动 V42 旗舰版诊断"):
    run_v42_engine(symbol, time_frame == "年度趋势 (Annual)")
