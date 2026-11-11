"""Planning tests with synthetic target profiles; not GPU/model benchmarks."""

import base64
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_release_policy as signature_fixture
from models import (
    GIB,
    Preferences,
    guided_recommendation,
    load_catalog,
    recommend,
    validate_catalog,
)

NOW = 1794441600


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        clock = patch("models.time.time", return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.catalog = load_catalog(now=NOW)
        self.target = {
            "architecture": "amd64",
            "cpuCount": 8,
            "ramBytes": 16 * GIB,
            "freeBytes": 30 * GIB,
            "usableAcceleration": None,
        }

    def preferences(self, priority="quality", use="dedicated", budget=8 * GIB):
        return Preferences("everyday", ("de", "en"), priority, use, budget)

    def test_optional_terminal_flow_and_skip_do_not_change_a_runtime(self):
        messages = {
            key: key
            for key in (
                "aiPlanNow",
                "aiPurpose",
                "aiLanguages",
                "aiPriority",
                "aiConcurrent",
                "aiBudget",
                "aiEstimates",
                "aiAlternatives",
            )
        }
        with (
            patch("builtins.input", return_value="skip"),
            patch("models.load_catalog") as loader,
        ):
            self.assertIsNone(guided_recommendation(self.target, messages))
        loader.assert_not_called()
        with (
            patch(
                "builtins.input",
                side_effect=["PLAN", "everyday", "de,en", "quality", "work", "8"],
            ),
            patch("builtins.print"),
        ):
            result = guided_recommendation(self.target, messages, self.catalog)
        self.assertEqual(result["recommended"]["id"], "qwen3:4b")
        self.assertFalse(result["downloadsStarted"])

    def test_quality_and_resource_priority_use_exact_reviewed_variants(self):
        quality = recommend(self.catalog, self.target, self.preferences())
        small = recommend(self.catalog, self.target, self.preferences("resources"))
        self.assertEqual(quality["recommended"]["id"], "qwen3:4b")
        self.assertEqual(small["recommended"]["id"], "qwen3:0.6b")
        self.assertEqual(small["recommended"]["downloadBytes"], 522653767)
        self.assertTrue(quality["estimates"])
        self.assertFalse(quality["benchmarkMeasured"])
        self.assertFalse(quality["cloudEnabled"])
        self.assertFalse(quality["downloadsStarted"])

    def test_reserves_budget_and_gaming_reduce_capacity(self):
        target = {**self.target, "ramBytes": 8 * GIB}
        dedicated = recommend(self.catalog, target, self.preferences())
        gaming = recommend(self.catalog, target, self.preferences(use="gaming"))
        self.assertEqual(dedicated["recommended"]["id"], "qwen3:0.6b")
        self.assertIsNone(gaming["recommended"])
        self.assertIsNone(
            recommend(self.catalog, self.target, self.preferences(budget=GIB))[
                "recommended"
            ]
        )

    def test_unknown_hardware_never_becomes_fictitious_capacity(self):
        for key in ("architecture", "ramBytes", "freeBytes", "cpuCount"):
            with self.subTest(key=key):
                value = recommend(
                    self.catalog, {**self.target, key: None}, self.preferences()
                )
                self.assertEqual(value["reason"], "hardware_unknown")
                self.assertIsNone(value["recommended"])
        value = recommend(
            self.catalog,
            {**self.target, "gpuVendorObservation": ["Synthetic GPU, 99999"]},
            self.preferences(),
        )
        self.assertEqual(value["executionEstimate"], "cpu-unbenchmarked")

    def test_disk_and_unsupported_language_are_not_ignored(self):
        self.assertIsNone(
            recommend(
                self.catalog, {**self.target, "freeBytes": GIB}, self.preferences()
            )["recommended"]
        )
        with self.assertRaisesRegex(ValueError, "E_MODEL_PREFERENCES"):
            recommend(
                self.catalog,
                self.target,
                Preferences("everyday", ("unsupported",), "speed", "work", GIB),
            )

    def test_expiry_sequence_duplicate_and_unsafe_sources_are_rejected(self):
        for key, replacement in (
            ("expiresAt", NOW),
            ("sequence", 0),
            ("models", [self.catalog["models"][0]] * 2),
        ):
            document = {**self.catalog, key: replacement}
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_catalog(document, now=NOW)
        document = copy.deepcopy(self.catalog)
        document["models"][0]["licenseUrl"] = "http://untrusted.test"
        with self.assertRaisesRegex(ValueError, "E_MODEL_CATALOG_SOURCE"):
            validate_catalog(document, now=NOW)
        with self.assertRaisesRegex(ValueError, "E_MODEL_CATALOG_SEQUENCE"):
            validate_catalog(self.catalog, minimum_sequence=2, now=NOW)


class SignedCatalogTests(unittest.TestCase):
    def test_actual_signed_catalog_scope_and_tampering(self):
        # Reuse the existing isolated Ed25519 test-key fixture, no production key.
        fixture = signature_fixture.SignatureTests(
            methodName="test_tampered_payload_is_rejected"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.trust["keys"][0].update(
            notBefore=NOW - 100,
            notAfter=NOW + 1000,
            usages=["model-catalog", "trust-rotation"],
        )
        document = load_catalog(now=NOW)
        envelope = fixture.sign(document)
        self.assertEqual(load_catalog(envelope, fixture.trust, now=NOW), document)
        changed = json.loads(envelope)
        document["sequence"] = 100
        changed["payload"] = base64.b64encode(json.dumps(document).encode()).decode()
        with self.assertRaisesRegex(ValueError, "E_SIGNATURE"):
            load_catalog(json.dumps(changed).encode(), fixture.trust, now=NOW)
        with self.assertRaisesRegex(ValueError, "E_MODEL_TRUST_REQUIRED"):
            load_catalog(envelope, now=NOW)
        fixture.trust["keys"][0]["usages"] = ["release-index", "trust-rotation"]
        with self.assertRaisesRegex(ValueError, "E_TRUST_KEY"):
            load_catalog(envelope, fixture.trust, now=NOW)
