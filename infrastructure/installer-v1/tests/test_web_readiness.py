"""Finite Web readiness and fail-closed TLS; network responses injected."""

import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import web_readiness


class WebReadiness(unittest.TestCase):
    def test_transient_refusal_and_proxy_warmup_require_real_success(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = b"<html>local login</html>"
        opener = Mock()
        opener.open.side_effect = [
            URLError(ConnectionRefusedError()),
            HTTPError("https://fixture.test/login", 502, "warmup", {}, None),
            response,
        ]
        with patch("runtime.time.sleep"):
            web_readiness(opener, "https://fixture.test/login")
        self.assertEqual(opener.open.call_count, 3)

    def test_certificate_failure_is_immediate_and_does_not_expose_details(self):
        opener = Mock()
        opener.open.side_effect = URLError(
            ssl.SSLCertVerificationError("private fixture detail")
        )
        with (
            patch("runtime.time.sleep") as sleep,
            self.assertRaisesRegex(ValueError, "^E_WEB_TLS$"),
        ):
            web_readiness(opener, "https://fixture.test/login")
        self.assertEqual(opener.open.call_count, 1)
        sleep.assert_not_called()

    def test_repeated_refusal_has_finite_attempts_and_never_reports_success(self):
        opener = Mock()
        opener.open.side_effect = URLError(ConnectionRefusedError())
        with patch("runtime.time.sleep"), self.assertRaisesRegex(ValueError, "^E_WEB$"):
            web_readiness(opener, "https://fixture.test/login")
        self.assertEqual(opener.open.call_count, 12)

    def test_permanent_http_failure_is_not_retried(self):
        opener = Mock()
        opener.open.side_effect = HTTPError(
            "https://fixture.test/login", 404, "missing", {}, None
        )
        with (
            patch("runtime.time.sleep") as sleep,
            self.assertRaisesRegex(ValueError, "^E_WEB$"),
        ):
            web_readiness(opener, "https://fixture.test/login")
        self.assertEqual(opener.open.call_count, 1)
        sleep.assert_not_called()

    def test_overall_budget_expiry_prevents_further_connections(self):
        opener = Mock()
        with (
            patch("runtime.time.monotonic", side_effect=[0, 61]),
            self.assertRaisesRegex(ValueError, "^E_WEB$"),
        ):
            web_readiness(opener, "https://fixture.test/login")
        opener.open.assert_not_called()
