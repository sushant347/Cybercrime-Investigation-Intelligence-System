import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

import { queryClient } from "@/app/queryClient";
import { router } from "@/app/router";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { AuthProvider } from "@/features/auth/AuthContext";
import { ColorModeProvider } from "@/theme/ColorModeProvider";

export default function App() {
  return (
    <ColorModeProvider>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </QueryClientProvider>
      </ErrorBoundary>
    </ColorModeProvider>
  );
}
