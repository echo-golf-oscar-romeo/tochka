import type { Config } from "tailwindcss";

// Tochka palette.
// Pure white surfaces, near-black text, one accent — a deep slate-blue —
// expressed as a 50/200/500/700/900 scale so we can pick shades without
// reaching for new hues.

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
        canvas:   "#ffffff",
        surface:  "#fafafa",
        border:   "#e5e7eb",
        rule:     "#f1f5f9",
        // Text
        ink:      "#0a0a0a",
        muted:    "#6b7280",
        subtle:   "#9ca3af",
        // Single accent ramp (slate-blue)
        accent: {
          50:  "#eff4ff",
          100: "#dbe4ff",
          200: "#b9c8ff",
          300: "#8aa4ff",
          400: "#5b7eff",
          500: "#2f55e6",   // primary
          600: "#1f3fbf",
          700: "#1a319a",
          800: "#172a7a",
          900: "#121f56",
        },
        // Semantic colors kept neutral to stay on-brand.
        warn:   "#1f3fbf",   // map "under" anomalies — uses accent 600 for cohesion
        good:   "#0a0a0a",   // not a color: just dark for emphasis
        // Old names kept as aliases so unmigrated components still work.
        paper:  "#ffffff",
        warm:   "#2f55e6",
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        serif: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        // tighter, more editorial scale
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.35rem' }],
        'base': ['0.9375rem', { lineHeight: '1.5rem' }],
        'lg': ['1.0625rem', { lineHeight: '1.6rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
      },
      maxWidth: {
        prose: "62ch",
      },
      letterSpacing: {
        tightish: "-0.01em",
      },
      boxShadow: {
        'panel': '0 1px 0 rgba(0,0,0,0.04), 0 0 0 1px rgba(0,0,0,0.06)',
        'soft': '0 4px 14px rgba(15,23,42,0.06)',
      },
    },
  },
  plugins: [],
};

export default config;
