import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { getManifest } from "@/lib/data";
import { ServiceWorker } from "@/components/ServiceWorker";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

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
    icon: "/icons/icon-192.png",
    apple: "/icons/icon-192.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#0B0F14",
  width: "device-width",
  initialScale: 1,
};

const NAV: { href: string; label: string }[] = [
  { href: "/", label: "Start" },
  { href: "/tabelle", label: "Tabelle" },
  { href: "/team", label: "Teams" },
  { href: "/spieler", label: "Spieler" },
  { href: "/modell", label: "Modell" },
  { href: "/simulation", label: "Simulation" },
  { href: "/rekorde", label: "Rekorde" },
  { href: "/methodik", label: "Methodik" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  let generatedAt = "";
  try {
    generatedAt = getManifest().generated_at;
  } catch {
    /* manifest not exported yet */
  }
  return (
    <html lang="de" className={inter.variable}>
      <body>
        <ServiceWorker />
        <header
          style={{ borderBottom: "1px solid var(--border)", background: "var(--surface)" }}
        >
          <div
            className="container-page"
            style={{ display: "flex", alignItems: "center", gap: "1.25rem", height: 56, flexWrap: "wrap" }}
          >
            <Link href="/" style={{ fontWeight: 700, letterSpacing: "-0.01em" }}>
              Bundesliga&nbsp;Hub
            </Link>
            <nav style={{ display: "flex", gap: "0.9rem", flexWrap: "wrap" }}>
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} className="muted" style={{ fontSize: "0.92rem" }}>
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="container-page" style={{ padding: "1.5rem 1rem 4rem" }}>
          {children}
        </main>
        <footer className="container-page" style={{ padding: "2rem 1rem", fontSize: "0.8rem" }}>
          <p className="muted">
            Daten: Understat (xG, Schüsse) &amp; football-data.co.uk (Anstoßzeiten).
            {generatedAt ? ` Stand: ${generatedAt}.` : ""}
          </p>
        </footer>
      </body>
    </html>
  );
}
