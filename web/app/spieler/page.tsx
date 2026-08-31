import { getManifest, getPlayerIndex } from "@/lib/data";
import { PlayerLeaderboard } from "@/components/PlayerLeaderboard";

export const metadata = { title: "Spieler — Bundesliga Hub" };

export default function SpielerPage() {
  const season = getManifest().current_season;
  const { players } = getPlayerIndex(season);

  if (!players.length) {
    return (
      <>
        <h1>Spieler</h1>
        <p className="muted">Für diese Saison liegen noch keine Aufstellungsdaten vor.</p>
      </>
    );
  }

  return (
    <>
      <p className="label" style={{ marginBottom: "0.4rem" }}>
        Saison {season}/{String((season + 1) % 100).padStart(2, "0")}
      </p>
      <h1 style={{ marginBottom: "1.5rem" }}>Spieler</h1>
      <PlayerLeaderboard players={players} season={season} />
    </>
  );
}
