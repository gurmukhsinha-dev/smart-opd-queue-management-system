from pathlib import Path
import os
import sys
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

os.environ["MYSQL_ENABLED"] = "0"
os.environ["OTP_MODE"] = "mock"
os.environ["OTP_PROVIDER"] = "mock"
os.environ["NOTIFICATION_MODE"] = "mock"

import app as app_module  # noqa: E402
from queue_engine import demo_data  # noqa: E402


class FlaskApiContractTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True)
        app_module.persistence.config.enabled = False
        app_module.user_service.config.enabled = False
        app_module.otp_service.mode = "mock"
        app_module.otp_service.provider = "mock"
        app_module.otp_service.pending.clear()
        app_module.otp_service.verified_numbers.clear()
        app_module.event_subscribers.clear()
        app_module.engine.load_demo_data(*demo_data())
        self.client = app_module.app.test_client()

    def test_health_endpoint_reports_memory_mode(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["persistence"]["mode"], "memory")
        self.assertFalse(payload["persistence"]["enabled"])

    def test_bootstrap_endpoint_exposes_core_dashboard_contract(self):
        response = self.client.get("/api/bootstrap")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("summary", payload)
        self.assertIn("patients", payload)
        self.assertIn("doctors", payload)
        self.assertIn("analytics", payload)
        self.assertGreater(payload["summary"]["active_tokens"], 0)
        self.assertGreater(len(payload["doctors"]), 0)

    def test_admin_endpoint_requires_login_and_accepts_admin_token(self):
        unauthorized = self.client.get("/api/admin/persistence")
        self.assertEqual(unauthorized.status_code, 401)

        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin@smartopd.local", "password": "Admin@123"},
        )
        self.assertEqual(login.status_code, 200)
        login_payload = login.get_json()
        self.assertEqual(login_payload["user"]["role"], "admin")
        self.assertTrue(login_payload["token"])

        authorized = self.client.get(
            "/api/admin/persistence",
            headers={"Authorization": f"Bearer {login_payload['token']}"},
        )
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(authorized.get_json()["mode"], "memory")

    def test_patient_registration_requires_otp_then_can_be_tracked(self):
        mobile_number = "7777777777"
        send_otp = self.client.post(
            "/api/patients/otp/send",
            json={"mobile_number": mobile_number},
        )
        self.assertEqual(send_otp.status_code, 200)
        otp_code = send_otp.get_json()["otp_preview"]

        verify_otp = self.client.post(
            "/api/patients/otp/verify",
            json={"mobile_number": mobile_number, "otp": otp_code},
        )
        self.assertEqual(verify_otp.status_code, 200)
        self.assertTrue(verify_otp.get_json()["verified"])

        department = app_module.engine.doctors[0]["department"]
        register = self.client.post(
            "/api/patients/register",
            json={
                "full_name": "API Contract Patient",
                "mobile_number": mobile_number,
                "age": 29,
                "preferred_language": "English",
                "department": department,
                "priority": "normal",
            },
        )
        self.assertEqual(register.status_code, 201)
        patient = register.get_json()["patient"]
        self.assertEqual(patient["department"], department)
        self.assertGreater(patient["token_number"], 0)

        track = self.client.get(f"/api/patients/track?q={patient['patient_id']}")
        self.assertEqual(track.status_code, 200)
        self.assertEqual(track.get_json()["patient"]["patient_id"], patient["patient_id"])


if __name__ == "__main__":
    unittest.main()
