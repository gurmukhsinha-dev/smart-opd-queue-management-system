from __future__ import annotations

from datetime import datetime
from queue import Empty, Queue
from threading import Lock

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from auth import authenticate, current_user, issue_token, require_roles
from deployment_readiness import build_deployment_readiness, build_provider_diagnostics
from env_utils import get_env, get_list_env
from notification_service import dispatch_direct_message
from otp_service import OTPService
from persistence import MySQLPersistence
from queue_engine import QueueEngine, demo_data
from user_service import user_service

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS(app, resources={r"/api/*": {"origins": get_list_env("APP_ALLOWED_ORIGINS", default_origins)}})

engine = QueueEngine()
persistence = MySQLPersistence()
otp_service = OTPService()
event_subscribers: list[Queue] = []
event_lock = Lock()
event_counter = 0


def sync_engine_from_persistence() -> None:
    snapshot = persistence.load_snapshot()
    if snapshot:
        engine.load_demo_data(*snapshot)
    elif not engine.doctors:
        engine.load_demo_data(*demo_data())
        if persistence.enabled:
            persistence.persist_snapshot(engine)


def persist_engine_state() -> None:
    persistence.persist_snapshot(engine)
    publish_event("state_updated")


def publish_event(event_type: str, payload: dict | None = None) -> None:
    global event_counter
    with event_lock:
        event_counter += 1
        message = {
            "event_id": event_counter,
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": payload or {},
        }
        stale = []
        for subscriber in event_subscribers:
            try:
                subscriber.put_nowait(message)
            except Exception:
                stale.append(subscriber)
        for subscriber in stale:
            if subscriber in event_subscribers:
                event_subscribers.remove(subscriber)


def _authorize_webhook(provider: str) -> tuple[bool, tuple[dict, int] | None]:
    expected = get_env("PROVIDER_WEBHOOK_TOKEN", "").strip()
    provider_specific = get_env(f"{provider.upper()}_WEBHOOK_TOKEN", "").strip()
    allowed = provider_specific or expected
    if not allowed:
        return True, None

    payload = request.get_json(silent=True) or {}
    received = (
        request.headers.get("X-Webhook-Token", "").strip()
        or request.args.get("token", "").strip()
        or str(payload.get("token", "")).strip()
    )
    if received != allowed:
        return False, ({"message": "Invalid webhook token."}, 401)
    return True, None


sync_engine_from_persistence()


@app.before_request
def refresh_engine_state():
    if persistence.enabled:
        sync_engine_from_persistence()


@app.get("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "persistence": persistence.health(),
        }
    )


@app.get("/api/bootstrap")
def bootstrap():
    return jsonify(engine.get_bootstrap())


@app.get("/api/events/stream")
def events_stream():
    subscriber: Queue = Queue()
    with event_lock:
        event_subscribers.append(subscriber)

    @stream_with_context
    def generate():
        try:
            yield "event: connected\ndata: {\"status\":\"ok\"}\n\n"
            while True:
                try:
                    message = subscriber.get(timeout=20)
                    yield f"id: {message['event_id']}\n"
                    yield f"event: {message['type']}\n"
                    yield "data: " + jsonify(message).get_data(as_text=True) + "\n\n"
                except Empty:
                    yield "event: heartbeat\ndata: {}\n\n"
        finally:
            with event_lock:
                if subscriber in event_subscribers:
                    event_subscribers.remove(subscriber)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/auth/login")
def login():
    payload = request.get_json(force=True)
    user = authenticate(payload.get("username", ""), payload.get("password", ""))
    if user is None:
        return jsonify({"message": "Invalid credentials"}), 401
    return jsonify({"token": issue_token(user), "user": user})


@app.get("/api/auth/me")
def me():
    user = current_user()
    if user is None:
        return jsonify({"message": "Authentication required"}), 401
    return jsonify({"user": user})


@app.post("/api/auth/forgot-password")
def forgot_password():
    payload = request.get_json(force=True)
    try:
        result = user_service.request_password_reset(payload.get("username", ""))
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(result)


@app.post("/api/auth/reset-password")
def reset_password():
    payload = request.get_json(force=True)
    try:
        result = user_service.reset_password(
            payload.get("username", ""),
            payload.get("reset_token", ""),
            payload.get("new_password", ""),
        )
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(result)


@app.get("/api/queue")
def queue_state():
    department = request.args.get("department")
    return jsonify(engine.get_queue_state(department))


@app.get("/api/doctors/<doctor_id>")
@require_roles("doctor", "admin")
def doctor_dashboard(doctor_id: str):
    user = current_user()
    if user and user["role"] == "doctor" and user.get("doctor_id") != doctor_id:
        return jsonify({"message": "Doctors may only access their own dashboard"}), 403
    return jsonify(engine.get_doctor_dashboard(doctor_id))


@app.get("/api/patients/track")
def track_patient():
    query = request.args.get("q", "")
    patient = engine.track_patient(query)
    if patient is None:
        return jsonify({"message": "Patient not found"}), 404
    return jsonify({"patient": patient})


@app.post("/api/patients/otp/send")
def send_patient_otp():
    payload = request.get_json(force=True)
    mobile_number = payload.get("mobile_number", "").strip()
    if len("".join(char for char in mobile_number if char.isdigit())) < 10:
        return jsonify({"message": "Enter a valid mobile number."}), 400
    result = otp_service.send_otp(mobile_number)
    status_code = 200 if result.get("status") != "failed" else 400
    return jsonify(result), status_code


@app.post("/api/patients/otp/verify")
def verify_patient_otp():
    payload = request.get_json(force=True)
    mobile_number = payload.get("mobile_number", "").strip()
    code = payload.get("otp", "").strip()
    result = otp_service.verify_otp(mobile_number, code)
    if not result["verified"]:
        return jsonify(result), 400
    return jsonify(result)


@app.post("/api/patients/register")
def register_patient():
    payload = request.get_json(force=True)
    mobile_number = payload.get("mobile_number", "").strip()
    if not otp_service.is_verified(mobile_number):
        return jsonify({"message": "Mobile number is not OTP verified."}), 400
    try:
        result = engine.register_patient(payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    otp_service.consume_verification(mobile_number)
    persist_engine_state()
    return jsonify(result), 201


@app.post("/api/patients/<patient_id>/action")
def patient_action(patient_id: str):
    payload = request.get_json(force=True)
    try:
        result = engine.patient_action(patient_id, payload["action"])
    except (KeyError, ValueError) as exc:
        return jsonify({"message": str(exc)}), 400
    persist_engine_state()
    return jsonify(result)


@app.post("/api/patients/check-in")
def patient_self_check_in():
    payload = request.get_json(force=True)
    try:
        result = engine.self_check_in(payload.get("check_in_code", ""))
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    persist_engine_state()
    return jsonify(result)


@app.post("/api/doctors/<doctor_id>/status")
@require_roles("doctor", "admin")
def update_doctor_status(doctor_id: str):
    user = current_user()
    if user and user["role"] == "doctor" and user.get("doctor_id") != doctor_id:
        return jsonify({"message": "Doctors may only update their own dashboard"}), 403
    payload = request.get_json(force=True)
    result = engine.update_doctor_status(
        doctor_id,
        payload.get("status"),
        int(payload.get("delay_minutes", 0)),
    )
    persist_engine_state()
    return jsonify(result)


@app.post("/api/doctors/<doctor_id>/complete")
@require_roles("doctor", "admin")
def complete_consultation(doctor_id: str):
    user = current_user()
    if user and user["role"] == "doctor" and user.get("doctor_id") != doctor_id:
        return jsonify({"message": "Doctors may only complete their own consultations"}), 403
    result = engine.complete_consultation(doctor_id)
    persist_engine_state()
    return jsonify(result)


@app.post("/api/doctors/<doctor_id>/mark-no-show")
@require_roles("doctor", "admin")
def mark_no_show(doctor_id: str):
    user = current_user()
    if user and user["role"] == "doctor" and user.get("doctor_id") != doctor_id:
        return jsonify({"message": "Doctors may only update their own dashboard"}), 403
    payload = request.get_json(silent=True) or {}
    result = engine.mark_no_show(doctor_id, payload.get("patient_id"))
    persist_engine_state()
    return jsonify(result)


@app.post("/api/doctors/<doctor_id>/call-next")
@require_roles("doctor", "admin")
def call_next(doctor_id: str):
    user = current_user()
    if user and user["role"] == "doctor" and user.get("doctor_id") != doctor_id:
        return jsonify({"message": "Doctors may only update their own dashboard"}), 403
    result = engine.call_next_patient(doctor_id)
    persist_engine_state()
    return jsonify(result)


@app.post("/api/doctors/<doctor_id>/emergency-insert")
@require_roles("doctor", "admin")
def emergency_insert(doctor_id: str):
    result = engine.insert_emergency_patient(doctor_id)
    persist_engine_state()
    return jsonify(result)


@app.get("/api/admin/persistence")
@require_roles("admin")
def persistence_status():
    return jsonify(persistence.health())


@app.get("/api/admin/notification-config")
@require_roles("admin")
def notification_config():
    return jsonify(engine.get_bootstrap()["notification_settings"])


@app.get("/api/admin/deployment-readiness")
@require_roles("admin")
def deployment_readiness():
    return jsonify(build_deployment_readiness(persistence.health(), engine.get_bootstrap()["notification_settings"]))


@app.get("/api/admin/provider-diagnostics")
@require_roles("admin")
def provider_diagnostics():
    return jsonify(build_provider_diagnostics(engine.get_bootstrap()["notification_settings"]))


@app.post("/api/admin/provider-test")
@require_roles("admin")
def provider_test():
    payload = request.get_json(force=True)
    test_type = (payload.get("test_type") or "notification").strip().lower()
    mobile_number = payload.get("mobile_number", "").strip()
    provider = (payload.get("provider") or "").strip().lower() or None
    channel = (payload.get("channel") or "sms").strip().lower()
    dry_run = bool(payload.get("dry_run", True))

    if len("".join(char for char in mobile_number if char.isdigit())) < 10:
        return jsonify({"message": "Enter a valid mobile number for provider testing."}), 400

    if test_type == "otp":
        if dry_run:
            diagnostics = build_provider_diagnostics(engine.get_bootstrap()["notification_settings"])
            return jsonify({"test_type": "otp", "dry_run": True, "result": diagnostics["otp"]})
        result = otp_service.send_otp(mobile_number)
        status = 200 if result.get("status") in {"sent", "delivered"} else 400
        return jsonify({"test_type": "otp", "dry_run": False, "result": result}), status

    message = payload.get("message", "").strip() or "Smart OPD provider test message from hospital admin."
    if dry_run:
        diagnostics = build_provider_diagnostics(engine.get_bootstrap()["notification_settings"])
        key = "whatsapp" if channel == "whatsapp" else "sms"
        return jsonify({"test_type": "notification", "dry_run": True, "result": diagnostics[key]}), 200

    result = dispatch_direct_message(
        channel=channel,
        mobile_number=mobile_number,
        message=message,
        provider=provider,
        metadata={"notification_id": f"admin-test-{channel}"},
    )
    status = 200 if result.get("status") in {"sent", "delivered"} else 400
    return jsonify({"test_type": "notification", "dry_run": False, "result": result}), status


@app.post("/api/admin/notifications/dispatch")
@require_roles("admin")
def dispatch_notifications():
    payload = request.get_json(silent=True) or {}
    result = engine.dispatch_due_notifications(force=bool(payload.get("force", False)))
    persist_engine_state()
    return jsonify(result)


@app.post("/api/admin/simulate-tick")
@require_roles("admin")
def simulate_tick():
    result = engine.simulate_tick()
    persist_engine_state()
    return jsonify(result)


@app.get("/api/admin/audit-logs")
@require_roles("admin")
def audit_logs():
    return jsonify({"audit_logs": engine.audit_logs[:50]})


@app.get("/api/admin/users")
@require_roles("admin")
def admin_users():
    return jsonify({"users": user_service.list_users()})


@app.post("/api/admin/users")
@require_roles("admin")
def create_admin_user():
    payload = request.get_json(force=True)
    try:
        user = user_service.create_user(payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"user": user}), 201


@app.patch("/api/admin/users/<user_id>")
@require_roles("admin")
def update_admin_user(user_id: str):
    payload = request.get_json(force=True)
    try:
        user = user_service.update_user(user_id, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"user": user})


@app.post("/api/webhooks/notifications/<provider>")
def notification_webhook(provider: str):
    authorized, error = _authorize_webhook(provider)
    if not authorized and error:
        body, status = error
        return jsonify(body), status

    payload = request.get_json(silent=True) or {}
    payload["provider"] = provider
    try:
        notification = engine.apply_notification_callback(payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    persist_engine_state()
    return jsonify({"status": "ok", "notification": notification})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
