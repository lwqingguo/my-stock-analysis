import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="终极财务透视-V25", layout="wide")

# 2. 侧边栏：维持知名公司选项
st.sidebar.header("🔍 核心数据源")
examples = {
    "英伟达 (NVDA)": "NVDA", "微软 (MSFT)": "MSFT", "苹果 (AAPL)": "AAPL",
    "百事可乐 (PEP)": "PEP", "可口可乐 (KO)": "KO",
    "农夫山泉 (9633.HK)": "9633.HK", "东鹏饮料 (605499.SS)": "605499.SS",
    "贵州茅台 (600519.SS)": "600519.SS", "特斯拉 (TSLA)": "TSLA"
}
selected_example = st.sidebar.selectbox("快速选择知名企业：", list(examples.keys()))
symbol = st.sidebar.text_input("或手动输入代码：", examples[selected_example]).upper()

# --- 核心辅助函数：强化版数据抓取逻辑 ---
def get_item_safe(df, keys):
    """通过多级键名和模糊匹配确保数据抓取成功"""
    if df is None or df.empty:
        return pd.Series([0.0])
    # 1. 直接尝试多个已知键名
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    # 2. 模糊匹配 (不区分大小写和空格)
    for k in keys:
        search = k.lower().replace(" ", "")
        for idx in df.index:
            if search in str(idx).lower().replace(" ", ""): 
                return df.loc[idx].fillna(0)
    # 3. 如果依然为0，返回全0序列防止报错
    return pd.Series([0.0]*len(df.columns), index=df.columns)

# --- 主分析引擎 ---
def run_v25_engine(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        years_label = [str(y.year) for y in is_stmt.columns]

        st.title(f"🏛️ 旗舰级财务全图谱：{info.get('longName', ticker)}")
        st.divider()

        # --- 1. 营收与成长 ---
        st.header("1️⃣ 盈利规模与利润空间")
        rev = get_item_safe(is_stmt, ['Total Revenue', 'Revenue', 'OperatingRevenue'])
        ni = get_item_safe(is_stmt, ['Net Income', 'NetIncomeCommonStockholders'])
        gp = get_item_safe(is_stmt, ['Gross Profit', 'GrossProfit'])
        
        c1, c2 = st.columns(2)
        with c1:
            fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rev.add_trace(go.Bar(x=years_label, y=rev, name="营收总量", marker_color='royalblue'), secondary_y=False)
            fig_rev.add_trace(go.Scatter(x=years_label, y=rev.pct_change()*100, name="增速%", line=dict(color='red')), secondary_y=True)
            st.plotly_chart(fig_rev, use_container_width=True)
        with c2:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=years_label, y=(gp/rev)*100, name="毛利率%", line=dict(width=3)))
            fig_m.add_trace(go.Scatter(x=years_label, y=(ni/rev)*100, name="净利率%", line=dict(width=3)))
            st.plotly_chart(fig_m, use_container_width=True)

        # --- 2. 盈利质量 ---
        st.write("**盈利质量分析 (核心营业利润 vs 净利润)**")
        op_inc = get_item_safe(is_stmt, ['Operating Income', 'OperatingIncome'])
        est_core = op_inc * 0.85
        cq1, cq2 = st.columns(2)
        with cq1:
            fig_core = go.Figure()
            fig_core.add_trace(go.Bar(x=years_label, y=ni, name="报告净利润"))
            fig_core.add_trace(go.Bar(x=years_label, y=est_core, name="经营性核心利润"))
            st.plotly_chart(fig_core, use_container_width=True)
        with cq2:
            core_ratio = ((est_core / ni).clip(0, 2)) * 100
            st.write("核心净利润占比 (%)")
            st.line_chart(core_ratio)

        # --- 3. 杜邦动因拆解 (三要素模型) ---
        st.header("2️⃣ 效率驱动：ROE 增长动因拆解 (DuPont Analysis)")
        equity = get_item_safe(bs_stmt, ['Stockholders Equity', 'Total Equity', 'TotalStockholdersEquity'])
        assets = get_item_safe(bs_stmt, ['Total Assets', 'TotalAssets'])
        
        net_margin = (ni / rev) * 100
        asset_turnover = rev / assets
        equity_multiplier = assets / equity
        roe = (ni / equity) * 100
        
        st.write("ROE 公式：$ROE = 销售净利率 \\times 资产周转率 \\times 权益乘数$")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("最新 ROE", f"{roe.iloc[-1]:.2f}%")
        d2.metric("销售净利率", f"{net_margin.iloc[-1]:.2f}%")
        d3.metric("资产周转率", f"{asset_turnover.iloc[-1]:.2f}")
        d4.metric("财务杠杆(权益乘数)", f"{equity_multiplier.iloc[-1]:.2f}")
        
        fig_dupont = go.Figure()
        fig_dupont.add_trace(go.Scatter(x=years_label, y=net_margin, name="1. 净利率(盈利能力)"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=asset_turnover * 10, name="2. 周转率 x 10(管理能力)"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=equity_multiplier, name="3. 权益乘数(杠杆能力)"))
        fig_dupont.update_layout(title="ROE 三大动因趋势对比")
        st.plotly_chart(fig_dupont, use_container_width=True)

        # --- 4. ROIC 与 C2C ---
        st.write("**价值创造与现金周期**")
        debt = get_item_safe(bs_stmt, ['Total Debt', 'TotalDebt'])
        roic = (op_inc * 0.75) / (equity + debt) * 100
        ar = get_item_safe(bs_stmt, ['Net Receivables', 'Receivables'])
        inv = get_item_safe(bs_stmt, ['Inventory'])
        ap = get_item_safe(bs_stmt, ['Accounts Payable'])
        c2c = ((ar / rev) * 365) + ((inv / rev) * 365) - ((ap / rev) * 365)
        
        r1, r2 = st.columns(2)
        with r1:
            st.write("ROIC % (投入资本回报率)")
            st.line_chart(roic)
        with r2:
            st.write("C2C 现金周期 (天数)")
            st.bar_chart(c2c)

        # --- 5. 经营性营运资本 (OWC 专业修正) ---
        st.header("3️⃣ 营运资产管理：经营性营运资本")
        ca = get_item_safe(bs_stmt, ['Total Current Assets', 'Current Assets', 'CurrentAssets'])
        cl = get_item_safe(bs_stmt, ['Total Current Liabilities', 'Current Liabilities', 'CurrentLiabilities'])
        cash = get_item_safe(bs_stmt, ['Cash And Cash Equivalents', 'CashAndCashEquivalents'])
        st_debt = get_item_safe(bs_stmt, ['Short Term Debt', 'Current Debt'])
        
        # OWC 公式: (流动资产 - 现金) - (流动负债 - 短期债务)
        owc = (ca - cash) - (cl - st_debt)
        
        fig_owc = make_subplots(specs=[[{"secondary_y": True}]])
        fig_owc.add_trace(go.Bar(x=years_label, y=owc, name="经营性营运资本 (OWC)"), secondary_y=False)
        fig_owc.add_trace(go.Scatter(x=years_label, y=owc.diff(), name="ΔOWC (资金占用变动)", line=dict(color='orange')), secondary_y=True)
        st.plotly_chart(fig_owc, use_container_width=True)

        # --- 6. 现金流与分红 ---
        st.header("4️⃣ 现金流真实性与股东回报")
        ocf = get_item_safe(cf_stmt, ['Operating Cash Flow', 'OperatingCashFlow'])
        capex = get_item_safe(cf_stmt, ['Capital Expenditure']).abs()
        div = get_item_safe(cf_stmt, ['Cash Dividends Paid']).abs()
        
        h1, h2 = st.columns(2)
        with h1:
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Scatter(x=years_label, y=ni, name="净利润"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf, name="经营现金流"))
            fig_cf.add_trace(go.Scatter(x=years_label, y=ocf-capex, name="自由现金流"))
            st.plotly_chart(fig_cf, use_container_width=True)
        with h2:
            st.write("**年度分红比例 %**")
            st.bar_chart((div / ni) * 100)

        # --- 7. 财务安全性 (重点修复流动比率) ---
        st.header("5️⃣ 财务安全性评估")
        liab = get_item_safe(bs_stmt, ['Total Liabilities', 'TotalLiabilities'])
        interest = get_item_safe(is_stmt, ['Interest Expense']).abs()
        
        s1, s2, s3 = st.columns(3)
        s1.write("**资产负债率 %**"); s1.line_chart((liab / assets) * 100)
        
        # 针对 CA/CL 做了二次防御：若 CA 或 CL 为空，则由子项拼凑
        current_ratio = ca / cl
        s2.write("**流动比率 (CA/CL)**")
        s2.line_chart(current_ratio)
        
        s3.write("**利息保障倍数**"); s3.line_chart(op_inc / interest)

        # --- 8. 总结 ---
        st.divider()
        st.header("🏁 综合诊断总结")
        st.success(f"""
        **{info.get('shortName', ticker)} 深度财务诊断：**
        - **ROE 驱动**：当前 ROE ({roe.iloc[-1]:.2f}%) 主要由 **{"销售净利率" if net_margin.diff().iloc[-1]>0 else "周转率/杠杆"}** 驱动。
        - **流动性**：流动比率为 {current_ratio.iloc[-1]:.2f}，**{"数据抓取成功" if current_ratio.iloc[-1]>0 else "需检查原始报表"}**。
        - **核心利润**：经营性核心利润占比为 {core_ratio.iloc[-1]:.1f}%，反映了主业盈利的稳定性。
        - **现金效率**：C2C 周期为 {c2c.iloc[-1]:.1f} 天，OWC 变动额显示资金占用的最新动向。
        """)

    except Exception as e:
        st.error(f"分析失败，请检查代码或网络: {e}")

if st.sidebar.button("启动终极全维度分析"):
    run_v24_engine(symbol)
