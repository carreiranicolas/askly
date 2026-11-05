/* ============================================================
   ASKLY — Theme controller
   Handles toggling between light/dark and persisting the choice
   in localStorage. The initial theme is applied by an inline
   script in <head> (base.html) to avoid a flash of the wrong
   theme (FOUC); this file only wires up the toggle controls and
   keeps things in sync.
   ============================================================ */
(() => {
  "use strict";

  const STORAGE_KEY = "askly-theme";
  const root = document.documentElement;

  /** Read the stored preference, falling back to system setting. */
  function storedTheme() {
    try {
      const value = window.localStorage.getItem(STORAGE_KEY);
      if (value === "light" || value === "dark") return value;
    } catch (e) {
      /* localStorage may be unavailable (private mode) — ignore */
    }
    return null;
  }

  function systemTheme() {
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function currentTheme() {
    return root.dataset.theme === "dark" ? "dark" : "light";
  }

  /** Apply a theme to the document and update toggle a11y state. */
  function applyTheme(theme) {
    const normalized = theme === "dark" ? "dark" : "light";
    root.dataset.theme = normalized;
    syncControls(normalized);
  }

  function persistTheme(theme) {
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      /* ignore persistence failures */
    }
  }

  function syncControls(theme) {
    const controls = document.querySelectorAll("[data-theme-toggle]");
    const isDark = theme === "dark";
    const label = isDark ? "Ativar tema claro" : "Ativar tema escuro";
    controls.forEach((el) => {
      el.setAttribute("aria-pressed", String(isDark));
      el.setAttribute("aria-label", label);
      el.setAttribute("title", label);
    });
  }

  function toggleTheme() {
    const next = currentTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
    persistTheme(next);
  }

  function bindControls() {
    document.querySelectorAll("[data-theme-toggle]").forEach((el) => {
      if (el.dataset.themeToggleBound === "1") return;
      el.dataset.themeToggleBound = "1";
      el.addEventListener("click", (e) => {
        e.preventDefault();
        toggleTheme();
      });
    });
    syncControls(currentTheme());
  }

  // Follow system changes only while the user hasn't picked explicitly.
  if (window.matchMedia) {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e) => {
      if (storedTheme()) return; // explicit choice wins
      applyTheme(e.matches ? "dark" : "light");
    };
    if (media.addEventListener) {
      media.addEventListener("change", onChange);
    } else if (media.addListener) {
      media.addListener(onChange);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindControls);
  } else {
    bindControls();
  }

  // Expose a tiny API for debugging / other scripts.
  window.AsklyTheme = {
    get: currentTheme,
    set: (t) => {
      applyTheme(t);
      persistTheme(t);
    },
    toggle: toggleTheme,
  };
})();
