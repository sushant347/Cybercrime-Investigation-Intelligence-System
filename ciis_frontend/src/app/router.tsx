import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { AppLayout } from "@/components/layout/AppLayout";

const StartPage = lazy(() => import("@/features/intake/StartPage"));
const NewCasePage = lazy(() => import("@/features/intake/NewCasePage"));
const OpenCasePage = lazy(() => import("@/features/intake/OpenCasePage"));
const CaseDetailPage = lazy(() => import("@/features/cases/CaseDetailPage"));
const EvidenceDetailPage = lazy(() => import("@/features/evidence/EvidenceDetailPage"));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage"));
const AdminPage = lazy(() => import("@/features/admin/AdminPage"));

// A guided, one-screen-at-a-time flow: choose -> identify the case -> work on
// it. There is no case list, dashboard, or cross-case view anywhere, so one
// case never exposes another. No authentication: this is an engine.
const wrap = (node: ReactNode) => <Suspense fallback={<DetailSkeleton />}>{node}</Suspense>;

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: wrap(<StartPage />) },
      { path: "/new", element: wrap(<NewCasePage />) },
      { path: "/open", element: wrap(<OpenCasePage />) },
      { path: "/cases/:caseId", element: wrap(<CaseDetailPage />) },
      { path: "/cases/:caseId/:tab", element: wrap(<CaseDetailPage />) },
      {
        path: "/cases/:caseId/evidence/:evidenceId",
        element: wrap(<EvidenceDetailPage />),
      },
      { path: "/settings", element: wrap(<SettingsPage />) },
      { path: "/admin", element: wrap(<AdminPage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
