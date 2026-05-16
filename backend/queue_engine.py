from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from statistics import mean
from typing import Dict, List, Optional

from notification_service import build_notification_plan, dispatch_notification, get_notification_settings, localized_message


PRIORITY_ORDER = {"emergency": 0, "elderly": 1, "high_risk": 1, "normal": 2}
STATUS_FLOW = {"consulting": 0, "ready": 1, "notified": 2, "waiting": 3, "no_show": 4, "cancelled": 5, "completed": 6}


class QueueEngine:
    def __init__(self) -> None:
        self.patients: List[dict] = []
        self.doctors: List[dict] = []
        self.notifications: List[dict] = []
        self.crowd_zones: List[dict] = []
        self.audit_logs: List[dict] = []

    def load_demo_data(
        self,
        doctors: List[dict],
        patients: List[dict],
        notifications: List[dict],
        crowd_zones: List[dict],
        audit_logs: Optional[List[dict]] = None,
    ) -> None:
        self.doctors = doctors
        self.patients = patients
        self.notifications = notifications
        self.crowd_zones = crowd_zones
        self.audit_logs = audit_logs or []
        for department in {doctor["department"] for doctor in doctors}:
            self.recalculate_queue(department)

    def get_bootstrap(self) -> dict:
        return {
            "summary": self.get_summary(),
            "patients": [self._decorate_patient(patient) for patient in self.patients],
            "doctors": deepcopy(self.doctors),
            "notifications": deepcopy(self.notifications[:12]),
            "notification_settings": get_notification_settings(),
            "crowd_zones": deepcopy(self.crowd_zones),
            "audit_logs": deepcopy(self.audit_logs[:20]),
            "analytics": self.get_analytics(),
            "departments": sorted({doctor["department"] for doctor in self.doctors}),
            "slot_catalog": self.get_slot_catalog(),
        }

    def get_summary(self) -> dict:
        active = self._active_patients()
        waits = [patient["predicted_wait_minutes"] for patient in active]
        on_site = len(
            [patient for patient in active if patient["arrival_state"] in {"arrived", "proceed_now"}]
        )
        outcomes = self._outcome_counts()
        return {
            "active_tokens": len(active),
            "average_wait_minutes": round(mean(waits), 1) if waits else 0,
            "active_doctors": len([doctor for doctor in self.doctors if doctor["status"] == "active"]),
            "patients_on_site": on_site,
            "checked_in_patients": len(
                [patient for patient in active if patient.get("arrival_state") == "arrived"]
            ),
            "crowd_risk_level": self._crowd_risk_level(),
            "completed_visits": outcomes["completed"],
            "no_shows": outcomes["no_show"],
            "cancelled_visits": outcomes["cancelled"],
        }

    def get_analytics(self) -> dict:
        notification_metrics = self._notification_metrics()
        return {
            "notification_success_rate": notification_metrics["success_rate"],
            "notification_read_rate": notification_metrics["read_rate"],
            "notification_failure_count": notification_metrics["failed"],
            "no_show_risk_percent": 11,
            "ai_accuracy_percent": 91,
            "peak_window": "10:30 AM - 12:00 PM",
            "recommended_action": "Open one additional registration desk for Cardiology after 10:30 AM.",
            "outcomes": self._outcome_counts(),
            "department_overview": [
                {
                    "department": doctor["department"],
                    "doctor_name": doctor["full_name"],
                    "status": doctor["status"],
                    "delay_minutes": doctor["delay_minutes"],
                    "queue_size": len(
                        [
                            patient
                            for patient in self.patients
                            if patient["department"] == doctor["department"]
                            and patient.get("visit_outcome", "active") == "active"
                        ]
                    ),
                    "average_wait_minutes": self._average_wait_for_department(doctor["department"]),
                }
                for doctor in self.doctors
            ],
        }

    def get_queue_state(self, department: Optional[str] = None) -> dict:
        active = self._active_patients()
        if department:
            active = [patient for patient in active if patient["department"] == department]
        ordered = sorted(
            active,
            key=lambda item: (
                item["department"],
                STATUS_FLOW.get(item["queue_status"], 9),
                PRIORITY_ORDER.get(item["priority"], 9),
                item.get("appointment_date", ""),
                self._slot_sort_key(item.get("slot_time")),
                item["token_number"],
            ),
        )
        return {
            "department": department or "all",
            "queue": [self._decorate_patient(patient) for patient in ordered],
            "count": len(ordered),
        }

    def get_doctor_dashboard(self, doctor_id: str) -> dict:
        doctor = next(doc for doc in self.doctors if doc["doctor_id"] == doctor_id)
        queue = self.get_queue_state(doctor["department"])["queue"]
        return {"doctor": deepcopy(doctor), "queue": queue}

    def get_slot_catalog(self) -> dict:
        return {
            doctor["department"]: {
                "doctor_id": doctor["doctor_id"],
                "doctor_name": doctor["full_name"],
                "appointment_date": date.today().isoformat(),
                "slots": self._generate_slots(doctor),
                "available_slots": self._available_slots(doctor, date.today().isoformat()),
            }
            for doctor in self.doctors
        }

    def register_patient(self, payload: dict) -> dict:
        department = payload["department"]
        doctor = self._get_department_doctor(department)
        appointment_date = payload.get("appointment_date") or date.today().isoformat()
        requested_slot = payload.get("slot_time")
        slot_time = self._reserve_slot_time(doctor, appointment_date, requested_slot)
        token_number = self._next_token_number(department)
        patient = {
            "patient_id": f"PAT-{len(self.patients) + 1:04d}",
            "full_name": payload["full_name"],
            "mobile_number": payload["mobile_number"],
            "age": int(payload.get("age", 0)),
            "preferred_language": payload.get("preferred_language", "English"),
            "department": department,
            "appointment_date": appointment_date,
            "slot_time": slot_time,
            "priority": payload.get("priority", "normal"),
            "queue_status": "waiting",
            "doctor_id": doctor["doctor_id"],
            "token_number": token_number,
            "predicted_consultation_minutes": doctor["avg_consultation_minutes"],
            "predicted_wait_minutes": 0,
            "arrival_state": "remote",
            "visit_outcome": "active",
            "support_flags": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        self.patients.append(patient)
        queue_state = self.recalculate_queue(department)
        self._schedule_notification(patient)
        self.dispatch_due_notifications()
        self._push_audit("patient_registered", f"{patient['full_name']} registered for {department}.")
        return {"patient": self._decorate_patient(patient), "queue_state": queue_state}

    def patient_action(self, patient_id: str, action: str) -> dict:
        patient = next(item for item in self.patients if item["patient_id"] == patient_id)
        if action == "arrived":
            patient["arrival_state"] = "arrived"
            if "checked_in" not in patient["support_flags"]:
                patient["support_flags"].append("checked_in")
            self._push_notification(patient, localized_message(patient, "arrived"))
            self._push_audit("patient_arrived", f"{patient['full_name']} marked as arrived.")
        elif action == "assistance":
            patient["support_flags"].append("assistance_requested")
            self._push_notification(patient, localized_message(patient, "assistance"))
            self._push_audit("patient_assistance", f"Assistance requested for {patient['full_name']}.")
        elif action == "share_status":
            self._push_notification(patient, localized_message(patient, "shared"))
            self._push_audit("patient_share_status", f"Status shared for {patient['full_name']}.")
        elif action == "cancel_visit":
            patient["visit_outcome"] = "cancelled"
            patient["queue_status"] = "cancelled"
            patient["arrival_state"] = "cancelled"
            self.recalculate_queue(patient["department"])
            self._push_notification(patient, localized_message(patient, "cancelled"))
            self._push_audit("patient_cancelled", f"{patient['full_name']} cancelled the OPD visit.")
        else:
            raise ValueError(f"Unsupported action: {action}")
        return {"patient": self._decorate_patient(patient), "notifications": deepcopy(self.notifications[:10])}

    def track_patient(self, query: str) -> Optional[dict]:
        query = query.strip().lower()
        digits = "".join([char for char in query if char.isdigit()])
        for patient in self.patients:
            token_label = self._token_label(patient).lower()
            if (
                patient["patient_id"].lower() == query
                or token_label == query
                or query in patient["full_name"].lower()
                or (len(digits) >= 4 and digits in patient["mobile_number"])
            ):
                return self._decorate_patient(patient)
        return None

    def self_check_in(self, check_in_code: str) -> dict:
        normalized = check_in_code.strip().upper()
        patient = next(
            (item for item in self.patients if self._check_in_code(item) == normalized),
            None,
        )
        if patient is None:
            raise ValueError("Invalid check-in code.")
        patient["arrival_state"] = "arrived"
        if "checked_in" not in patient["support_flags"]:
            patient["support_flags"].append("checked_in")
        if patient["queue_status"] == "waiting":
            patient["queue_status"] = "notified"
        self._push_notification(patient, localized_message(patient, "self_check_in"))
        self._push_audit("patient_self_check_in", f"{patient['full_name']} checked in using self-service code.")
        queue_state = self.recalculate_queue(patient["department"])
        return {"patient": self._decorate_patient(patient), "queue_state": queue_state}

    def update_doctor_status(self, doctor_id: str, status: Optional[str], delay_minutes: int) -> dict:
        doctor = next(doc for doc in self.doctors if doc["doctor_id"] == doctor_id)
        if status:
            doctor["status"] = status
        doctor["delay_minutes"] = max(0, doctor["delay_minutes"] + delay_minutes)
        queue_state = self.recalculate_queue(doctor["department"])
        self._reschedule_department_notifications(doctor["department"])
        self.dispatch_due_notifications()
        self._push_audit("doctor_status_updated", f"{doctor['full_name']} updated to {doctor['status']} with delay {doctor['delay_minutes']} min.")
        return {"doctor": deepcopy(doctor), "queue_state": queue_state}

    def complete_consultation(self, doctor_id: str) -> dict:
        doctor = next(doc for doc in self.doctors if doc["doctor_id"] == doctor_id)
        current = next(
            (
                patient
                for patient in self.patients
                if patient["department"] == doctor["department"] and patient["queue_status"] == "consulting"
            ),
            None,
        )
        if current:
            current["queue_status"] = "completed"
            current["visit_outcome"] = "completed"
            doctor["completed_today"] += 1
            self._push_audit("consultation_completed", f"{doctor['full_name']} completed consultation for {current['full_name']}.")
        queue_state = self.recalculate_queue(doctor["department"])
        return {"completed_patient": self._decorate_patient(current) if current else None, "queue_state": queue_state}

    def mark_no_show(self, doctor_id: str, patient_id: Optional[str] = None) -> dict:
        doctor = next(doc for doc in self.doctors if doc["doctor_id"] == doctor_id)
        queue = [
            patient
            for patient in self.patients
            if patient["department"] == doctor["department"] and patient.get("visit_outcome", "active") == "active"
        ]
        queue.sort(
            key=lambda item: (
                STATUS_FLOW.get(item["queue_status"], 9),
                PRIORITY_ORDER.get(item["priority"], 9),
                item.get("appointment_date", ""),
                self._slot_sort_key(item.get("slot_time")),
                item["token_number"],
            )
        )
        target = None
        if patient_id:
            target = next((patient for patient in queue if patient["patient_id"] == patient_id), None)
        if target is None:
            target = next((patient for patient in queue if patient["queue_status"] in {"ready", "notified", "waiting"}), None)
        if target is None:
            return {"message": "No eligible patient available to mark as no-show.", "queue_state": self.recalculate_queue(doctor["department"])}

        target["visit_outcome"] = "no_show"
        target["queue_status"] = "no_show"
        target["arrival_state"] = "absent"
        queue_state = self.recalculate_queue(doctor["department"])
        self._push_notification(target, localized_message(target, "no_show"))
        self._push_audit("patient_no_show", f"{target['full_name']} marked as no-show in {doctor['department']}.")
        return {"patient": self._decorate_patient(target), "queue_state": queue_state}

    def call_next_patient(self, doctor_id: str) -> dict:
        doctor = next(doc for doc in self.doctors if doc["doctor_id"] == doctor_id)
        current = next(
            (
                patient
                for patient in self.patients
                if patient["department"] == doctor["department"] and patient["queue_status"] == "consulting"
            ),
            None,
        )
        if current is not None:
            return {"message": "Consultation already in progress.", "queue_state": self.recalculate_queue(doctor["department"])}

        queue = [
            patient
            for patient in self.patients
            if patient["department"] == doctor["department"] and patient.get("visit_outcome", "active") == "active"
        ]
        queue.sort(
            key=lambda item: (
                STATUS_FLOW.get(item["queue_status"], 9),
                PRIORITY_ORDER.get(item["priority"], 9),
                item.get("appointment_date", ""),
                self._slot_sort_key(item.get("slot_time")),
                item["token_number"],
            )
        )
        if queue:
            queue[0]["queue_status"] = "consulting"
            queue[0]["arrival_state"] = "arrived"
            self._push_notification(queue[0], localized_message(queue[0], "proceed"))
            self._push_audit("call_next", f"{queue[0]['full_name']} called for consultation in {doctor['department']}.")
        queue_state = self.recalculate_queue(doctor["department"])
        return {"queue_state": queue_state}

    def insert_emergency_patient(self, doctor_id: str) -> dict:
        doctor = next(doc for doc in self.doctors if doc["doctor_id"] == doctor_id)
        token_number = self._next_token_number(doctor["department"])
        patient = {
            "patient_id": f"PAT-{len(self.patients) + 1:04d}",
            "full_name": "Emergency Walk-in",
            "mobile_number": "9898989898",
            "age": 58,
            "preferred_language": "English",
            "department": doctor["department"],
            "appointment_date": date.today().isoformat(),
            "slot_time": self._next_slot_time(doctor),
            "priority": "emergency",
            "queue_status": "ready",
            "doctor_id": doctor["doctor_id"],
            "token_number": token_number,
            "predicted_consultation_minutes": doctor["avg_consultation_minutes"] + 3,
            "predicted_wait_minutes": 5,
            "arrival_state": "proceed_now",
            "visit_outcome": "active",
            "support_flags": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        self.patients.append(patient)
        queue_state = self.recalculate_queue(doctor["department"])
        self._push_notification(patient, localized_message(patient, "emergency"))
        self._reschedule_department_notifications(doctor["department"])
        self._push_audit("emergency_inserted", f"Emergency walk-in inserted for {doctor['department']}.")
        return {"patient": self._decorate_patient(patient), "queue_state": queue_state}

    def simulate_tick(self) -> dict:
        for doctor in self.doctors:
            if doctor["delay_minutes"] > 0:
                doctor["delay_minutes"] -= 1
        for department in {doctor["department"] for doctor in self.doctors}:
            self.recalculate_queue(department)
        self.dispatch_due_notifications()
        self._push_audit("simulation_tick", "Admin triggered queue simulation tick.")
        return self.get_bootstrap()

    def dispatch_due_notifications(self, force: bool = False) -> dict:
        dispatched = 0
        failed = 0
        now = datetime.utcnow()
        patients_by_id = {patient["patient_id"]: patient for patient in self.patients}

        for notification in self.notifications:
            if notification.get("status") not in {"scheduled", "failed"}:
                continue
            scheduled_at = datetime.fromisoformat(notification["scheduled_at"].replace("Z", ""))
            if not force and scheduled_at > now:
                continue

            patient = patients_by_id.get(notification["patient_id"])
            if patient is None:
                notification["status"] = "failed"
                notification["error"] = "Patient record missing during dispatch."
                failed += 1
                continue

            result = dispatch_notification(notification, patient)
            notification["status"] = result["status"]
            notification["provider"] = result["provider"]
            notification["provider_message_id"] = result["provider_message_id"]
            notification["sent_at"] = result["sent_at"]
            notification["delivered_at"] = result["sent_at"] if result["status"] == "delivered" else notification.get("delivered_at")
            notification["read_at"] = notification.get("read_at")
            notification["error"] = result["error"]
            if result["status"] == "failed":
                failed += 1
                self._push_audit(
                    "notification_failed",
                    f"{notification['channel']} alert failed for {patient['full_name']}: {result['error']}.",
                )
            else:
                dispatched += 1
                self._push_audit(
                    "notification_dispatched",
                    f"{notification['channel']} alert sent to {patient['full_name']} via {result['provider']}.",
                )

        return {"dispatched": dispatched, "failed": failed}

    def apply_notification_callback(self, payload: dict) -> dict:
        notification = self._match_notification(payload)
        if notification is None:
            raise ValueError("Notification not found for callback payload.")

        status = self._normalize_delivery_status(payload.get("status") or payload.get("delivery_status") or payload.get("event"))
        if not status:
            raise ValueError("Unsupported callback status.")

        provider = (payload.get("provider") or notification.get("provider") or "callback").strip().lower()
        provider_message_id = payload.get("provider_message_id") or payload.get("message_id") or payload.get("external_id")
        event_at = payload.get("event_at") or payload.get("timestamp") or datetime.utcnow().isoformat() + "Z"
        error_message = payload.get("error") or payload.get("reason")

        notification["provider"] = provider
        if provider_message_id:
            notification["provider_message_id"] = str(provider_message_id)
        notification["status"] = status
        if status in {"sent", "delivered", "read"}:
            notification["sent_at"] = notification.get("sent_at") or self._safe_iso(event_at)
        if status in {"delivered", "read"}:
            notification["delivered_at"] = self._safe_iso(event_at)
        if status == "read":
            notification["read_at"] = self._safe_iso(event_at)
        if status == "failed":
            notification["error"] = error_message or "Provider reported delivery failure."
        elif error_message:
            notification["error"] = error_message

        self._push_audit(
            "notification_callback",
            f"{notification['channel']} callback updated {notification['notification_id']} to {status} via {provider}.",
        )
        return deepcopy(notification)

    def recalculate_queue(self, department: str) -> dict:
        doctor = self._get_department_doctor(department)
        queue = [
            patient
            for patient in self.patients
            if patient["department"] == department and patient.get("visit_outcome", "active") == "active"
        ]
        queue.sort(
            key=lambda item: (
                PRIORITY_ORDER.get(item["priority"], 9),
                item.get("appointment_date", ""),
                self._slot_sort_key(item.get("slot_time")),
                item["token_number"],
            )
        )

        consulting_exists = any(patient["queue_status"] == "consulting" for patient in queue)
        eta_by_token: Dict[int, int] = {}
        rolling_wait = doctor["delay_minutes"]
        queue_position = 1

        for index, patient in enumerate(queue):
            patient["predicted_consultation_minutes"] = doctor["avg_consultation_minutes"] + (2 if patient["priority"] == "elderly" else 0)
            patient["queue_position"] = queue_position
            if consulting_exists and patient["queue_status"] == "consulting":
                patient["predicted_wait_minutes"] = 0
                patient["arrival_state"] = "arrived"
                eta_by_token[patient["token_number"]] = 0
                queue_position += 1
                continue
            if not consulting_exists and index == 0:
                patient["queue_status"] = "ready"
                patient["predicted_wait_minutes"] = 0
                patient["arrival_state"] = "proceed_now"
                consulting_exists = True
                eta_by_token[patient["token_number"]] = 0
                queue_position += 1
                continue

            patient["predicted_wait_minutes"] = rolling_wait
            patient["queue_status"] = "ready" if rolling_wait <= 10 else "notified" if rolling_wait <= 30 else "waiting"
            patient["arrival_state"] = "proceed_now" if rolling_wait <= 10 else "leave_now" if rolling_wait <= 25 else "remote"
            if "checked_in" in patient.get("support_flags", []):
                patient["arrival_state"] = "arrived"
            eta_by_token[patient["token_number"]] = rolling_wait
            rolling_wait += patient["predicted_consultation_minutes"]
            queue_position += 1

        return {
            "department": department,
            "doctor": deepcopy(doctor),
            "queue": deepcopy(queue),
            "eta_by_token": eta_by_token,
        }

    def _schedule_notification(self, patient: dict) -> None:
        plan = build_notification_plan(patient, patient["predicted_wait_minutes"])
        self.notifications.insert(
            0,
            {
                "notification_id": f"NTF-{len(self.notifications) + 1:04d}",
                "patient_id": patient["patient_id"],
                "patient_name": patient["full_name"],
                "channel": plan["channel"],
                "provider": plan["provider"],
                "status": "scheduled",
                "scheduled_at": plan["scheduled_at"],
                "sent_at": None,
                "delivered_at": None,
                "read_at": None,
                "message": plan["message_preview"],
                "provider_message_id": None,
                "error": None,
            },
        )
        self.notifications = self.notifications[:30]

    def _reschedule_department_notifications(self, department: str) -> None:
        for patient in self.patients:
            if patient["department"] == department and patient.get("visit_outcome", "active") == "active":
                self._push_notification(
                    patient,
                    localized_message(patient, "eta_updated", token_label=self._token_label(patient)),
                )

    def _push_notification(self, patient: dict, message: str) -> None:
        self.notifications.insert(
            0,
            {
                "notification_id": f"NTF-{len(self.notifications) + 1:04d}",
                "patient_id": patient["patient_id"],
                "patient_name": patient["full_name"],
                "channel": "whatsapp" if patient["mobile_number"].startswith(("9", "8")) else "sms",
                "provider": None,
                "status": "scheduled",
                "scheduled_at": datetime.utcnow().isoformat() + "Z",
                "sent_at": None,
                "delivered_at": None,
                "read_at": None,
                "message": message,
                "provider_message_id": None,
                "error": None,
            },
        )
        self.dispatch_due_notifications()
        self.notifications = self.notifications[:30]

    def _push_audit(self, action: str, message: str) -> None:
        self.audit_logs.insert(
            0,
            {
                "audit_id": f"AUD-{len(self.audit_logs) + 1:04d}",
                "action": action,
                "message": message,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )
        self.audit_logs = self.audit_logs[:50]

    def _match_notification(self, payload: dict) -> Optional[dict]:
        notification_id = (payload.get("notification_id") or "").strip()
        provider_message_id = str(payload.get("provider_message_id") or payload.get("message_id") or payload.get("external_id") or "").strip()
        patient_id = (payload.get("patient_id") or "").strip()

        for notification in self.notifications:
            if notification_id and notification["notification_id"] == notification_id:
                return notification
            if provider_message_id and str(notification.get("provider_message_id") or "").strip() == provider_message_id:
                return notification
            if patient_id and notification["patient_id"] == patient_id:
                return notification
        return None

    @staticmethod
    def _normalize_delivery_status(raw_status: Optional[str]) -> Optional[str]:
        status = (raw_status or "").strip().lower()
        mapping = {
            "queued": "sent",
            "accepted": "sent",
            "submitted": "sent",
            "sent": "sent",
            "delivered": "delivered",
            "delivery_success": "delivered",
            "read": "read",
            "seen": "read",
            "failed": "failed",
            "undelivered": "failed",
            "delivery_failed": "failed",
            "rejected": "failed",
        }
        return mapping.get(status)

    @staticmethod
    def _safe_iso(value: str) -> str:
        try:
            return datetime.fromisoformat(value.replace("Z", "")).isoformat() + "Z"
        except ValueError:
            return datetime.utcnow().isoformat() + "Z"

    def _average_wait_for_department(self, department: str) -> float:
        waits = [
            patient["predicted_wait_minutes"]
            for patient in self.patients
            if patient["department"] == department and patient.get("visit_outcome", "active") == "active"
        ]
        return round(mean(waits), 1) if waits else 0

    def _active_patients(self) -> List[dict]:
        return [patient for patient in self.patients if patient.get("visit_outcome", "active") == "active"]

    def _outcome_counts(self) -> dict:
        return {
            "completed": len([patient for patient in self.patients if patient.get("visit_outcome") == "completed"]),
            "no_show": len([patient for patient in self.patients if patient.get("visit_outcome") == "no_show"]),
            "cancelled": len([patient for patient in self.patients if patient.get("visit_outcome") == "cancelled"]),
        }

    def _crowd_risk_level(self) -> str:
        if not self.crowd_zones:
            return "Low"
        priority = {"low": 0, "moderate": 1, "high": 2}
        highest = max(self.crowd_zones, key=lambda zone: priority.get(zone["level"], 0))
        return highest["level"].capitalize()

    def _next_token_number(self, department: str) -> int:
        token_numbers = [patient["token_number"] for patient in self.patients if patient["department"] == department]
        default_seed = {"General OPD": 100, "Cardiology": 200, "Pediatrics": 300}.get(department, 100)
        return max(token_numbers, default=default_seed) + 1

    def _generate_slots(self, doctor: dict) -> List[str]:
        start = datetime.combine(date.today(), time(9, 0))
        end = datetime.combine(date.today(), time(13, 0))
        step = max(int(doctor["avg_consultation_minutes"]), 5)
        slots = []
        current = start
        while current <= end:
            slots.append(current.strftime("%H:%M"))
            current += timedelta(minutes=step)
        return slots[:18]

    def _next_slot_time(self, doctor: dict) -> str:
        return self._reserve_slot_time(doctor, date.today().isoformat(), None)

    def _available_slots(self, doctor: dict, appointment_date: str) -> List[str]:
        booked = {
            patient.get("slot_time")
            for patient in self.patients
            if patient["doctor_id"] == doctor["doctor_id"]
            and patient.get("appointment_date") == appointment_date
            and patient.get("visit_outcome", "active") == "active"
        }
        slots = self._generate_slots(doctor)
        return [slot for slot in slots if slot not in booked]

    def _reserve_slot_time(self, doctor: dict, appointment_date: str, requested_slot: Optional[str]) -> str:
        available = self._available_slots(doctor, appointment_date)
        if requested_slot:
            if requested_slot not in self._generate_slots(doctor):
                raise ValueError("Selected appointment slot is invalid for this doctor.")
            if requested_slot not in available:
                raise ValueError("Selected appointment slot is no longer available.")
            return requested_slot
        if not available:
            raise ValueError("No appointment slots are available for this department.")
        return available[0]

    def _slot_sort_key(self, value: Optional[str]) -> str:
        return value or "23:59"

    def _check_in_code(self, patient: dict) -> str:
        return f"CHK-{patient['department'][0]}{patient['token_number']}-{patient['mobile_number'][-4:]}"

    def _decorate_patient(self, patient: Optional[dict]) -> Optional[dict]:
        if patient is None:
            return None
        enriched = deepcopy(patient)
        enriched["check_in_code"] = self._check_in_code(patient)
        enriched["qr_payload"] = (
            f"smartopd://check-in?"
            f"code={self._check_in_code(patient)}&patient_id={patient['patient_id']}&token={patient['token_number']}"
        )
        history = self._notification_history(patient["patient_id"])
        enriched["notification_history"] = history
        enriched["latest_notification_status"] = history[0]["status"] if history else "none"
        return enriched

    def _get_department_doctor(self, department: str) -> dict:
        return next(doc for doc in self.doctors if doc["department"] == department)

    def _token_label(self, patient: dict) -> str:
        prefix = {"General OPD": "G", "Cardiology": "C", "Pediatrics": "P"}.get(patient["department"], "O")
        return f"{prefix}-{patient['token_number']}"

    def _notification_history(self, patient_id: str) -> List[dict]:
        history = [deepcopy(item) for item in self.notifications if item["patient_id"] == patient_id]
        history.sort(key=lambda item: item.get("scheduled_at", ""), reverse=True)
        return history[:5]

    def _notification_metrics(self) -> dict:
        actual = [item for item in self.notifications if item.get("status") not in {"scheduled"}]
        if not actual:
            return {"success_rate": 100, "read_rate": 0, "failed": 0}
        successful = len([item for item in actual if item.get("status") in {"sent", "delivered", "read"}])
        read = len([item for item in actual if item.get("status") == "read"])
        failed = len([item for item in actual if item.get("status") == "failed"])
        total = len(actual)
        return {
            "success_rate": round((successful / total) * 100),
            "read_rate": round((read / total) * 100),
            "failed": failed,
        }


def demo_data() -> tuple[list, list, list, list, list]:
    doctors = [
        {
            "doctor_id": "DOC-001",
            "full_name": "Dr. Meera Nair",
            "department": "General OPD",
            "room_number": "G-12",
            "avg_consultation_minutes": 8,
            "status": "active",
            "delay_minutes": 5,
            "completed_today": 21,
        },
        {
            "doctor_id": "DOC-002",
            "full_name": "Dr. Arvind Rao",
            "department": "Cardiology",
            "room_number": "C-04",
            "avg_consultation_minutes": 10,
            "status": "active",
            "delay_minutes": 12,
            "completed_today": 16,
        },
        {
            "doctor_id": "DOC-003",
            "full_name": "Dr. Nisha Kulkarni",
            "department": "Pediatrics",
            "room_number": "P-07",
            "avg_consultation_minutes": 7,
            "status": "break",
            "delay_minutes": 15,
            "completed_today": 11,
        },
    ]

    patients = [
        {
            "patient_id": "PAT-0001",
            "full_name": "Suresh Verma",
            "mobile_number": "9876543210",
            "age": 67,
            "preferred_language": "Hindi",
            "department": "General OPD",
            "appointment_date": date.today().isoformat(),
            "slot_time": "09:00",
            "priority": "elderly",
            "queue_status": "consulting",
            "doctor_id": "DOC-001",
            "token_number": 101,
            "predicted_consultation_minutes": 10,
            "predicted_wait_minutes": 0,
            "arrival_state": "arrived",
            "visit_outcome": "active",
            "support_flags": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
        {
            "patient_id": "PAT-0002",
            "full_name": "Ananya Iyer",
            "mobile_number": "9123456780",
            "age": 29,
            "preferred_language": "English",
            "department": "General OPD",
            "appointment_date": date.today().isoformat(),
            "slot_time": "09:10",
            "priority": "normal",
            "queue_status": "waiting",
            "doctor_id": "DOC-001",
            "token_number": 102,
            "predicted_consultation_minutes": 8,
            "predicted_wait_minutes": 0,
            "arrival_state": "remote",
            "visit_outcome": "active",
            "support_flags": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
        {
            "patient_id": "PAT-0003",
            "full_name": "Mohan Patel",
            "mobile_number": "9988776655",
            "age": 72,
            "preferred_language": "Gujarati",
            "department": "Cardiology",
            "appointment_date": date.today().isoformat(),
            "slot_time": "09:00",
            "priority": "elderly",
            "queue_status": "consulting",
            "doctor_id": "DOC-002",
            "token_number": 205,
            "predicted_consultation_minutes": 12,
            "predicted_wait_minutes": 0,
            "arrival_state": "arrived",
            "visit_outcome": "active",
            "support_flags": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
        {
            "patient_id": "PAT-0004",
            "full_name": "Riya Sharma",
            "mobile_number": "9001100110",
            "age": 4,
            "preferred_language": "Hindi",
            "department": "Cardiology",
            "appointment_date": date.today().isoformat(),
            "slot_time": "09:10",
            "priority": "emergency",
            "queue_status": "waiting",
            "doctor_id": "DOC-002",
            "token_number": 206,
            "predicted_consultation_minutes": 13,
            "predicted_wait_minutes": 0,
            "arrival_state": "remote",
            "visit_outcome": "active",
            "support_flags": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
        {
            "patient_id": "PAT-0005",
            "full_name": "Baby Tara",
            "mobile_number": "9090909090",
            "age": 3,
            "preferred_language": "English",
            "department": "Pediatrics",
            "appointment_date": date.today().isoformat(),
            "slot_time": "09:00",
            "priority": "normal",
            "queue_status": "waiting",
            "doctor_id": "DOC-003",
            "token_number": 301,
            "predicted_consultation_minutes": 7,
            "predicted_wait_minutes": 0,
            "arrival_state": "remote",
            "visit_outcome": "active",
            "support_flags": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
    ]

    notifications = [
        {
            "notification_id": "NTF-0001",
            "patient_id": "PAT-0002",
            "patient_name": "Ananya Iyer",
            "channel": "whatsapp",
            "status": "delivered",
            "scheduled_at": datetime.utcnow().isoformat() + "Z",
            "message": "Please reach OPD in about 20 minutes. Token G-102.",
        },
        {
            "notification_id": "NTF-0002",
            "patient_id": "PAT-0004",
            "patient_name": "Riya Sharma",
            "channel": "sms",
            "status": "delivered",
            "scheduled_at": datetime.utcnow().isoformat() + "Z",
            "message": "Cardiology queue moving faster. Please arrive now. Token C-206.",
        },
    ]

    crowd_zones = [
        {"zone": "East Waiting Hall", "level": "moderate", "count": 22},
        {"zone": "Cardiology Lobby", "level": "high", "count": 31},
        {"zone": "Pediatrics Corner", "level": "low", "count": 8},
    ]
    audit_logs = [
        {
            "audit_id": "AUD-0001",
            "action": "system_bootstrap",
            "message": "Smart OPD demo state loaded.",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    ]
    return doctors, patients, notifications, crowd_zones, audit_logs
