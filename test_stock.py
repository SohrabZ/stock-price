#!/usr/bin/env python3
"""Unit tests for stock.py."""

import json
import io
import os
import sys
import unittest
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


class TestCLI(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_table_output(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        captured = io.StringIO()
        with patch.object(sys, "argv", ["stock.py", "AAPL", "-p", "1d"]):
            with patch.object(sys, "stdout", captured):
                try:
                    stock.main()
                except SystemExit:
                    pass
        out = captured.getvalue()
        self.assertIn("Apple Inc.", out)
        self.assertIn("2021-01-01", out)
        self.assertIn("150.0", out)

    @patch("urllib.request.urlopen")
    def test_json_output(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        captured = io.StringIO()
        with patch.object(sys, "argv", ["stock.py", "AAPL", "-p", "1d", "-f", "json"]):
            with patch.object(sys, "stdout", captured):
                try:
                    stock.main()
                except SystemExit:
                    pass
        out = captured.getvalue()
        data = json.loads(out)
        self.assertIn("AAPL", data)
        self.assertEqual(data["AAPL"]["bars"][0]["close"], 150.0)

    @patch("urllib.request.urlopen")
    def test_multiple_tickers(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        captured = io.StringIO()
        with patch.object(sys, "argv", ["stock.py", "AAPL", "MSFT", "-p", "1d"]):
            with patch.object(sys, "stdout", captured):
                try:
                    stock.main()
                except SystemExit:
                    pass
        out = captured.getvalue()
        self.assertIn("Apple Inc.", out)
        self.assertEqual(out.count("Apple Inc."), 2)

    @patch("urllib.request.urlopen")
    def test_invalid_ticker(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_ERROR)
        captured = io.StringIO()
        err = io.StringIO()
        with patch.object(sys, "argv", ["stock.py", "DEAD", "-p", "1d"]):
            with patch.object(sys, "stdout", captured):
                with patch.object(sys, "stderr", err):
                    try:
                        stock.main()
                    except SystemExit:
                        pass
        self.assertIn("ERROR", err.getvalue())

    @patch("urllib.request.urlopen")
    def test_volume_stats(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        captured = io.StringIO()
        with patch.object(sys, "argv", ["stock.py", "AAPL", "-p", "5d"]):
            with patch.object(sys, "stdout", captured):
                try:
                    stock.main()
                except SystemExit:
                    pass
        out = captured.getvalue()
        self.assertIn("Avg volume:", out)
        self.assertIn("Volume change:", out)

    @patch("urllib.request.urlopen")
    def test_graph_flag(self, mock_urlopen):
        if not stock.MATPLOTLIB_OK:
            self.skipTest("matplotlib not installed")
        mock_urlopen.return_value = _mock_response(SAMPLE_YAHOO_RESPONSE)
        captured = io.StringIO()
        with patch.object(sys, "argv", ["stock.py", "AAPL", "-p", "5d", "--graph", "--graph-output", "/tmp/test_graph.png"]):
            with patch.object(sys, "stdout", captured):
                try:
                    stock.main()
                except SystemExit:
                    pass
        out = captured.getvalue()
        self.assertIn("Graph saved", out)
        self.assertTrue(os.path.exists("/tmp/test_graph.png"))
        os.remove("/tmp/test_graph.png")


if __name__ == "__main__":
    unittest.main()
