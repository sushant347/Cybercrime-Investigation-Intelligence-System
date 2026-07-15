import { CssBaseline, ThemeProvider } from "@mui/material";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { buildTheme } from "./theme";

interface ColorModeContextValue {
  mode: "dark" | "light";
  toggle: () => void;
  setMode: (mode: "dark" | "light") => void;
}

const ColorModeContext = createContext<ColorModeContextValue | null>(null);

const STORAGE_KEY = "ciis.theme";

export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<"dark" | "light">(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "light" ? "light" : "dark";
  });

  const setMode = useCallback((next: "dark" | "light") => {
    localStorage.setItem(STORAGE_KEY, next);
    setModeState(next);
  }, []);

  const toggle = useCallback(
    () => setMode(mode === "dark" ? "light" : "dark"),
    [mode, setMode],
  );

  const theme = useMemo(() => buildTheme(mode), [mode]);
  const value = useMemo(() => ({ mode, toggle, setMode }), [mode, toggle, setMode]);

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export function useColorMode(): ColorModeContextValue {
  const ctx = useContext(ColorModeContext);
  if (!ctx) throw new Error("useColorMode must be used within ColorModeProvider");
  return ctx;
}
