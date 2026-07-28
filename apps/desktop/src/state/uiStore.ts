import { create } from "zustand";

export type ThemeMode = "dark" | "light";

interface UiState {
  readonly themeMode: ThemeMode;
  readonly toggleTheme: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  themeMode: "dark",
  toggleTheme: () => {
    set((current) => ({
      themeMode: current.themeMode === "dark" ? "light" : "dark",
    }));
  },
}));
