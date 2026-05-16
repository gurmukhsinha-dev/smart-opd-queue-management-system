import { useMemo, useState } from "react";

function tokenLabel(patient) {
  const prefix = { "General OPD": "G", Cardiology: "C", Pediatrics: "P" }[patient.department] || "O";
  return `${prefix}-${patient.token_number}`;
}

export function PatientInterface({
  data,
  onRegister,
  onSendOtp,
  onVerifyOtp,
  onTrack,
  onPatientAction,
  onSelfCheckIn
}) {
  const [form, setForm] = useState({
    full_name: "",
    mobile_number: "",
    age: "",
    preferred_language: "English",
    department: "General OPD",
    appointment_date: new Date().toISOString().slice(0, 10),
    slot_time: "",
    priority: "normal"
  });
  const [search, setSearch] = useState("");
  const [trackedPatient, setTrackedPatient] = useState(data.patients[0]);
  const [checkInCode, setCheckInCode] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpState, setOtpState] = useState({
    requested: false,
    verified: false,
    preview: ""
  });

  const currentDoctor = useMemo(
    () => data.doctors.find((doctor) => doctor.doctor_id === trackedPatient?.doctor_id),
    [data.doctors, trackedPatient]
  );

  const liveQueue = useMemo(
    () => data.patients.filter((patient) => patient.visit_outcome === "active"),
    [data.patients]
  );

  const slotOptions = data.slot_catalog?.[form.department]?.available_slots || [];

  return (
    <section className="dashboard-grid patient-layout">
      <div className="hero-card gradient-card wide">
        <div>
          <p className="eyebrow">Patient Interface</p>
          <h3>Arrive only when your consultation is near.</h3>
          <p className="muted">
            Patients can register, track tokens, request support, and receive dynamic arrival guidance through
            SMS or WhatsApp.
          </p>
        </div>
        <div className="token-chip">
          <span>Tracked Token</span>
          <strong>{trackedPatient ? tokenLabel(trackedPatient) : "--"}</strong>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Registration</p>
            <h3>Digital token generation</h3>
          </div>
          <span className="status-badge">Mobile-led</span>
        </div>
        <div className="form-grid">
          <label>
            Patient Name
            <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </label>
          <label>
            Mobile Number
            <input
              value={form.mobile_number}
              onChange={(e) => {
                setForm({ ...form, mobile_number: e.target.value });
                setOtpState({ requested: false, verified: false, preview: "" });
              }}
            />
          </label>
          <label>
            Age
            <input value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} />
          </label>
          <label>
            Preferred Language
            <select
              value={form.preferred_language}
              onChange={(e) => setForm({ ...form, preferred_language: e.target.value })}
            >
              {["English", "Hindi", "Gujarati", "Tamil"].map((language) => (
                <option key={language}>{language}</option>
              ))}
            </select>
          </label>
          <label>
            Department
            <select
              value={form.department}
              onChange={(e) =>
                setForm({
                  ...form,
                  department: e.target.value,
                  slot_time: data.slot_catalog?.[e.target.value]?.available_slots?.[0] || ""
                })
              }
            >
              {data.departments.map((department) => (
                <option key={department}>{department}</option>
              ))}
            </select>
          </label>
          <label>
            Appointment Date
            <input
              type="date"
              value={form.appointment_date}
              onChange={(e) => setForm({ ...form, appointment_date: e.target.value })}
            />
          </label>
          <label>
            Slot Time
            <select value={form.slot_time} onChange={(e) => setForm({ ...form, slot_time: e.target.value })}>
              {slotOptions.map((slot) => (
                <option key={slot} value={slot}>
                  {slot}
                </option>
              ))}
            </select>
          </label>
          <label>
            Priority
            <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option value="normal">Normal</option>
              <option value="elderly">Elderly</option>
              <option value="emergency">Emergency</option>
            </select>
          </label>
        </div>
        <div className="otp-card">
          <div className="otp-row">
            <button
              type="button"
              onClick={async () => {
                const result = await onSendOtp(form.mobile_number);
                setOtpState({
                  requested: true,
                  verified: false,
                  preview: result.otp_preview || ""
                });
              }}
              disabled={!form.mobile_number}
            >
              Send OTP
            </button>
            <input
              placeholder="Enter OTP"
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value)}
            />
            <button
              type="button"
              onClick={async () => {
                await onVerifyOtp(form.mobile_number, otpCode);
                setOtpState((state) => ({ ...state, verified: true }));
              }}
              disabled={!otpState.requested || !otpCode}
            >
              Verify OTP
            </button>
          </div>
          <div className="otp-hint">
            {otpState.verified
              ? "Mobile verified. You can book the OPD slot now."
              : otpState.preview
                ? `Mock OTP preview: ${otpState.preview}`
                : "Verify the patient mobile number before registration."}
          </div>
        </div>
        <div className="action-row">
          <button
            disabled={!otpState.verified}
            onClick={() =>
              onRegister({
                ...form,
                age: Number(form.age) || 0
              })
            }
          >
            Register Patient
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Token Lookup</p>
            <h3>Track by token, name, or mobile</h3>
          </div>
          <span className="status-badge amber">Front-desk friendly</span>
        </div>
        <div className="lookup-row">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="G-102 or patient name" />
          <button
            onClick={async () => {
              const patient = await onTrack(search);
              setTrackedPatient(patient);
            }}
          >
            Track
          </button>
        </div>
        {trackedPatient ? (
          <div className="metric-list">
            <div className="metric-row">
              <span>Patient</span>
              <strong>{trackedPatient.full_name}</strong>
            </div>
            <div className="metric-row">
              <span>Doctor</span>
              <strong>{currentDoctor?.full_name ?? "--"}</strong>
            </div>
            <div className="metric-row">
              <span>Estimated Wait</span>
              <strong>{trackedPatient.predicted_wait_minutes} min</strong>
            </div>
            <div className="metric-row">
              <span>Booked Slot</span>
              <strong>{trackedPatient.appointment_date} {trackedPatient.slot_time || "--"}</strong>
            </div>
            <div className="metric-row">
              <span>Check-In Code</span>
              <strong>{trackedPatient.check_in_code || "--"}</strong>
            </div>
            <div className="metric-row">
              <span>Arrival Guidance</span>
              <strong>{trackedPatient.arrival_state}</strong>
            </div>
            <div className="metric-row">
              <span>Visit Outcome</span>
              <strong>{trackedPatient.visit_outcome}</strong>
            </div>
            <div className="metric-row">
              <span>Latest Notification</span>
              <strong>{trackedPatient.latest_notification_status || "none"}</strong>
            </div>
          </div>
        ) : null}
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Notification Timeline</p>
            <h3>Recent patient alerts</h3>
          </div>
        </div>
        {trackedPatient?.notification_history?.length ? (
          <div className="timeline-card">
            {trackedPatient.notification_history.map((item) => (
              <div key={item.notification_id} className="notification-timeline-item">
                <span>
                  {item.channel} via {item.provider || "pending"} | {item.status}
                </span>
                <strong>{item.message}</strong>
                <small>
                  Scheduled: {item.scheduled_at}
                  {item.delivered_at ? ` | Delivered: ${item.delivered_at}` : ""}
                  {item.read_at ? ` | Read: ${item.read_at}` : ""}
                </small>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">No notification history is available for this patient yet.</p>
        )}
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Self Check-In</p>
            <h3>Token scan or code entry</h3>
          </div>
        </div>
        <div className="lookup-row">
          <input
            value={checkInCode}
            onChange={(e) => setCheckInCode(e.target.value)}
            placeholder="Enter CHK code from SMS or QR"
          />
          <button
            onClick={async () => {
              const patient = await onSelfCheckIn(checkInCode);
              setTrackedPatient(patient);
            }}
          >
            Check In
          </button>
        </div>
        {trackedPatient?.qr_payload ? (
          <div className="timeline-card checkin-card">
            <div>QR-ready payload: {trackedPatient.qr_payload}</div>
            <div>Use the code above for kiosk or scan workflows.</div>
          </div>
        ) : null}
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Patient Help</p>
            <h3>Quick service requests</h3>
          </div>
        </div>
        {trackedPatient ? (
          <div className="quick-actions-grid">
            <button onClick={() => onPatientAction(trackedPatient.patient_id, "arrived")}>I Have Arrived</button>
            <button onClick={() => onPatientAction(trackedPatient.patient_id, "assistance")}>Need Assistance</button>
            <button onClick={() => onPatientAction(trackedPatient.patient_id, "share_status")}>Share With Attendant</button>
            <button onClick={() => onPatientAction(trackedPatient.patient_id, "cancel_visit")}>Cancel Visit</button>
          </div>
        ) : (
          <p className="muted">Track a patient first to use support actions.</p>
        )}
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Live Queue</p>
            <h3>Realtime patient queue</h3>
          </div>
          <span className="status-badge rose">Dynamic rescheduling on</span>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Token</th>
              <th>Patient</th>
              <th>Priority</th>
              <th>Slot</th>
              <th>Status</th>
              <th>Outcome</th>
              <th>ETA</th>
              <th>Arrival</th>
            </tr>
          </thead>
          <tbody>
            {liveQueue.map((patient) => (
              <tr key={patient.patient_id}>
                <td>{tokenLabel(patient)}</td>
                <td>{patient.full_name}</td>
                <td>{patient.priority}</td>
                <td>{patient.slot_time || "--"}</td>
                <td>{patient.queue_status}</td>
                <td>{patient.visit_outcome}</td>
                <td>{patient.predicted_wait_minutes} min</td>
                <td>{patient.arrival_state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
