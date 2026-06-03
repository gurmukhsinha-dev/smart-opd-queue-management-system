from pathlib import Path
import sys
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from queue_engine import QueueEngine, demo_data  # noqa: E402


def build_engine() -> QueueEngine:
    engine = QueueEngine()
    engine.load_demo_data(*demo_data())
    return engine


class QueueEngineSmokeTests(unittest.TestCase):
    def test_bootstrap_contains_recruiter_visible_system_sections(self):
        engine = build_engine()

        bootstrap = engine.get_bootstrap()

        self.assertTrue({"summary", "patients", "doctors", "analytics", "slot_catalog"}.issubset(bootstrap))
        self.assertGreater(bootstrap["summary"]["active_tokens"], 0)
        self.assertTrue(bootstrap["departments"])

    def test_register_patient_assigns_token_and_notification_plan(self):
        engine = build_engine()
        department = engine.doctors[0]["department"]
        existing_tokens = [
            patient["token_number"]
            for patient in engine.patients
            if patient["department"] == department
        ]

        result = engine.register_patient(
            {
                "full_name": "Portfolio Test Patient",
                "mobile_number": "7777777777",
                "age": 32,
                "preferred_language": "English",
                "department": department,
                "priority": "normal",
            }
        )

        patient = result["patient"]
        self.assertGreater(patient["token_number"], max(existing_tokens))
        self.assertEqual(patient["department"], department)
        self.assertEqual(result["queue_state"]["department"], department)
        self.assertTrue(
            any(
                notification["patient_id"] == patient["patient_id"]
                for notification in engine.notifications
            )
        )


if __name__ == "__main__":
    unittest.main()
