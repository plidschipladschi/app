import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="My Portfolio Tracker", layout="wide")

st.title("🚀 My Automated Live Portfolio Tracker (EUR)")

# --- UNFEHLBARE PORTFOLIO MATRIX ---
portfolio_data = {
    "Ticker": [
        "TMUS", "CRM", "ORCL", "NFLX", "ALI1.DE", "UBER", "NOW", "IBM", 
        "HOOD", "ACN", "APP", "QBTS", "RKLB", "RUU.CN", "CRML", "SLI", "NB", "KTOS"
    ],
    "Name": [
        "T-Mobile US Inc.", "Salesforce Inc.", "Oracle Corporation", "Netflix Inc.",
        "Almonty Industries", "Uber Technologies", "ServiceNow Inc.", "IBM Corp.",
        "Robinhood Markets", "Accenture plc", "AppLovin Corp.", "D-Wave Quantum", 
        "Rocket Lab USA", "Refined Energy", "Critical Metals", "Standard Lithium", 
        "NioCorp Developments", "Kratos Defense"
    ],
    "Sector": [
        "Telecom Utilities", "Cloud & B2B SaaS", "Cloud & B2B SaaS", "Consumer Media & Tech",
        "Defense & Hard Assets", "Consumer Media & Tech", "Cloud & B2B SaaS", "Pure Quantum Basket",
        "Fintech & Platform", "Cloud & B2B SaaS", "Cloud & B2B SaaS", "Pure Quantum Basket",
        "Defense & Hard Assets", "Speculative Mining", "Speculative Mining", "Speculative Mining",
        "Speculative Mining", "Defense & Hard Assets"
    ],
    "Shares": [
        4.0, 2.0, 3.0, 4.0, 16.333333, 4.0, 2.0, 1.0, 
        2.0, 1.0, 1.0, 8.0, 2.0, 669.0, 9.0, 25.0, 27.0, 1.0
    ]
}
df = pd.DataFrame(portfolio_data)

# Live-Preise abrufen mit synchroner Multi-Währungskonvertierung
@st.cache_data(ttl=60)
def get_live_prices(tickers):
    prices = {}
    try:
        usd_data = yf.Ticker("USDEUR=X").history(period="1d")["Close"]
        usd_to_eur = float(usd_data.to_numpy().flatten()[-1])
    except:
        usd_to_eur = 0.89
        
    try:
        cad_data = yf.Ticker("CADEUR=X").history(period="1d")["Close"]
        cad_to_eur = float(cad_data.to_numpy().flatten()[-1])
    except:
        cad_to_eur = 0.64
        
    for t in tickers:
        ticker_clean = t.strip()
        try:
            data = yf.Ticker(ticker_clean).history(period="5d")["Close"]
            flat_arr = data.to_numpy().flatten()
            raw_price = float(flat_arr[-1]) if flat_arr.size > 0 else 0.0
            
            if ".CN" in ticker_clean:
                prices[t] = raw_price * cad_to_eur
            elif ".DE" in ticker_clean or ".F" in ticker_clean:
                prices[t] = raw_price
            else:
                prices[t] = raw_price * usd_to_eur
        except:
            prices[t] = 0.0
    return prices

# Historische Kurse abrufen (BATCH-DOWNLOAD METHODE GEGEN YAHOO-BUG)
@st.cache_data(ttl=300)
def get_portfolio_history(positions, period, interval, live_prices_map):
    tickers = positions["Ticker"].tolist()
    
    # 1. Sonderfall für die feine Intraday-Linie von heute (1 Day - 1m)
    if interval == "1m":
        portfolio_history = pd.DataFrame()
        try:
            usd_data = yf.Ticker("USDEUR=X").history(period="1d", interval="1m")["Close"]
            usd_to_eur = usd_data.to_numpy().flatten()[-1] if usd_data.size > 0 else 0.89
        except:
            usd_to_eur = 0.89
            
        for t in tickers:
            ticker_clean = t.strip()
            try:
                if ticker_clean in ["RUU.CN", "ALI1.DE"]:
                    continue
                asset_data = yf.Ticker(ticker_clean).history(period="1d", interval="1m")["Close"]
                asset_arr = asset_data.to_numpy().flatten()
                
                if portfolio_history.empty and asset_arr.size > 0:
                    portfolio_history = pd.DataFrame(index=asset_data.index)
                
                shares = positions.loc[positions["Ticker"] == t, "Shares"].values[0]
                portfolio_history[t] = asset_arr * usd_to_eur * shares
            except:
                continue
        if not portfolio_history.empty:
            portfolio_history = portfolio_history.ffill().bfill()
            try:
                portfolio_history.index = portfolio_history.index.tz_convert("Europe/Amsterdam")
            except:
                try:
                    portfolio_history.index = portfolio_history.index.tz_localize("UTC").tz_convert("Europe/Amsterdam")
                except:
                    pass
            result = pd.DataFrame(portfolio_history.sum(axis=1), columns=["Total Portfolio"])
            ruu_shares = positions.loc[positions["Ticker"] == "RUU.CN", "Shares"].values[0]
            ali_shares = positions.loc[positions["Ticker"] == "ALI1.DE", "Shares"].values[0]
            static_addon = (live_prices_map.get("RUU.CN", 0.0) * ruu_shares) + (live_prices_map.get("ALI1.DE", 0.0) * ali_shares)
            result["Total Portfolio"] = result["Total Portfolio"] + static_addon
            return result

    # 2. PROFI-BATCH DOWNLOAD FÜR ALLE WEITERE TIMEFRAMES (.download mit allen Tickers auf einmal)
    # Das zieht ein sauberes MultiIndex DataFrame, das wir unten gezielt zerlegen.
    all_download_tickers = tickers + ["USDEUR=X", "CADEUR=X"]
    try:
        raw_data = yf.download(all_download_tickers, period=period, interval=interval, group_by="ticker", progress=False)
    except:
        return pd.DataFrame(columns=["Total Portfolio"])

    # Erzeuge ein sauberes, leeres Ziel-Zahlenblatt basierend auf dem Zeitindex von Yahoo
    master_history = pd.DataFrame(index=raw_data.index)
    
    # Extrahiere die Devisenkurse absolut sicher aus dem verschachtelten Ticker-Kollumnen-Block
    try:
        usd_eur_hist = raw_data["USDEUR=X"]["Close"].ffill().bfill()
    except:
        usd_eur_hist = pd.Series(0.89, index=raw_data.index)
        
    try:
        cad_eur_hist = raw_data["CADEUR=X"]["Close"].ffill().bfill()
    except:
        cad_eur_hist = pd.Series(0.64, index=raw_data.index)

    for t in tickers:
        ticker_clean = t.strip()
        try:
            if ticker_clean not in raw_data.columns.levels[0]:
                continue
            
            # Ziehe den reinen, eindimensionalen Schlusskursvektor der Aktie
            asset_series = raw_data[ticker_clean]["Close"].ffill().bfill()
            shares = float(positions.loc[positions["Ticker"] == t, "Shares"].values[0])
            
            if ".CN" in ticker_clean:
                master_history[t] = asset_series * cad_eur_hist * shares
            elif ".DE" in ticker_clean or ".F" in ticker_clean:
                master_history[t] = asset_series * shares
            else:
                master_history[t] = asset_series * usd_eur_hist * shares
        except:
            continue
            
    if not master_history.empty:
        # Füllt zeitliche Differenzen der Datenpunkte glatt via ffill/bfill
        master_history = master_history.ffill().bfill()
        
        # Zeitzonen-Konvertierung nach Vorgabe
        try:
            if master_history.index.tz is not None:
                master_history.index = master_history.index.tz_convert("Europe/Amsterdam")
            else:
                master_history.index = master_history.index.tz_localize("UTC").tz_convert("Europe/Amsterdam")
        except:
            pass
            
        final_df = pd.DataFrame(master_history.sum(axis=1), columns=["Total Portfolio"])
        return final_df
    return pd.DataFrame(columns=["Total Portfolio"])


# --- AUTOMATISCHES LIVE-DASHBOARD ENGINE ---
@st.fragment(run_every="10s")
def render_live_dashboard():
    tickers_list = df["Ticker"].tolist()
    live_prices = get_live_prices(tickers_list)
    
    df["Current Price (EUR)"] = df["Ticker"].map(live_prices)
    df["Total Value (EUR)"] = df["Shares"] * df["Current Price (EUR)"]
    
    sorted_df = df.sort_values(by=["Sector", "Total Value (EUR)"], ascending=[True, False]).reset_index(drop=True)
    sorted_df.index = sorted_df.index + 1
    
    total_portfolio_value = sorted_df["Total Value (EUR)"].sum()
    
    # Division-by-Zero Protection
    if total_portfolio_value > 0:
        sorted_df["Weight (%)"] = (sorted_df["Total Value (EUR)"] / total_portfolio_value) * 100
    else:
        sorted_df["Weight (%)"] = 0

    # 1. Gesamtwert live anzeigen
    st.metric("Total Portfolio Value", f"€ {total_portfolio_value:,.2f}")

    # 2. Zeitlauf-Chart (Hochauflösend nach Vorgabe)
    st.subheader("Portfolio Performance History")
    
    timeframe = st.segmented_control(
        "Select Timeframe:",
        options=["5 Years", "3 Years", "1 Year", "YTD", "6 Months", "3 Months", "1 Month", "1 Week", "1 Day"],
        default="1 Year"
    )
    
    # Die hochauflösende, zackenfreie Taktungs-Matrix nach Vorgabe
    mapping = {
        "5 Years": ("5y", "1wk"),
        "3 Years": ("3y", "1wk"),
        "1 Year": ("1y", "1d"),
        "YTD": ("ytd", "1d"),
        "6 Months": ("6mo", "1d"),
        "3 Months": ("3mo", "4h"),     # 4-Stunden Takt
        "1 Month": ("1mo", "1h"),      # 1-Stunden Takt
        "1 Week": ("5d", "30m"),       # Hochauflösender 30-Minuten Takt für über 100+ Datenpunkte
        "1 Day": ("1d", "1m")          # Hochauflösender 1-Minuten Takt für heute
    }
    
    yf_period, yf_interval = mapping[timeframe]
    hist_df = get_portfolio_history(sorted_df, yf_period, yf_interval, live_prices)
    
    fig_line = px.line(hist_df, y="Total Portfolio", labels={"index": "Date/Time (Amsterdam)", "Total Portfolio": "Value (€)"})
    
    # Visuelle Spline-Glättung mit unified Hover
    fig_line.update_traces(line=dict(width=3, shape="spline", smoothing=1.1))
    fig_line.update_layout(hovermode="x unified")
    
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("---")

    # 3. & 4. Nebeneinander-Layout (Responsive)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Sector Breakdown Table (Starts at 1)")
        st.dataframe(
            sorted_df[["Sector", "Name", "Ticker", "Shares", "Current Price (EUR)", "Total Value (EUR)", "Weight (%)"]].style.format({
                "Current Price (EUR)": "€ {:.2f}", 
                "Total Value (EUR)": "€ {:.2f}", 
                "Weight (%)": "{:.2f}%"
            }), 
            use_container_width=True
        )
        
    with col2:
        st.subheader("Exploding Sector Distribution (With % Weights)")
        fig_sunburst = px.sunburst(
            sorted_df, 
            path=["Sector", "Name"], 
            values="Total Value (EUR)",
            color="Sector",
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_sunburst.update_traces(textinfo="label+percent entry")
        fig_sunburst.update_layout(margin=dict(t=0, l=0, r=0, b=0))
        st.plotly_chart(fig_sunburst, use_container_width=True)

# Dashboard starten
render_live_dashboard()
