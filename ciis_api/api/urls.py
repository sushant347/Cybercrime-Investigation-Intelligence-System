from django.urls import path

from .views import (
    audit,
    cases,
    dashboard,
    evidence,
    intake,
    investigation,
    notifications,
    reports,
    system,
)

urlpatterns = [
    path("dashboard/", dashboard.DashboardView.as_view()),
    # Intake (no auth: case reference -> hashed case id)
    path("intake/", intake.IntakeView.as_view()),
    path("intake/resolve/", intake.IntakeResolveView.as_view()),
    # Cases
    path("cases/", cases.CaseListCreateView.as_view()),
    path("cases/<str:case_id>/", cases.CaseDetailView.as_view()),
    path("cases/<str:case_id>/archive/", cases.CaseArchiveView.as_view()),
    path("cases/<str:case_id>/history/", cases.CaseHistoryView.as_view()),
    # Evidence
    path("cases/<str:case_id>/evidence/", evidence.EvidenceListView.as_view()),
    path("cases/<str:case_id>/evidence/upload/", evidence.EvidenceUploadView.as_view()),
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
    # Audit, notifications, settings
    path("audit/", audit.AuditLogView.as_view()),
    path("notifications/", notifications.NotificationListView.as_view()),
    path("notifications/mark-read/", notifications.NotificationMarkReadView.as_view()),
    path("settings/", system.SystemSettingsView.as_view()),
]
