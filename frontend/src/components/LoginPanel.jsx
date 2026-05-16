import { useEffect, useState } from "react";

const defaultsByRole = {
  admin: { username: "admin@smartopd.local", password: "Admin@123" },
  doctor: { username: "doctor.cardiology@smartopd.local", password: "Doctor@123" },
  staff: { username: "staff.frontdesk@smartopd.local", password: "Staff@123" }
};

const labelsByRole = {
  admin: "Admin",
  doctor: "Doctor",
  staff: "Staff"
};

export function LoginPanel({ role, error, message, onLogin, onShowForgot, onShowReset }) {
  const [form, setForm] = useState(defaultsByRole[role] || defaultsByRole.staff);

  useEffect(() => {
    setForm(defaultsByRole[role] || defaultsByRole.staff);
  }, [role]);

  return (
    <section className="auth-shell">
      <div className="auth-card">
        <p className="eyebrow">Secure Staff Access</p>
        <h3>{labelsByRole[role]} login</h3>
        <p className="muted">
          Hospital staff actions are protected with role-based access, hashed passwords, and session validation.
        </p>
        <div className="form-grid">
          <label>
            Username
            <input
              value={form.username}
              onChange={(event) => setForm({ ...form, username: event.target.value })}
              placeholder="staff.frontdesk@smartopd.local"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              placeholder="Enter password"
            />
          </label>
        </div>
        {error ? <div className="feedback error">{error}</div> : null}
        {message ? <div className="feedback success">{message}</div> : null}
        <div className="action-row">
          <button onClick={() => onLogin(form)}>Sign In</button>
          <button className="secondary-button" onClick={onShowForgot}>
            Forgot Password
          </button>
          <button className="secondary-button" onClick={onShowReset}>
            Reset With Token
          </button>
        </div>
        <div className="timeline-card">
          <div>Admin: `admin@smartopd.local` / `Admin@123`</div>
          <div>Doctor: `doctor.cardiology@smartopd.local` / `Doctor@123`</div>
          <div>Staff: `staff.frontdesk@smartopd.local` / `Staff@123`</div>
        </div>
      </div>
    </section>
  );
}
