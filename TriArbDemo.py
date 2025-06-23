import asyncio
import json
import aiohttp
import websockets
import streamlit as st
import pandas as pd
import altair as alt
from collections import defaultdict, deque

# Constants
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/!ticker@arr"
EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"

class TriangularArbitrage:
    def __init__(self):
        self.prices = {}
        self.symbol_info = {}
        self.asset_to_symbols = defaultdict(set)
        self.triangles = []
        self.best_trade = None
        self.history = deque(maxlen=50)

    async def fetch_symbol_info(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(EXCHANGE_INFO_URL) as resp:
                data = await resp.json()
                for s in data["symbols"]:
                    if s["status"] != "TRADING":
                        continue
                    symbol = s["symbol"]
                    base = s["baseAsset"]
                    quote = s["quoteAsset"]
                    self.symbol_info[symbol] = {"base": base, "quote": quote}
                    self.asset_to_symbols[base].add(symbol)
                    self.asset_to_symbols[quote].add(symbol)

    def update_price(self, symbol, bid, ask):
        self.prices[symbol] = {'bid': float(bid), 'ask': float(ask)}

    def build_triangles(self):
        checked = set()
        for sym1 in self.symbol_info:
            base1, quote1 = self.symbol_info[sym1]["base"], self.symbol_info[sym1]["quote"]
            for sym2 in self.asset_to_symbols.get(quote1, []):
                base2, quote2 = self.symbol_info[sym2]["base"], self.symbol_info[sym2]["quote"]
                mid = quote2 if base2 == quote1 else base2 if quote2 == quote1 else None
                if mid and mid != base1:
                    for sym3 in self.asset_to_symbols.get(mid, []):
                        base3, quote3 = self.symbol_info[sym3]["base"], self.symbol_info[sym3]["quote"]
                        if (base3 == base1 and quote3 == mid) or (quote3 == base1 and base3 == mid):
                            triangle = (sym1, sym2, sym3)
                            key = tuple(sorted(triangle))
                            if key not in checked:
                                self.triangles.append(triangle)
                                checked.add(key)

    def get_rate(self, symbol, from_asset, to_asset):
        if symbol not in self.prices:
            return None
        bid = self.prices[symbol]['bid']
        ask = self.prices[symbol]['ask']
        base = self.symbol_info[symbol]['base']
        quote = self.symbol_info[symbol]['quote']
        if from_asset == base and to_asset == quote:
            return 1 / ask
        elif from_asset == quote and to_asset == base:
            return bid
        else:
            return None

    def find_arbitrage(self):
        best = None

        for sym1, sym2, sym3 in self.triangles:
            base1 = self.symbol_info[sym1]["base"]
            quote1 = self.symbol_info[sym1]["quote"]
            if not all(sym in self.prices for sym in (sym1, sym2, sym3)):
                continue

            start = base1
            amt = 1.0

            rate1 = self.get_rate(sym1, start, quote1)
            quote2 = self.symbol_info[sym2]["base"] if self.symbol_info[sym2]["base"] != quote1 else self.symbol_info[sym2]["quote"]
            rate2 = self.get_rate(sym2, quote1, quote2)
            rate3 = self.get_rate(sym3, quote2, start)

            if None in (rate1, rate2, rate3):
                continue

            amt *= rate1 * rate2 * rate3
            profit = (amt - 1.0) * 100

            summary = {
                "path": f"{sym1} → {sym2} → {sym3}",
                "return": amt,
                "profit": profit
            }

            if profit > 0 and (not best or summary["profit"] > best["profit"]):
                best = summary

        if best:
            self.best_trade = best
            self.history.appendleft(best)

# Streamlit UI
st.set_page_config(page_title="Crypto Arbitrage Tracker", layout="wide")
st.title("📈 Live Triangular Arbitrage Opportunities")

initial_amount = st.number_input("Enter your GBP investment amount:", min_value=10.0, value=1000.0)
status_placeholder = st.empty()
summary_placeholder = st.empty()
history_placeholder = st.empty()
chart_placeholder = st.empty()

arb = TriangularArbitrage()
gbp_balance = initial_amount
cumulative_profits = []
trade_count = []

async def run_arbitrage():
    global gbp_balance

    await arb.fetch_symbol_info()
    arb.build_triangles()

    async with websockets.connect(BINANCE_WS_URL) as ws:
        count = 0
        while True:
            try:
                msg = await ws.recv()
                tickers = json.loads(msg)
                for ticker in tickers:
                    symbol = ticker["s"]
                    bid = ticker["b"]
                    ask = ticker["a"]
                    arb.update_price(symbol, bid, ask)

                arb.find_arbitrage()

                if arb.best_trade:
                    trade = arb.best_trade
                    new_balance = gbp_balance * trade["return"]
                    profit = new_balance - gbp_balance
                    gbp_balance = new_balance

                    cumulative_profits.append(gbp_balance - initial_amount)
                    trade_count.append(count)
                    count += 1

                    summary_placeholder.markdown(f"""
                        ### 🥇 Best Arbitrage Trade
                        - **Path**: `{trade["path"]}`
                        - **Profit**: `£{profit:.2f}`
                        - **New Balance**: `£{gbp_balance:.2f}`
                        - **Return %**: `{trade["profit"]:.2f}%`
                    """)
                else:
                    summary_placeholder.markdown("⏳ No profitable arbitrage opportunities found.")

                if arb.history:
                    history_md = "### 📜 Trade History (Recent Best)\n"
                    for h in arb.history:
                        history_md += f"- `{h['path']}` | Profit: `{h['profit']:.2f}%`\n"
                    history_placeholder.markdown(history_md)

                if cumulative_profits:
                    chart_data = pd.DataFrame({
                        "Trade Count": trade_count,  # Custom x-axis data
                        "Profit (£)": cumulative_profits  # Custom y-axis data
                    })

                    # Create the base line chart for cumulative profits
                    base_chart = alt.Chart(chart_data).mark_line().encode(
                        x=alt.X("Trade Count:Q", title="Number of Trades", axis=alt.Axis(format="d")),  # Force integer display
                        y=alt.Y("Profit (£):Q", title="Profits (£)")  # Custom y-axis label
                    ).properties(
                        title="Cumulative Profits Over Trades"  # Add a title to the chart
                    )

                    # Add tracker points to show profit values on the timeline
                    points = alt.Chart(chart_data).mark_point(size=50, color="red").encode(
                        x="Trade Count:Q",
                        y="Profit (£):Q",
                        tooltip=["Trade Count", "Profit (£)"]  # Tooltip to show detailed values
                    )

                    # Add external labels for the chart
                    labels = alt.Chart(chart_data).mark_text(
                        align="left",
                        dx=5,  # Offset for label placement
                        dy=-5  # Offset for label placement
                    ).encode(
                        x="Trade Count:Q",
                        y="Profit (£):Q",
                        text=alt.Text("Profit (£):Q", format=".2f")  # Display profit values as labels
                    )

                    # Combine the line chart, tracker points, and labels
                    final_chart = base_chart + points + labels

                    # Render the chart in the placeholder
                    chart_placeholder.altair_chart(final_chart, use_container_width=True)

                await asyncio.sleep(3)

            except Exception as e:
                status_placeholder.error(f"⚠️ Error: {e}")
                await asyncio.sleep(5)

def main():
    asyncio.run(run_arbitrage())

if __name__ == "__main__":
    main()

#cd /Users/Administrator/PyCharmProjects/TriArb