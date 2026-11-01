// The unfolded half of an "Als Nächstes" card: everything useful for sizing
// up a match beforehand. Server component; data comes from analyzeFixture().
import Link from "next/link";
import type { FixtureAnalysis, FormGame, SideAnalysis } from "@/lib/fixtureAnalysis";
import { fmtDate, fmtNum, fmtSigned, slugify } from "@/lib/format";
import { teamName } from "@/lib/teamColors";
import { teamCode } from "@/lib/teamCodes";
import { CompareBlock, type CmpRow } from "./CompareBlock";
import { TeamChip } from "./TeamChip";

const pct = (p: number) => `${fmtNum(p * 100, p < 0.01 && p > 0 ? 1 : 0)} %`;

function FormStrip({ s }: { s: SideAnalysis }) {
  if (!s.form.length) return <p className="muted fx-small">Noch keine Spiele.</p>;
  return (
    <>
      <div className="fx-form">
        {s.form.map((g: FormGame, i) => (
          <span
            key={i}
            className="fx-game"
            data-res={g.res}
            title={`${g.venue === "home" ? "Heim" : "Auswärts"} gegen ${teamName(g.opponent)} ${g.gf}:${g.ga} · xG ${fmtNum(g.xgf, 1)}:${fmtNum(g.xga, 1)}`}
          >
            <span className="fx-res">{g.res === "W" ? "S" : g.res === "D" ? "U" : "N"}</span>
            <span className="fx-opp">
              {g.venue === "away" ? "@" : ""}
              {teamCode(g.opponent)}
            </span>
            <span className="fx-score num">
              {g.gf}:{g.ga}
            </span>
            <span className="fx-xg num">
              {fmtNum(g.xgf, 1)}:{fmtNum(g.xga, 1)}
            </span>
          </span>
        ))}
      </div>
      <p className="muted fx-small num" style={{ margin: "0.4rem 0 0" }}>
        {s.formPts} Pkt (xPkt {fmtNum(s.formXpts, 1)}) · xG-Diff {fmtSigned(s.formXgDiff, 1)}
      </p>
    </>
  );
}

function Profile({ s }: { s: SideAnalysis }) {
  const r = s.row;
  return (
    <div className="fx-profile">
      <div className="fx-profile-head">
        <TeamChip team={s.team} variant="code-name" />
      </div>
      <dl className="fx-facts">
        <div>
          <dt>Platz</dt>
          <dd className="num">
            {s.rank}.{" "}
            <span className="muted">
              (xPkt-Rang {s.xRank}.)
            </span>
          </dd>
        </div>
        <div>
          <dt>Bilanz</dt>
          <dd className="num">
            {r.won}–{r.drawn}–{r.lost} · {r.goals_for}:{r.goals_against}
          </dd>
        </div>
        <div>
          <dt>Punkte / xPunkte</dt>
          <dd className="num">
            {r.points} / {fmtNum(r.xpoints, 1)}
          </dd>
        </div>
        {s.venue && (
          <div>
            <dt>{s.venue.label}spiele ({s.venue.games})</dt>
            <dd className="num">
              {fmtNum(s.venue.ppg, 1)} P/Sp · Tore {fmtNum(s.venue.gf, 1)}:{fmtNum(s.venue.ga, 1)} · xG {fmtNum(s.venue.xgf, 1)}:{fmtNum(s.venue.xga, 1)}
            </dd>
          </div>
        )}
        {s.sim && (
          <div>
            <dt>Saisonprognose</dt>
            <dd className="num">
              Titel {pct(s.sim.title)} · CL {pct(s.sim.cl)} · Abstieg {pct(s.sim.relegation)}
            </dd>
          </div>
        )}
      </dl>
      <div className="label" style={{ margin: "0.7rem 0 0.35rem" }}>Form (letzte {s.form.length})</div>
      <FormStrip s={s} />
    </div>
  );
}

export function FixtureDetail({ a }: { a: FixtureAnalysis }) {
  const { home: h, away: aw } = a;
  const rows: CmpRow[] = [
    {
      label: "Punkte pro Spiel",
      short: "Pkt/Sp",
      home: h.ppg,
      away: aw.ppg,
      homeText: fmtNum(h.ppg, 2),
      awayText: fmtNum(aw.ppg, 2),
    },
    {
      label: "xPunkte pro Spiel",
      short: "xPkt/Sp",
      home: h.xppg,
      away: aw.xppg,
      homeText: fmtNum(h.xppg, 2),
      awayText: fmtNum(aw.xppg, 2),
      info: "xpunkte",
    },
    {
      label: "xG pro Spiel",
      short: "xG",
      home: h.xgfPg,
      away: aw.xgfPg,
      homeText: fmtNum(h.xgfPg, 2),
      awayText: fmtNum(aw.xgfPg, 2),
      info: "xg",
    },
    {
      label: "xG zugelassen (niedriger = besser)",
      short: "xGA",
      home: h.xgaPg,
      away: aw.xgaPg,
      homeText: fmtNum(h.xgaPg, 2),
      awayText: fmtNum(aw.xgaPg, 2),
    },
  ];
  if (h.ppda !== null && aw.ppda !== null) {
    rows.push({
      label: "PPDA (niedriger = mehr Pressing)",
      short: "PPDA",
      home: h.ppda,
      away: aw.ppda,
      homeText: fmtNum(h.ppda, 1),
      awayText: fmtNum(aw.ppda, 1),
    });
  }
  if (h.deep !== null && aw.deep !== null) {
    rows.push({
      label: "Zuspiele in Tornähe",
      short: "Tornähe",
      home: h.deep,
      away: aw.deep,
      homeText: fmtNum(h.deep, 1),
      awayText: fmtNum(aw.deep, 1),
    });
  }

  return (
    <div className="fx-detail">
      {a.insights.length > 0 && (
        <section>
          <div className="label fx-label">Worauf achten</div>
          <ul className="fx-insights">
            {a.insights.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <div className="label fx-label">Chancenprofil</div>
        <div className="fx-expected">
          <span className="num">{fmtNum(a.expectedXg.home, 1)}</span>
          <span className="muted">xG-Erwartung</span>
          <span className="num">{fmtNum(a.expectedXg.away, 1)}</span>
        </div>
        <p className="muted fx-small" style={{ margin: "0.25rem 0 0", textAlign: "center" }}>
          Mittel aus eigenem Angriff und gegnerischer Abwehr — ein einfaches Profil, kein Modelltipp.
        </p>
      </section>

      <div className="fx-cmp">
        <CompareBlock home={h.team} away={aw.team} rows={rows} />
      </div>

      <section className="fx-profiles">
        <Profile s={h} />
        <Profile s={aw} />
      </section>

      {a.h2h && (
        <section>
          <div className="label fx-label">Direkter Vergleich</div>
          <p className="fx-small" style={{ margin: "0 0 0.5rem" }}>
            <span className="num">{a.h2h.record.home}</span> S ·{" "}
            <span className="num">{a.h2h.record.draw}</span> U ·{" "}
            <span className="num">{a.h2h.record.away}</span> N für {teamName(h.team)}
            <span className="muted"> ({a.h2h.record.played} Spiele)</span>
          </p>
          <ul className="fx-meetings">
            {a.h2h.meetings.map((m) => (
              <li key={m.match_id}>
                <Link href={`/spiel/${m.match_id}`} className="fx-meeting">
                  <span className="muted num">{fmtDate(m.date)}</span>
                  <span>
                    {teamName(m.home_team)}{" "}
                    <span className="num" style={{ fontWeight: 600 }}>
                      {m.home_goals}:{m.away_goals}
                    </span>{" "}
                    {teamName(m.away_team)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="fx-small" style={{ margin: 0, display: "flex", gap: "1rem", flexWrap: "wrap" }}>
        <Link href={`/team/${slugify(h.team)}`} style={{ color: "var(--accent)" }}>
          {teamName(h.team)} →
        </Link>
        <Link href={`/team/${slugify(aw.team)}`} style={{ color: "var(--accent)" }}>
          {teamName(aw.team)} →
        </Link>
        <Link href={`/vergleich/${slugify(h.team)}/${slugify(aw.team)}`} style={{ color: "var(--accent)" }}>
          Direktvergleich →
        </Link>
      </p>
    </div>
  );
}
