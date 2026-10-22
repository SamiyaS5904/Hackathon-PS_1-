import type { Config } from "tailwindcss";

const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  // `dark:` follows the device unless the user picked a theme (html[data-theme]).
  darkMode: ["variant", [
    "&:is([data-theme=dark] *)",
    "@media (prefers-color-scheme: dark) { &:not([data-theme=light] *) }",
  ]],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        "surface-2": token("surface-2"),
        border: token("border"),
        "border-strong": token("border-strong"),
        text: token("text"),
        muted: token("muted"),
        accent: token("accent"),
        "accent-soft": token("accent-soft"),
        "accent-text": token("accent-text"),
        ok: token("ok"),
        "ok-soft": token("ok-soft"),
        warn: token("warn"),
        "warn-soft": token("warn-soft"),
        danger: token("danger"),
        "danger-soft": token("danger-soft"),
      },
      borderRadius: { DEFAULT: "8px" },
      fontFamily: { mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"] },
    },
  },
  plugins: [],
} satisfies Config;
