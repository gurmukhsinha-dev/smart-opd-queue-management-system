const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";

export const EVENTS_URL = `${API_BASE}/events/stream`;

const SESSION_KEY = "smart-opd-session";

function buildHeaders(token, customHeaders = {}) {
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...customHeaders
  };
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: buildHeaders(options.token, options.headers),
    ...options
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ message: "Request failed" }));
    throw new Error(payload.message || "Request failed");
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export function saveSession(session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function getStoredSession() {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

export const api = {
  getBootstrap: () => request("/bootstrap"),
  login: (credentials) =>
    request("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials)
    }),
  me: (token) => request("/auth/me", { token }),
  forgotPassword: (username) =>
    request("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ username })
    }),
  resetPassword: (payload) =>
    request("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  sendOtp: (mobile_number) =>
    request("/patients/otp/send", {
      method: "POST",
      body: JSON.stringify({ mobile_number })
    }),
  verifyOtp: (mobile_number, otp) =>
    request("/patients/otp/verify", {
      method: "POST",
      body: JSON.stringify({ mobile_number, otp })
    }),
  registerPatient: (payload) =>
    request("/patients/register", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  trackPatient: (query) => request(`/patients/track?q=${encodeURIComponent(query)}`),
  patientAction: (patientId, action) =>
    request(`/patients/${patientId}/action`, {
      method: "POST",
      body: JSON.stringify({ action })
    }),
  selfCheckIn: (check_in_code) =>
    request("/patients/check-in", {
      method: "POST",
      body: JSON.stringify({ check_in_code })
    }),
  completeConsultation: (doctorId, token) =>
    request(`/doctors/${doctorId}/complete`, {
      method: "POST",
      token
    }),
  callNext: (doctorId, token) =>
    request(`/doctors/${doctorId}/call-next`, {
      method: "POST",
      token
    }),
  markNoShow: (doctorId, token, payload) =>
    request(`/doctors/${doctorId}/mark-no-show`, {
      method: "POST",
      token,
      body: JSON.stringify(payload || {})
    }),
  emergencyInsert: (doctorId, token) =>
    request(`/doctors/${doctorId}/emergency-insert`, {
      method: "POST",
      token
    }),
  updateDoctorStatus: (doctorId, token, payload) =>
    request(`/doctors/${doctorId}/status`, {
      method: "POST",
      token,
      body: JSON.stringify(payload)
    }),
  getDeploymentReadiness: (token) =>
    request("/admin/deployment-readiness", { token }),
  getProviderDiagnostics: (token) =>
    request("/admin/provider-diagnostics", { token }),
  dispatchNotifications: (token, payload = {}) =>
    request("/admin/notifications/dispatch", {
      method: "POST",
      token,
      body: JSON.stringify(payload)
    }),
  simulateTick: (token) =>
    request("/admin/simulate-tick", {
      method: "POST",
      token
    }),
  providerTest: (token, payload) =>
    request("/admin/provider-test", {
      method: "POST",
      token,
      body: JSON.stringify(payload)
    }),
  getUsers: (token) => request("/admin/users", { token })
};
