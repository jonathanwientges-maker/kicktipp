import Link from "next/link";
import { getManifest, getSeasonMatches } from "@/lib/data";
import { fmtDate, fmtNum, fmtTime } from "@/lib/format";
import { teamColor, teamName } from "@/lib/teamColors";

export const dynamicParams = false;

export function generateStaticParams() {
  const manifest = getManifest();
  const { matches } = getSeasonMatches(manifest.current_season);
  const mds = Array.from(new Set(matches.map((m) => m.round)));
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
  const list = matches.filter((m) => m.round === n).sort((a, b) => a.date.localeCompare(b.date));

  return (
    <>
      <h1 style={{ marginBottom: "1.5rem" }}>
        <span className="display-l num" style={{ marginRight: "0.4rem" }}>{n}.</span>
        Spieltag
      </h1>
      <div className="surface table-scroll">
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Begegnung</th>
              <th className="num">Ergebnis</th>
              <th className="num">xG</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {list.map((m) => (
              <tr key={m.match_id}>
                <td className="num muted">
                  {fmtDate(m.date)}
                  {m.time ? ` ${fmtTime(m.time)}` : ""}
                </td>
                <td>
                  <span className="team-cell">
                    <span className="team-bar" style={{ ["--tc" as any]: teamColor(m.home).color }} />
                    {teamName(m.home)} <span className="muted">–</span> {teamName(m.away)}
                  </span>
                </td>
                <td className="num" style={{ fontWeight: 700 }}>
                  {m.home_goals}:{m.away_goals}
                </td>
                <td className="num">
                  {fmtNum(m.home_xg)} : {fmtNum(m.away_xg)}
                </td>
                <td>
                  <Link href={`/spiel/${m.match_id}`} className="nav-link" style={{ borderBottom: "none" }}>
                    Bericht →
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
