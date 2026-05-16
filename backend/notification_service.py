from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from env_utils import get_env

TRANSLATIONS = {
    "english": {
        "eta": "Dear {name}, your OPD token #{token} for {department} is expected in about {minutes} minutes. Please reach the hospital accordingly.",
        "arrived": "Patient marked as arrived at hospital.",
        "assistance": "Assistance requested for patient. Support desk notified.",
        "shared": "Live queue status shared with attendant.",
        "cancelled": "Your OPD visit has been cancelled. You may rebook when convenient.",
        "self_check_in": "Self check-in completed successfully. Please follow the OPD guidance board.",
        "no_show": "You were marked as no-show for this OPD turn. Please contact the desk to rejoin.",
        "proceed": "Please proceed now. Your consultation room is ready.",
        "emergency": "Emergency priority inserted into the queue.",
        "eta_updated": "ETA updated for {token_label} due to queue movement.",
    },
    "hindi": {
        "eta": "प्रिय {name}, आपका OPD टोकन #{token} ({department}) लगभग {minutes} मिनट में आने की संभावना है। कृपया उसी अनुसार अस्पताल पहुंचे।",
        "arrived": "रोगी के अस्पताल पहुंचने की पुष्टि हो गई है।",
        "assistance": "रोगी के लिए सहायता का अनुरोध दर्ज किया गया है। सहायता डेस्क को सूचित कर दिया गया है।",
        "shared": "लाइव कतार स्थिति परिचारक के साथ साझा कर दी गई है।",
        "cancelled": "आपकी OPD यात्रा रद्द कर दी गई है। आप सुविधानुसार दोबारा बुक कर सकते हैं।",
        "self_check_in": "स्वयं चेक-इन सफल रहा। कृपया OPD मार्गदर्शन बोर्ड का पालन करें।",
        "no_show": "इस OPD टर्न के लिए आपको अनुपस्थित चिह्नित किया गया है। दोबारा जुड़ने के लिए डेस्क से संपर्क करें।",
        "proceed": "कृपया अब आगे बढ़ें। आपका परामर्श कक्ष तैयार है।",
        "emergency": "आपातकालीन प्राथमिकता रोगी को कतार में जोड़ा गया है।",
        "eta_updated": "कतार में बदलाव के कारण {token_label} के लिए ETA अपडेट किया गया है।",
    },
    "gujarati": {
        "eta": "પ્રિય {name}, તમારો OPD ટોકન #{token} ({department}) આશરે {minutes} મિનિટમાં આવશે. કૃપા કરીને તે મુજબ હોસ્પિટલ પહોંચો.",
        "arrived": "દર્દી હોસ્પિટલમાં આવી ગયો છે.",
        "assistance": "દર્દી માટે મદદની વિનંતી નોંધાઈ ગઈ છે. સપોર્ટ ડેસ્કને જાણ કરવામાં આવી છે.",
        "shared": "લાઇવ કતાર સ્થિતિ અટેન્ડન્ટ સાથે શેર કરવામાં આવી છે.",
        "cancelled": "તમારી OPD મુલાકાત રદ થઈ ગઈ છે. તમે અનુકૂળ સમયે ફરી બુક કરી શકો છો.",
        "self_check_in": "સેલ્ફ ચેક-ઇન સફળ રહ્યું. કૃપા કરીને OPD માર્ગદર્શન બોર્ડનું પાલન કરો.",
        "no_show": "આ OPD ટર્ન માટે તમને ગેરહાજર તરીકે ચિહ્નિત કરવામાં આવ્યા છે. ફરી જોડાવા માટે ડેસ્કનો સંપર્ક કરો.",
        "proceed": "કૃપા કરીને હવે આગળ વધો. તમારો કન્સલ્ટેશન રૂમ તૈયાર છે.",
        "emergency": "એમરજન્સી પ્રાથમિકતા ધરાવતા દર્દીને કતારમાં ઉમેરવામાં આવ્યો છે.",
        "eta_updated": "કતારમાં ફેરફારને કારણે {token_label} માટે ETA અપડેટ થયું છે.",
    },
    "tamil": {
        "eta": "அன்புள்ள {name}, உங்கள் OPD டோக்கன் #{token} ({department}) சுமார் {minutes} நிமிடங்களில் வரும் என எதிர்பார்க்கப்படுகிறது. அதன்படி மருத்துவமனைக்கு வரவும்.",
        "arrived": "நோயாளர் மருத்துவமனைக்கு வந்துள்ளார்.",
        "assistance": "நோயாளருக்கான உதவி கோரிக்கை பதிவு செய்யப்பட்டது. உதவி மேசைக்கு தகவல் அனுப்பப்பட்டது.",
        "shared": "நேரடி வரிசை நிலை பாதுகாவலருடன் பகிரப்பட்டுள்ளது.",
        "cancelled": "உங்கள் OPD வருகை ரத்து செய்யப்பட்டது. வசதியான நேரத்தில் மீண்டும் முன்பதிவு செய்யலாம்.",
        "self_check_in": "சுய செக்-இன் வெற்றிகரமாக முடிந்தது. OPD வழிகாட்டி பலகையை பின்பற்றவும்.",
        "no_show": "இந்த OPD முறைப்பாட்டிற்காக நீங்கள் வராதவராக குறிக்கப்பட்டுள்ளீர்கள். மீண்டும் சேர டெஸ்க்கை தொடர்பு கொள்ளவும்.",
        "proceed": "இப்போது உள்ளே செல்லவும். உங்கள் கலந்தாய்வு அறை தயாராக உள்ளது.",
        "emergency": "அவசர முன்னுரிமை நோயாளர் வரிசையில் சேர்க்கப்பட்டுள்ளார்.",
        "eta_updated": "வரிசை மாற்றம் காரணமாக {token_label} க்கான ETA புதுப்பிக்கப்பட்டுள்ளது.",
    },
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def choose_channel(patient: dict) -> str:
    return "whatsapp" if patient["mobile_number"].startswith(("9", "8")) else "sms"


def choose_notification_lead(predicted_wait_minutes: int, priority: str) -> int:
    if priority == "emergency":
        return 5
    if predicted_wait_minutes >= 45:
        return 30
    if predicted_wait_minutes >= 25:
        return 25
    return 20


def build_notification_plan(patient: dict, predicted_wait_minutes: int) -> dict:
    lead_time = choose_notification_lead(predicted_wait_minutes, patient["priority"])
    eta = _utcnow() + timedelta(minutes=predicted_wait_minutes)
    scheduled = max(_utcnow(), eta - timedelta(minutes=lead_time))
    channel = choose_channel(patient)
    return {
        "channel": channel,
        "provider": _provider_for(channel),
        "lead_time_minutes": lead_time,
        "predicted_wait_minutes": predicted_wait_minutes,
        "scheduled_at": scheduled.isoformat() + "Z",
        "message_preview": localized_message(
            patient,
            "eta",
            token=patient["token_number"],
            department=patient["department"],
            minutes=predicted_wait_minutes,
        ),
    }


def get_notification_settings() -> dict:
    mode = get_env("NOTIFICATION_MODE", "mock").lower()
    sms_provider = _provider_for("sms")
    whatsapp_provider = _provider_for("whatsapp")
    return {
        "mode": mode,
        "sms_provider": sms_provider,
        "whatsapp_provider": whatsapp_provider,
        "otp_provider": get_env("OTP_PROVIDER", "mock").lower(),
        "twilio_configured": bool(get_env("TWILIO_ACCOUNT_SID") and get_env("TWILIO_AUTH_TOKEN")),
        "msg91_sms_configured": bool(get_env("MSG91_AUTH_KEY") and get_env("MSG91_SMS_FLOW_ID")),
        "gupshup_sms_configured": bool(get_env("GUPSHUP_SMS_USER_ID") and get_env("GUPSHUP_SMS_PASSWORD")),
        "gupshup_whatsapp_configured": bool(get_env("GUPSHUP_API_KEY") and get_env("GUPSHUP_WHATSAPP_SOURCE")),
        "sms_webhook_configured": bool(_webhook_url("sms")),
        "whatsapp_webhook_configured": bool(_webhook_url("whatsapp")),
    }


def dispatch_notification(notification: dict, patient: dict) -> dict:
    delivery = dispatch_direct_message(
        channel=notification["channel"],
        mobile_number=patient["mobile_number"],
        message=notification["message"],
        provider=notification.get("provider"),
        metadata={
            "notification_id": notification["notification_id"],
            "patient_id": patient["patient_id"],
            "full_name": patient["full_name"],
            "token_number": patient["token_number"],
            "department": patient["department"],
        },
    )
    return {
        "status": delivery["status"],
        "provider": delivery["provider"],
        "provider_message_id": delivery["provider_message_id"],
        "sent_at": delivery["sent_at"],
        "error": delivery["error"],
    }


def dispatch_direct_message(
    channel: str,
    mobile_number: str,
    message: str,
    provider: str | None = None,
    metadata: dict | None = None,
    mode_override: str | None = None,
) -> dict:
    selected_provider = (provider or _provider_for(channel)).strip().lower()
    mode = (mode_override or get_env("NOTIFICATION_MODE", "mock")).lower()

    notification_id = (metadata or {}).get("notification_id", "direct-message")
    if mode != "live" or selected_provider == "mock":
        return {
            "status": "delivered",
            "provider": "mock",
            "provider_message_id": f"mock-{str(notification_id).lower()}",
            "sent_at": _utcnow().isoformat() + "Z",
            "error": None,
        }

    if selected_provider == "twilio":
        return _dispatch_via_twilio(channel, mobile_number, message)

    if selected_provider == "msg91":
        return _dispatch_via_msg91(channel, mobile_number, message, metadata or {})

    if selected_provider == "gupshup":
        return _dispatch_via_gupshup(channel, mobile_number, message, metadata or {})

    if selected_provider == "webhook":
        return _dispatch_via_webhook(channel, mobile_number, message, metadata or {})

    return _config_error(selected_provider, f"Unsupported provider: {selected_provider}")


def _provider_for(channel: str) -> str:
    env_key = "WHATSAPP_PROVIDER" if channel == "whatsapp" else "SMS_PROVIDER"
    return get_env(env_key, "mock").strip().lower() or "mock"


def localized_message(patient: dict, key: str, **kwargs) -> str:
    language = (patient.get("preferred_language") or "English").strip().lower()
    catalog = TRANSLATIONS.get(language, TRANSLATIONS["english"])
    template = catalog.get(key) or TRANSLATIONS["english"].get(key) or ""
    return template.format(name=patient.get("full_name", "Patient"), **kwargs)


def _dispatch_via_twilio(channel: str, mobile_number: str, message: str) -> dict:
    account_sid = get_env("TWILIO_ACCOUNT_SID", "")
    auth_token = get_env("TWILIO_AUTH_TOKEN", "")
    sms_from = get_env("TWILIO_SMS_FROM", "")
    whatsapp_from = get_env("TWILIO_WHATSAPP_FROM", "")

    if not account_sid or not auth_token:
        return _config_error("twilio", "Missing Twilio credentials.")

    from_number = whatsapp_from if channel == "whatsapp" else sms_from
    if not from_number:
        return _config_error("twilio", f"Missing Twilio sender for {channel}.")

    to_number = _normalize_phone_number(mobile_number)
    if channel == "whatsapp":
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    encoded = urllib.parse.urlencode({"To": to_number, "From": from_number, "Body": message}).encode()
    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    request = urllib.request.Request(
        endpoint,
        data=encoded,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        payload = _load_json_response(request)
    except urllib.error.HTTPError as exc:
        return _http_error("twilio", exc)
    except OSError as exc:
        return _network_error("twilio", exc)

    provider_status = (payload.get("status") or "sent").lower()
    return {
        "status": "delivered" if provider_status == "delivered" else "sent",
        "provider": "twilio",
        "provider_message_id": payload.get("sid"),
        "sent_at": _utcnow().isoformat() + "Z",
        "error": None,
    }


def _dispatch_via_msg91(channel: str, mobile_number: str, message: str, metadata: dict) -> dict:
    if channel != "sms":
        return _config_error("msg91", "MSG91 adapter currently supports SMS delivery. Use Gupshup or Twilio for WhatsApp.")

    auth_key = get_env("MSG91_AUTH_KEY", "")
    flow_id = get_env("MSG91_SMS_FLOW_ID", "")
    sender = get_env("MSG91_SMS_SENDER", "")
    route = get_env("MSG91_SMS_ROUTE", "")
    template_id = get_env("MSG91_SMS_TEMPLATE_ID", "")
    endpoint = get_env("MSG91_SMS_URL", "https://control.msg91.com/api/v5/flow/")
    message_variable = get_env("MSG91_SMS_FLOW_MESSAGE_VAR", "message")

    if not auth_key or not flow_id:
        return _config_error("msg91", "Missing MSG91 auth key or SMS flow id.")

    payload = {
        "flow_id": flow_id,
        "mobiles": _digits_phone_number(mobile_number, include_country_code=True),
    }
    if sender:
        payload["sender"] = sender
    if route:
        payload["route"] = route
    if template_id:
        payload["template_id"] = template_id
    payload[message_variable] = message

    token_number = metadata.get("token_number")
    if token_number:
        payload.setdefault("token_number", token_number)
    patient_name = metadata.get("full_name")
    if patient_name:
        payload.setdefault("patient_name", patient_name)
    department = metadata.get("department")
    if department:
        payload.setdefault("department", department)

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={
            "authkey": auth_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        result = _load_json_response(request)
    except urllib.error.HTTPError as exc:
        return _http_error("msg91", exc)
    except OSError as exc:
        return _network_error("msg91", exc)

    return {
        "status": "sent",
        "provider": "msg91",
        "provider_message_id": result.get("request_id") or result.get("id"),
        "sent_at": _utcnow().isoformat() + "Z",
        "error": None,
    }


def _dispatch_via_gupshup(channel: str, mobile_number: str, message: str, metadata: dict) -> dict:
    if channel == "whatsapp":
        return _dispatch_via_gupshup_whatsapp(mobile_number, message, metadata)
    if channel == "sms":
        return _dispatch_via_gupshup_sms(mobile_number, message)
    return _config_error("gupshup", f"Unsupported Gupshup channel: {channel}")


def _dispatch_via_gupshup_whatsapp(mobile_number: str, message: str, metadata: dict) -> dict:
    api_key = get_env("GUPSHUP_API_KEY", "")
    source = get_env("GUPSHUP_WHATSAPP_SOURCE", "")
    app_name = get_env("GUPSHUP_APP_NAME", "SmartOPD")
    endpoint = get_env("GUPSHUP_WHATSAPP_URL", "https://api.gupshup.io/wa/api/v1/msg")

    if not api_key or not source:
        return _config_error("gupshup", "Missing Gupshup WhatsApp credentials.")

    payload = {
        "channel": "whatsapp",
        "source": source,
        "destination": _digits_phone_number(mobile_number, include_country_code=True),
        "message": json.dumps({"type": "text", "text": message}),
        "src.name": metadata.get("app_name") or app_name,
    }

    request = urllib.request.Request(
        endpoint,
        data=urllib.parse.urlencode(payload).encode(),
        headers={
            "apikey": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        result = _load_json_response(request)
    except urllib.error.HTTPError as exc:
        return _http_error("gupshup", exc)
    except OSError as exc:
        return _network_error("gupshup", exc)

    return {
        "status": "sent",
        "provider": "gupshup",
        "provider_message_id": _extract_provider_message_id(result),
        "sent_at": _utcnow().isoformat() + "Z",
        "error": None,
    }


def _dispatch_via_gupshup_sms(mobile_number: str, message: str) -> dict:
    user_id = get_env("GUPSHUP_SMS_USER_ID", "")
    password = get_env("GUPSHUP_SMS_PASSWORD", "")
    sender = get_env("GUPSHUP_SMS_SENDER", "")
    entity_id = get_env("GUPSHUP_SMS_ENTITY_ID", "")
    template_id = get_env("GUPSHUP_SMS_TEMPLATE_ID", "")
    endpoint = get_env("GUPSHUP_SMS_URL", "https://enterprise.smsgupshup.com/GatewayAPI/rest")

    if not user_id or not password:
        return _config_error("gupshup", "Missing Gupshup SMS credentials.")

    payload = {
        "method": "SendMessage",
        "send_to": _digits_phone_number(mobile_number, include_country_code=True),
        "msg": message,
        "msg_type": "TEXT",
        "userid": user_id,
        "password": password,
        "auth_scheme": "PLAIN",
        "v": "1.1",
        "format": "json",
    }
    if sender:
        payload["sender"] = sender
    if entity_id:
        payload["entityid"] = entity_id
    if template_id:
        payload["templateid"] = template_id

    request = urllib.request.Request(
        endpoint,
        data=urllib.parse.urlencode(payload).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        result = _load_json_response(request)
    except urllib.error.HTTPError as exc:
        return _http_error("gupshup", exc)
    except OSError as exc:
        return _network_error("gupshup", exc)

    return {
        "status": "sent",
        "provider": "gupshup",
        "provider_message_id": _extract_provider_message_id(result),
        "sent_at": _utcnow().isoformat() + "Z",
        "error": None,
    }


def _dispatch_via_webhook(channel: str, mobile_number: str, message: str, metadata: dict) -> dict:
    webhook_url = _webhook_url(channel)
    if not webhook_url:
        return _config_error("webhook", f"Missing webhook URL for {channel}.")

    payload = {
        "channel": channel,
        "patient_id": metadata.get("patient_id"),
        "full_name": metadata.get("full_name"),
        "mobile_number": _normalize_phone_number(mobile_number),
        "token_number": metadata.get("token_number"),
        "department": metadata.get("department"),
        "message": message,
        "notification_id": metadata.get("notification_id"),
    }
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        result = _load_json_response(request)
    except urllib.error.HTTPError as exc:
        return _http_error("webhook", exc)
    except OSError as exc:
        return _network_error("webhook", exc)

    return {
        "status": result.get("status", "sent"),
        "provider": "webhook",
        "provider_message_id": result.get("message_id") or result.get("id"),
        "sent_at": _utcnow().isoformat() + "Z",
        "error": result.get("error"),
    }


def _webhook_url(channel: str) -> str:
    specific_key = "WHATSAPP_WEBHOOK_URL" if channel == "whatsapp" else "SMS_WEBHOOK_URL"
    return get_env(specific_key) or get_env("NOTIFICATION_WEBHOOK_URL", "")


def _normalize_phone_number(mobile_number: str) -> str:
    if mobile_number.startswith("+"):
        return mobile_number
    digits = "".join(char for char in mobile_number if char.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}" if digits else mobile_number


def _digits_phone_number(mobile_number: str, include_country_code: bool = True) -> str:
    normalized = _normalize_phone_number(mobile_number)
    digits = "".join(char for char in normalized if char.isdigit())
    if include_country_code:
        return digits
    return digits[-10:] if len(digits) > 10 else digits


def _load_json_response(request: urllib.request.Request) -> dict:
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read().decode().strip()
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def _extract_provider_message_id(payload: dict) -> str | None:
    return (
        payload.get("messageId")
        or payload.get("message_id")
        or payload.get("request_id")
        or payload.get("id")
    )


def _config_error(provider: str, message: str) -> dict:
    return {
        "status": "failed",
        "provider": provider,
        "provider_message_id": None,
        "sent_at": _utcnow().isoformat() + "Z",
        "error": message,
    }


def _network_error(provider: str, exc: OSError) -> dict:
    return {
        "status": "failed",
        "provider": provider,
        "provider_message_id": None,
        "sent_at": _utcnow().isoformat() + "Z",
        "error": str(exc),
    }


def _http_error(provider: str, exc: urllib.error.HTTPError) -> dict:
    try:
        body = exc.read().decode()
    except OSError:
        body = exc.reason
    return {
        "status": "failed",
        "provider": provider,
        "provider_message_id": None,
        "sent_at": _utcnow().isoformat() + "Z",
        "error": body or str(exc),
    }
