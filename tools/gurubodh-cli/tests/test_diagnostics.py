import math
from types import SimpleNamespace
import unittest

import gurubodh.audit as audit
from gurubodh.diagnostics import safe_request_diagnostics
import gurubodh.proofreading.policy as policy
import gurubodh.proofreading.service as service


class DiagnosticsTests(unittest.TestCase):
    def test_dictionary_and_object_inputs_preserve_the_allowlisted_payload(self):
        raw = {
            "attempts": [
                {
                    "attempt": 2,
                    "http_status": 503,
                    "elapsed_seconds": 1.23456,
                    "retry_delay_seconds": 0,
                    "server_retry_hint_used": True,
                    "response_body": "private response",
                    "request_body": "private request",
                    "unknown": "excluded",
                }
            ],
            "terminal_retry_exhaustion_reason": "service_unavailable_retry_exhausted",
            "source_text": "private source",
        }
        expected = {
            "attempts": [
                {
                    "attempt": 2,
                    "http_status": 503,
                    "elapsed_seconds": 1.235,
                    "retry_delay_seconds": 0.0,
                    "server_retry_hint_used": True,
                }
            ],
            "terminal_retry_exhaustion_reason": "service_unavailable_retry_exhausted",
        }

        self.assertEqual(safe_request_diagnostics(raw), expected)
        self.assertEqual(
            safe_request_diagnostics(SimpleNamespace(request_diagnostics=raw)),
            expected,
        )

    def test_invalid_values_are_omitted_without_broadening_numeric_inputs(self):
        diagnostics = safe_request_diagnostics(
            {
                "attempts": [
                    None,
                    {},
                    {
                        "attempt": 0,
                        "http_status": 99,
                        "elapsed_seconds": -0.001,
                        "retry_delay_seconds": math.inf,
                        "server_retry_hint_used": "yes",
                    },
                    {
                        "attempt": 1.5,
                        "http_status": 600,
                        "elapsed_seconds": True,
                        "retry_delay_seconds": "1.0",
                    },
                ],
                "terminal_retry_exhaustion_reason": "INVALID-REASON",
            }
        )

        self.assertIsNone(diagnostics)
        for value in (None, [], "diagnostics", SimpleNamespace()):
            with self.subTest(value=value):
                self.assertIsNone(safe_request_diagnostics(value))

    def test_attempts_are_bounded_before_filtering_and_numeric_limits_hold(self):
        attempts = [
            {
                "attempt": index,
                "http_status": 599,
                "elapsed_seconds": 0,
                "retry_delay_seconds": 1e100,
                "server_retry_hint_used": False,
            }
            for index in range(1, 34)
        ]

        diagnostics = safe_request_diagnostics({"attempts": attempts})

        self.assertEqual(len(diagnostics["attempts"]), 32)
        self.assertEqual(diagnostics["attempts"][-1]["attempt"], 32)
        self.assertEqual(diagnostics["attempts"][0]["http_status"], 599)
        self.assertEqual(diagnostics["attempts"][0]["elapsed_seconds"], 0.0)
        self.assertEqual(
            diagnostics["attempts"][0]["retry_delay_seconds"], 1e100
        )
        self.assertIsNone(diagnostics["terminal_retry_exhaustion_reason"])

        bounded_after_invalid = safe_request_diagnostics(
            {"attempts": [None] * 32 + [{"attempt": 33}]}
        )
        self.assertIsNone(bounded_after_invalid)

    def test_terminal_reason_is_bounded_and_can_exist_without_attempts(self):
        self.assertEqual(
            safe_request_diagnostics(
                {"terminal_retry_exhaustion_reason": "a" * 80}
            ),
            {
                "attempts": [],
                "terminal_retry_exhaustion_reason": "a" * 80,
            },
        )
        self.assertIsNone(
            safe_request_diagnostics(
                {"terminal_retry_exhaustion_reason": "a" * 81}
            )
        )

    def test_all_consumers_resolve_to_the_authoritative_implementation(self):
        self.assertIs(policy.safe_request_diagnostics, safe_request_diagnostics)
        self.assertIs(audit.safe_request_diagnostics, safe_request_diagnostics)
        self.assertIs(service.safe_request_diagnostics, safe_request_diagnostics)


if __name__ == "__main__":
    unittest.main()
