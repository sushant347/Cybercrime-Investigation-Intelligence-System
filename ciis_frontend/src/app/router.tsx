import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { AppLayout } from "@/components/layout/AppLayout";

const IntakePage = lazy(() => import("@/features/intake/IntakePage"));
const DashboardPage = lazy(() => import("@/features/dashboard/DashboardPage"));
const CasesPage = lazy(() => import("@/features/cases/CasesPage"));
const CaseDetailPage = lazy(() => import("@/features/cases/CaseDetailPage"));
const EvidenceDetailPage = lazy(() => import("@/features/evidence/EvidenceDetailPage"));
const AuditPage = lazy(() => import("@/features/audit/AuditPage"));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage"));
const NotificationsPage = lazy(() => import("@/features/notifications/NotificationsPage"));

// No authentication and no route guards: this is a case-centric engine, not a
// multi-user system. A case is reached by its reference, not by an identity.
const wrap = (node: ReactNode) => <Suspense fallback={<DetailSkeleton />}>{node}</Suspense>;

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: wrap(<IntakePage />) },
      { path: "/dashboard", element: wrap(<DashboardPage />) },
      { path: "/cases", element: wrap(<CasesPage />) },
      { path: "/cases/:caseId", element: wrap(<CaseDetailPage />) },
      { path: "/cases/:caseId/:tab", element: wrap(<CaseDetailPage />) },
      {
        path: "/cases/:caseId/evidence/:evidenceId",
        element: wrap(<EvidenceDetailPage />),
      },
      { path: "/audit", element: wrap(<AuditPage />) },
      { path: "/settings", element: wrap(<SettingsPage />) },
      { path: "/notifications", element: wrap(<NotificationsPage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
