import type { ReactNode } from "react";

// One place for every metric explanation. Keys are stable slugs; the
// Explainer component and the Methodik page both read from here so the
// wording never drifts.
export const GLOSSARY: Record<string, ReactNode> = {
  xg: (
    <>
      <strong>xG (expected goals)</strong> schätzt für jeden Torschuss die Wahrscheinlichkeit, dass
      er zum Tor führt — aus Position, Winkel, Situation und Art des Abschlusses. Die xG-Summe eines
      Teams ist die Toranzahl, die ein Durchschnittsteam aus genau diesen Chancen erzielt hätte.
    </>
  ),
  npxg: (
    <>
      <strong>npxG (non-penalty xG)</strong> ist xG ohne Elfmeter. Ein Elfmeter hat immer denselben
      festen Wert (~0,76) und sagt nichts über die Chancenerarbeitung aus dem Spiel heraus aus —
      npxG misst nur, wie gefährlich ein Team ohne Strafstöße war.
    </>
  ),
  xpunkte: (
    <>
      <strong>xPunkte</strong> sind die Punkte, die ein Team im Schnitt für seine Chancenqualität
      geholt hätte. Aus den Einzelwahrscheinlichkeiten aller Schüsse wird per exakter Faltung die
      Verteilung der möglichen Toranzahl je Team berechnet, daraus die Wahrscheinlichkeit für Sieg,
      Unentschieden und Niederlage — und daraus der Punkt-Erwartungswert. Diese Seite rechnet das
      für jede Saison selbst, statt Understats xPTS zu übernehmen (das gibt es nur für ältere
      Spielzeiten).
    </>
  ),
  gluecksfaktor: (
    <>
      <strong>Glücksfaktor</strong> = tatsächliche Punkte − xPunkte. Positiv heißt: das Team hat
      mehr Punkte geholt, als seine Chancen hergaben (starke Verwertung, gehaltene Elfmeter,
      späte Tore). Negativ heißt das Gegenteil. Über eine Saison gleicht sich das meist aus —
      Chancenverwertung schwankt stärker als Spielkontrolle.
    </>
  ),
  grosschancen: (
    <>
      <strong>Großchancen</strong> sind Schüsse mit einem xG-Wert über 0,3 — also Gelegenheiten,
      die im Schnitt jede dritte Mal ein Tor werden.
    </>
  ),
  ppda: (
    <>
      <strong>PPDA (passes allowed per defensive action)</strong> misst Pressing-Intensität: wie
      viele gegnerische Pässe ein Team in dessen Spielhälfte zulässt, bevor es selbst verteidigend
      eingreift (Tackling, Foul, Abfangen). <em>Niedrig = aggressives, hohes Pressing;
      hoch = passives, tiefes Verteidigen.</em>
    </>
  ),
  deep: (
    <>
      <strong>Zuspiele in Tornähe</strong> (deep completions) zählt die angekommenen Pässe eines
      Teams innerhalb von ~20 Metern vor dem gegnerischen Tor — ein Maß dafür, wie oft ein Team
      die gefährliche Zone überhaupt erreicht.
    </>
  ),
  xgtabelle: (
    <>
      <strong>xG-Tabelle</strong> sortiert nach erzielten xG statt nach echten Toren — sie zeigt,
      wo ein Team stünde, wenn jede Chance exakt ihren Erwartungswert eingebracht hätte.
    </>
  ),
  xarace: (
    <>
      Der <strong>xG-Verlauf</strong> summiert die npxG beider Teams Minute für Minute auf. Ein
      steiler Anstieg = eine Drangphase; die Punkte markieren Tore. Wer am Ende oben liegt, hatte
      die besseren Chancen — unabhängig vom Ergebnis.
    </>
  ),
  schusskarte: (
    <>
      Die <strong>Schusskarte</strong> zeigt jeden Abschluss an seiner Position. Punktgröße =
      xG-Wert (größer = bessere Chance). Ausgefüllt mit Ring = Tor, blass = kein Tor.
    </>
  ),
  standardanteil: (
    <>
      <strong>Standard / offenes Spiel</strong> teilt die xG danach auf, ob die Chance aus dem
      laufenden Spiel, nach einem ruhenden Ball (Ecke, Freistoß) oder per Elfmeter entstand.
    </>
  ),
  rollingxg: (
    <>
      Der <strong>rollende xG-Schnitt</strong> mittelt die letzten bis zu 8 Spiele — er glättet
      Ausreißer und zeigt den Formtrend bei erzielten und zugelassenen Chancen. Aussagekräftig
      erst ab einigen gespielten Partien.
    </>
  ),
  modelltabelle: (
    <>
      Die <strong>Modell-Tabelle</strong> nimmt jeden abgegebenen Modell-Tipp als Ergebnis und
      rechnet daraus eine Tabelle. Der Vergleich mit der echten Tabelle zeigt, wo das Modell die
      Realität über- oder unterschätzt hat.
    </>
  ),
  simulation: (
    <>
      Für jedes ausstehende Spiel werden aus den <strong>Dixon-Coles-Stärken</strong> (Angriff,
      Abwehr, Heimvorteil) Tor-Erwartungswerte berechnet und die Tore als unabhängige
      Poisson-Ziehungen 10.000-mal simuliert. Aus den Endtabellen ergeben sich die gezeigten
      Wahrscheinlichkeiten. Keine Wettquoten fließen ein.
    </>
  ),
};
