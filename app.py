import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="My Portfolio Tracker", layout="wide")

st.title("🚀 My Live Portfolio Tracker")

# 1. Your Portfolio Positions (Edit these numbers as you trade)
portfolio_data = {
    "Ticker": ["ORCL", "NFLX", "IBM", "CRM", "TMUS", "APP"],
    "Shares": [6, 8, 2, 2, 2, 1]
}
df = pd.DataFrame(portfolio_data)

# 2. Pull Live Prices Function
@st.cache_data
def get_live_prices(tickers):
    prices = {}
    for t in tickers:
        try:
            data = yf.Ticker(t).history(period="1d")
            prices[t] = data["Close"].iloc[-1]
        except:
            prices[t] = 0.0
    return prices

if st.button("🔄 Refresh Live Market Prices"):
    st.cache_data.clear()

# Fetch data
tickers_list = df["Ticker"].tolist()
live_prices = get_live_prices(tickers_list)

# Calculate values
df["Current Price (USD/EUR)"] = df["Ticker"].map(live_prices)
df["Total Value"] = df["Shares"] * df["Current Price (USD/EUR)"]

total_portfolio_value = df["Total Value"].sum()
df["Weight (%)"] = (df["Total Value"] / total_portfolio_value) * 100

# Display metrics
st.metric("Total Portfolio Value", f"€ {total_portfolio_value:,.2f}")

# Show table
st.subheader("Position Breakdown")
st.dataframe(df.style.format({"Current Price (USD/EUR)": "€ {:.2f}", "Total Value": "€ {:.2f}", "Weight (%)": "{:.2f}%"}))

# Show Interactive Pie Chart
st.subheader("Portfolio Distribution")
fig = px.pie(df, values='Total Value', names='Ticker', hole=0.4)
st.plotly_chart(fig, width='stretch')
