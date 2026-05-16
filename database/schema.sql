CREATE DATABASE IF NOT EXISTS smart_opd;
USE smart_opd;

CREATE TABLE patients (
    patient_id VARCHAR(20) PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(20) NULL,
    mobile_number VARCHAR(20) NOT NULL UNIQUE,
    preferred_language VARCHAR(30) DEFAULT 'en',
    priority_category ENUM('normal', 'elderly', 'emergency', 'high_risk') DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE doctors (
    doctor_id VARCHAR(20) PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    department VARCHAR(80) NOT NULL,
    room_number VARCHAR(20) NOT NULL,
    avg_consultation_minutes INT DEFAULT 8,
    status ENUM('active', 'break', 'offline', 'emergency') DEFAULT 'active',
    delay_minutes INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE appointments (
    appointment_id VARCHAR(20) PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL,
    doctor_id VARCHAR(20) NOT NULL,
    appointment_date DATE NOT NULL,
    slot_time TIME NULL,
    check_in_status ENUM('pending', 'arrived', 'cancelled', 'no_show') DEFAULT 'pending',
    consultation_status ENUM('scheduled', 'ready', 'consulting', 'completed') DEFAULT 'scheduled',
    visit_outcome ENUM('active', 'completed', 'no_show', 'cancelled') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_appointments_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    CONSTRAINT fk_appointments_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
);

CREATE TABLE queue_tokens (
    token_id VARCHAR(20) PRIMARY KEY,
    appointment_id VARCHAR(20) NOT NULL,
    token_number INT NOT NULL,
    queue_status ENUM('waiting', 'notified', 'ready', 'consulting', 'completed', 'no_show', 'cancelled') DEFAULT 'waiting',
    queue_position INT DEFAULT 0,
    predicted_wait_minutes DECIMAL(6,2) DEFAULT 0,
    predicted_consultation_minutes DECIMAL(6,2) DEFAULT 0,
    notification_lead_minutes INT DEFAULT 20,
    last_recalculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_queue_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
);

CREATE TABLE notifications (
    notification_id VARCHAR(20) PRIMARY KEY,
    token_id VARCHAR(20) NOT NULL,
    channel ENUM('sms', 'whatsapp') NOT NULL,
    provider VARCHAR(40) NULL,
    provider_message_id VARCHAR(120) NULL,
    scheduled_at DATETIME NOT NULL,
    sent_at DATETIME NULL,
    delivered_at DATETIME NULL,
    read_at DATETIME NULL,
    delivery_status ENUM('scheduled', 'sent', 'delivered', 'read', 'failed') DEFAULT 'scheduled',
    error_message VARCHAR(255) NULL,
    template_name VARCHAR(80) NOT NULL,
    message_preview VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_token FOREIGN KEY (token_id) REFERENCES queue_tokens(token_id)
);

CREATE TABLE doctor_status_logs (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    doctor_id VARCHAR(20) NOT NULL,
    status ENUM('active', 'break', 'offline', 'emergency') NOT NULL,
    delay_minutes INT DEFAULT 0,
    noted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_status_log_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
);

CREATE TABLE crowd_density_events (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    department VARCHAR(80) NOT NULL,
    density_level ENUM('low', 'moderate', 'high', 'critical') NOT NULL,
    source_type ENUM('cctv', 'wifi', 'ble', 'manual') DEFAULT 'manual',
    observed_count INT DEFAULT 0,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    audit_id VARCHAR(20) PRIMARY KEY,
    action VARCHAR(80) NOT NULL,
    message VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
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
);

CREATE TABLE password_reset_tokens (
    token_id VARCHAR(24) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reset_user FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_doctors_department ON doctors(department);
CREATE INDEX idx_appointments_date ON appointments(appointment_date, doctor_id);
CREATE INDEX idx_queue_status ON queue_tokens(queue_status, queue_position);
CREATE INDEX idx_notifications_schedule ON notifications(scheduled_at, delivery_status);
CREATE INDEX idx_notifications_provider_message_id ON notifications(provider_message_id);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at);
CREATE INDEX idx_users_role_status ON users(role, status);
