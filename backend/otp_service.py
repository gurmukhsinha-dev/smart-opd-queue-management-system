from __future__ import annotations

import base64
import random
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from env_utils import get_env
from notification_service import dispatch_direct_message


class OTPService:
    def __init__(self) -> None:
        self.mode = get_env("OTP_MODE", "mock").lower()
        self.provider = get_env("OTP_PROVIDER", "mock").lower()
        self.channel = get_env("OTP_CHANNEL", "sms").lower()
        self.expiry_minutes = int(get_env("OTP_EXPIRY_MINUTES", "5"))
        self.pending: dict[str, dict] = {}
        self.verified_numbers: set[str] = set()

    def send_otp(self, mobile_number: str) -> dict:
        code = f"{random.randint(0, 999999):06d}"
        expires_at = datetime.utcnow() + timedelta(minutes=self.expiry_minutes)

        response = {
            "status": "sent",
            "mobile_number": mobile_number,
            "expires_at": expires_at.isoformat() + "Z",
            "mode": self.mode,
            "provider": self.provider,
            "channel": self.channel,
        }

        if self.mode == "mock" or self.provider == "mock":
            self.pending[mobile_number] = {
                "code": code,
                "expires_at": expires_at,
            }
            response["otp_preview"] = code
            return response

        if self.provider == "twilio_verify":
            delivery = self._send_via_twilio_verify(mobile_number)
            response.update(delivery)
            return response

        self.pending[mobile_number] = {
            "code": code,
            "expires_at": expires_at,
        }
        delivery = dispatch_direct_message(
            channel=self.channel,
            mobile_number=mobile_number,
            message=self._build_otp_message(code),
            provider=self.provider,
            metadata={"notification_id": f"otp-{mobile_number[-4:]}"},
            mode_override=self.mode,
        )

        response.update(
            {
                "status": "sent" if delivery["status"] in {"sent", "delivered"} else "failed",
                "provider_message_id": delivery["provider_message_id"],
                "delivery_status": delivery["status"],
                "error": delivery["error"],
            }
        )
        return response

    def verify_otp(self, mobile_number: str, code: str) -> dict:
        if self.mode != "mock" and self.provider == "twilio_verify":
            return self._verify_via_twilio_verify(mobile_number, code)

        record = self.pending.get(mobile_number)
        if record is None:
            return {"verified": False, "message": "No OTP request found for this mobile number."}
        if datetime.utcnow() > record["expires_at"]:
            self.pending.pop(mobile_number, None)
            return {"verified": False, "message": "OTP expired. Please request a fresh code."}
        if record["code"] != code:
            return {"verified": False, "message": "Invalid OTP."}
        self.pending.pop(mobile_number, None)
        self.verified_numbers.add(mobile_number)
        return {"verified": True, "mobile_number": mobile_number}

    def is_verified(self, mobile_number: str) -> bool:
        return mobile_number in self.verified_numbers

    def consume_verification(self, mobile_number: str) -> None:
        self.verified_numbers.discard(mobile_number)

    def _build_otp_message(self, code: str) -> str:
        template = get_env(
            "OTP_MESSAGE_TEMPLATE",
            "Smart OPD verification code: {code}. It expires in {minutes} minutes.",
        )
        return template.format(code=code, minutes=self.expiry_minutes)

    def _send_via_twilio_verify(self, mobile_number: str) -> dict:
        account_sid = get_env("TWILIO_ACCOUNT_SID", "")
        auth_token = get_env("TWILIO_AUTH_TOKEN", "")
        service_sid = get_env("TWILIO_VERIFY_SERVICE_SID", "")
        if not account_sid or not auth_token or not service_sid:
            return {
                "status": "failed",
                "delivery_status": "failed",
                "provider_message_id": None,
                "error": "Missing Twilio Verify configuration.",
            }

        endpoint = f"https://verify.twilio.com/v2/Services/{service_sid}/Verifications"
        payload = urllib.parse.urlencode(
            {"To": self._normalize_phone_number(mobile_number), "Channel": self.channel}
        ).encode()
        credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            return {
                "status": "failed",
                "delivery_status": "failed",
                "provider_message_id": None,
                "error": self._error_body(exc),
            }
        except OSError as exc:
            return {
                "status": "failed",
                "delivery_status": "failed",
                "provider_message_id": None,
                "error": str(exc),
            }

        return {
            "status": "sent",
            "delivery_status": data.get("status", "pending"),
            "provider_message_id": data.get("sid"),
            "error": None,
        }

    def _verify_via_twilio_verify(self, mobile_number: str, code: str) -> dict:
        account_sid = get_env("TWILIO_ACCOUNT_SID", "")
        auth_token = get_env("TWILIO_AUTH_TOKEN", "")
        service_sid = get_env("TWILIO_VERIFY_SERVICE_SID", "")
        if not account_sid or not auth_token or not service_sid:
            return {"verified": False, "message": "Missing Twilio Verify configuration."}

        endpoint = f"https://verify.twilio.com/v2/Services/{service_sid}/VerificationCheck"
        payload = urllib.parse.urlencode(
            {"To": self._normalize_phone_number(mobile_number), "Code": code}
        ).encode()
        credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            return {"verified": False, "message": self._error_body(exc)}
        except OSError as exc:
            return {"verified": False, "message": str(exc)}

        if data.get("status") == "approved":
            self.verified_numbers.add(mobile_number)
            return {"verified": True, "mobile_number": mobile_number}
        return {"verified": False, "message": "Invalid OTP."}

    @staticmethod
    def _normalize_phone_number(mobile_number: str) -> str:
        digits = "".join(char for char in mobile_number if char.isdigit())
        if digits.startswith("91") and len(digits) == 12:
            return f"+{digits}"
        if len(digits) == 10:
            return f"+91{digits}"
        return mobile_number if mobile_number.startswith("+") else f"+{digits}"

    @staticmethod
    def _error_body(exc: urllib.error.HTTPError) -> str:
        try:
            return exc.read().decode() or str(exc)
        except OSError:
            return str(exc)
