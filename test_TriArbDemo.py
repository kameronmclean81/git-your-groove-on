import unittest
from unittest.mock import patch, AsyncMock
from TriArbDemo import TriangularArbitrage  # Import the actual class
import aiohttp

class TestTriangularArbitrage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Setup the object before each test
        self.arb = TriangularArbitrage()
        self.arb.prices = {}
        self.arb.symbol_info = {}
        self.arb.asset_to_symbols = {}
        self.arb.triangles = []
        self.arb.profitable_trades = []

    def test_update_price(self):
        # Test if prices are updated correctly
        self.arb.update_price("BTCUSDT", 30000, 30010)
        self.assertEqual(self.arb.prices["BTCUSDT"], {"bid": 30000.0, "ask": 30010.0})

    def test_get_rate(self):
        # Test rate calculation
        self.arb.symbol_info = {"BTCUSDT": {"base": "BTC", "quote": "USDT"}}
        self.arb.prices = {
            "BTCUSDT": {"bid": 30000.0, "ask": 30010.0},
            "ETHBTC": {"bid": 0.07, "ask": 0.069},
            "ETHUSDT": {"bid": 2105.0, "ask": 2110.0},
        }

        # Test buy rate (base → quote)
        rate = self.arb.get_rate("BTCUSDT", "BTC", "USDT")
        self.assertAlmostEqual(rate, 1 / 30010.0)

        # Test sell rate (quote → base)
        rate = self.arb.get_rate("BTCUSDT", "USDT", "BTC")
        self.assertAlmostEqual(rate, 30000.0)

        # Test invalid rate
        rate = self.arb.get_rate("BTCUSDT", "BTC", "ETH")
        self.assertIsNone(rate)


    def test_build_triangles(self):
        # Prepare symbol info and asset to symbol mappings
        self.arb.symbol_info = {
            "BTCUSDT": {"base": "BTC", "quote": "USDT"},
            "ETHBTC": {"base": "ETH", "quote": "BTC"},
            "ETHUSDT": {"base": "ETH", "quote": "USDT"},
        }
        self.arb.asset_to_symbols = {
            "BTC": {"BTCUSDT", "ETHBTC"},
            "USDT": {"BTCUSDT", "ETHUSDT"},
            "ETH": {"ETHBTC", "ETHUSDT"},
        }
        self.arb.build_triangles()  # Assuming this method exists and is implemented

        # Check if the triangle exists in any order
        expected_triangle = {"BTCUSDT", "ETHBTC", "ETHUSDT"}
        self.assertTrue(any(set(triangle) == expected_triangle for triangle in self.arb.triangles))

    @patch("TriArbDemo.aiohttp.ClientSession.get", new_callable=AsyncMock)
    async def test_fetch_symbol_info(self, mock_get):
        # Mock response object
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            "symbols": [
                {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "ETHBTC", "baseAsset": "ETH", "quoteAsset": "BTC", "status": "TRADING"},
                {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT", "status": "TRADING"},
            ]
        })

        # Configure the mock to support `async with`
        mock_get.return_value.__aenter__.return_value = mock_response

        # Call the async method
        await self.arb.fetch_symbol_info()

        # Verify symbol info and asset-to-symbol mappings
        self.assertEqual(self.arb.symbol_info["BTCUSDT"], {"base": "BTC", "quote": "USDT"})
        self.assertIn("BTCUSDT", self.arb.asset_to_symbols["BTC"])
        self.assertIn("BTCUSDT", self.arb.asset_to_symbols["USDT"])

    def test_find_arbitrage(self):
        # Adjusted prices to create a potential arbitrage opportunity
        self.arb.symbol_info = {
            "BTCUSDT": {"base": "BTC", "quote": "USDT"},
            "ETHBTC": {"base": "ETH", "quote": "BTC"},
            "ETHUSDT": {"base": "ETH", "quote": "USDT"},
        }
        self.arb.prices = {
            "BTCUSDT": {"bid": 30000.0, "ask": 30010.0},  # Buying BTC with USDT
            "ETHBTC": {"bid": 0.07, "ask": 0.069},       # Adjusted ask price
            "ETHUSDT": {"bid": 2105.0, "ask": 2110.0},   # Adjusted bid price
        }
        
        # Adding a triangle with an arbitrage path
        self.arb.triangles = [("BTCUSDT", "ETHBTC", "ETHUSDT")]
        
        # Debugging output to check prices and triangles
        print("Initial Prices:", self.arb.prices)
        print("Triangles:", self.arb.triangles)

        # Simulate the arbitrage finding logic
        self.arb.find_arbitrage()

        # Debugging output to see the result
        print("Profitable Trades:", self.arb.profitable_trades)

        # Assert that at least one profitable trade was found
        self.assertGreater(len(self.arb.profitable_trades), 0, "No profitable trades found!")

   
   
   
if __name__ == "__main__":
    unittest.main()