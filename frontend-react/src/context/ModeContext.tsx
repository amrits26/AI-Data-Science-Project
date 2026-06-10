import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

export type AppMode = "customer" | "salesperson"

type ModeContextValue = {
  mode: AppMode
  setMode: (nextMode: AppMode) => void
  isSalespersonMode: boolean
}

const MODE_STORAGE_KEY = "imperial-ui-mode"

const ModeContext = createContext<ModeContextValue | undefined>(undefined)

function getInitialMode(): AppMode {
  if (typeof window === "undefined") {
    return "customer"
  }

  const savedMode = window.localStorage.getItem(MODE_STORAGE_KEY)
  return savedMode === "salesperson" ? "salesperson" : "customer"
}

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<AppMode>(getInitialMode)

  useEffect(() => {
    window.localStorage.setItem(MODE_STORAGE_KEY, mode)
  }, [mode])

  const value = useMemo(
    () => ({
      mode,
      setMode,
      isSalespersonMode: mode === "salesperson",
    }),
    [mode]
  )

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>
}

export function useMode(): ModeContextValue {
  const context = useContext(ModeContext)
  if (!context) {
    throw new Error("useMode must be used within a ModeProvider")
  }

  return context
}
