import { useEffect, useMemo, useState } from "react";
import { AdminPanel } from "./components/AdminPanel";
import { DoctorDashboard } from "./components/DoctorDashboard";
import { KioskPanel } from "./components/KioskPanel";
import { LoginPanel } from "./components/LoginPanel";
import { PasswordResetPanel } from "./components/PasswordResetPanel";
import { PatientInterface } from "./components/PatientInterface";
import { StaffDashboard } from "./components/StaffDashboard";
import { useHospitalData } from "./hooks/useHospitalData";
import { api, clearSession, getStoredSession, saveSession } from "./services/api";

const viewOptions = [
  { id: "patient", label: "Patient" },
  { id: "kiosk", label: "Kiosk" },
  { id: "staff", label: "Staff" },
  { id: "doctor", label: "Doctor" },
  { id: "admin", label: "Admin" }
];

function requiresAuth(view) {
  return ["staff", "doctor", "admin"].includes(view);
}

export default function App() {
  const { data, loading, error, refresh } = useHospitalData();
  const [activeView, setActiveView] = useState("patient");
  const [session, setSession] = useState(() => getStoredSession());
  const [authMode, setAuthMode] = useState("login");
  const [authError, setAuthError] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [selectedDoctorId, setSelectedDoctorId] = useState("");
  const [deploymentReadiness, setDeploymentReadiness] = useState(null);
  const [providerDiagnostics, setProviderDiagnostics] = useState(null);

  const currentUser = session?.user || null;
  const currentToken = session?.token || "";

  useEffect(() => {
    if (!session?.token) {
      return;
    }

    let cancelled = false;

    const validateSession = async () => {
      try {
        const result = await api.me(session.token);
        if (cancelled) return;
        const nextSession = { ...session, user: result.user };
        setSession(nextSession);
        saveSession(nextSession);
      } catch {
        if (cancelled) return;
        clearSession();
        setSession(null);
        setAuthError("Your previous session has expired. Please sign in again.");
      }
    };

    validateSession();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!data?.doctors?.length) {
      return;
    }
    if (currentUser?.role === "doctor" && currentUser.doctor_id) {
      setSelectedDoctorId(currentUser.doctor_id);
      return;
    }
    if (!selectedDoctorId) {
      setSelectedDoctorId(data.doctors[0].doctor_id);
    }
  }, [data, currentUser, selectedDoctorId]);

  useEffect(() => {
    if (activeView === "admin" && currentUser?.role === "admin") {
      loadAdminDiagnostics();
    }
  }, [activeView, currentUser?.role]);

  const selectedDoctor = useMemo(
    () => data?.doctors?.find((doctor) => doctor.doctor_id === selectedDoctorId) || data?.doctors?.[0] || null,
    [data, selectedDoctorId]
  );

  const doctorQueue = useMemo(() => {
    if (!data || !selectedDoctor) return [];
    return data.patients.filter(
      (patient) => patient.doctor_id === selectedDoctor.doctor_id && patient.visit_outcome !== "cancelled"
    );
  }, [data, selectedDoctor]);

  async function loadAdminDiagnostics() {
    if (!currentToken) return;
    try {
      const [readiness, diagnostics] = await Promise.all([
        api.getDeploymentReadiness(currentToken),
        api.getProviderDiagnostics(currentToken)
      ]);
      setDeploymentReadiness(readiness);
      setProviderDiagnostics(diagnostics);
    } catch (loadError) {
      setAuthError(loadError.message || "Unable to load admin diagnostics.");
    }
  }

  async function syncAfterMutation({ adminReload = false } = {}) {
    await refresh({ silent: true });
    if (adminReload && activeView === "admin" && currentUser?.role === "admin") {
      await loadAdminDiagnostics();
    }
  }

  async function handleLogin(credentials) {
    try {
      setAuthError("");
      setAuthMessage("");
      const result = await api.login(credentials);
      const nextSession = { token: result.token, user: result.user };
      saveSession(nextSession);
      setSession(nextSession);
      setActiveView(result.user.role);
      setAuthMode("login");
    } catch (loginError) {
      setAuthError(loginError.message || "Unable to sign in.");
    }
  }

  async function handleForgotPassword(username) {
    try {
      setAuthError("");
      const result = await api.forgotPassword(username);
      const preview = result.reset_token ? ` Reset token: ${result.reset_token}` : "";
      setAuthMessage(`${result.message}${preview}`);
    } catch (forgotError) {
      setAuthError(forgotError.message || "Unable to create reset token.");
    }
  }

  async function handleResetPassword(payload) {
    try {
      setAuthError("");
      const result = await api.resetPassword(payload);
      setAuthMessage(result.message || "Password updated successfully.");
      setAuthMode("login");
    } catch (resetError) {
      setAuthError(resetError.message || "Unable to reset password.");
    }
  }

  function handleLogout() {
    clearSession();
    setSession(null);
    setAuthMode("login");
    setAuthMessage("");
    setAuthError("");
  }

  async function handleRegister(payload) {
    const result = await api.registerPatient(payload);
    await syncAfterMutation();
    return result;
  }

  async function handleSendOtp(mobileNumber) {
    return api.sendOtp(mobileNumber);
  }

  async function handleVerifyOtp(mobileNumber, otp) {
    return api.verifyOtp(mobileNumber, otp);
  }

  async function handleTrack(query) {
    const result = await api.trackPatient(query);
    return result.patient;
  }

  async function handlePatientAction(patientId, action) {
    const result = await api.patientAction(patientId, action);
    await syncAfterMutation();
    return result.patient || result;
  }

  async function handleSelfCheckIn(checkInCode) {
    const result = await api.selfCheckIn(checkInCode);
    await syncAfterMutation();
    return result.patient;
  }

  async function handleDoctorAction(action, payload = {}) {
    if (!selectedDoctor) return null;
    let result = null;
    if (action === "complete") {
      result = await api.completeConsultation(selectedDoctor.doctor_id, currentToken);
    } else if (action === "call-next") {
      result = await api.callNext(selectedDoctor.doctor_id, currentToken);
    } else if (action === "no-show") {
      result = await api.markNoShow(selectedDoctor.doctor_id, currentToken, payload);
    } else if (action === "delay") {
      result = await api.updateDoctorStatus(selectedDoctor.doctor_id, currentToken, {
        status: selectedDoctor.status,
        delay_minutes: payload.delay_minutes || 0
      });
    } else if (action === "status") {
      result = await api.updateDoctorStatus(selectedDoctor.doctor_id, currentToken, {
        status: payload.status,
        delay_minutes: payload.delay_minutes || 0
      });
    } else if (action === "emergency") {
      result = await api.emergencyInsert(selectedDoctor.doctor_id, currentToken);
    }
    await syncAfterMutation();
    return result;
  }

  async function handleAdminRefresh() {
    await syncAfterMutation({ adminReload: true });
  }

  async function handleSimulateTick() {
    await api.simulateTick(currentToken);
    await syncAfterMutation({ adminReload: true });
  }

  async function handleDispatchNotifications() {
    await api.dispatchNotifications(currentToken, { force: true });
    await syncAfterMutation({ adminReload: true });
  }

  async function handleProviderTest(payload) {
    return api.providerTest(currentToken, payload);
  }

  const roleMismatch = requiresAuth(activeView) && currentUser?.role !== activeView;

  if (loading) {
    return (
      <main className="state-screen">
        <div className="state-card">
          <p className="eyebrow">Smart OPD</p>
          <h1>Loading hospital operations workspace...</h1>
        </div>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="state-screen">
        <div className="state-card error">
          <p className="eyebrow">System Error</p>
          <h1>{error || "Unable to load Smart OPD."}</h1>
        </div>
      </main>
    );
  }

  const renderProtectedView = () => {
    if (!currentUser || roleMismatch) {
      if (authMode === "forgot" || authMode === "reset") {
        return (
          <PasswordResetPanel
            mode={authMode}
            error={authError}
            message={authMessage}
            onBack={() => {
              setAuthMode("login");
              setAuthError("");
              setAuthMessage("");
            }}
            onForgotPassword={handleForgotPassword}
            onResetPassword={handleResetPassword}
          />
        );
      }

      return (
        <LoginPanel
          role={activeView}
          error={authError}
          message={authMessage}
          onLogin={handleLogin}
          onShowForgot={() => {
            setAuthMode("forgot");
            setAuthError("");
            setAuthMessage("");
          }}
          onShowReset={() => {
            setAuthMode("reset");
            setAuthError("");
            setAuthMessage("");
          }}
        />
      );
    }

    if (activeView === "doctor" && selectedDoctor) {
      return (
        <DoctorDashboard
          doctors={data.doctors}
          selectedDoctor={selectedDoctor}
          setSelectedDoctorId={setSelectedDoctorId}
          queue={doctorQueue}
          onDoctorAction={handleDoctorAction}
        />
      );
    }

    if (activeView === "staff") {
      return (
        <StaffDashboard
          data={data}
          currentUser={currentUser}
          onRefresh={() => syncAfterMutation()}
          onRegister={handleRegister}
          onSendOtp={handleSendOtp}
          onVerifyOtp={handleVerifyOtp}
          onTrack={handleTrack}
          onPatientAction={handlePatientAction}
          onSelfCheckIn={handleSelfCheckIn}
        />
      );
    }

    return (
      <AdminPanel
        data={data}
        deploymentReadiness={deploymentReadiness}
        providerDiagnostics={providerDiagnostics}
        onRefresh={handleAdminRefresh}
        onSimulateTick={handleSimulateTick}
        onDispatchNotifications={handleDispatchNotifications}
        onProviderTest={handleProviderTest}
      />
    );
  };

  return (
    <div className="hospital-app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Smart OPD Queue Management</p>
          <h1>Reduce waiting hall crowding with live queue guidance</h1>
        </div>
        <div className="topbar-side">
          <div className="view-switcher">
            {viewOptions.map((option) => (
              <button
                key={option.id}
                className={option.id === activeView ? "chip active" : "chip"}
                onClick={() => {
                  setActiveView(option.id);
                  setAuthError("");
                  setAuthMessage("");
                  setAuthMode("login");
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
          {currentUser ? (
            <div className="session-card">
              <span>{currentUser.name || currentUser.username}</span>
              <strong>{currentUser.role}</strong>
              <button className="secondary-button" onClick={handleLogout}>
                Sign Out
              </button>
            </div>
          ) : null}
        </div>
      </header>

      <section className="summary-strip">
        <div className="summary-card">
          <span>Active Queue</span>
          <strong>{data.summary.active_tokens}</strong>
        </div>
        <div className="summary-card">
          <span>Patients On Site</span>
          <strong>{data.summary.patients_on_site}</strong>
        </div>
        <div className="summary-card">
          <span>Checked In</span>
          <strong>{data.summary.checked_in_patients}</strong>
        </div>
        <div className="summary-card">
          <span>Average Wait</span>
          <strong>{data.summary.average_wait_minutes} min</strong>
        </div>
        <div className="summary-card">
          <span>Crowd Risk</span>
          <strong>{data.summary.crowd_risk_level}</strong>
        </div>
      </section>

      <main className="main-shell">
        {activeView === "patient" ? (
          <PatientInterface
            data={data}
            onRegister={handleRegister}
            onSendOtp={handleSendOtp}
            onVerifyOtp={handleVerifyOtp}
            onTrack={handleTrack}
            onPatientAction={handlePatientAction}
            onSelfCheckIn={handleSelfCheckIn}
          />
        ) : null}

        {activeView === "kiosk" ? <KioskPanel data={data} onSelfCheckIn={handleSelfCheckIn} /> : null}

        {requiresAuth(activeView) ? renderProtectedView() : null}
      </main>
    </div>
  );
}
