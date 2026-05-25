import "./globals.css";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "tochka — location intelligence",
  description: "Upload your network. The agent decides the methodology. Read the storymap.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
