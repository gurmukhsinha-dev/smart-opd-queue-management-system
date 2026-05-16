import { useMemo, useState } from "react";

export function KioskPanel({ data, onSelfCheckIn }) {
  const [checkInCode, setCheckInCode] = useState("");
  const [checkedInPatient, setCheckedInPatient] = useState(null);

  const recentArrivals = useMemo(
    () =>
      data.patients
        .filter((patient) => patient.arrival_state === "arrived")
        .slice()
        .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
        .slice(0, 8),
    [data.patients]
  );

  return (
    <section className="dashboard-grid">
      <div className="hero-card gradient-card wide">
        <div>
          <p className="eyebrow">Kiosk Mode</p>
          <h3>Lobby self check-in and arrival guidance</h3>
          <p className="muted">
            Patients can enter their check-in code from SMS or scan-ready token details to confirm they are on site.
          </p>
        </div>
        <div className="token-chip">
          <span>Checked In Today</span>
          <strong>{data.summary.checked_in_patients}</strong>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Arrival Kiosk</p>
            <h3>Enter code to check in</h3>
          </div>
          <span className="status-badge">Self Service</span>
        </div>
        <div className="lookup-row">
          <input
            value={checkInCode}
            onChange={(e) => setCheckInCode(e.target.value)}
            placeholder="CHK-G104-0009"
          />
          <button
            onClick={async () => {
              const patient = await onSelfCheckIn(checkInCode);
              setCheckedInPatient(patient);
            }}
          >
            Confirm Arrival
          </button>
        </div>
        {checkedInPatient ? (
          <div className="timeline-card checkin-card">
            <div>Patient: {checkedInPatient.full_name}</div>
            <div>Department: {checkedInPatient.department}</div>
            <div>Room: {data.doctors.find((doctor) => doctor.doctor_id === checkedInPatient.doctor_id)?.room_number}</div>
            <div>Guidance: {checkedInPatient.arrival_state}</div>
          </div>
        ) : null}
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">On-Site Snapshot</p>
            <h3>Current arrival status</h3>
          </div>
        </div>
        <div className="timeline-card">
          <div>Patients on site: {data.summary.patients_on_site}</div>
          <div>Checked-in patients: {data.summary.checked_in_patients}</div>
          <div>Active queue: {data.summary.active_tokens}</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Queue Guidance</p>
            <h3>Arrival handling rules</h3>
          </div>
        </div>
        <div className="timeline-card">
          <div>Proceed-now patients should move directly to the room corridor.</div>
          <div>Arrived patients remain visible to the doctor and admin teams.</div>
          <div>Delayed departments automatically keep ETA and guidance up to date.</div>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Recent Arrivals</p>
            <h3>Latest checked-in patients</h3>
          </div>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Patient</th>
              <th>Department</th>
              <th>Token</th>
              <th>Slot</th>
              <th>Status</th>
              <th>Arrival</th>
            </tr>
          </thead>
          <tbody>
            {recentArrivals.map((patient) => (
              <tr key={patient.patient_id}>
                <td>{patient.full_name}</td>
                <td>{patient.department}</td>
                <td>{patient.token_number}</td>
                <td>{patient.slot_time || "--"}</td>
                <td>{patient.queue_status}</td>
                <td>{patient.arrival_state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
