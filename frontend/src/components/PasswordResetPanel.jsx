import { useState } from "react";

export function PasswordResetPanel({ mode, error, message, onBack, onForgotPassword, onResetPassword }) {
  const [requestUsername, setRequestUsername] = useState("staff.frontdesk@smartopd.local");
  const [resetForm, setResetForm] = useState({
    username: "staff.frontdesk@smartopd.local",
    reset_token: "",
    new_password: ""
  });

  const isForgotMode = mode === "forgot";

  return (
    <section className="auth-shell">
      <div className="auth-card">
        <p className="eyebrow">Password Assistance</p>
        <h3>{isForgotMode ? "Request reset token" : "Complete password reset"}</h3>
        <p className="muted">
          Staff can request a short-lived reset token and use it to securely set a new password.
        </p>

        {isForgotMode ? (
          <div className="form-grid">
            <label>
              Username
              <input
                value={requestUsername}
                onChange={(event) => setRequestUsername(event.target.value)}
                placeholder="doctor.general@smartopd.local"
              />
            </label>
          </div>
        ) : (
          <div className="form-grid">
            <label>
              Username
              <input
                value={resetForm.username}
                onChange={(event) => setResetForm({ ...resetForm, username: event.target.value })}
              />
            </label>
            <label>
              Reset Token
              <input
                value={resetForm.reset_token}
                onChange={(event) => setResetForm({ ...resetForm, reset_token: event.target.value })}
                placeholder="Paste token from reset step"
              />
            </label>
            <label className="wide-field">
              New Password
              <input
                type="password"
                value={resetForm.new_password}
                onChange={(event) => setResetForm({ ...resetForm, new_password: event.target.value })}
                placeholder="At least 8 characters"
              />
            </label>
          </div>
        )}

        {error ? <div className="feedback error">{error}</div> : null}
        {message ? <div className="feedback success">{message}</div> : null}

        <div className="action-row">
          {isForgotMode ? (
            <button onClick={() => onForgotPassword(requestUsername)}>Generate Reset Token</button>
          ) : (
            <button onClick={() => onResetPassword(resetForm)}>Update Password</button>
          )}
          <button className="secondary-button" onClick={onBack}>
            Back To Login
          </button>
        </div>
      </div>
    </section>
  );
}
