import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { AppLayout } from "@/components/layout/AppLayout";
import { RequireAuth } from "@/features/auth/RequireAuth";

const LoginPage = lazy(() => import("@/features/auth/LoginPage"));
const DashboardPage = lazy(() => import("@/features/dashboard/DashboardPage"));
const CasesPage = lazy(() => import("@/features/cases/CasesPage"));
const CaseDetailPage = lazy(() => import("@/features/cases/CaseDetailPage"));
const EvidenceDetailPage = lazy(() => import("@/features/evidence/EvidenceDetailPage"));
const AuditPage = lazy(() => import("@/features/audit/AuditPage"));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage"));
const NotificationsPage = lazy(() => import("@/features/notifications/NotificationsPage"));
const UsersPage = lazy(() => import("@/features/users/UsersPage"));

const wrap = (node: ReactNode, permission?: string) => (
  <RequireAuth permission={permission}>
    <Suspense fallback={<DetailSkeleton />}>{node}</Suspense>
  </RequireAuth>
);

export const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <Suspense fallback={null}>
        <LoginPage />
      </Suspense>
    ),
  },
  {
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { path: "/", element: wrap(<DashboardPage />, "case.view") },
      { path: "/cases", element: wrap(<CasesPage />, "case.view") },
      { path: "/cases/:caseId", element: wrap(<CaseDetailPage />, "case.view") },
      { path: "/cases/:caseId/:tab", element: wrap(<CaseDetailPage />, "case.view") },
      {
        path: "/cases/:caseId/evidence/:evidenceId",
        element: wrap(<EvidenceDetailPage />, "evidence.view"),
      },
      { path: "/audit", element: wrap(<AuditPage />, "audit.view") },
      { path: "/settings", element: wrap(<SettingsPage />, "settings.view") },
      { path: "/notifications", element: wrap(<NotificationsPage />) },
      { path: "/admin/users", element: wrap(<UsersPage />, "user.manage") },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
