import type { Config } from "tailwindcss";

// tochka palette — round 5
//
// One vivid purple is the single accent (#4F35F8). Secondary warning red
// (#FB3640). Off-black ink (#0A0903), near-white canvas (#FDFDFD).
// An 8-colour layer palette is exposed under `theme.colors.layer.*` so
// new analysis or chat layers can rotate through a saturated rainbow
// without re-using the primary purple (which is reserved for the brand
// + the user's own network).

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
        canvas:  "#FDFDFD",
        surface: "#f6f6f5",
        border:  "#e7e6e2",
        rule:    "#f0efeb",
        // Text
        ink:     "#0A0903",       // off-black
        muted:   "#5c5b56",
        subtle:  "#9a9890",
        // Single accent ramp — tochka electric purple
        accent: {
          50:  "#efecff",
          100: "#dcd6ff",
          200: "#beb2ff",
          300: "#9986ff",
          400: "#7560fb",
          500: "#4F35F8",         // primary
          600: "#3f24e0",
          700: "#321bb8",
          800: "#27158f",
          900: "#1c0f66",
        },
        // Secondary — warning red for emphasis / cannibalisation / anomalies
        highlight: {
          50:  "#ffeaeb",
          100: "#ffcccf",
          500: "#FB3640",
          600: "#d92129",
        },
        // 8-colour rotating palette for non-primary data layers (chat
        // results, per-archetype outputs, classified categories). Frontend
        // code picks by `LAYER_PALETTE[i % 8]`.
        layer: {
          0: "#FAD037",           // yellow
          1: "#FB3640",           // red (also = highlight.500)
          2: "#FA37B2",           // pink
          3: "#C637FA",           // purple-magenta
          4: "#37B2FA",           // sky blue
          5: "#37FADD",           // mint
          6: "#37FA7E",           // green
          7: "#FA8237",           // orange
        },
        // Aliases so older code continues to compile
        paper: "#FDFDFD",
        warm:  "#4F35F8",
        warn:  "#FB3640",
        good:  "#0A0903",
      },
      fontFamily: {
        sans:  ['Inter', 'system-ui', 'sans-serif'],
        serif: ['Inter', 'system-ui', 'sans-serif'],
        mono:  ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
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
        'panel': '0 1px 0 rgba(10,9,3,0.03), 0 0 0 1px rgba(10,9,3,0.06)',
        'soft':  '0 8px 24px -8px rgba(10,9,3,0.10), 0 2px 6px -2px rgba(10,9,3,0.06)',
        'card':  '0 1px 2px rgba(10,9,3,0.04), 0 1px 0 rgba(10,9,3,0.03), 0 0 0 1px rgba(10,9,3,0.05)',
        'pop':   '0 20px 50px -12px rgba(10,9,3,0.18), 0 6px 12px -6px rgba(10,9,3,0.08)',
        'glass': '0 8px 28px -10px rgba(10,9,3,0.22), 0 1px 0 rgba(255,255,255,0.6) inset, 0 0 0 1px rgba(10,9,3,0.06)',
      },
      backdropBlur: {
        'glass': '14px',
      },
    },
  },
  plugins: [],
};

export default config;
