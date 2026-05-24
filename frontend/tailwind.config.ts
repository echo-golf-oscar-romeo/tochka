import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Aino-inspired palette. Soft, paperish; data layers carry the colour weight.
        paper: "#f6f4ef",
        ink: "#1a1a1a",
        muted: "#6b6760",
        accent: "#0f5ea8",
        warm: "#e07a5f",
        warn: "#c44536",
        good: "#3a7d44",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        serif: ["Source Serif Pro", "Georgia", "serif"],
      },
      maxWidth: {
        prose: "62ch",
      },
    },
  },
  plugins: [],
};

export default config;
