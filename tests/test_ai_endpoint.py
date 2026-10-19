import unittest

from fastapi.testclient import TestClient
from main import app


class TestAIClassificationEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_billing_classification(self):
        response = self.client.post(
            "/ai/classify",
            json={"text": "I was charged twice for my subscription."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "billing")

    def test_bug_classification(self):
        response = self.client.post(
            "/ai/classify",
            json={"text": "The application crashes when I log in."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "bug")

    def test_feature_classification(self):
        response = self.client.post(
            "/ai/classify",
            json={"text": "Please add a dark mode feature."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "feature")

    def test_other_classification(self):
        response = self.client.post(
            "/ai/classify",
            json={"text": "I have a question about your product."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "other")

    def test_response_schema(self):
        response = self.client.post(
            "/ai/classify",
            json={"text": "I was charged twice."},
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(
            set(data.keys()),
            {"category", "urgency", "confidence", "reason"},
        )
        self.assertIn(data["urgency"], ["low", "normal", "high"])
        self.assertGreaterEqual(data["confidence"], 0.0)
        self.assertLessEqual(data["confidence"], 1.0)
        self.assertIsInstance(data["reason"], str)

    def test_rejects_empty_message(self):
        response = self.client.post(
            "/ai/classify",
            json={"text": ""},
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_overlong_message(self):
        response = self.client.post(
            "/ai/classify",
            json={"text": "a" * 2001},
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_unexpected_input_field(self):
        response = self.client.post(
            "/ai/classify",
            json={
                "text": "I need help with my account.",
                "unexpected": "extra data",
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
