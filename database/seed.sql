USE smart_opd;

INSERT INTO doctors (doctor_id, full_name, department, room_number, avg_consultation_minutes, status, delay_minutes) VALUES
('DOC-001', 'Dr. Meera Nair', 'General OPD', 'G-12', 8, 'active', 5),
('DOC-002', 'Dr. Arvind Rao', 'Cardiology', 'C-04', 10, 'active', 12),
('DOC-003', 'Dr. Nisha Kulkarni', 'Pediatrics', 'P-07', 7, 'break', 15);

INSERT INTO patients (patient_id, full_name, age, gender, mobile_number, preferred_language, priority_category) VALUES
('PAT-0001', 'Suresh Verma', 67, 'M', '9876543210', 'hi', 'elderly'),
('PAT-0002', 'Ananya Iyer', 29, 'F', '9123456780', 'en', 'normal'),
('PAT-0003', 'Mohan Patel', 72, 'M', '9988776655', 'gu', 'elderly');
