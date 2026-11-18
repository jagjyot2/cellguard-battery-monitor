import type {
  AlarmLogRow,
  AlarmThresholds,
  CalibrationCalcRequest,
  CalibrationCalcResponse,
  DatasetMeta,
  HealthResponse,
  SessionInfo,
  TelemetrySample,
} from "./types";

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export const api = {
  getHealth: (): Promise<HealthResponse> => requestJson("/api/health"),

  getSessions: (): Promise<{
    active_session_id: string;
    sessions: SessionInfo[];
    datasets: DatasetMeta[];
  }> => requestJson("/api/sessions"),

  replayDataset: (dataset_id: string): Promise<{ session_id: string; title: string; sample_count: number }> =>
    requestJson("/api/sessions/replay", {
      method: "POST",
      body: JSON.stringify({ dataset_id }),
    }),

  getHistory: (
    session_id?: string,
    limit = 1000
  ): Promise<{
    session_id: string;
    session: SessionInfo | null;
    count: number;
    samples: TelemetrySample[];
  }> => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (session_id) q.set("session_id", session_id);
    return requestJson(`/api/telemetry/history?${q.toString()}`);
  },

  getAlarms: (session_id?: string): Promise<{ session_id: string; alarms: AlarmLogRow[] }> => {
    const q = session_id ? `?session_id=${encodeURIComponent(session_id)}` : "";
    return requestJson(`/api/alarms${q}`);
  },

  ackAlarms: (session_id?: string): Promise<{ acknowledged_count: number }> => {
    const q = session_id ? `?session_id=${encodeURIComponent(session_id)}` : "";
    return requestJson(`/api/alarms/ack${q}`, { method: "POST" });
  },

  getThresholds: (): Promise<AlarmThresholds> => requestJson("/api/thresholds"),

  updateThresholds: (thresholds: AlarmThresholds): Promise<{ status: string; thresholds: AlarmThresholds }> =>
    requestJson("/api/thresholds", {
      method: "PUT",
      body: JSON.stringify(thresholds),
    }),

  calculateCalibration: (payload: CalibrationCalcRequest): Promise<CalibrationCalcResponse> =>
    requestJson("/api/calibration/calculate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getCsvExportUrl: (session_id?: string): string =>
    session_id ? `/api/export/csv?session_id=${encodeURIComponent(session_id)}` : "/api/export/csv",
};
