// src/state/UIContext.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Global UI state — spec Section 5.1.
// Fields: language, role, activeView exactly as specified.
// No selectedNC, no selectedConcord — those are editor-local state.
// No localStorage — prohibited by Section 1 and Section 8.
// ─────────────────────────────────────────────────────────────────────────────
import { createContext, useContext, useState, useCallback } from "react";

const UIContext = createContext(null);

export function UIProvider({ children }) {
  // ── Three fields exactly as Section 5.1 ──────────────────────────────────
  const [language,   setLanguage] = useState("chitonga");
  const [role,       setRole]     = useState("teacher");   // "teacher" | "student"
  const [activeView, setView]     = useState("nc");        // sidebar tab key

  // ── Toast notification (not in spec but needed for UX; no localStorage) ──
  const [toast, setToast] = useState(null);
  const showToast = useCallback((msg, type = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2800);
  }, []);

  // ── Drag state for upload screen ─────────────────────────────────────────
  const [drag, setDrag] = useState(false);

  const value = {
    language,   setLanguage,
    role,       setRole,
    activeView, setView,
    toast,      showToast,
    drag,       setDrag,
  };

  return (
    <UIContext.Provider value={value}>
      {children}
    </UIContext.Provider>
  );
}

export const useUI = () => {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error("useUI must be used inside <UIProvider>");
  return ctx;
};
