import Link from "next/link";
import { getManifest, getSeasonMatches } from "@/lib/data";
import { fmtDate, fmtNum, fmtTime } from "@/lib/format";

export const dynamicParams = false;

export function generateStaticParams() {
  const manifest = getManifest();
  const { matches } = getSeasonMatches(manifest.current_season);
  const mds = Array.from(new Set(matches.map((m) => m.matchday)));
  return mds.map((n) => ({ n: String(n) }));
}

export async function generateMetadata({ params }: { params: Promise<{ n: string }> }) {
  const { n } = await params;
  return { title: `Spieltag ${n} — Bundesliga Hub` };
}

export default async function SpieltagPage({ params }: { params: Promise<{ n: string }> }) {
  const { n: nRaw } = await params;
  const n = parseInt(nRaw, 10);
  const manifest = getManifest();
  const { matches } = getSeasonMatches(manifest.current_season);
  const list = matches.filter((m) => m.matchday === n).sort((a, b) => a.date.localeCompare(b.date));

  return (
    <>
      <h1 style={{ fontSize: "1.4rem", marginBottom: "1rem" }}>Spieltag {n}</h1>
      <div className="surface table-scroll">
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Begegnung</th>
              <th>Ergebnis</th>
              <th>xG</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {list.map((m) => (
              <tr key={m.match_id}>
                <td>
                  {fmtDate(m.date)}
                  {m.time ? ` ${fmtTime(m.time)}` : ""}
                </td>
                <td style={{ textAlign: "left" }}>
                  {m.home} – {m.away}
                </td>
                <td className="num">
                  {m.home_goals}:{m.away_goals}
                </td>
                <td className="num">
                  {fmtNum(m.home_xg)} : {fmtNum(m.away_xg)}
                </td>
                <td>
                  <Link href={`/spiel/${m.match_id}`} style={{ color: "var(--accent)" }}>
                    Bericht
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
