"""Delivery regression tests; all webhook requests are mocked."""

import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

import send_feishu as sender


class DeliveryTests(unittest.TestCase):
    def response(self, body):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = body
        return response

    def test_explicit_acknowledgement_required(self):
        for body in (b"not json", b"{}", b"[]", b'{"code":false}', b'{"code":1}'):
            with self.subTest(body=body), patch.object(sender.urllib.request, "urlopen", return_value=self.response(body)):
                with self.assertRaises(RuntimeError):
                    sender.send_chunk("https://example.invalid", "news", 1, 1)

    def test_both_success_response_formats(self):
        for body in (b'{"code":0}', b'{"StatusCode":0}', b'{"code":"0"}'):
            with self.subTest(body=body), patch.object(sender.urllib.request, "urlopen", return_value=self.response(body)):
                sender.send_chunk("https://example.invalid", "news", 1, 1)

    def test_long_chinese_and_emoji_reports_fit_without_loss(self):
        report = "财经新闻📈\n" * 12000
        chunks = sender.split_text(report)
        self.assertEqual("".join(chunks), report)
        for chunk in chunks:
            payload = sender.markdown_to_card(chunk, "每日财经日报")
            self.assertLess(len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 100, sender.MAX_PAYLOAD_BYTES)

    def test_timeout_does_not_claim_success_or_blindly_retry(self):
        with patch.object(sender.urllib.request, "urlopen", side_effect=TimeoutError("private webhook")) as request:
            with self.assertRaisesRegex(RuntimeError, "unconfirmed") as error:
                sender.send_chunk("https://example.invalid", "news", 1, 1)
            self.assertNotIn("private webhook", str(error.exception))
            self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
