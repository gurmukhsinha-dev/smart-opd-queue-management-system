import { useMemo, useState } from "react";

function tokenLabel(patient) {
  const prefix = { "General OPD": "G", Cardiology: "C", Pediatrics: "P" }[patient.department] || "O";
  return `${prefix}-${patient.token_number}`;
}

export function StaffDashboard({
  data,
  currentUser,
  onRefresh,
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
  const [otpState, setOtpState] = useState({ requested: false, verified: false, preview: "" });
  const [otpCode, setOtpCode] = useState("");
  const [search, setSearch] = useState("");
  const [trackedPatient, setTrackedPatient] = useState(data.patients[0] || null);
  const [checkInCode, setCheckInCode] = useState("");

  const slotOptions = data.slot_catalog?.[form.department]?.available_slots || [];
  const actionQueue = useMemo(
    () => data.patients.filter((patient) => ["waiting", "notified", "ready"].includes(patient.queue_status)),
    [data.patients]
  );
  const recentNotifications = useMemo(() => data.notifications.slice(0, 6), [data.notifications]);

  return (
    <section className="dashboard-grid">
      <div className="hero-card gradient-card wide">
        <div>
          <p className="eyebrow">Staff Dashboard</p>
          <h3>Front desk control for registration, arrivals, and queue guidance</h3>
          <p className="muted">
            Logged in as {currentUser?.name || currentUser?.username}. Use this workspace to onboard patients,
            verify OTP, check them in, and handle queue-side help requests.
          </p>
        </div>
        <div className="token-chip">
          <span>On-Site Patients</span>
          <strong>{data.summary.patients_on_site}</strong>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Front Desk Snapshot</p>
            <h3>Operational status</h3>
          </div>
          <button className="secondary-button" onClick={onRefresh}>Refresh</button>
        </div>
        <div className="kpi-strip">
          <div>
            <span>Active Queue</span>
            <strong>{data.summary.active_tokens}</strong>
          </div>
          <div>
            <span>Checked In</span>
            <strong>{data.summary.checked_in_patients}</strong>
          </div>
          <div>
            <span>Average Wait</span>
            <strong>{data.summary.average_wait_minutes} min</strong>
          </div>
          <div>
            <span>No-Shows</span>
            <strong>{data.summary.no_shows}</strong>
          </div>
          <div>
            <span>Cancelled</span>
            <strong>{data.summary.cancelled_visits}</strong>
          </div>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Registration Desk</p>
            <h3>New OPD booking with OTP verification</h3>
          </div>
          <span className="status-badge">Staff Assisted</span>
        </div>
        <div className="form-grid">
          <label>
            Patient Name
            <input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} />
          </label>
          <label>
            Mobile Number
            <input
              value={form.mobile_number}
              onChange={(event) => {
                setForm({ ...form, mobile_number: event.target.value });
                setOtpState({ requested: false, verified: false, preview: "" });
              }}
            />
          </label>
          <label>
            Age
            <input value={form.age} onChange={(event) => setForm({ ...form, age: event.target.value })} />
          </label>
          <label>
            Preferred Language
            <select
              value={form.preferred_language}
              onChange={(event) => setForm({ ...form, preferred_language: event.target.value })}
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
              onChange={(event) =>
                setForm({
                  ...form,
                  department: event.target.value,
                  slot_time: data.slot_catalog?.[event.target.value]?.available_slots?.[0] || ""
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
              onChange={(event) => setForm({ ...form, appointment_date: event.target.value })}
            />
          </label>
          <label>
            Slot Time
            <select value={form.slot_time} onChange={(event) => setForm({ ...form, slot_time: event.target.value })}>
              {slotOptions.map((slot) => (
                <option key={slot} value={slot}>
                  {slot}
                </option>
              ))}
            </select>
          </label>
          <label>
            Priority
            <select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
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
            >
              Send OTP
            </button>
            <input
              value={otpCode}
              onChange={(event) => setOtpCode(event.target.value)}
              placeholder="Enter OTP code"
            />
            <button
              type="button"
              onClick={async () => {
                await onVerifyOtp(form.mobile_number, otpCode);
                setOtpState((current) => ({ ...current, verified: true }));
              }}
              disabled={!otpState.requested || !otpCode}
            >
              Verify OTP
            </button>
          </div>
          <div className="otp-hint">
            {otpState.verified
              ? "OTP verified. Registration is now unlocked."
              : otpState.preview
                ? `Current OTP preview: ${otpState.preview}`
                : "Send and verify OTP before registering the patient."}
          </div>
        </div>
        <div className="action-row">
          <button
            disabled={!otpState.verified}
            onClick={() => onRegister({ ...form, age: Number(form.age) || 0 })}
          >
            Create Appointment Token
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Patient Lookup</p>
            <h3>Search and support</h3>
          </div>
        </div>
        <div className="lookup-row">
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, mobile, or token" />
          <button
            onClick={async () => {
              const patient = await onTrack(search);
              setTrackedPatient(patient);
            }}
          >
            Search
          </button>
        </div>
        {trackedPatient ? (
          <>
            <div className="metric-list">
              <div className="metric-row">
                <span>Patient</span>
                <strong>{trackedPatient.full_name}</strong>
              </div>
              <div className="metric-row">
                <span>Token</span>
                <strong>{tokenLabel(trackedPatient)}</strong>
              </div>
              <div className="metric-row">
                <span>Queue Status</span>
                <strong>{trackedPatient.queue_status}</strong>
              </div>
              <div className="metric-row">
                <span>Visit Outcome</span>
                <strong>{trackedPatient.visit_outcome}</strong>
              </div>
              <div className="metric-row">
                <span>Check-In Code</span>
                <strong>{trackedPatient.check_in_code || "--"}</strong>
              </div>
            </div>
            <div className="quick-actions-grid">
              <button onClick={() => onPatientAction(trackedPatient.patient_id, "arrived")}>Mark Arrived</button>
              <button onClick={() => onPatientAction(trackedPatient.patient_id, "assistance")}>Raise Assistance</button>
              <button onClick={() => onPatientAction(trackedPatient.patient_id, "share_status")}>Share Status</button>
              <button onClick={() => onPatientAction(trackedPatient.patient_id, "cancel_visit")}>Cancel Visit</button>
            </div>
          </>
        ) : (
          <p className="muted">Search for a patient to view queue details and support actions.</p>
        )}
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Self Check-In Support</p>
            <h3>Desk-assisted arrival confirmation</h3>
          </div>
        </div>
        <div className="lookup-row">
          <input
            value={checkInCode}
            onChange={(event) => setCheckInCode(event.target.value)}
            placeholder="CHK-G101-0001"
          />
          <button
            onClick={async () => {
              const patient = await onSelfCheckIn(checkInCode);
              setTrackedPatient(patient);
            }}
          >
            Confirm Check-In
          </button>
        </div>
        <div className="timeline-card">
          <div>Checked-in patients today: {data.summary.checked_in_patients}</div>
          <div>Patients currently on site: {data.summary.patients_on_site}</div>
          <div>Crowd risk level: {data.summary.crowd_risk_level}</div>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Front Desk Queue</p>
            <h3>Patients needing desk attention</h3>
          </div>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Token</th>
              <th>Patient</th>
              <th>Department</th>
              <th>Slot</th>
              <th>Status</th>
              <th>ETA</th>
              <th>Arrival</th>
            </tr>
          </thead>
          <tbody>
            {actionQueue.map((patient) => (
              <tr key={patient.patient_id}>
                <td>{tokenLabel(patient)}</td>
                <td>{patient.full_name}</td>
                <td>{patient.department}</td>
                <td>{patient.slot_time || "--"}</td>
                <td>{patient.queue_status}</td>
                <td>{patient.predicted_wait_minutes} min</td>
                <td>{patient.arrival_state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Recent Notifications</p>
            <h3>Messages patients are acting on</h3>
          </div>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Patient</th>
              <th>Channel</th>
              <th>Status</th>
              <th>Scheduled</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {recentNotifications.map((item) => (
              <tr key={item.notification_id}>
                <td>{item.patient_name}</td>
                <td>{item.channel}</td>
                <td>{item.status}</td>
                <td>{item.scheduled_at}</td>
                <td>{item.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
