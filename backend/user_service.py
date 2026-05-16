from __future__ import annotations

import hashlib
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash

from env_utils import get_env
from persistence import load_config


class UserService:
    def __init__(self) -> None:
        self.config = load_config()
        self._fallback_users = self._build_fallback_users()
        if self.config.enabled:
            self.ensure_schema()
            self.seed_default_users()

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

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        normalized = username.strip().lower()
        if self.config.enabled:
            with self.connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT user_id, username, full_name, password_hash, role, doctor_id, status, session_version
                    FROM users
                    WHERE username = %s
                    """,
                    (normalized,),
                )
                row = cursor.fetchone()
                if not row or row["status"] != "active":
                    return None
                if not check_password_hash(row["password_hash"], password):
                    return None
                cursor.execute(
                    "UPDATE users SET last_login_at = %s WHERE user_id = %s",
                    (datetime.utcnow(), row["user_id"]),
                )
                connection.commit()
                return self._sanitize_user(row)

        row = self._fallback_users.get(normalized)
        if not row or not check_password_hash(row["password_hash"], password):
            return None
        return self._sanitize_user(row)

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        if self.config.enabled:
            with self.connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT user_id, username, full_name, role, doctor_id, status, session_version
                    FROM users
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
                return self._sanitize_user(row) if row and row["status"] == "active" else None

        row = next((user for user in self._fallback_users.values() if user["user_id"] == user_id), None)
        return self._sanitize_user(row) if row else None

    def list_users(self) -> list[dict]:
        if self.config.enabled:
            with self.connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT user_id, username, full_name, role, doctor_id, status, session_version, created_at, last_login_at
                    FROM users
                    ORDER BY role, username
                    """
                )
                return [self._serialize_user_row(row) for row in cursor.fetchall()]

        return [self._serialize_user_row(user) for user in self._fallback_users.values()]

    def create_user(self, payload: dict) -> dict:
        username = payload.get("username", "").strip().lower()
        password = payload.get("password", "")
        full_name = payload.get("full_name", "").strip()
        role = payload.get("role", "staff").strip().lower()
        doctor_id = payload.get("doctor_id")
        self._validate_user_payload(username, password, full_name, role)

        if self.config.enabled:
            with self.connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    raise ValueError("A user with this username already exists.")
                user_id = self._next_user_id(cursor)
                cursor.execute(
                    """
                    INSERT INTO users (user_id, username, full_name, password_hash, role, doctor_id, status, session_version, password_changed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'active', 1, %s)
                    """,
                    (
                        user_id,
                        username,
                        full_name,
                        generate_password_hash(password),
                        role,
                        doctor_id,
                        datetime.utcnow(),
                    ),
                )
                connection.commit()
                return self.get_user_by_id(user_id)

        user_id = f"USR-{len(self._fallback_users) + 1:04d}"
        row = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "password_hash": generate_password_hash(password),
            "role": role,
            "doctor_id": doctor_id,
            "status": "active",
            "session_version": 1,
            "created_at": datetime.utcnow(),
            "last_login_at": None,
        }
        self._fallback_users[username] = row
        return self._serialize_user_row(row)

    def update_user(self, user_id: str, payload: dict) -> dict:
        role = payload.get("role")
        status = payload.get("status")
        full_name = payload.get("full_name")
        password = payload.get("password")

        if self.config.enabled:
            with self.connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                if not row:
                    raise ValueError("User not found.")
                updates = []
                values = []
                bump_session = False
                if role:
                    updates.append("role = %s")
                    values.append(role.strip().lower())
                    bump_session = True
                if status:
                    updates.append("status = %s")
                    values.append(status.strip().lower())
                    bump_session = True
                if full_name:
                    updates.append("full_name = %s")
                    values.append(full_name.strip())
                if password:
                    self._validate_password(password)
                    updates.append("password_hash = %s")
                    values.append(generate_password_hash(password))
                    updates.append("password_changed_at = %s")
                    values.append(datetime.utcnow())
                    bump_session = True
                if payload.get("doctor_id") is not None:
                    updates.append("doctor_id = %s")
                    values.append(payload.get("doctor_id"))
                    bump_session = True
                if bump_session:
                    updates.append("session_version = session_version + 1")
                if not updates:
                    return self._serialize_user_row(row)
                values.append(user_id)
                cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = %s", tuple(values))
                connection.commit()
                return self.get_user_by_id(user_id) or self._serialize_user_row({**row, **payload})

        row = next((user for user in self._fallback_users.values() if user["user_id"] == user_id), None)
        if not row:
            raise ValueError("User not found.")
        if role:
            row["role"] = role.strip().lower()
            row["session_version"] += 1
        if status:
            row["status"] = status.strip().lower()
            row["session_version"] += 1
        if full_name:
            row["full_name"] = full_name.strip()
        if password:
            self._validate_password(password)
            row["password_hash"] = generate_password_hash(password)
            row["session_version"] += 1
        if payload.get("doctor_id") is not None:
            row["doctor_id"] = payload.get("doctor_id")
            row["session_version"] += 1
        return self._serialize_user_row(row)

    def request_password_reset(self, username: str) -> dict:
        normalized = username.strip().lower()
        expires_at = datetime.utcnow() + timedelta(minutes=int(get_env("RESET_TOKEN_TTL_MINUTES", "30")))
        raw_token = secrets.token_urlsafe(24)
        token_hash = self._hash_token(raw_token)

        if self.config.enabled:
            with self.connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT user_id, username, status FROM users WHERE username = %s", (normalized,))
                row = cursor.fetchone()
                if not row or row["status"] != "active":
                    raise ValueError("No active user found for this username.")
                token_id = self._next_reset_token_id(cursor)
                cursor.execute(
                    """
                    INSERT INTO password_reset_tokens (token_id, user_id, token_hash, expires_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (token_id, row["user_id"], token_hash, expires_at),
                )
                connection.commit()
                return {
                    "message": "Password reset token created.",
                    "username": normalized,
                    "reset_token": raw_token,
                    "expires_at": expires_at.isoformat() + "Z",
                }

        row = self._fallback_users.get(normalized)
        if not row:
            raise ValueError("No active user found for this username.")
        row["reset_token_hash"] = token_hash
        row["reset_token_expires_at"] = expires_at
        return {
            "message": "Password reset token created.",
            "username": normalized,
            "reset_token": raw_token,
            "expires_at": expires_at.isoformat() + "Z",
        }

    def reset_password(self, username: str, reset_token: str, new_password: str) -> dict:
        normalized = username.strip().lower()
        self._validate_password(new_password)
        token_hash = self._hash_token(reset_token)

        if self.config.enabled:
            with self.connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT prt.token_id, prt.user_id, prt.expires_at, prt.used_at, prt.token_hash, u.username
                    FROM password_reset_tokens prt
                    JOIN users u ON u.user_id = prt.user_id
                    WHERE u.username = %s
                    ORDER BY prt.created_at DESC
                    """,
                    (normalized,),
                )
                rows = cursor.fetchall()
                match = next((row for row in rows if row["used_at"] is None and row["token_hash"] == token_hash), None)
                if not match:
                    raise ValueError("No valid reset token found.")
                if match["expires_at"] < datetime.utcnow():
                    raise ValueError("Reset token has expired.")
                cursor.execute(
                    """
                    UPDATE users
                    SET password_hash = %s, password_changed_at = %s, session_version = session_version + 1
                    WHERE user_id = %s
                    """,
                    (generate_password_hash(new_password), datetime.utcnow(), match["user_id"]),
                )
                cursor.execute(
                    "UPDATE password_reset_tokens SET used_at = %s WHERE token_id = %s",
                    (datetime.utcnow(), match["token_id"]),
                )
                connection.commit()
                user = self.get_user_by_id(match["user_id"])
                return {"message": "Password reset successful.", "user": user}

        row = self._fallback_users.get(normalized)
        if not row:
            raise ValueError("No active user found for this username.")
        if row.get("reset_token_hash") != token_hash:
            raise ValueError("Invalid reset token.")
        if row.get("reset_token_expires_at") and row["reset_token_expires_at"] < datetime.utcnow():
            raise ValueError("Reset token has expired.")
        row["password_hash"] = generate_password_hash(new_password)
        row["session_version"] += 1
        row["reset_token_hash"] = None
        row["reset_token_expires_at"] = None
        return {"message": "Password reset successful.", "user": self._serialize_user_row(row)}

    def ensure_schema(self) -> None:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(20) PRIMARY KEY,
                    username VARCHAR(120) NOT NULL UNIQUE,
                    full_name VARCHAR(120) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role ENUM('admin', 'doctor', 'staff') NOT NULL DEFAULT 'staff',
                    doctor_id VARCHAR(20) NULL,
                    status ENUM('active', 'disabled') NOT NULL DEFAULT 'active',
                    session_version INT NOT NULL DEFAULT 1,
                    password_changed_at DATETIME NULL,
                    last_login_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_users_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token_id VARCHAR(24) PRIMARY KEY,
                    user_id VARCHAR(20) NOT NULL,
                    token_hash CHAR(64) NOT NULL,
                    expires_at DATETIME NOT NULL,
                    used_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_reset_user FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """
            )
            connection.commit()

    def seed_default_users(self) -> None:
        with self.connect() as connection:
            cursor = connection.cursor(dictionary=True)
            defaults = [
                {
                    "username": "admin@smartopd.local",
                    "full_name": "Hospital Admin",
                    "password": "Admin@123",
                    "role": "admin",
                    "doctor_id": None,
                },
                {
                    "username": "staff.frontdesk@smartopd.local",
                    "full_name": "Front Desk Staff",
                    "password": "Staff@123",
                    "role": "staff",
                    "doctor_id": None,
                },
            ]
            cursor.execute("SELECT doctor_id, full_name, department FROM doctors ORDER BY doctor_id")
            for row in cursor.fetchall():
                username = f"doctor.{row['department'].lower().replace(' ', '')}@smartopd.local"
                if row["doctor_id"] == "DOC-001":
                    username = "doctor.general@smartopd.local"
                elif row["doctor_id"] == "DOC-002":
                    username = "doctor.cardiology@smartopd.local"
                defaults.append(
                    {
                        "username": username,
                        "full_name": row["full_name"],
                        "password": "Doctor@123",
                        "role": "doctor",
                        "doctor_id": row["doctor_id"],
                    }
                )
            for default_user in defaults:
                cursor.execute("SELECT user_id FROM users WHERE username = %s", (default_user["username"],))
                if cursor.fetchone():
                    continue
                cursor.execute(
                    """
                    INSERT INTO users (user_id, username, full_name, password_hash, role, doctor_id, status, session_version, password_changed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'active', 1, %s)
                    """,
                    (
                        self._next_user_id(cursor),
                        default_user["username"],
                        default_user["full_name"],
                        generate_password_hash(default_user["password"]),
                        default_user["role"],
                        default_user["doctor_id"],
                        datetime.utcnow(),
                    ),
                )
            connection.commit()

    def _build_fallback_users(self) -> dict[str, dict]:
        return {
            "admin@smartopd.local": {
                "user_id": "USR-0001",
                "username": "admin@smartopd.local",
                "full_name": "Hospital Admin",
                "password_hash": generate_password_hash("Admin@123"),
                "role": "admin",
                "doctor_id": None,
                "status": "active",
                "session_version": 1,
                "created_at": datetime.utcnow(),
                "last_login_at": None,
            },
            "doctor.cardiology@smartopd.local": {
                "user_id": "USR-0002",
                "username": "doctor.cardiology@smartopd.local",
                "full_name": "Dr. Arvind Rao",
                "password_hash": generate_password_hash("Doctor@123"),
                "role": "doctor",
                "doctor_id": "DOC-002",
                "status": "active",
                "session_version": 1,
                "created_at": datetime.utcnow(),
                "last_login_at": None,
            },
            "doctor.general@smartopd.local": {
                "user_id": "USR-0003",
                "username": "doctor.general@smartopd.local",
                "full_name": "Dr. Meera Nair",
                "password_hash": generate_password_hash("Doctor@123"),
                "role": "doctor",
                "doctor_id": "DOC-001",
                "status": "active",
                "session_version": 1,
                "created_at": datetime.utcnow(),
                "last_login_at": None,
            },
            "staff.frontdesk@smartopd.local": {
                "user_id": "USR-0004",
                "username": "staff.frontdesk@smartopd.local",
                "full_name": "Front Desk Staff",
                "password_hash": generate_password_hash("Staff@123"),
                "role": "staff",
                "doctor_id": None,
                "status": "active",
                "session_version": 1,
                "created_at": datetime.utcnow(),
                "last_login_at": None,
            },
        }

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters long.")

    def _validate_user_payload(self, username: str, password: str, full_name: str, role: str) -> None:
        if "@" not in username:
            raise ValueError("Username must be a valid email-style login.")
        if not full_name:
            raise ValueError("Full name is required.")
        if role not in {"admin", "doctor", "staff"}:
            raise ValueError("Role must be admin, doctor, or staff.")
        self._validate_password(password)

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @staticmethod
    def _sanitize_user(row: Optional[dict]) -> Optional[dict]:
        if row is None:
            return None
        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "name": row.get("full_name") or row.get("name"),
            "role": row["role"],
            "doctor_id": row.get("doctor_id"),
            "status": row.get("status", "active"),
            "session_version": row.get("session_version", 1),
        }

    @staticmethod
    def _serialize_user_row(row: dict) -> dict:
        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "full_name": row.get("full_name") or row.get("name"),
            "role": row["role"],
            "doctor_id": row.get("doctor_id"),
            "status": row.get("status", "active"),
            "session_version": row.get("session_version", 1),
            "created_at": row.get("created_at").isoformat() + "Z" if isinstance(row.get("created_at"), datetime) else None,
            "last_login_at": row.get("last_login_at").isoformat() + "Z" if isinstance(row.get("last_login_at"), datetime) else None,
        }

    @staticmethod
    def _next_user_id(cursor) -> str:
        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total = cursor.fetchone()["total"]
        return f"USR-{total + 1:04d}"

    @staticmethod
    def _next_reset_token_id(cursor) -> str:
        cursor.execute("SELECT COUNT(*) AS total FROM password_reset_tokens")
        total = cursor.fetchone()["total"]
        return f"RST-{total + 1:04d}"


user_service = UserService()
