import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { getManifest } from "@/lib/data";
import { ServiceWorker } from "@/components/ServiceWorker";
import { NavBar } from "@/components/NavBar";

const display = localFont({
  src: [
    { path: "./fonts/archivo-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "./fonts/archivo-latin-600-normal.woff2", weight: "600", style: "normal" },
    { path: "./fonts/archivo-latin-700-normal.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-display",
  display: "swap",
});

const body = localFont({
  src: [
    { path: "./fonts/public-sans-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "./fonts/public-sans-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "./fonts/public-sans-latin-600-normal.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Bundesliga Hub",
  description: "xG, xPunkte und Modell-Analysen zur Bundesliga",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "BL Hub",
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.jpg", sizes: "192x192", type: "image/jpeg" },
      { url: "/icons/icon-512.jpg", sizes: "512x512", type: "image/jpeg" },
    ],
    apple: { url: "/icons/apple-touch-icon.jpg", sizes: "180x180", type: "image/jpeg" },
  },
};

export const viewport: Viewport = {
  themeColor: "#0D0E11",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  let generatedAt = "";
  try {
    generatedAt = getManifest().generated_at;
  } catch {
    /* manifest not exported yet */
  }
  return (
    <html lang="de" className={`${display.variable} ${body.variable}`}>
      <body>
        <ServiceWorker />
        <div className="noise-overlay" aria-hidden="true" />
        <NavBar />
        <main
          className="container-page"
          style={{
            padding: "1.75rem 1rem 4rem",
            paddingBottom: "calc(4rem + env(safe-area-inset-bottom))",
            position: "relative",
            zIndex: 2,
          }}
        >
          {children}
        </main>
        <footer
          className="container-page"
          style={{ padding: "2rem 1rem", fontSize: "var(--fs-small)", position: "relative", zIndex: 2 }}
        >
          <p className="muted">
            Daten: Understat (xG, Schüsse) &amp; football-data.co.uk (Anstoßzeiten).
            {generatedAt ? ` Stand: ${generatedAt}.` : ""}
          </p>
        </footer>
      </body>
    </html>
  );
}
