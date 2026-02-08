import streamlit as st
import yfinance as yf
import pandas as pd

# 网页配置
st.set_page_config(page_title="智能股票体检中心", layout="wide")

st.title("📈 个人股票综合分析平台")
st.markdown("---")

# 侧边栏设置
st.sidebar.header("配置参数")
symbol = st.sidebar.text_input("请输入股票代码 (美股如 AAPL, A股如 600519.SS)", "AAPL").upper()

if st.sidebar.button("开始全面体检"):
    with st.spinner('正在调取全球金融数据...'):
        try:
            stock = yf.Ticker(symbol)
            
            # 获取数据
            info = stock.info
            df_cf = stock.cashflow
            df_is = stock.income_stmt
            
            # 基础信息
            st.header(f"{info.get('longName', symbol)} - 实时概况")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("当前股价", f"${info.get('currentPrice', 'N/A')}")
            col2.metric("市盈率 (PE)", info.get('trailingPE', 'N/A'))
            col3.metric("市值", f"{info.get('marketCap', 0)/1e9:.2f}B")
            col4.metric("股息率", f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "0%")

            # 核心逻辑：现金为王体检
            st.subheader("🔍 核心指标深度体检")
            
            # 提取最近一年数据
            ocf = df_cf.loc['Operating Cash Flow'].iloc[0]
            cap_ex = df_cf.loc['Capital Expenditure'].iloc[0]
            net_income = df_is.loc['Net Income'].iloc[0]
            fcf = ocf + cap_ex # 自由现金流

            c1, c2 = st.columns(2)
            with c1:
                st.write("**1. 自由现金流 (FCF) 状况**")
                if fcf > 0:
                    st.success(f"✅ 自由现金流为正: ${fcf/1e9:.2f}B。公司有闲钱发分红或回购。")
                else:
                    st.error(f"❌ 自由现金流为负: ${fcf/1e9:.2f}B。公司正在失血，风险较大。")
            
            with c2:
                st.write("**2. 利润含金量 (现金/净利)**")
                ratio = ocf / net_income
                if ratio > 1:
                    st.success(f"✅ 含金量: {ratio:.2f}。赚的都是真金白银，财务质量高。")
                else:
                    st.warning(f"⚠️ 含金量: {ratio:.2f}。账面富贵，现金回收较慢。")

        except Exception as e:
            st.error(f"获取数据失败：{e}")
            st.info("提示：A股请记得加后缀，如茅台是 600519.SS，腾讯是 0700.HK")

st.sidebar.markdown("---")
st.sidebar.caption("小白专属分析工具 v1.0")
