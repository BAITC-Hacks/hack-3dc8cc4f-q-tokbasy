"""Mocked tests for the optional OpenAI explanation layer."""

import json
import os
import sys
import types
import unittest
from unittest.mock import patch

# The core test suite intentionally runs without third-party packages. Provide
# a tiny import-only FastAPI stand-in when dependencies have not been installed.
try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    class _FastAPI:
        def __init__(self, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda function: function

    class _HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

    fastapi_stub = types.ModuleType("fastapi")
    fastapi_stub.FastAPI = _FastAPI
    fastapi_stub.HTTPException = _HTTPException
    middleware_stub = types.ModuleType("fastapi.middleware")
    cors_stub = types.ModuleType("fastapi.middleware.cors")
    cors_stub.CORSMiddleware = object
    sys.modules.update({
        "fastapi": fastapi_stub,
        "fastapi.middleware": middleware_stub,
        "fastapi.middleware.cors": cors_stub,
    })

import main
from ai_service import AICareerCoach, deterministic_explanation, verified_facts


VALID_OUTPUT = {
    "headline": "A focused next step",
    "summary": "This quest addresses a verified gap.",
    "why_this_quest": ["It develops a required skill."],
    "expected_impact": "Python: 2 → 3, target 4",
    "career_connection": "It supports the target grade.",
    "history_insight": "Participation history was included.",
}


class FakeResponses:
    def __init__(self, output):
        self.output = output
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return types.SimpleNamespace(output_text=self.output)


def fake_openai_module(output):
    responses = FakeResponses(output)
    client = types.SimpleNamespace(responses=responses)
    module = types.SimpleNamespace(OpenAI=lambda **kwargs: client)
    return module, responses


class AIServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.employee = main.data.employees_by_id["E0001"]
        cls.gap = main.engine.career_gap("E0001")
        cls.recommendation = main.engine.recommendations("E0001")[0]
        cls.facts = verified_facts(cls.employee, cls.gap, cls.recommendation)

    def test_success_uses_responses_api_and_allowlisted_facts(self):
        module, responses = fake_openai_module(json.dumps(VALID_OUTPUT))
        with patch.dict(sys.modules, {"openai": module}):
            result = AICareerCoach(api_key="test-key", model="test-model").explain(self.facts)
        self.assertEqual(result["source"], "openai")
        request = responses.requests[0]
        self.assertEqual(request["model"], "test-model")
        sent = json.loads(request["input"])
        self.assertEqual(sent, self.facts)
        self.assertNotIn("full_name", request["input"])
        self.assertNotIn("test-key", json.dumps(request))

    def test_missing_key_uses_deterministic_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            result = AICareerCoach().explain(self.facts)
        self.assertEqual(result["source"], "deterministic")

    def test_openai_failure_uses_deterministic_fallback(self):
        module, _ = fake_openai_module(TimeoutError("network timeout"))
        with patch.dict(sys.modules, {"openai": module}):
            result = AICareerCoach(api_key="secret").explain(self.facts)
        self.assertEqual(result, deterministic_explanation(self.facts))

    def test_invalid_openai_output_uses_deterministic_fallback(self):
        for output in ("not json", json.dumps({"headline": "incomplete"})):
            module, _ = fake_openai_module(output)
            with self.subTest(output=output), patch.dict(sys.modules, {"openai": module}):
                self.assertEqual(AICareerCoach(api_key="secret").explain(self.facts)["source"], "deterministic")


class AIEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_ai_copy_cannot_overwrite_deterministic_facts_or_leak_secret(self):
        original = main.engine.recommendations("E0001", limit=3)

        class MockCoach:
            enabled = True
            model = "mock-model"

            def explain(self, facts):
                return {"source": "openai", **VALID_OUTPUT, "event_id": "FAKE", "score": 1000, "actual_gain": 99}

        with patch.object(main, "ai_coach", MockCoach()):
            response = await main.get_ai_recommendations("E0001")

        self.assertEqual(response["provider"], "openai")
        self.assertEqual(len(response["recommendations"]), len(original))
        for actual, expected in zip(response["recommendations"], original):
            self.assertEqual(actual["event_id"], expected["event_id"])
            self.assertEqual(actual["score"], expected["score"])
            self.assertEqual(actual["skill_impacts"], expected["skill_impacts"])
        serialized = json.dumps(response)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("secret", serialized)

    async def test_disabled_endpoint_still_returns_recommendations(self):
        coach = AICareerCoach(api_key="")
        with patch.object(main, "ai_coach", coach):
            response = await main.get_ai_recommendations("E0001")
        self.assertFalse(response["ai_enabled"])
        self.assertIsNone(response["provider"])
        self.assertTrue(response["recommendations"])
        self.assertTrue(all(item["explanation"]["source"] == "deterministic" for item in response["recommendations"]))


if __name__ == "__main__":
    unittest.main()
