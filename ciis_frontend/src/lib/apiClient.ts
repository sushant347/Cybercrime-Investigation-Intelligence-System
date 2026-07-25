/**
 * Axios instance for the CIIS API.
 *
 * There are no user accounts and no JWT: investigators use the engine
 * anonymously. The one privileged surface is the **admin role**, unlocked with
 * a shared password; its signed token is kept in sessionStorage and sent as
 * `X-Admin-Token` on every request so admin endpoints authorise transparently.
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

const ADMIN_TOKEN_KEY = "ciis.admin";

export const adminToken = {
  get(): string | null {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
  },
  set(token: string): void {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
  },
  clear(): void {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  },
  get isPresent(): boolean {
    return !!sessionStorage.getItem(ADMIN_TOKEN_KEY);
  },
};

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api`,
  timeout: 60_000,
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = adminToken.get();
  if (token) config.headers["X-Admin-Token"] = token;
  return config;
});

apiClient.interceptors.response.use(undefined, (error: AxiosError) => {
  // An expired/invalid admin token should not leave the UI in a fake
  // "signed in" state — drop it so the admin page asks for the password again.
  if (error.response?.status === 403 && error.config?.url?.includes("/admin/")) {
    adminToken.clear();
  }
  return Promise.reject(error);
});

/** Human-friendly message for any API error (uniform error envelope). */
export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string } | undefined;
    if (data?.detail) return data.detail;
    if (error.response?.status === 403) return "Admin access required.";
    if (error.code === "ERR_NETWORK") return "Cannot reach the CIIS API server.";
  }
  return "Something went wrong. Please try again.";
}
