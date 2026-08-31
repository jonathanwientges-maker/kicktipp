import { Section } from "@/components/Section";

export const metadata = { title: "Methodik — Bundesliga Hub" };

function Term({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "1.25rem" }}>
      <div className="label" style={{ marginBottom: "0.3rem" }}>{name}</div>
      <p style={{ margin: 0 }}>{children}</p>
    </div>
  );
}

export default function MethodikPage() {
  return (
    <div style={{ maxWidth: 680 }}>
      <h1 style={{ marginBottom: "0.35rem" }}>Methodik</h1>
      <p className="muted" style={{ marginTop: 0, marginBottom: "2rem", fontSize: "var(--fs-small)" }}>
        Was die Kennzahlen bedeuten und wie sie berechnet werden.
      </p>

      <Section title="Kennzahlen zu Torchancen">
        <Term name="xG — Expected Goals">
          xG schätzt für jeden Torschuss die Wahrscheinlichkeit, dass er zum Tor führt — aus
          Schussposition, Winkel zum Tor, Situation (offenes Spiel, Ecke, Konter …) und Art des
          Abschlusses (Fuß, Kopf). Ein Schuss mit xG 0,25 wird im Schnitt jedes vierte Mal ein Tor.
          Die xG-Summe eines Teams ist die Toranzahl, die ein Durchschnittsteam aus genau diesen
          Chancen erzielt hätte.
        </Term>
        <Term name="npxG — Non-Penalty xG">
          npxG ist xG ohne Elfmeter. Ein Elfmeter hat immer denselben festen Wert (rund 0,76) und
          verrät nichts über die Chancenerarbeitung aus dem Spiel heraus. npxG misst nur, wie
          gefährlich ein Team ohne Strafstöße war — es ist das ehrlichere Maß für die Spielanlage.
        </Term>
        <Term name="Großchancen">
          Schüsse mit einem xG-Wert über 0,3 — also Gelegenheiten, die im Schnitt häufiger als jede
          dritte zum Tor werden.
        </Term>
        <Term name="Standard / offenes Spiel">
          Aufteilung der xG danach, wie die Chance entstand: aus dem laufenden Spiel, nach einem
          ruhenden Ball (Ecke, direkter oder indirekter Freistoß) oder per Elfmeter.
        </Term>
        <Term name="xG-Verlauf">
          Der xG-Verlauf im Spielbericht summiert die npxG beider Teams Minute für Minute auf. Ein
          steiler Abschnitt ist eine Drangphase; die Punkte auf den Linien markieren Tore. Wer am
          Ende oben liegt, hatte die besseren Chancen — unabhängig vom tatsächlichen Ergebnis.
        </Term>
        <Term name="Schusskarte">
          Zeigt jeden Abschluss an seiner Position auf dem Feld. Die Punktgröße entspricht dem
          xG-Wert (größer = bessere Chance). Ausgefüllt mit hellem Ring = Tor, blass = kein Tor.
        </Term>
      </Section>

      <Section title="xPunkte und Glücksfaktor">
        <Term name="xPunkte — Expected Points">
          Die Punkte, die ein Team im Schnitt für seine Chancenqualität geholt hätte. Aus den
          Einzelwahrscheinlichkeiten aller Schüsse wird per exakter Faltung die Verteilung der
          möglichen Toranzahl je Team bestimmt, daraus die Wahrscheinlichkeit für Sieg,
          Unentschieden und Niederlage — und daraus der Erwartungswert der Ligapunkte (3 / 1 / 0).
          Diese Seite berechnet das für jede Saison selbst und übernimmt bewusst nicht Understats
          xPTS-Spalte, die nur für ältere Spielzeiten vorliegt. So ist der Wert über alle zwölf
          Spielzeiten identisch definiert.
        </Term>
        <Term name="Glücksfaktor">
          Tatsächliche Punkte minus xPunkte. Ein Plus heißt: das Team hat mehr Punkte geholt, als
          seine Chancen hergaben — durch überdurchschnittliche Verwertung, gehaltene Elfmeter oder
          späte Tore. Ein Minus heißt das Gegenteil. Große Abweichungen gleichen sich über eine
          Saison meist aus, weil Chancenverwertung stärker schwankt als Spielkontrolle; genau
          darauf weist die <em>Regressionswarnung</em> auf der Tabellenseite hin (Teams mit einem
          Betrag über 5).
        </Term>
        <Term name="xG-Tabelle / xG-Differenz">
          Dieselbe Tabelle, aber sortiert nach erzielten xG bzw. nach der Differenz aus erzielten
          und zugelassenen xG statt nach echten Toren — sie zeigt, wo ein Team stünde, wenn jede
          Chance exakt ihren Erwartungswert eingebracht hätte.
        </Term>
      </Section>

      <Section title="Pressing und Feldkontrolle">
        <Term name="PPDA — Passes Allowed per Defensive Action">
          Wie viele gegnerische Pässe ein Team in dessen Spielhälfte zulässt, bevor es selbst
          verteidigend eingreift (Tackling, Foul, abgefangener Pass, Zweikampf). Ein niedriger Wert
          bedeutet aggressives, hohes Pressing; ein hoher Wert passives, tiefes Verteidigen.
        </Term>
        <Term name="Zuspiele in Tornähe — Deep Completions">
          Die Zahl der angekommenen Pässe eines Teams innerhalb von rund 20 Metern vor dem
          gegnerischen Tor — ein Maß dafür, wie oft ein Team die gefährliche Zone überhaupt
          erreicht.
        </Term>
        <Term name="Diese Felder fehlen manchmal">
          PPDA und Zuspiele in Tornähe stammen aus einem optionalen Datenblock von Understat, der
          nicht für jede Saison bereitsteht. Wo er fehlt, werden die entsprechenden Panels
          ausgeblendet; der Rest der Seite bleibt vollständig.
        </Term>
      </Section>

      <Section title="Formkurven">
        <Term name="Rollender xG-Schnitt">
          Mittelwert der letzten bis zu 8 Spiele für erzielte und zugelassene xG, getrennt nach
          Heim- und Auswärtsspielen. Glättet einzelne Ausreißer und zeigt den Formtrend. Zu Beginn
          einer Saison mit erst einem Spiel wird stattdessen der Einzelwert genannt.
        </Term>
      </Section>

      <Section title="Das Modell">
        <Term name="Modell-Tabelle">
          Jeder vom Modell abgegebene Ergebnis-Tipp wird als Resultat genommen und daraus eine
          Tabelle gerechnet. Der Vergleich mit der echten Tabelle zeigt, wo das Modell die Realität
          über- oder unterschätzt hat. Es geht ausschließlich um die Frage „wie gut hat das Modell
          die Realität getroffen“ — nicht um Tipprunden oder einzelne Tipper.
        </Term>
        <Term name="Trefferquote und 2:1-Basis">
          Kicktipp-Wertung je Tipp: exakt getroffenes Ergebnis 4 Punkte, richtige Tordifferenz 3,
          nur richtige Tendenz 2, sonst 0. Als Vergleich dient der Dauer-Tipp „immer 2:1“.
        </Term>
        <Term name="Saisonsimulation">
          Für jedes ausstehende Spiel werden aus den Dixon-Coles-Stärken (Angriff, Abwehr,
          Heimvorteil) Tor-Erwartungswerte je Mannschaft berechnet und die Tore als unabhängige
          Poisson-Ziehungen 10.000-mal simuliert. Aus den Endtabellen ergeben sich die gezeigten
          Platzierungswahrscheinlichkeiten. Diese Simulation nutzt ausschließlich die
          Dixon-Coles-Bewertung, keine Wettquoten.
        </Term>
      </Section>

      <Section title="Datenquellen">
        <p style={{ margin: 0 }}>
          Schuss- und xG-Daten sowie Aufstellungen stammen von <strong>Understat</strong>.
          Anstoßzeiten kommen von <strong>football-data.co.uk</strong> und werden von britischer auf
          mitteleuropäische Zeit umgerechnet; die von Understat gelieferten Uhrzeiten sind zwischen
          den Spielzeiten nicht konsistent und werden daher nicht angezeigt. Fehlt die Anstoßzeit
          ganz, steht nur das Datum.
        </p>
      </Section>
    </div>
  );
}
