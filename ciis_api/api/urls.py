from django.urls import path

from .views import (
    admin,
    audit,
    cases,
    dashboard,
    evidence,
    intake,
    investigation,
    maintenance,
    notifications,
    reports,
    system,
)

urlpatterns = [
    # Intake (no auth: case reference -> hashed case id)
    path("intake/", intake.IntakeView.as_view()),
    path("intake/resolve/", intake.IntakeResolveView.as_view()),
    # Cases.
    # NOTE: the case *list* and *dashboard* endpoints are intentionally absent.
    # Cases are private to whoever knows the reference, so nothing enumerates
    # them; every route below addresses one already-known case id.
    path("cases/<str:case_id>/", cases.CaseDetailView.as_view()),
    path("cases/<str:case_id>/archive/", cases.CaseArchiveView.as_view()),
    path("cases/<str:case_id>/history/", cases.CaseHistoryView.as_view()),
    # Evidence
    path("cases/<str:case_id>/evidence/", evidence.EvidenceListView.as_view()),
    path("cases/<str:case_id>/evidence/upload/", evidence.EvidenceUploadView.as_view()),
    path("cases/<str:case_id>/evidence/url/", evidence.EvidenceUrlView.as_view()),
    path("cases/<str:case_id>/evidence/<str:evidence_id>/", evidence.EvidenceDetailView.as_view()),
    path(
        "cases/<str:case_id>/evidence/<str:evidence_id>/download/",
        evidence.EvidenceDownloadView.as_view(),
    ),
    path("jobs/", evidence.JobListView.as_view()),
    path("jobs/<int:job_id>/", evidence.JobStatusView.as_view()),
    # Investigation (Phase-2 artifacts)
    path("cases/<str:case_id>/artifacts/", investigation.ArtifactIndexView.as_view()),
    path("cases/<str:case_id>/artifacts/<str:key>/", investigation.ArtifactView.as_view()),
    path("cases/<str:case_id>/analyze/", investigation.RunAnalysisView.as_view()),
    # Reports
    path("cases/<str:case_id>/reports/", reports.ReportListView.as_view()),
    path("cases/<str:case_id>/reports/latest/", reports.ReportLatestView.as_view()),
    path(
        "cases/<str:case_id>/reports/<str:file_name>/download/",
        reports.ReportDownloadView.as_view(),
    ),
    # Engine configuration (read-only)
    path("settings/", system.SystemSettingsView.as_view()),
    # Testing maintenance: clear all cases and entities.
    path("maintenance/reset/", maintenance.ResetView.as_view()),
    # Admin role (shared password): view every case, delete a case.
    path("admin/login/", admin.AdminLoginView.as_view()),
    path("admin/session/", admin.AdminSessionView.as_view()),
    path("admin/cases/", admin.AdminCaseListView.as_view()),
    path("admin/cases/<str:case_id>/", admin.AdminCaseDeleteView.as_view()),
    # Operational surface: cross-case dashboard, unified audit trail, and
    # engine-wide notifications (written by the workers, now also served).
    path("dashboard/", dashboard.DashboardView.as_view()),
    path("audit/", audit.AuditLogView.as_view()),
    path("notifications/", notifications.NotificationListView.as_view()),
    path("notifications/mark-read/", notifications.NotificationMarkReadView.as_view()),
]
