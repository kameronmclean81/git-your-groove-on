import asyncio
import json
import aiohttp
import websockets
from collections import defaultdict

# Constants
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/!ticker@arr"
EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"

class TriangularArbitrage:
    def __init__(self):
        self.prices = {}  # {'BTCUSDT': {'bid': float, 'ask': float}, ...}
        self.symbol_info = {}  # {'BTCUSDT': {'base': 'BTC', 'quote': 'USDT'}}
        self.asset_to_symbols = defaultdict(set)  # {'BTC': set(['BTCUSDT', ...])}
        self.triangles = []

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
                mid = None
                if base2 == quote1:
                    mid = quote2
                elif quote2 == quote1:
                    mid = base2
                if mid and mid != base1:
                    for sym3 in self.asset_to_symbols.get(mid, []):
                        base3, quote3 = self.symbol_info[sym3]["base"], self.symbol_info[sym3]["quote"]
                        if (base3 == base1 and quote3 == mid) or (quote3 == base1 and base3 == mid):
                            triangle = (sym1, sym2, sym3)
                            key = tuple(sorted(triangle))
                            if key not in checked:
                                self.triangles.append(triangle)
                                checked.add(key)

        print(f"🔺 Total triangles found: {len(self.triangles)}")

    def get_rate(self, symbol, from_asset, to_asset):
        """Return price for trading from from_asset to to_asset via symbol"""
        if symbol not in self.prices:
            return None
        bid = self.prices[symbol]['bid']
        ask = self.prices[symbol]['ask']
        base = self.symbol_info[symbol]['base']
        quote = self.symbol_info[symbol]['quote']
        if from_asset == base and to_asset == quote:
            return 1 / ask  # Buy base → pay quote
        elif from_asset == quote and to_asset == base:
            return bid  # Sell base → receive quote
        else:
            return None

    def find_arbitrage(self):
        for sym1, sym2, sym3 in self.triangles:
            base1 = self.symbol_info[sym1]["base"]
            quote1 = self.symbol_info[sym1]["quote"]

            if not all(sym in self.prices for sym in (sym1, sym2, sym3)):
                continue

            start = base1
            amt = 1.0

            rate1 = self.get_rate(sym1, start, quote1)
            rate2 = self.get_rate(sym2, quote1, quote2 := (self.symbol_info[sym2]["base"] if self.symbol_info[sym2]["base"] != quote1 else self.symbol_info[sym2]["quote"]))
            rate3 = self.get_rate(sym3, quote2, start)

            if None in (rate1, rate2, rate3):
                continue

            amt *= rate1
            amt *= rate2
            amt *= rate3
            profit = (amt - 1.0) * 100

            print(f"[ARB] {sym1} → {sym2} → {sym3} | Return: {amt:.6f} | Profit: {profit:.4f}%")

async def main():
    arb = TriangularArbitrage()
    print("🌐 Fetching Binance symbol info...")
    await arb.fetch_symbol_info()
    print("✅ Building trading triangles...")
    arb.build_triangles()

    async with websockets.connect(BINANCE_WS_URL) as ws:
        print("📡 Connected to Binance WebSocket. Listening for live price updates...")
        while True:
            try:
                msg = await ws.recv()
                tickers = json.loads(msg)

                for ticker in tickers:
                    symbol = ticker["s"]
                    bid = ticker["b"]
                    ask = ticker["a"]
                    arb.update_price(symbol, bid, ask)

                if arb.triangles:
                    arb.find_arbitrage()
            except Exception as e:
                print(f"⚠️ Error: {e}")
                await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Terminated by user.")



def run_arbitrage():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Terminated by user.")
    except Exception as e:
        print(f"⚠️ Error: {e}")