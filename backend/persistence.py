from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import mysql.connector

from env_utils import get_bool_env, get_env


@dataclass
class PersistenceConfig:
    enabled: bool
    host: str
    port: int
    database: str
    user: str
    password: str


def load_config() -> PersistenceConfig:
    return PersistenceConfig(
        enabled=get_bool_env("MYSQL_ENABLED", False),
        host=get_env("MYSQL_HOST", "127.0.0.1"),
        port=int(get_env("MYSQL_PORT", "3306")),
        database=get_env("MYSQL_DATABASE", "smart_opd"),
        user=get_env("MYSQL_USER", "smartopd"),
        password=get_env("MYSQL_PASSWORD", "smartopd"),
    )


class MySQLPersistence:
    def __init__(self, config: Optional[PersistenceConfig] = None) -> None:
        self.config = config or load_config()
        if self.enabled:
            self.ensure_schema()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @contextmanager
    def connect(self):
        connection = mysql.connector.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
        )
        try:
            yield connection
        finally:
            connection.close()

    def health(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "connected": False, "mode": "memory"}
        try:
            with self.connect() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {"enabled": True, "connected": True, "mode": "mysql"}
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            return {"enabled": True, "connected": False, "mode": "mysql", "error": str(exc)}

    def ensure_schema(self) -> None:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                ALTER TABLE appointments
                MODIFY COLUMN check_in_status ENUM('pending', 'arrived', 'cancelled', 'no_show') DEFAULT 'pending'
                """
            )
            cursor.execute(
                """
                ALTER TABLE appointments
                MODIFY COLUMN consultation_status ENUM('scheduled', 'ready', 'consulting', 'completed') DEFAULT 'scheduled'
                """
            )
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'appointments'
                  AND COLUMN_NAME = 'visit_outcome'
                """,
                (self.config.database,),
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    """
                    ALTER TABLE appointments
                    ADD COLUMN visit_outcome ENUM('active', 'completed', 'no_show', 'cancelled') DEFAULT 'active'
                    """
                )
            cursor.execute(
                """
                ALTER TABLE queue_tokens
                MODIFY COLUMN queue_status ENUM('waiting', 'notified', 'ready', 'consulting', 'completed', 'no_show', 'cancelled') DEFAULT 'waiting'
                """
            )
            self._ensure_notification_column(cursor, "provider", "ALTER TABLE notifications ADD COLUMN provider VARCHAR(40) NULL AFTER channel")
            self._ensure_notification_column(
                cursor,
                "provider_message_id",
                "ALTER TABLE notifications ADD COLUMN provider_message_id VARCHAR(120) NULL AFTER provider",
            )
            self._ensure_notification_column(
                cursor,
                "delivered_at",
                "ALTER TABLE notifications ADD COLUMN delivered_at DATETIME NULL AFTER sent_at",
            )
            self._ensure_notification_column(
                cursor,
                "read_at",
                "ALTER TABLE notifications ADD COLUMN read_at DATETIME NULL AFTER delivered_at",
            )
            self._ensure_notification_column(
                cursor,
                "error_message",
                "ALTER TABLE notifications ADD COLUMN error_message VARCHAR(255) NULL AFTER delivery_status",
            )
            cursor.execute(
                """
                UPDATE appointments
                SET visit_outcome = CASE
                    WHEN check_in_status = 'cancelled' THEN 'cancelled'
                    WHEN check_in_status = 'no_show' THEN 'no_show'
                    WHEN consultation_status = 'completed' THEN 'completed'
                    ELSE 'active'
                END
                """
            )
            cursor.execute(
                """
                UPDATE queue_tokens qt
                JOIN appointments a ON a.appointment_id = qt.appointment_id
                SET qt.queue_status = CASE
                    WHEN a.visit_outcome = 'cancelled' THEN 'cancelled'
                    WHEN a.visit_outcome = 'no_show' THEN 'no_show'
                    ELSE qt.queue_status
                END
                WHERE a.visit_outcome IN ('cancelled', 'no_show')
                """
            )
            connection.commit()

    def load_snapshot(self) -> Optional[tuple[list, list, list, list, list]]:
        if not self.enabled:
            return None

        with self.connect() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT doctor_id, full_name, department, room_number, avg_consultation_minutes, status, delay_minutes FROM doctors ORDER BY department")
            doctors = [
                {
                    **row,
                    "completed_today": 0,
                }
                for row in cursor.fetchall()
            ]
            if not doctors:
                return None

            cursor.execute(
                """
                SELECT
                    p.patient_id,
                    p.full_name,
                    p.mobile_number,
                    p.age,
                    p.preferred_language,
                    a.doctor_id,
                    d.department,
                    p.priority_category AS priority,
                    qt.queue_status,
                    qt.token_number,
                    qt.predicted_consultation_minutes,
                    qt.predicted_wait_minutes,
                    a.appointment_date,
                    a.slot_time,
                    a.check_in_status,
                    a.consultation_status,
                    a.visit_outcome,
                    p.created_at
                FROM patients p
                JOIN appointments a ON a.patient_id = p.patient_id
                JOIN queue_tokens qt ON qt.appointment_id = a.appointment_id
                JOIN doctors d ON d.doctor_id = a.doctor_id
                ORDER BY d.department, qt.queue_position, qt.token_number
                """
            )
            patients = []
            for row in cursor.fetchall():
                arrival_state = "arrived" if row["check_in_status"] == "arrived" else "remote"
                if row["check_in_status"] == "cancelled":
                    arrival_state = "cancelled"
                elif row["check_in_status"] == "arrived":
                    arrival_state = "arrived"
                elif row["queue_status"] == "ready":
                    arrival_state = "proceed_now"
                elif row["queue_status"] == "notified":
                    arrival_state = "leave_now"
                elif row["queue_status"] == "no_show":
                    arrival_state = "absent"
                visit_outcome = row.get("visit_outcome") or "active"
                patients.append(
                    {
                        "patient_id": row["patient_id"],
                        "full_name": row["full_name"],
                        "mobile_number": row["mobile_number"],
                        "age": row["age"],
                        "preferred_language": row["preferred_language"],
                        "department": row["department"],
                        "priority": row["priority"],
                        "appointment_date": row["appointment_date"].isoformat() if row.get("appointment_date") else datetime.utcnow().date().isoformat(),
                        "slot_time": self._format_time_value(row.get("slot_time")),
                        "queue_status": row["queue_status"],
                        "doctor_id": row["doctor_id"],
                        "token_number": row["token_number"],
                        "predicted_consultation_minutes": float(row["predicted_consultation_minutes"] or 0),
                        "predicted_wait_minutes": float(row["predicted_wait_minutes"] or 0),
                        "arrival_state": arrival_state,
                        "visit_outcome": visit_outcome,
                        "support_flags": ["checked_in"] if row["check_in_status"] == "arrived" else [],
                        "created_at": row["created_at"].isoformat() + "Z" if row["created_at"] else datetime.utcnow().isoformat() + "Z",
                    }
                )

            cursor.execute(
                """
                SELECT
                    n.notification_id,
                    p.patient_id,
                    p.full_name AS patient_name,
                    n.channel,
                    n.provider,
                    n.provider_message_id,
                    n.delivery_status AS status,
                    n.scheduled_at,
                    n.sent_at,
                    n.delivered_at,
                    n.read_at,
                    n.error_message AS error,
                    n.message_preview AS message
                FROM notifications n
                JOIN queue_tokens qt ON qt.token_id = n.token_id
                JOIN appointments a ON a.appointment_id = qt.appointment_id
                JOIN patients p ON p.patient_id = a.patient_id
                ORDER BY n.created_at DESC
                LIMIT 30
                """
            )
            notifications = [
                {
                    **row,
                    "scheduled_at": row["scheduled_at"].isoformat() + "Z" if row["scheduled_at"] else datetime.utcnow().isoformat() + "Z",
                    "sent_at": row["sent_at"].isoformat() + "Z" if row.get("sent_at") else None,
                    "delivered_at": row["delivered_at"].isoformat() + "Z" if row.get("delivered_at") else None,
                    "read_at": row["read_at"].isoformat() + "Z" if row.get("read_at") else None,
                }
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT department AS zone, density_level AS level, observed_count AS count
                FROM crowd_density_events
                ORDER BY observed_at DESC
                LIMIT 3
                """
            )
            crowd = cursor.fetchall()

            try:
                cursor.execute(
                    """
                    SELECT audit_id, action, message, created_at
                    FROM audit_logs
                    ORDER BY created_at DESC
                    LIMIT 50
                    """
                )
                audit_logs = [
                    {
                        "audit_id": row["audit_id"],
                        "action": row["action"],
                        "message": row["message"],
                        "timestamp": row["created_at"].isoformat() + "Z" if row["created_at"] else datetime.utcnow().isoformat() + "Z",
                    }
                    for row in cursor.fetchall()
                ]
            except mysql.connector.Error:
                audit_logs = []
            return doctors, patients, notifications, crowd, audit_logs

    def persist_snapshot(self, engine) -> None:
        if not self.enabled:
            return

        with self.connect() as connection:
            cursor = connection.cursor()
            connection.start_transaction()

            cursor.execute("DELETE FROM notifications")
            cursor.execute("DELETE FROM queue_tokens")
            cursor.execute("DELETE FROM appointments")
            cursor.execute("DELETE FROM patients")
            cursor.execute("DELETE FROM doctor_status_logs")
            cursor.execute("DELETE FROM crowd_density_events")
            try:
                cursor.execute("DELETE FROM audit_logs")
            except mysql.connector.Error:
                pass
            cursor.execute("DELETE FROM doctors")

            for doctor in engine.doctors:
                cursor.execute(
                    """
                    INSERT INTO doctors
                    (doctor_id, full_name, department, room_number, avg_consultation_minutes, status, delay_minutes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        doctor["doctor_id"],
                        doctor["full_name"],
                        doctor["department"],
                        doctor["room_number"],
                        doctor["avg_consultation_minutes"],
                        doctor["status"],
                        doctor["delay_minutes"],
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO doctor_status_logs (doctor_id, status, delay_minutes)
                    VALUES (%s, %s, %s)
                    """,
                    (doctor["doctor_id"], doctor["status"], doctor["delay_minutes"]),
                )

            for patient in engine.patients:
                cursor.execute(
                    """
                    INSERT INTO patients
                    (patient_id, full_name, age, gender, mobile_number, preferred_language, priority_category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        patient["patient_id"],
                        patient["full_name"],
                        patient["age"],
                        None,
                        patient["mobile_number"],
                        patient.get("preferred_language", "English"),
                        patient["priority"],
                    ),
                )
                appointment_id = patient["patient_id"].replace("PAT", "APT")
                token_id = patient["patient_id"].replace("PAT", "TKN")
                visit_outcome = patient.get("visit_outcome", "active")
                check_in_status = "arrived" if patient["arrival_state"] in {"arrived", "proceed_now"} else "pending"
                if visit_outcome == "cancelled":
                    check_in_status = "cancelled"
                elif visit_outcome == "no_show":
                    check_in_status = "no_show"
                consultation_status = patient["queue_status"]
                if consultation_status in {"waiting", "notified", "no_show", "cancelled"}:
                    consultation_status = "scheduled"
                elif consultation_status == "ready":
                    consultation_status = "ready"
                elif consultation_status == "consulting":
                    consultation_status = "consulting"
                if visit_outcome == "completed":
                    consultation_status = "completed"
                elif visit_outcome in {"cancelled", "no_show"}:
                    consultation_status = "scheduled"
                queue_status = patient["queue_status"]
                cursor.execute(
                    """
                    INSERT INTO appointments
                    (appointment_id, patient_id, doctor_id, appointment_date, slot_time, check_in_status, consultation_status, visit_outcome)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        appointment_id,
                        patient["patient_id"],
                        patient["doctor_id"],
                        patient.get("appointment_date"),
                        self._normalize_time(patient.get("slot_time")),
                        check_in_status,
                        consultation_status,
                        visit_outcome,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO queue_tokens
                    (token_id, appointment_id, token_number, queue_status, queue_position, predicted_wait_minutes, predicted_consultation_minutes, notification_lead_minutes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        token_id,
                        appointment_id,
                        patient["token_number"],
                        queue_status,
                        patient.get("queue_position", 0),
                        patient["predicted_wait_minutes"],
                        patient["predicted_consultation_minutes"],
                        20,
                    ),
                )

            for notification in engine.notifications[:30]:
                token_id = notification["patient_id"].replace("PAT", "TKN")
                cursor.execute(
                    """
                    INSERT INTO notifications
                    (notification_id, token_id, channel, provider, provider_message_id, scheduled_at, sent_at, delivered_at, read_at, delivery_status, error_message, template_name, message_preview)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        notification["notification_id"],
                        token_id,
                        notification["channel"],
                        notification.get("provider"),
                        notification.get("provider_message_id"),
                        self._normalize_datetime(notification["scheduled_at"]),
                        self._normalize_datetime(notification["sent_at"]) if notification.get("sent_at") else None,
                        self._normalize_datetime(notification["delivered_at"]) if notification.get("delivered_at") else None,
                        self._normalize_datetime(notification["read_at"]) if notification.get("read_at") else None,
                        notification["status"],
                        (notification.get("error") or "")[:255] or None,
                        "smart_opd_eta",
                        notification["message"][:255],
                    ),
                )

            for zone in engine.crowd_zones:
                cursor.execute(
                    """
                    INSERT INTO crowd_density_events (department, density_level, source_type, observed_count)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        zone["zone"],
                        "critical" if zone["level"] == "high" else zone["level"],
                        "manual",
                        zone["count"],
                    ),
                )

            try:
                for audit in engine.audit_logs[:50]:
                    cursor.execute(
                        """
                        INSERT INTO audit_logs (audit_id, action, message, created_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            audit["audit_id"],
                            audit["action"],
                            audit["message"],
                            self._normalize_datetime(audit["timestamp"]),
                        ),
                    )
            except mysql.connector.Error:
                pass

            connection.commit()

    @staticmethod
    def _normalize_datetime(value: str):
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value.replace("Z", ""))

    def _ensure_notification_column(self, cursor, column_name: str, alter_sql: str) -> None:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'notifications'
              AND COLUMN_NAME = %s
            """,
            (self.config.database, column_name),
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(alter_sql)

    @staticmethod
    def _normalize_time(value: Optional[str]):
        if not value:
            return None
        return value

    @staticmethod
    def _format_time_value(value):
        if value is None:
            return None
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds())
            hours = (total_seconds // 3600) % 24
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        if hasattr(value, "strftime"):
            return value.strftime("%H:%M")
        return str(value)[:5]
