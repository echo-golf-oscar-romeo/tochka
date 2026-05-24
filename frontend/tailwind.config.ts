import type { Config } from "tailwindcss";

// Tochka palette — Aino-leaning.
//
// One vivid blue is the single accent ("4657fa" is what Aino itself uses).
// Complementary highlight (warm amber) is reserved for emphasis / Beautify.
// Background is pure white, ink is near-black with a hint of slate.
// All other colors are neutral grays in the slate family.

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surface
        canvas:  "#ffffff",
        surface: "#fafbfc",
        border:  "#e7eaee",
        rule:    "#f3f4f7",
        // Text
        ink:     "#0b1020",   // near-black with a hint of slate-blue
        muted:   "#5c6470",
        subtle:  "#9097a3",
        // Single accent ramp — Aino electric blue
        accent: {
          50:  "#eef0ff",
          100: "#dbe0ff",
          200: "#b9c2ff",
          300: "#8b97ff",
          400: "#6772fa",
          500: "#4657fa",   // primary
          600: "#3344e0",
          700: "#2734b8",
          800: "#1f298f",
          900: "#171f63",
        },
        // Complementary warm — used sparingly for highlight states
        highlight: {
          50:  "#fff5e8",
          100: "#ffe6c4",
          500: "#f59e0b",
          600: "#d97706",
        },
        // Aliases so older code continues to compile
        paper: "#ffffff",
        warm:  "#4657fa",
        warn:  "#3344e0",
        good:  "#0b1020",
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        display: ['Instrument Serif', 'Georgia', 'serif'],
        serif:   ['Inter', 'system-ui', 'sans-serif'],
        mono:    ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        'xs':   ['0.75rem',   { lineHeight: '1rem' }],
        'sm':   ['0.875rem',  { lineHeight: '1.35rem' }],
        'base': ['0.9375rem', { lineHeight: '1.5rem' }],
        'lg':   ['1.0625rem', { lineHeight: '1.6rem' }],
        'xl':   ['1.25rem',   { lineHeight: '1.75rem' }],
        '2xl':  ['1.5rem',    { lineHeight: '2rem' }],
        '3xl':  ['1.875rem',  { lineHeight: '2.25rem' }],
        '4xl':  ['2.25rem',   { lineHeight: '2.5rem' }],
        '5xl':  ['3rem',      { lineHeight: '3.25rem' }],
      },
      maxWidth: {
        prose: "62ch",
      },
      letterSpacing: {
        tightish: "-0.01em",
      },
      boxShadow: {
        // softer than Tailwind defaults, more "paper"
        'panel': '0 1px 0 rgba(0,0,0,0.03), 0 0 0 1px rgba(11,16,32,0.06)',
        'soft':  '0 8px 24px -8px rgba(11,16,32,0.10), 0 2px 6px -2px rgba(11,16,32,0.06)',
        'card':  '0 1px 2px rgba(11,16,32,0.04), 0 1px 0 rgba(11,16,32,0.03), 0 0 0 1px rgba(11,16,32,0.04)',
        'pop':   '0 20px 50px -12px rgba(11,16,32,0.18), 0 6px 12px -6px rgba(11,16,32,0.08)',
      },
    },
  },
  plugins: [],
};

export default config;
