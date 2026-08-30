import { getManifest, getPlayerIndex } from "@/lib/data";
import { PlayerLeaderboard } from "@/components/PlayerLeaderboard";

export const metadata = { title: "Spieler — Bundesliga Hub" };

export default function SpielerPage() {
  const season = getManifest().current_season;
  const { players } = getPlayerIndex(season);

  if (!players.length) {
    return (
      <>
        <h1 style={{ fontSize: "1.4rem" }}>Spieler</h1>
        <p className="muted">
          Für diese Saison liegen noch keine Aufstellungsdaten vor.
        </p>
      </>
    );
  }

  return (
    <>
      <h1 style={{ fontSize: "1.4rem", marginBottom: "1rem" }}>Spieler</h1>
      <PlayerLeaderboard players={players} season={season} />
    </>
  );
}
