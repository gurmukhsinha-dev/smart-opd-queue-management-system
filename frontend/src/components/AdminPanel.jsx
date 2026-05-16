import { useState } from "react";

export function AdminPanel({
  data,
  deploymentReadiness,
  providerDiagnostics,
  onRefresh,
  onSimulateTick,
  onDispatchNotifications,
  onProviderTest
}) {
  const blockers = deploymentReadiness?.blockers || [];
  const [testForm, setTestForm] = useState({
    test_type: "notification",
    channel: "sms",
    provider: "",
    mobile_number: "",
    message: "Smart OPD provider test message from hospital admin.",
    dry_run: true
  });
  const [testResult, setTestResult] = useState(null);

  const handleTestSubmit = async (event) => {
    event.preventDefault();
    const result = await onProviderTest(testForm);
    setTestResult(result?.result || null);
  };

  const updateTestForm = (key, value) => {
    setTestForm((current) => ({ ...current, [key]: value }));
  };

  return (
    <section className="dashboard-grid">
      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Hospital Admin Panel</p>
            <h3>Operational command center</h3>
          </div>
          <span className="status-badge">Realtime</span>
        </div>
        <div className="kpi-strip">
          <div>
            <span>Daily Patients</span>
            <strong>{data.summary.active_tokens}</strong>
          </div>
          <div>
            <span>No-show Risk</span>
            <strong>{data.analytics.no_show_risk_percent}%</strong>
          </div>
          <div>
            <span>Notification Success</span>
            <strong>{data.analytics.notification_success_rate}%</strong>
          </div>
          <div>
            <span>Notification Read</span>
            <strong>{data.analytics.notification_read_rate}%</strong>
          </div>
          <div>
            <span>AI Accuracy</span>
            <strong>{data.analytics.ai_accuracy_percent}%</strong>
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
        <div className="action-row">
          <button onClick={onRefresh}>Refresh Dashboard</button>
          <button onClick={onSimulateTick}>Simulate Queue Tick</button>
          <button onClick={onDispatchNotifications}>Dispatch Notifications</button>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Department Overview</p>
            <h3>Queue, delay, and throughput</h3>
          </div>
          <span className="status-badge amber">{data.summary.crowd_risk_level} density</span>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Department</th>
              <th>Doctor</th>
              <th>Status</th>
              <th>Delay</th>
              <th>Queue Size</th>
              <th>Avg Wait</th>
            </tr>
          </thead>
          <tbody>
            {data.analytics.department_overview.map((row) => (
              <tr key={row.department}>
                <td>{row.department}</td>
                <td>{row.doctor_name}</td>
                <td>{row.status}</td>
                <td>{row.delay_minutes} min</td>
                <td>{row.queue_size}</td>
                <td>{row.average_wait_minutes} min</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Crowd Density</p>
            <h3>Waiting hall overview</h3>
          </div>
        </div>
        <div className="density-grid">
          {data.crowd_zones.map((zone) => (
            <div key={zone.zone} className={`density-card ${zone.level}`}>
              <span>{zone.zone}</span>
              <strong>{zone.count}</strong>
              <small>{zone.level}</small>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Operational Insight</p>
            <h3>Predictive scheduling</h3>
          </div>
        </div>
        <div className="timeline-card">
          <div>Peak window: {data.analytics.peak_window}</div>
          <div>Recommended action: {data.analytics.recommended_action}</div>
          <div>Patients on-site: {data.summary.patients_on_site}</div>
          <div>Booked departments: {Object.keys(data.slot_catalog || {}).length}</div>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Appointment Slots</p>
            <h3>Daily OPD booking windows</h3>
          </div>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Department</th>
              <th>Doctor</th>
              <th>Date</th>
              <th>Sample Slots</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.slot_catalog || {}).map(([department, details]) => (
              <tr key={department}>
                <td>{department}</td>
                <td>{details.doctor_name}</td>
                <td>{details.appointment_date}</td>
                <td>{details.slots.slice(0, 6).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Notification Setup</p>
            <h3>Provider routing</h3>
          </div>
        </div>
        <div className="timeline-card">
          <div>Mode: {data.notification_settings?.mode || "mock"}</div>
          <div>OTP provider: {data.notification_settings?.otp_provider || "mock"}</div>
          <div>SMS provider: {data.notification_settings?.sms_provider || "mock"}</div>
          <div>WhatsApp provider: {data.notification_settings?.whatsapp_provider || "mock"}</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Deployment Readiness</p>
            <h3>Production checks</h3>
          </div>
          <span className={`status-badge ${deploymentReadiness?.status === "ready" ? "" : "amber"}`}>
            {deploymentReadiness?.status || "unknown"}
          </span>
        </div>
        <div className="timeline-card">
          <div>MySQL mode: {deploymentReadiness?.persistence?.mode || "unknown"}</div>
          <div>OTP: {deploymentReadiness?.otp?.provider || "mock"} / {deploymentReadiness?.otp?.mode || "mock"}</div>
          <div>SMS: {deploymentReadiness?.notifications?.sms?.provider || "mock"}</div>
          <div>WhatsApp: {deploymentReadiness?.notifications?.whatsapp?.provider || "mock"}</div>
          <div>Origins locked: {deploymentReadiness?.security?.restricted_origins ? "Yes" : "No"}</div>
          <div>App secret: {deploymentReadiness?.security?.app_secret_configured ? "Configured" : "Needs update"}</div>
          <div>Blockers: {blockers.length}</div>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Go-Live Checklist</p>
            <h3>What still needs attention</h3>
          </div>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Area</th>
              <th>Status</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>OTP delivery</td>
              <td>{deploymentReadiness?.otp?.ready ? "Ready" : "Needs setup"}</td>
              <td>{deploymentReadiness?.otp?.note || "-"}</td>
            </tr>
            <tr>
              <td>SMS alerts</td>
              <td>{deploymentReadiness?.notifications?.sms?.ready ? "Ready" : "Needs setup"}</td>
              <td>
                {deploymentReadiness?.notifications?.sms?.missing?.join(", ")
                  || deploymentReadiness?.notifications?.sms?.note
                  || "-"}
              </td>
            </tr>
            <tr>
              <td>WhatsApp alerts</td>
              <td>{deploymentReadiness?.notifications?.whatsapp?.ready ? "Ready" : "Needs setup"}</td>
              <td>
                {deploymentReadiness?.notifications?.whatsapp?.missing?.join(", ")
                  || deploymentReadiness?.notifications?.whatsapp?.note
                  || "-"}
              </td>
            </tr>
            <tr>
              <td>Security</td>
              <td>{deploymentReadiness?.security?.app_secret_configured ? "Ready" : "Needs setup"}</td>
              <td>
                {blockers.length ? blockers.join(" | ") : "No critical blockers detected."}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Provider Diagnostics</p>
            <h3>Secrets and vendor readiness</h3>
          </div>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Flow</th>
              <th>Mode</th>
              <th>Provider</th>
              <th>Status</th>
              <th>Secrets</th>
            </tr>
          </thead>
          <tbody>
            {["otp", "sms", "whatsapp"].map((key) => {
              const item = providerDiagnostics?.[key];
              return (
                <tr key={key}>
                  <td>{key.toUpperCase()}</td>
                  <td>{item?.mode || "-"}</td>
                  <td>{item?.provider || "-"}</td>
                  <td>{item?.ready ? "Ready" : "Needs setup"}</td>
                  <td>
                    {(item?.secrets || []).map((secret) => (
                      <div key={`${key}-${secret.key}`}>
                        {secret.key}: {secret.configured ? `configured via ${secret.source}` : "missing"}
                      </div>
                    ))}
                    {!item?.secrets?.length ? (item?.note || "-") : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Provider Test Console</p>
            <h3>Dry run or live test delivery</h3>
          </div>
        </div>
        <form className="form-grid" onSubmit={handleTestSubmit}>
          <label>
            Test Type
            <select
              value={testForm.test_type}
              onChange={(event) => updateTestForm("test_type", event.target.value)}
            >
              <option value="notification">Notification</option>
              <option value="otp">OTP</option>
            </select>
          </label>
          <label>
            Channel
            <select
              value={testForm.channel}
              onChange={(event) => updateTestForm("channel", event.target.value)}
              disabled={testForm.test_type === "otp"}
            >
              <option value="sms">SMS</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </label>
          <label>
            Override Provider
            <select
              value={testForm.provider}
              onChange={(event) => updateTestForm("provider", event.target.value)}
            >
              <option value="">Use configured provider</option>
              <option value="msg91">MSG91</option>
              <option value="gupshup">Gupshup</option>
              <option value="twilio">Twilio</option>
              <option value="webhook">Webhook</option>
              <option value="mock">Mock</option>
            </select>
          </label>
          <label>
            Mobile Number
            <input
              value={testForm.mobile_number}
              onChange={(event) => updateTestForm("mobile_number", event.target.value)}
              placeholder="9876543210"
            />
          </label>
          <label className="wide-field">
            Message
            <input
              value={testForm.message}
              onChange={(event) => updateTestForm("message", event.target.value)}
              disabled={testForm.test_type === "otp"}
            />
          </label>
          <label className="toggle-field">
            <input
              type="checkbox"
              checked={testForm.dry_run}
              onChange={(event) => updateTestForm("dry_run", event.target.checked)}
            />
            Dry run only
          </label>
          <div className="action-row compact">
            <button type="submit">Run Provider Test</button>
          </div>
        </form>
        {testResult ? (
          <div className="test-result-card">
            <strong>Latest test result</strong>
            <pre>{JSON.stringify(testResult, null, 2)}</pre>
          </div>
        ) : null}
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Visit Outcomes</p>
            <h3>Queue recovery signals</h3>
          </div>
        </div>
        <div className="timeline-card">
          <div>Completed visits: {data.summary.completed_visits}</div>
          <div>No-shows: {data.summary.no_shows}</div>
          <div>Cancelled visits: {data.summary.cancelled_visits}</div>
        </div>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Notification Feed</p>
            <h3>Recent patient alerts</h3>
          </div>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Patient</th>
              <th>Channel</th>
              <th>Provider</th>
              <th>Status</th>
              <th>Provider Ref</th>
              <th>Scheduled</th>
              <th>Delivered</th>
              <th>Read</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {data.notifications.map((notification) => (
              <tr key={notification.notification_id}>
                <td>{notification.patient_name}</td>
                <td>{notification.channel}</td>
                <td>{notification.provider || "-"}</td>
                <td>{notification.status}</td>
                <td>{notification.provider_message_id || "-"}</td>
                <td>{notification.scheduled_at}</td>
                <td>{notification.delivered_at || "-"}</td>
                <td>{notification.read_at || "-"}</td>
                <td>{notification.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Audit Trail</p>
            <h3>Recent operational actions</h3>
          </div>
        </div>
        <table className="queue-table">
          <thead>
            <tr>
              <th>Action</th>
              <th>Message</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {(data.audit_logs || []).map((audit) => (
              <tr key={audit.audit_id}>
                <td>{audit.action}</td>
                <td>{audit.message}</td>
                <td>{audit.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
