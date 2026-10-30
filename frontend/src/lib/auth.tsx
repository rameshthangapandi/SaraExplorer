import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, authPost, refreshSession, setAccessToken, setSessionLostHandler, type User } from "./api";

type AuthResponse = { access_token: string; user: User };

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<void>;
  register: (data: { name: string; email: string; phone?: string; password: string; remember: boolean }) => Promise<void>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  setUser: (u: User) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore the session silently from the refresh cookie: no login prompt while the session is alive.
  useEffect(() => {
    setSessionLostHandler(() => {
      setAccessToken(null);
      setUser(null);
    });
    refreshSession().then((u) => {
      setUser(u);
      setLoading(false);
    });
  }, []);

  // Keep the short-lived access token fresh while the tab is open.
  useEffect(() => {
    if (!user) return;
    const id = setInterval(() => {
      refreshSession().then((u) => {
        if (!u) setUser(null);
      });
    }, 12 * 60 * 1000);
    return () => clearInterval(id);
  }, [user]);

  const accept = useCallback((data: AuthResponse) => {
    setAccessToken(data.access_token);
    setUser(data.user);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      setUser,
      login: async (email, password, remember) => accept(await authPost<AuthResponse>("/api/auth/login", { email, password, remember })),
      register: async (data) => accept(await authPost<AuthResponse>("/api/auth/register", data)),
      logout: async () => {
        try {
          await authPost("/api/auth/logout");
        } finally {
          setAccessToken(null);
          setUser(null);
        }
      },
      logoutAll: async () => {
        try {
          await api("/api/auth/logout-all", { method: "POST" });
        } finally {
          setAccessToken(null);
          setUser(null);
        }
      },
    }),
    [user, loading, accept],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
