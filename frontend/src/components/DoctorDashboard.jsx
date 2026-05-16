export function DoctorDashboard({ doctors, selectedDoctor, setSelectedDoctorId, queue, onDoctorAction }) {
  const currentPatient = queue.find((patient) => patient.queue_status === "consulting");
  const nextPatient = queue.find((patient) => patient.queue_status !== "consulting");
  const noShowCandidate = queue.find((patient) => ["ready", "notified", "waiting"].includes(patient.queue_status));

  return (
    <section className="dashboard-grid">
      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Doctor Dashboard</p>
            <h3>{selectedDoctor.full_name}</h3>
          </div>
          <span className="status-badge">{selectedDoctor.status}</span>
        </div>

        <div className="doctor-switcher">
          {doctors.map((doctor) => (
            <button
              key={doctor.doctor_id}
              className={doctor.doctor_id === selectedDoctor.doctor_id ? "chip active" : "chip"}
              onClick={() => setSelectedDoctorId(doctor.doctor_id)}
            >
              {doctor.department}
            </button>
          ))}
        </div>

        <div className="kpi-strip">
          <div>
            <span>Current Patient</span>
            <strong>{currentPatient?.full_name ?? "None"}</strong>
          </div>
          <div>
            <span>Delay</span>
            <strong>{selectedDoctor.delay_minutes} min</strong>
          </div>
          <div>
            <span>Predicted Consult</span>
            <strong>{selectedDoctor.avg_consultation_minutes} min</strong>
          </div>
          <div>
            <span>Patients Remaining</span>
            <strong>{queue.length}</strong>
          </div>
        </div>

        <div className="action-row">
          <button onClick={() => onDoctorAction("complete")}>Complete Consultation</button>
          <button onClick={() => onDoctorAction("call-next")}>Call Next</button>
          <button
            onClick={() => onDoctorAction("no-show", { patient_id: noShowCandidate?.patient_id })}
            disabled={!noShowCandidate}
          >
            Mark No-Show
          </button>
          <button onClick={() => onDoctorAction("delay", { delay_minutes: 10 })}>Delay +10 min</button>
          <button onClick={() => onDoctorAction("emergency")}>Emergency Insert</button>
          <button onClick={() => onDoctorAction("status", { status: "break" })}>Mark Break</button>
          <button onClick={() => onDoctorAction("status", { status: "active" })}>Mark Active</button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Room Summary</p>
            <h3>Consultation flow</h3>
          </div>
        </div>
        <div className="timeline-card">
          <div>Current: {currentPatient?.full_name ?? "No active patient"}</div>
          <div>Next: {nextPatient?.full_name ?? "Queue clear"}</div>
          <div>Next slot: {nextPatient?.slot_time ?? "--"}</div>
          <div>No-show candidate: {noShowCandidate?.full_name ?? "None"}</div>
          <div>Room: {selectedDoctor.room_number}</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Priority Logic</p>
            <h3>Clinical safety rules</h3>
          </div>
        </div>
        <div className="timeline-card">
          <div>Emergency patients are inserted near the front safely.</div>
          <div>Elderly patients are prioritized to reduce long on-site exposure.</div>
          <div>ETA and notifications are refreshed after every doctor action.</div>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Department Queue</p>
            <h3>Realtime token movement</h3>
          </div>
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
            {queue.map((patient) => (
              <tr key={patient.patient_id}>
                <td>{patient.token_number}</td>
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
