import unittest
from unittest.mock import patch, AsyncMock
from TriArbDemo import TriangularArbitrage


class TestTriangularArbitrage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Set up a fresh instance of TriangularArbitrage for each test."""
        self.arb = TriangularArbitrage()
        self.arb.prices = {}
        self.arb.symbol_info = {}
        self.arb.asset_to_symbols = {}
        self.arb.triangles = []
        self.arb.profitable_trades = []

    def test_update_price(self):
        """Test if prices are updated correctly."""
        # Valid price update
        self.arb.update_price("BTCUSDT", 30000, 30010)
        self.assertEqual(
            self.arb.prices["BTCUSDT"],
            {"bid": 30000.0, "ask": 30010.0},
            "Price update failed for BTCUSDT"
        )

    def test_get_rate(self):
        """Test rate calculation for valid and invalid inputs."""
        # Setup symbol info and prices
        self.arb.symbol_info = {"BTCUSDT": {"base": "BTC", "quote": "USDT"}}
        self.arb.prices = {
            "BTCUSDT": {"bid": 30000.0, "ask": 30010.0},
            "ETHBTC": {"bid": 0.07, "ask": 0.069},
            "ETHUSDT": {"bid": 2105.0, "ask": 2110.0},
        }

        # Test buy rate (base → quote)
        rate = self.arb.get_rate("BTCUSDT", "BTC", "USDT")
        self.assertAlmostEqual(rate, 1 / 30010.0, msg="Buy rate calculation failed")

        # Test sell rate (quote → base)
        rate = self.arb.get_rate("BTCUSDT", "USDT", "BTC")
        self.assertAlmostEqual(rate, 30000.0, msg="Sell rate calculation failed")

        # Test invalid rate
        rate = self.arb.get_rate("BTCUSDT", "BTC", "ETH")
        self.assertIsNone(rate, "Invalid rate should return None")

    def test_build_triangles(self):
        """Test triangle creation based on symbol info and asset mappings."""
        # Setup symbol info and asset mappings
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

        # Build triangles
        self.arb.build_triangles()

        # Verify triangle creation
        expected_triangle = {"BTCUSDT", "ETHBTC", "ETHUSDT"}
        self.assertTrue(
            any(set(triangle) == expected_triangle for triangle in self.arb.triangles),
            "Triangle build failed"
        )

    @patch("TriArbDemo.aiohttp.ClientSession.get", new_callable=AsyncMock)
    async def test_fetch_symbol_info(self, mock_get):
        """Test fetching symbol info from Binance API."""
        # Mock Binance API response
        mock_response = {
            "symbols": [
                {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "ETHBTC", "baseAsset": "ETH", "quoteAsset": "BTC", "status": "TRADING"},
                {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT", "status": "TRADING"},
            ]
        }
        mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)

        # Call the method
        await self.arb.fetch_symbol_info()

        # Verify the mock was called with the correct URL
        mock_get.assert_called_once_with("https://api.binance.com/api/v3/exchangeInfo")

        # Verify symbol info and asset mappings
        self.assertEqual(
            self.arb.symbol_info["BTCUSDT"],
            {"base": "BTC", "quote": "USDT"},
            "Symbol info mapping failed for BTCUSDT"
        )
        self.assertIn("BTCUSDT", self.arb.asset_to_symbols["BTC"], "BTCUSDT missing in asset_to_symbols for BTC")
        self.assertIn("BTCUSDT", self.arb.asset_to_symbols["USDT"], "BTCUSDT missing in asset_to_symbols for USDT")

    def test_find_arbitrage(self):
        """Test finding profitable arbitrage opportunities."""
        # Setup symbol info, prices, and triangles
        self.arb.symbol_info = {
        "BTCUSDT": {"base": "BTC", "quote": "USDT"},
        "ETHBTC": {"base": "ETH", "quote": "BTC"},
        "ETHUSDT": {"base": "ETH", "quote": "USDT"},
    }
        self.arb.prices = {
        "BTCUSDT": {"bid": 30000.0, "ask": 30010.0},
        "ETHBTC": {"bid": 0.07, "ask": 0.069},
        "ETHUSDT": {"bid": 2105.0, "ask": 2110.0},
    }
        self.arb.triangles = [("BTCUSDT", "ETHBTC", "ETHUSDT")]

    # Simulate a profitable arbitrage scenario
        self.arb.find_arbitrage()

    # Verify profitable trades
        if self.arb.best_trade:
            self.assertGreater(
                self.arb.best_trade["profit"],
                0,
            f"Expected profit greater than 0, but got {self.arb.best_trade['profit']}"
        )
        else:
            self.fail("No profitable trade found")


if __name__ == "__main__":
    unittest.main(verbosity=2)