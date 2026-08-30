import { Section } from "@/components/Section";

export const metadata = { title: "Methodik — Bundesliga Hub" };

export default function MethodikPage() {
  return (
    <>
      <h1 style={{ fontSize: "1.4rem", marginBottom: "1rem" }}>Methodik</h1>

      <Section title="xG und npxG">
        <p>
          <strong>xG</strong> (expected goals) schätzt für jeden Torschuss die Wahrscheinlichkeit,
          dass er zu einem Tor führt — aus Schussposition, Situation und Art des Abschlusses.
          Die Summe der xG-Werte eines Teams ist die Zahl der Tore, die ein durchschnittliches
          Team aus diesen Chancen erzielt hätte. <strong>npxG</strong> (non-penalty xG) lässt
          Elfmeter weg, weil deren fester Wert von rund 0,76 die Chancenqualität aus dem Spiel
          heraus verzerrt.
        </p>
        <p className="muted">
          Liegen die Tore deutlich über den xG, war die Chancenverwertung überdurchschnittlich —
          das schwankt von Spiel zu Spiel stark und gleicht sich über eine Saison meist aus.
        </p>
      </Section>

      <Section title="xPunkte">
        <p>
          Die <strong>xPunkte</strong> auf dieser Seite werden für jede Saison gleich berechnet:
          per exakter Faltung über die Einzelwahrscheinlichkeiten aller Schüsse. Daraus ergibt sich
          die Verteilung der möglichen Toranzahl je Team, daraus die Wahrscheinlichkeit für Sieg,
          Unentschieden und Niederlage und daraus der Erwartungswert der Punkte.
        </p>
        <p className="muted">
          Wir übernehmen bewusst nicht die xPTS-Spalte von Understat: diese liegt nur für ältere
          Spielzeiten vor, sodass eine gemischte Datenbasis entstünde. Die eigene Berechnung ist
          über alle zwölf Spielzeiten identisch.
        </p>
      </Section>

      <Section title="Datenquellen">
        <p>
          Schuss- und xG-Daten stammen von <strong>Understat</strong>. Anstoßzeiten kommen von{" "}
          <strong>football-data.co.uk</strong> und werden von britischer auf mitteleuropäische Zeit
          umgerechnet; die von Understat gelieferten Uhrzeiten sind zwischen den Spielzeiten nicht
          konsistent und werden daher nicht angezeigt.
        </p>
      </Section>

      <Section title="Saisonsimulation">
        <p>
          Für die ausstehenden Spiele werden aus den <strong>Dixon-Coles-Stärken</strong>
          (Angriff, Abwehr, Heimvorteil) Tor-Erwartungswerte je Mannschaft berechnet und die Tore
          als unabhängige Poisson-Ziehungen simuliert — <strong>10.000 Durchläufe</strong>. Aus den
          Endtabellen ergeben sich die gezeigten Platzierungswahrscheinlichkeiten. Diese Simulation
          nutzt ausschließlich die Dixon-Coles-Bewertung, keine Wettquoten.
        </p>
      </Section>
    </>
  );
}
