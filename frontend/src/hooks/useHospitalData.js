import { useEffect, useState } from "react";
import { api, EVENTS_URL } from "../services/api";

export function useHospitalData() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = async (options = {}) => {
    try {
      if (!options.silent) setLoading(true);
      setError("");
      const payload = await api.getBootstrap();
      setData(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      if (!options.silent) setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const source = new EventSource(EVENTS_URL);

    const handleRefresh = () => refresh({ silent: true });

    source.addEventListener("state_updated", handleRefresh);
    source.addEventListener("connected", handleRefresh);
    source.onerror = () => {
      refresh({ silent: true });
    };

    return () => {
      source.close();
    };
  }, []);

  return {
    data,
    loading,
    error,
    refresh,
    setData
  };
}
