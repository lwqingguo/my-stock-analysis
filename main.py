import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 页面配置
st.set_page_config(page_title="旗舰级财务透视系统-V15", layout="wide")

# 2. 侧边栏
st.sidebar.header("🔍 数据控制台")
examples = {"手动输入": "", "英伟达 (NVDA)": "NVDA", "苹果 (AAPL)": "AAPL", "贵州茅台 (600519.SS)": "600519.SS", "农夫山泉 (9633.HK)": "9633.HK"}
selected = st.sidebar.selectbox("选择示例股票：", list(examples.keys()))
symbol = st.sidebar.text_input("输入代码：", examples[selected] if examples[selected] else "NVDA").upper()

def get_data_safe(df, keys):
    for k in keys:
        if k in df.index: return df.loc[k].fillna(0)
    return pd.Series([0.0]*len(df.columns), index=df.columns)

def run_v15_engine(ticker):
    try:
        stock = yf.Ticker(ticker)
        is_stmt = stock.income_stmt.sort_index(axis=1).iloc[:, -10:]
        cf_stmt = stock.cashflow.sort_index(axis=1).iloc[:, -10:]
        bs_stmt = stock.balance_sheet.sort_index(axis=1).iloc[:, -10:]
        info = stock.info
        
        years = is_stmt.columns
        years_label = [str(y.year) for y in years]
        
        st.title(f"🏛️ 全维度财务透视报告：{info.get('longName', ticker)}")
        
        # --- 维度一：杜邦分析与 ROE 拆解 ---
        st.header("1️⃣ 杜邦分析：ROE 核心驱动拆解")
        net_income = get_data_safe(is_stmt, ['Net Income'])
        rev = get_data_safe(is_stmt, ['Total Revenue'])
        assets = get_data_safe(bs_stmt, ['Total Assets'])
        equity = get_data_safe(bs_stmt, ['Stockholders Equity'])
        
        roe = (net_income / equity) * 100
        net_margin = (net_income / rev) * 100
        asset_turnover = rev / assets
        equity_multiplier = assets / equity

        fig_dupont = make_subplots(rows=2, cols=2, subplot_titles=("ROE %", "净利率 %", "资产周转率", "权益乘数 (杠杆)"))
        fig_dupont.add_trace(go.Scatter(x=years_label, y=roe, name="ROE"), row=1, col=1)
        fig_dupont.add_trace(go.Scatter(x=years_label, y=net_margin, name="净利率"), row=1, col=2)
        fig_dupont.add_trace(go.Scatter(x=years_label, y=asset_turnover, name="周转率"), row=2, col=1)
        fig_dupont.add_trace(go.Scatter(x=years_label, y=equity_multiplier, name="杠杆"), row=2, col=2)
        fig_dupont.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig_dupont, use_container_width=True)
        st.info("💡 **怎么看：** 理想的 ROE 增长应由净利率或周转率驱动。若仅由杠杆驱动，则风险增加。")

        # --- 维度二：ROIC 驱动力拆解 ---
        st.header("2️⃣ ROIC 深度拆解：谁在驱动投资回报？")
        ebit = get_data_safe(is_stmt, ['EBIT'])
        tax_rate = 0.25 # 设定平均税率
        nopat = ebit * (1 - tax_rate)
        invested_capital = equity + get_data_safe(bs_stmt, ['Total Debt'])
        roic = (nopat / invested_capital) * 100
        
        # 拆解 ROIC = 税后经营净利率 * 投资资本周转率
        nopat_margin = (nopat / rev) * 100
        ic_turnover = rev / invested_capital

        c_r1, c_r2 = st.columns(2)
        with c_r1:
            st.write("**ROIC 核心趋势 %**")
            st.line_chart(roic)
        with c_r2:
            fig_ic = go.Figure()
            fig_ic.add_trace(go.Scatter(x=years_label, y=nopat_margin, name="税后经营净利率 %"))
            fig_ic.add_trace(go.Scatter(x=years_label, y=ic_turnover * 10, name="投资资本周转率(x10)"))
            fig_ic.update_layout(title="ROIC 驱动因素 (盈利 vs 效率)")
            st.plotly_chart(fig_ic, use_container_width=True)
        st.info("💡 **怎么看：** 观察 ROIC 的波动是因为利润变薄（净利率跌）还是资产变重（周转率跌）。")

        # --- 维度三：营运效率与现金流 (整合保留) ---
        st.header("3️⃣ 营运效率与现金含金量")
        receivables = get_data_safe(bs_stmt, ['Net Receivables'])
        inventory = get_data_safe(bs_stmt, ['Inventory'])
        ocf = get_data_safe(cf_stmt, ['Operating Cash Flow'])
        fcf = ocf + get_data_safe(cf_stmt, ['Capital Expenditure'])

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.write("**周转天数 (天)**")
            dso = (receivables / rev) * 365
            st.bar_chart(dso)
        with col_e2:
            st.write("**盈利含金量 (OCF/Net Income)**")
            st.line_chart(ocf / net_income)

        # --- 维度四：财务安全性与股东回报 ---
        st.header("4️⃣ 安全边际与股东回报")
        debt_ratio = (get_data_safe(bs_stmt, ['Total Liabilities']) / assets) * 100
        div_paid = get_data_safe(cf_stmt, ['Cash Dividends Paid']).abs()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("资产负债率 %", f"{debt_ratio.iloc[-1]:.2f}%")
        m2.metric("最新分红 (亿)", f"{div_paid.iloc[-1]/1e8:.2f}")
        m3.metric("流动比率", f"{(get_data_safe(bs_stmt, ['Total Current Assets'])/get_data_safe(bs_stmt, ['Total Current Liabilities'])).iloc[-1]:.2f}")

        # --- 维度五：总结评估 ---
        st.divider()
        st.header("🏁 综合评估总结 (Financial Summary)")
        
        latest_roe = roe.iloc[-1]
        latest_roic = roic.iloc[-1]
        latest_debt = debt_ratio.iloc[-1]
        cash_quality = (ocf / net_income).iloc[-1]

        score_p = "优秀" if latest_roe > 15 else "一般"
        score_e = "高效" if latest_roic > 10 else "待提升"
        score_s = "稳健" if latest_debt < 60 else "高风险"

        summary = f"""
        基于过去 10 年财务数据分析，**{info.get('shortName', ticker)}** 的综合评估如下：
        1. **盈利能力**：ROE 为 `{latest_roe:.2f}%`，盈利表现 **{score_p}**。ROIC 为 `{latest_roic:.2f}%`，说明资本利用效率 **{score_e}**。
        2. **现金质量**：利润含金量为 `{cash_quality:.2f}`。值 {">1" if cash_quality > 1 else "<1"} 代表经营现金流{"能" if cash_quality > 1 else "不能"}覆盖净利润，钱的真实度{"高" if cash_quality > 1 else "存疑"}。
        3. **风险评估**：资产负债率为 `{latest_debt:.2f}%`，财务杠杆水平处于 **{score_s}** 区间。
        4. **总体建议**：重点观察其**{ "净利率" if net_margin.iloc[-1] < net_margin.mean() else "资产周转率" }**的变动趋势，这是目前驱动 ROE 的核心变变量。
        """
        st.success(summary)

    except Exception as e:
        st.error(f"分析失败: {e}")

if st.sidebar.button("启动全维度分析引擎"):
    run_v15_engine(symbol)
