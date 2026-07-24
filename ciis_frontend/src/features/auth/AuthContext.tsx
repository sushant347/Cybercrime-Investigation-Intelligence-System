/**
 * Engine session.
 *
 * This is a case-centric evidence processing engine, not a multi-user case
 * management system: there are no accounts, no login, and no RBAC. A case is
 * reached by its *reference* (hashed into a case id) rather than by an
 * identity.
 *
 * `hasPermission` is retained as a documented no-op so feature components keep
 * declaring which capability they represent - mirroring `require()` on the API
 * side (`accounts/permissions.py`). Restoring access control means restoring
 * both.
 */
import { createContext, useContext, useMemo, type ReactNode } from "react";

interface SessionValue {
  /** Always true - access control is not enforced in engine mode. */
  hasPermission: (permission: string) => boolean;
}

const SessionContext = createContext<SessionValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const value = useMemo<SessionValue>(() => ({ hasPermission: () => true }), []);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useAuth(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
