/**
 * Axios instance with JWT auth and automatic token refresh.
 * All API access flows through this single client (API-layer rule).
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

const TOKEN_KEY = "ciis.access";
const REFRESH_KEY = "ciis.refresh";

export const tokenStore = {
  get access(): string | null {
    return sessionStorage.getItem(TOKEN_KEY);
  },
  get refresh(): string | null {
    return sessionStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string): void {
    sessionStorage.setItem(TOKEN_KEY, access);
    if (refresh) sessionStorage.setItem(REFRESH_KEY, refresh);
  },
  clear(): void {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
  },
};

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api`,
  timeout: 60_000,
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refresh = tokenStore.refresh;
  if (!refresh) throw new Error("No refresh token");
  const { data } = await axios.post<{ access: string; refresh?: string }>(
    `${BASE_URL}/api/auth/refresh/`,
    { refresh },
  );
  tokenStore.set(data.access, data.refresh);
  return data.access;
}

apiClient.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config as
    | (InternalAxiosRequestConfig & { _retried?: boolean })
    | undefined;
  if (
    error.response?.status === 401 &&
    original &&
    !original._retried &&
    tokenStore.refresh &&
    !original.url?.includes("/auth/")
  ) {
    original._retried = true;
    try {
      refreshing = refreshing ?? refreshAccessToken();
      const access = await refreshing;
      refreshing = null;
      original.headers.Authorization = `Bearer ${access}`;
      return apiClient(original);
    } catch {
      refreshing = null;
      tokenStore.clear();
      window.location.assign("/login");
    }
  }
  return Promise.reject(error);
});

/** Human-friendly message for any API error (uniform error envelope). */
export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string } | undefined;
    if (data?.detail) return data.detail;
    if (error.response?.status === 403) return "You do not have permission to do this.";
    if (error.code === "ERR_NETWORK") return "Cannot reach the CIIS API server.";
  }
  return "Something went wrong. Please try again.";
}
