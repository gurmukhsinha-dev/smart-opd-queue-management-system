from __future__ import annotations

from env_utils import env_source, get_env, get_list_env, has_env


def build_deployment_readiness(persistence_health: dict, notification_settings: dict) -> dict:
    app_secret_value = get_env("APP_SECRET_KEY", "")
    origins = get_list_env("APP_ALLOWED_ORIGINS")

    otp_mode = get_env("OTP_MODE", "mock").lower()
    otp_provider = get_env("OTP_PROVIDER", "mock").lower()
    otp_channel = get_env("OTP_CHANNEL", "sms").lower()
    otp_check = _provider_check(otp_provider, otp_channel, treat_mock_as_ready=otp_mode != "live")

    notification_mode = get_env("NOTIFICATION_MODE", "mock").lower()
    sms_provider = notification_settings.get("sms_provider", "mock")
    whatsapp_provider = notification_settings.get("whatsapp_provider", "mock")
    sms_check = _provider_check(sms_provider, "sms", treat_mock_as_ready=notification_mode != "live")
    whatsapp_check = _provider_check(
        whatsapp_provider,
        "whatsapp",
        treat_mock_as_ready=notification_mode != "live",
    )

    blockers: list[str] = []
    if persistence_health.get("mode") != "mysql" or not persistence_health.get("connected"):
        blockers.append("MySQL persistence is not connected.")
    if not origins:
        blockers.append("APP_ALLOWED_ORIGINS is empty.")
    if app_secret_value in {"", "smart-opd-dev-secret"}:
        blockers.append("APP_SECRET_KEY is using a missing or development value.")
    if otp_mode == "live" and not otp_check["ready"]:
        blockers.append(f"OTP provider is not ready: {', '.join(otp_check['missing']) or otp_check['note']}")
    if notification_mode == "live" and not sms_check["ready"]:
        blockers.append(f"SMS provider is not ready: {', '.join(sms_check['missing']) or sms_check['note']}")
    if notification_mode == "live" and not whatsapp_check["ready"]:
        blockers.append(
            f"WhatsApp provider is not ready: {', '.join(whatsapp_check['missing']) or whatsapp_check['note']}"
        )

    return {
        "status": "ready" if not blockers else "attention_required",
        "blockers": blockers,
        "persistence": persistence_health,
        "security": {
            "app_secret_configured": app_secret_value not in {"", "smart-opd-dev-secret"},
            "app_secret_source": env_source("APP_SECRET_KEY"),
            "allowed_origins": origins,
            "restricted_origins": bool(origins),
        },
        "otp": {
            "mode": otp_mode,
            "provider": otp_provider,
            "channel": otp_channel,
            **otp_check,
        },
        "notifications": {
            "mode": notification_mode,
            "sms": sms_check,
            "whatsapp": whatsapp_check,
        },
    }


def build_provider_diagnostics(notification_settings: dict) -> dict:
    otp_mode = get_env("OTP_MODE", "mock").lower()
    otp_provider = get_env("OTP_PROVIDER", "mock").lower()
    otp_channel = get_env("OTP_CHANNEL", "sms").lower()
    notification_mode = get_env("NOTIFICATION_MODE", "mock").lower()
    sms_provider = notification_settings.get("sms_provider", "mock")
    whatsapp_provider = notification_settings.get("whatsapp_provider", "mock")

    return {
        "otp": _provider_diagnostic_entry(otp_provider, otp_channel, otp_mode),
        "sms": _provider_diagnostic_entry(sms_provider, "sms", notification_mode),
        "whatsapp": _provider_diagnostic_entry(whatsapp_provider, "whatsapp", notification_mode),
    }


def _provider_check(provider: str, channel: str, treat_mock_as_ready: bool) -> dict:
    normalized_provider = (provider or "mock").strip().lower()

    if normalized_provider == "mock":
        return {
            "provider": "mock",
            "channel": channel,
            "ready": treat_mock_as_ready,
            "missing": [],
            "note": "Safe mock mode is enabled." if treat_mock_as_ready else "Live provider credentials are required.",
        }

    if normalized_provider == "twilio":
        required = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"]
        required.append("TWILIO_WHATSAPP_FROM" if channel == "whatsapp" else "TWILIO_SMS_FROM")
        return _build_check("twilio", channel, required)

    if normalized_provider == "msg91":
        if channel == "whatsapp":
            return {
                "provider": "msg91",
                "channel": channel,
                "ready": False,
                "missing": [],
                "note": "Built-in MSG91 support is SMS flow only. Use Gupshup or Twilio for WhatsApp.",
            }
        return _build_check("msg91", channel, ["MSG91_AUTH_KEY", "MSG91_SMS_FLOW_ID"])

    if normalized_provider == "gupshup":
        if channel == "whatsapp":
            return _build_check("gupshup", channel, ["GUPSHUP_API_KEY", "GUPSHUP_WHATSAPP_SOURCE"])
        return _build_check("gupshup", channel, ["GUPSHUP_SMS_USER_ID", "GUPSHUP_SMS_PASSWORD"])

    if normalized_provider == "webhook":
        specific_key = "WHATSAPP_WEBHOOK_URL" if channel == "whatsapp" else "SMS_WEBHOOK_URL"
        shared_key = "NOTIFICATION_WEBHOOK_URL"
        ready = has_env(specific_key) or has_env(shared_key)
        return {
            "provider": "webhook",
            "channel": channel,
            "ready": ready,
            "missing": [] if ready else [specific_key, shared_key],
            "note": "Webhook provider ready." if ready else "Provide a channel-specific or shared webhook URL.",
        }

    return {
        "provider": normalized_provider,
        "channel": channel,
        "ready": False,
        "missing": [],
        "note": "Unknown provider configuration.",
    }


def _build_check(provider: str, channel: str, required_keys: list[str]) -> dict:
    missing = [key for key in required_keys if not has_env(key)]
    return {
        "provider": provider,
        "channel": channel,
        "ready": not missing,
        "missing": missing,
        "note": "Configured." if not missing else "Missing required provider settings.",
    }


def _provider_diagnostic_entry(provider: str, channel: str, mode: str) -> dict:
    normalized_provider = (provider or "mock").strip().lower()
    treat_mock_as_ready = mode != "live"
    check = _provider_check(normalized_provider, channel, treat_mock_as_ready)
    required_keys = _required_keys_for_provider(normalized_provider, channel)
    return {
        "mode": mode,
        "provider": normalized_provider,
        "channel": channel,
        "ready": check["ready"],
        "missing": check["missing"],
        "note": check["note"],
        "secrets": [
            {"key": key, "source": env_source(key), "configured": has_env(key)}
            for key in required_keys
        ],
    }


def _required_keys_for_provider(provider: str, channel: str) -> list[str]:
    if provider == "twilio":
        return [
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_WHATSAPP_FROM" if channel == "whatsapp" else "TWILIO_SMS_FROM",
        ]
    if provider == "msg91":
        return [] if channel == "whatsapp" else ["MSG91_AUTH_KEY", "MSG91_SMS_FLOW_ID"]
    if provider == "gupshup":
        if channel == "whatsapp":
            return ["GUPSHUP_API_KEY", "GUPSHUP_WHATSAPP_SOURCE"]
        return ["GUPSHUP_SMS_USER_ID", "GUPSHUP_SMS_PASSWORD"]
    if provider == "webhook":
        return ["WHATSAPP_WEBHOOK_URL" if channel == "whatsapp" else "SMS_WEBHOOK_URL", "NOTIFICATION_WEBHOOK_URL"]
    return []
