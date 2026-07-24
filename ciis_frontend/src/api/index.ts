/**
 * API layer - every backend call the platform makes, typed end-to-end.
 * UI components never call axios directly.
 */
import { apiClient } from "@/lib/apiClient";
import type {
  AppNotification,
  ArtifactAvailability,
  ArtifactDocument,
  AuditEntry,
  BackgroundJob,
  CaseAnalytics,
  CaseDetail,
  CaseHistoryEntry,
  CasePriority,
  CaseSummary,
  CampaignAnalysis,
  CorrelationAnalysis,
  DashboardData,
  EvidenceDetail,
  EvidenceRow,
  GraphStatistics,
  GraphSummary,
  InvestigationReport,
  LoginResponse,
  Paginated,
  RegisteredCase,
  RelationshipGraph,
  ReportFile,
  SuspectAssessment,
  SystemSettings,
  TimelineAnalysis,
  User,
  UserPreference,
} from "@/types";

type Query = Record<string, string | number | boolean | undefined>;

// ------------------------------------------------------------------- auth
export const authApi = {
  login: (username: string, password: string) =>
    apiClient
      .post<LoginResponse>("/auth/login/", { username, password })
      .then((r) => r.data),
  logout: (refresh: string | null) =>
    apiClient.post("/auth/logout/", { refresh }).then(() => undefined),
  me: () => apiClient.get<User>("/auth/me/").then((r) => r.data),
  updatePreferences: (patch: Partial<UserPreference>) =>
    apiClient.patch<UserPreference>("/auth/me/preferences/", patch).then((r) => r.data),
  listUsers: (params?: Query) =>
    apiClient.get<Paginated<User>>("/auth/users/", { params }).then((r) => r.data),
  createUser: (payload: Record<string, unknown>) =>
    apiClient.post<User>("/auth/users/", payload).then((r) => r.data),
  updateUser: (id: number, patch: Record<string, unknown>) =>
    apiClient.patch<User>(`/auth/users/${id}/`, patch).then((r) => r.data),
  permissionMatrix: () =>
    apiClient
      .get<{
        matrix: Record<string, string[]>;
        available_permissions: { code: string; label: string }[];
      }>("/auth/permissions/")
      .then((r) => r.data),
  savePermissions: (role: string, permissions: string[]) =>
    apiClient
      .put("/auth/permissions/", {
        role,
        entries: permissions.map((permission) => ({ role, permission })),
      })
      .then((r) => r.data),
};

// -------------------------------------------------------------- dashboard
export const dashboardApi = {
  get: () => apiClient.get<DashboardData>("/dashboard/").then((r) => r.data),
};

// ------------------------------------------------------------------ cases
export const casesApi = {
  list: (params?: Query) =>
    apiClient.get<Paginated<CaseSummary>>("/cases/", { params }).then((r) => r.data),
  detail: (caseId: string) =>
    apiClient.get<CaseDetail>(`/cases/${caseId}/`).then((r) => r.data),
  create: (payload: { title: string; description?: string; notes?: string; tags?: string[] }) =>
    apiClient.post<CaseSummary>("/cases/", payload).then((r) => r.data),
  update: (caseId: string, patch: Record<string, unknown>) =>
    apiClient.patch<CaseDetail>(`/cases/${caseId}/`, patch).then((r) => r.data),
  archive: (caseId: string, unarchive = false) =>
    apiClient.post(`/cases/${caseId}/archive/`, { unarchive }).then((r) => r.data),
  history: (caseId: string, params?: Query) =>
    apiClient
      .get<Paginated<CaseHistoryEntry>>(`/cases/${caseId}/history/`, { params })
      .then((r) => r.data),
};

// --------------------------------------------------------------- evidence
export const evidenceApi = {
  list: (caseId: string, params?: Query) =>
    apiClient
      .get<Paginated<EvidenceRow>>(`/cases/${caseId}/evidence/`, { params })
      .then((r) => r.data),
  detail: (caseId: string, evidenceId: string) =>
    apiClient
      .get<EvidenceDetail>(`/cases/${caseId}/evidence/${evidenceId}/`)
      .then((r) => r.data),
  upload: (caseId: string, file: File, notes: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("notes", notes);
    return apiClient
      .post<BackgroundJob>(`/cases/${caseId}/evidence/upload/`, form)
      .then((r) => r.data);
  },
  downloadUrl: (caseId: string, evidenceId: string, preview = false) =>
    `${apiClient.defaults.baseURL}/cases/${caseId}/evidence/${evidenceId}/download/${preview ? "?preview=1" : ""}`,
  downloadBlob: (caseId: string, evidenceId: string, preview = false) =>
    apiClient
      .get<Blob>(`/cases/${caseId}/evidence/${evidenceId}/download/`, {
        params: preview ? { preview: 1 } : undefined,
        responseType: "blob",
      })
      .then((r) => r.data),
  jobs: (params?: Query) =>
    apiClient.get<Paginated<BackgroundJob>>("/jobs/", { params }).then((r) => r.data),
  job: (jobId: number) =>
    apiClient.get<BackgroundJob>(`/jobs/${jobId}/`).then((r) => r.data),
};

// ---------------------------------------------- investigation (Phase 2)
export const investigationApi = {
  availability: (caseId: string) =>
    apiClient
      .get<ArtifactAvailability>(`/cases/${caseId}/artifacts/`)
      .then((r) => r.data),
  correlation: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<CorrelationAnalysis>>(`/cases/${caseId}/artifacts/correlation/`)
      .then((r) => r.data),
  graph: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<RelationshipGraph>>(`/cases/${caseId}/artifacts/graph/`)
      .then((r) => r.data),
  graphStatistics: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<GraphStatistics>>(`/cases/${caseId}/artifacts/graph_statistics/`)
      .then((r) => r.data),
  graphSummary: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<GraphSummary>>(`/cases/${caseId}/artifacts/graph_summary/`)
      .then((r) => r.data),
  campaigns: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<CampaignAnalysis>>(`/cases/${caseId}/artifacts/campaigns/`)
      .then((r) => r.data),
  suspects: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<SuspectAssessment>>(`/cases/${caseId}/artifacts/suspects/`)
      .then((r) => r.data),
  timeline: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<TimelineAnalysis>>(`/cases/${caseId}/artifacts/timeline/`)
      .then((r) => r.data),
  analytics: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<CaseAnalytics>>(`/cases/${caseId}/artifacts/analytics/`)
      .then((r) => r.data),
  priority: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<CasePriority>>(`/cases/${caseId}/artifacts/priority/`)
      .then((r) => r.data),
  runAnalysis: (caseId: string) =>
    apiClient.post<BackgroundJob>(`/cases/${caseId}/analyze/`).then((r) => r.data),
};

// ----------------------------------------------------------------- intake
// There is deliberately no "list cases" call: cases are private to whoever
// knows the reference, and the API does not expose the registry.
export const intakeApi = {
  /** Open a case by reference, creating it on first use. */
  open: (reference: string, title = "") =>
    apiClient
      .post<RegisteredCase>("/intake/", { reference, title })
      .then((r) => r.data),
  /** Check whether a reference already maps to a case (creates nothing). */
  resolve: (reference: string) =>
    apiClient
      .get<{ case_id: string; exists: boolean; case: RegisteredCase | null }>(
        "/intake/resolve/",
        { params: { reference } },
      )
      .then((r) => r.data),
};

// ---------------------------------------------------------------- reports
export const reportsApi = {
  list: (caseId: string) =>
    apiClient
      .get<{ case_id: string; reports: ReportFile[] }>(`/cases/${caseId}/reports/`)
      .then((r) => r.data),
  latest: (caseId: string) =>
    apiClient
      .get<ArtifactDocument<InvestigationReport>>(`/cases/${caseId}/reports/latest/`)
      .then((r) => r.data),
  previewMarkdown: (caseId: string, fileName: string) =>
    apiClient
      .get<string>(`/cases/${caseId}/reports/${fileName}/download/`, {
        params: { preview: 1 },
        responseType: "text",
      })
      .then((r) => r.data),
  downloadBlob: (caseId: string, fileName: string) =>
    apiClient
      .get<Blob>(`/cases/${caseId}/reports/${fileName}/download/`, { responseType: "blob" })
      .then((r) => r.data),
};

// ------------------------------------------------------------------ audit
export const auditApi = {
  list: (params?: Query) =>
    apiClient.get<Paginated<AuditEntry>>("/audit/", { params }).then((r) => r.data),
};

// ---------------------------------------------------------- notifications
export const notificationsApi = {
  list: (params?: Query) =>
    apiClient
      .get<Paginated<AppNotification>>("/notifications/", { params })
      .then((r) => r.data),
  markRead: (ids?: number[]) =>
    apiClient.post("/notifications/mark-read/", { ids }).then((r) => r.data),
};

// --------------------------------------------------------------- settings
export const settingsApi = {
  get: () => apiClient.get<SystemSettings>("/settings/").then((r) => r.data),
};
