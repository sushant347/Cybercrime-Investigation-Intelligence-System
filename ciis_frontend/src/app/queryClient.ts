import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error: unknown) => {
        const status = (error as { response?: { status?: number } })?.response?.status;
        // Never retry auth/permission failures or missing artifacts.
        if (status === 401 || status === 403 || status === 404 || status === 503) {
          return false;
        }
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
  },
});
