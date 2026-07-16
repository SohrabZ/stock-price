#!/usr/bin/env python3
"""Unit tests for stock.py."""

import io
import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import patch, MagicMock

import stock

SAMPLE_YAHOO_RESPONSE = {
    "chart": {
        "result": [{
            "meta": {
                "currency": "USD",
                "symbol": "AAPL",
                "exchangeName": "NMS",
                "shortName": "Apple Inc.",
                "chartPreviousClose": 150.0,
                "regularMarketPrice": 155.0,
            },
            "timestamp": [1609459200, 1609545600],
            "indicators": {
                "quote": [{
                    "open": [149.0, 151.0],
                    "high": [152.0, 154.0],
                    "low": [148.0, 150.0],
                    "close": [150.0, 153.0],
                    "volume": [1000000, 1200000],
                }],
                "adjclose": [{"adjclose": [150.0, 153.0]}]
            }
        }],
        "error": None
    }
}

SAMPLE_YAHOO_ERROR = {
    "chart": {
        "result": [],
        "error": {"code": "Not Found", "description": "No data found, symbol may be delisted"}
    }
}


def _mock_response(payload, status=200):
    """Build a mock HTTP response for urlopen."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = lambda s, *args: None
    return mock_resp


def _run_cli(argv):
    """Run stock.main() with given argv and capture stdout/stderr."""
    captured = io.StringIO()
    err = io.StringIO()
    with patch.object(sys, "argv", argv):
        with patch.object(sys, "stdout", captured):
            with patch.object(sys, "stderr", err):
                try:
                    stock.main()
                except SystemExit:
                    pass
    return captured.getvalue(), err.getvalue()


class TestFetchChart(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_fetch_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        result = stock.fetch_chart("AAPL", "1d", "1d")
        self.assertEqual(result["meta"]["symbol"], "AAPL")
        self.assertEqual(len(result["timestamp"]), 2)

    @patch("urllib.request.urlopen")
    def test_fetch_error(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_ERROR)
        with self.assertRaises(ValueError) as ctx:
            stock.fetch_chart("DEAD", "1d", "1d")
        self.assertIn("No data found", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_fetch_rate_limit(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 429, "Too Many Requests", {}, None
        )
        with self.assertRaises(ValueError) as ctx:
            stock.fetch_chart("AAPL", "1d", "1d")
        self.assertIn("Rate limited", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_fetch_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        with self.assertRaises(ValueError) as ctx:
            stock.fetch_chart("AAPL", "1d", "1d")
        self.assertIn("Network error", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_fetch_bad_json(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *args: None
        mock_urlopen.return_value = mock_resp
        with self.assertRaises(ValueError) as ctx:
            stock.fetch_chart("AAPL", "1d", "1d")
        self.assertIn("Invalid JSON", str(ctx.exception))


class TestParseResult(unittest.TestCase):
    def test_parse_bars(self):
        meta, bars = stock.parse_result(SAMPLE_YAHOO_RESPONSE["chart"]["result"][0])
        self.assertEqual(meta["symbol"], "AAPL")
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["date"], "2021-01-01")
        self.assertEqual(bars[0]["close"], 150.0)
        self.assertEqual(bars[1]["close"], 153.0)
        self.assertEqual(bars[1]["volume"], 1200000)

    def test_parse_empty(self):
        empty = {
            "meta": {"symbol": "X"},
            "timestamp": [],
            "indicators": {"quote": [{}], "adjclose": []}
        }
        meta, bars = stock.parse_result(empty)
        self.assertEqual(bars, [])

    def test_parse_with_none_values(self):
        """Test that bars with None values are parsed correctly."""
        data = {
            "meta": {"symbol": "X"},
            "timestamp": [1609459200, 1609545600],
            "indicators": {
                "quote": [{
                    "open": [100.0, None],
                    "high": [105.0, None],
                    "low": [95.0, None],
                    "close": [102.0, None],
                    "volume": [1000000, None],
                }],
                "adjclose": []
            }
        }
        meta, bars = stock.parse_result(data)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["close"], 102.0)
        self.assertIsNone(bars[1]["close"])


class TestCLI(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_table_output(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        out, err = _run_cli(["stock.py", "AAPL", "-p", "1d"])
        self.assertIn("Apple Inc.", out)
        self.assertIn("2021-01-01", out)
        self.assertIn("150.00", out)  # 2 decimal formatting

    @patch("urllib.request.urlopen")
    def test_json_output(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        out, err = _run_cli(["stock.py", "AAPL", "-p", "1d", "-f", "json"])
        data = json.loads(out)
        self.assertIn("AAPL", data)
        self.assertEqual(data["AAPL"]["bars"][0]["close"], 150.0)

    @patch("urllib.request.urlopen")
    def test_json_output_to_file(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        tmp_path = "/tmp/test_stock_output.json"
        out, err = _run_cli(["stock.py", "AAPL", "-p", "1d", "-f", "json", "-o", tmp_path])
        self.assertIn("JSON written to", out)
        with open(tmp_path, "r") as f:
            data = json.load(f)
        self.assertIn("AAPL", data)
        os.remove(tmp_path)

    @patch("urllib.request.urlopen")
    def test_multiple_tickers(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        out, err = _run_cli(["stock.py", "AAPL", "MSFT", "-p", "1d"])
        self.assertIn("Apple Inc.", out)
        self.assertEqual(out.count("Apple Inc."), 2)

    @patch("urllib.request.urlopen")
    def test_invalid_ticker(self, mock_urlopen):
        """Invalid ticker symbols are rejected before network call."""
        out, err = _run_cli(["stock.py", "AAPL?bad", "-p", "1d"])
        self.assertIn("ERROR", err)
        self.assertIn("Invalid ticker", err)
        # Should NOT call urlopen for invalid tickers
        mock_urlopen.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_delisted_ticker(self, mock_urlopen):
        """Delisted/unknown tickers rejected by Yahoo."""
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_ERROR)
        out, err = _run_cli(["stock.py", "DEAD", "-p", "1d"])
        self.assertIn("ERROR", err)
        self.assertIn("No data found", err)

    @patch("urllib.request.urlopen")
    def test_volume_stats(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        out, err = _run_cli(["stock.py", "AAPL", "-p", "5d"])
        self.assertIn("Avg volume:", out)
        self.assertIn("Volume change:", out)

    @patch("urllib.request.urlopen")
    def test_graph_flag(self, mock_urlopen):
        if not stock.MATPLOTLIB_OK:
            self.skipTest("matplotlib not installed")
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        out, err = _run_cli(["stock.py", "AAPL", "-p", "5d", "--graph", "--graph-output", "/tmp/test_graph.png"])
        self.assertIn("Graph saved", out)
        self.assertTrue(os.path.exists("/tmp/test_graph.png"))
        os.remove("/tmp/test_graph.png")

    @patch("urllib.request.urlopen")
    def test_single_bar_period_change(self, mock_urlopen):
        """1d period uses chartPreviousClose for period change."""
        single_bar_response = {
            "chart": {
                "result": [{
                    "meta": {
                        "currency": "USD",
                        "symbol": "AAPL",
                        "exchangeName": "NMS",
                        "shortName": "Apple Inc.",
                        "chartPreviousClose": 148.0,
                    },
                    "timestamp": [1609459200],
                    "indicators": {
                        "quote": [{
                            "open": [149.0],
                            "high": [152.0],
                            "low": [148.0],
                            "close": [150.0],
                            "volume": [1000000],
                        }],
                        "adjclose": [{"adjclose": [150.0]}]
                    }
                }],
                "error": None
            }
        }
        mock_urlopen.return_value = _mock_response(single_bar_response)
        out, err = _run_cli(["stock.py", "AAPL", "-p", "1d"])
        self.assertIn("Period change:", out)
        self.assertIn("+2.00", out)  # 150 - 148 = 2


if __name__ == "__main__":
    unittest.main()
