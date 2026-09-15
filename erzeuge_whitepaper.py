"""Erzeugt `whitepaper_preview.pdf` — die öffentliche Vorschau des MMP/MMB-Whitepapers.

Bewusst ohne neue Abhängigkeit: PyMuPDF ist bereits Projektabhängigkeit (requirements.txt,
wird von der Ingestion für PDF-Text gebraucht). reportlab ist nicht installiert und wird
dafür auch nicht gebraucht.

IP-SCHUTZ — die Regel für jede künftige Änderung an diesem Skript:
Der Text bleibt auf der architektonischen und konzeptionellen Ebene. Was hier NICHT
hineingehört, auch nicht "nur als Beispiel":
  - Schemas, Tabellen- oder Spaltennamen, Migrationslogik,
  - Relokationsverfahren, Ordinal-Tie-Breaker, Fuzzy-Matching, Hash-Berechnung,
  - Quellcode oder Dateinamen aus `mmp/` und `mmb/`.
Fachbegriffe der Protokolloberfläche (`origin`, `procedure`, die vier Zustandsnamen) sind
ausdrücklich erlaubt — sie tragen das Sicherheitsargument und sagen nichts über den Bau aus.

ZAHLEN — zweite Regel: keine Messzahl in dieses Dokument, solange sie nicht gemessen,
gegengeprüft und freigegeben ist. Der Abschnitt "Empirical Impact" beschreibt deshalb den
Messansatz und die Kostenstruktur, nicht ein Ergebnis. Das ist keine Zurückhaltung aus
Vorsicht, sondern der Grund, warum das Dokument einer technischen Prüfung standhält.

Aufruf:
    .venv\\Scripts\\python.exe dist_public/erzeuge_whitepaper.py
    .venv\\Scripts\\python.exe dist_public/erzeuge_whitepaper.py --ziel /tmp/vorschau.pdf
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

# --------------------------------------------------------------------------------------
# Gestaltung
# --------------------------------------------------------------------------------------

SEITE = pymupdf.paper_rect("a4")          # 595 x 842 pt
RAND_LINKS = 62.0
RAND_RECHTS = 62.0
RAND_OBEN = 64.0
RAND_UNTEN = 62.0
TEXTBREITE = SEITE.width - RAND_LINKS - RAND_RECHTS

# Base-14-Schriften: keine Einbettung nötig, damit ist die PDF klein und überall lesbar.
SERIF = "tiro"          # Times-Roman — Fließtext
SERIF_KURSIV = "tiit"
SANS_FETT = "hebo"      # Helvetica-Bold — Überschriften
SANS = "helv"
MONO = "cour"

TINTE = (0.13, 0.14, 0.16)
TINTE_MATT = (0.42, 0.44, 0.48)
AKZENT = (0.11, 0.28, 0.52)
LINIE = (0.80, 0.82, 0.85)

# Zustandsfarben für das Diagramm: Ampel, aber gedeckt — ein Whitepaper ist kein Dashboard.
FARBE_FRESH = (0.16, 0.45, 0.31)
FARBE_DRIFTED = (0.62, 0.45, 0.10)
FARBE_STALE = (0.62, 0.22, 0.20)
FARBE_ORPHANED = (0.40, 0.42, 0.46)

# Polaritaet im Kostendiagramm — BEWUSST nicht die Zustandsfarben oben. Dort steht eine Farbe
# für einen Status, hier für eine Richtung (gespart / mehr bezahlt). Wer beides gleich
# einfärbt, lädt den Leser ein, "teurer" als "kaputt" zu lesen.
FARBE_ERSPARNIS = AKZENT
FARBE_MEHRKOSTEN = (0.84, 0.33, 0.10)
FARBE_NULLACHSE = (0.55, 0.57, 0.61)
FARBE_GITTER = (0.88, 0.89, 0.91)

STAND = "September 2026"
AUTOR = "Justin Paul Urbaniak"
TITEL = ("Architectural Foundations of Deterministic Agent Memory: "
         "Mitigating Context Rot and Indirect Prompt Injections via "
         "Harvard-Decoupled State Meshes")


# --------------------------------------------------------------------------------------
# Kleiner Satzspiegel: eigener Umbruch statt insert_textbox, damit die Y-Position jederzeit
# exakt bekannt ist und ein Seitenumbruch nie mitten in eine Überschrift fällt.
# --------------------------------------------------------------------------------------

def _pruefe_zeichensatz(text: str) -> str:
    """Die Base-14-Schriften können nur Latin-1. Alles darüber (Geviertstrich U+2014,
    Halbgeviertstrich, typografische Anführungszeichen) setzt PyMuPDF stillschweigend als
    Mittelpunkt `·` — der Text sieht dann im PDF falsch aus, ohne dass irgendetwas meldet.

    Genau so ein stiller Rückfall ist hier schon einmal teuer geworden, deshalb bricht das
    Skript lieber ab und nennt das Zeichen. Wer echte Typografie will, muss eine Unicode-
    Schrift einbetten — das ist eine Lizenzentscheidung und keine Nebenwirkung."""
    try:
        text.encode("latin-1")
    except UnicodeEncodeError as fehler:
        schlecht = text[fehler.start:fehler.end]
        raise ValueError(
            f"Zeichen {schlecht!r} (U+{ord(schlecht[0]):04X}) ist nicht Latin-1 und würde im "
            f"PDF stumm zu '·' werden. Stelle: ...{text[max(0, fehler.start - 40):fehler.end + 40]}..."
        ) from fehler
    return text


def _umbrich(text: str, schrift: str, groesse: float, breite: float) -> list[str]:
    """Bricht `text` auf `breite` um. Ein Wort, das allein zu breit ist, bleibt stehen -
    besser eine überstehende URL als eine stillschweigend zerschnittene."""
    _pruefe_zeichensatz(text)
    zeilen: list[str] = []
    laufend = ""
    for wort in text.split():
        versuch = f"{laufend} {wort}".strip()
        if pymupdf.get_text_length(versuch, schrift, groesse) <= breite or not laufend:
            laufend = versuch
        else:
            zeilen.append(laufend)
            laufend = wort
    if laufend:
        zeilen.append(laufend)
    return zeilen


class Satz:
    """Fortlaufender Satzspiegel über mehrere Seiten mit eigener Cursorführung."""

    def __init__(self) -> None:
        self.doc = pymupdf.open()
        self.seite: pymupdf.Page | None = None
        self.y = 0.0
        self.seitenzahl = 0
        self._neue_seite()

    # -- Seitengerüst ------------------------------------------------------------------

    def _neue_seite(self) -> None:
        self.seite = self.doc.new_page(width=SEITE.width, height=SEITE.height)
        self.seitenzahl += 1
        self.y = RAND_OBEN
        if self.seitenzahl > 1:
            self._kopfzeile()

    def _kopfzeile(self) -> None:
        self.seite.insert_text(
            (RAND_LINKS, RAND_OBEN - 22),
            "Memory Mesh Protocol (MMP) & Bridge (MMB)  ·  Whitepaper Preview",
            fontname=SANS, fontsize=7.5, color=TINTE_MATT,
        )
        self.seite.draw_line(
            pymupdf.Point(RAND_LINKS, RAND_OBEN - 14),
            pymupdf.Point(SEITE.width - RAND_RECHTS, RAND_OBEN - 14),
            color=LINIE, width=0.5,
        )

    def _fusszeilen(self) -> None:
        """Erst am Ende, weil die Gesamtseitenzahl vorher nicht feststeht."""
        gesamt = self.doc.page_count
        for nr, seite in enumerate(self.doc, start=1):
            seite.draw_line(
                pymupdf.Point(RAND_LINKS, SEITE.height - RAND_UNTEN + 22),
                pymupdf.Point(SEITE.width - RAND_RECHTS, SEITE.height - RAND_UNTEN + 22),
                color=LINIE, width=0.5,
            )
            seite.insert_text(
                (RAND_LINKS, SEITE.height - RAND_UNTEN + 36),
                f"Public preview · {STAND} · No implementation details",
                fontname=SANS, fontsize=7, color=TINTE_MATT,
            )
            rechts = f"{nr} / {gesamt}"
            breite = pymupdf.get_text_length(rechts, SANS, 7)
            seite.insert_text(
                (SEITE.width - RAND_RECHTS - breite, SEITE.height - RAND_UNTEN + 36),
                rechts, fontname=SANS, fontsize=7, color=TINTE_MATT,
            )

    def _platz(self, hoehe: float) -> None:
        """Sorgt dafür, dass `hoehe` noch auf die Seite passt — sonst umbrechen.

        Die Satzspiegel-Unterkante ist NICHT RAND_UNTEN: die Fusszeilenlinie sitzt bei
        `SEITE.height - RAND_UNTEN + 22`. Wer bei RAND_UNTEN umbricht, verschenkt 22 pt je
        Seite und schiebt am Ende einen Zweizeiler auf eine sonst leere Seite."""
        if self.y + hoehe > SEITE.height - RAND_UNTEN + 10:
            self._neue_seite()

    # -- Bausteine ---------------------------------------------------------------------

    def abstand(self, hoehe: float) -> None:
        self.y += hoehe

    def titelblock(self) -> None:
        self.seite.insert_text(
            (RAND_LINKS, self.y + 4), "WHITEPAPER PREVIEW",
            fontname=SANS_FETT, fontsize=8, color=AKZENT,
        )
        self.y += 26
        for zeile in _umbrich(TITEL, SANS_FETT, 16, TEXTBREITE):
            self.seite.insert_text((RAND_LINKS, self.y), zeile,
                                   fontname=SANS_FETT, fontsize=16, color=TINTE)
            self.y += 21
        self.y += 6
        self.seite.draw_line(
            pymupdf.Point(RAND_LINKS, self.y), pymupdf.Point(RAND_LINKS + 64, self.y),
            color=AKZENT, width=2.0,
        )
        self.y += 18
        for zeile in _umbrich(
            "Memory Mesh Protocol (MMP) and Memory Mesh Bridge (MMB): a deterministic "
            "long-term state architecture for autonomous AI agents.",
            SERIF_KURSIV, 10.5, TEXTBREITE,
        ):
            self.seite.insert_text((RAND_LINKS, self.y), zeile,
                                   fontname=SERIF_KURSIV, fontsize=10.5, color=TINTE_MATT)
            self.y += 14
        self.y += 8
        # Namenszeile: das Dokument soll auch als Urheberschaftsnachweis taugen, deshalb
        # steht der Autor sichtbar im Dokument und nicht nur in den Metadaten.
        self.seite.insert_text((RAND_LINKS, self.y), AUTOR,
                               fontname=SANS_FETT, fontsize=9.5, color=TINTE)
        self.y += 15
        self.seite.insert_text(
            (RAND_LINKS, self.y),
            f"Architectural preview · {STAND} · Conceptual level only: no implementation "
            "details, schemas or algorithms",
            fontname=SANS, fontsize=7.5, color=TINTE_MATT,
        )
        self.y += 22

    def ueberschrift(self, text: str) -> None:
        self._platz(52)
        self.y += 12
        self.seite.insert_text((RAND_LINKS, self.y), text,
                               fontname=SANS_FETT, fontsize=12, color=AKZENT)
        self.y += 6
        self.seite.draw_line(
            pymupdf.Point(RAND_LINKS, self.y),
            pymupdf.Point(SEITE.width - RAND_RECHTS, self.y),
            color=LINIE, width=0.5,
        )
        self.y += 14

    def absatz(self, text: str, schrift: str = SERIF, groesse: float = 9.8,
               farbe: tuple[float, float, float] = TINTE) -> None:
        zeilen = _umbrich(text, schrift, groesse, TEXTBREITE)
        self._platz(len(zeilen) * (groesse + 3.4) + 6)
        for zeile in zeilen:
            self.seite.insert_text((RAND_LINKS, self.y), zeile,
                                   fontname=schrift, fontsize=groesse, color=farbe)
            self.y += groesse + 3.4
        self.y += 6

    def aufzaehlung(self, punkte: list[tuple[str, str]]) -> None:
        """Je Punkt eine fette Marke und der zugehörige Text."""
        for marke, text in punkte:
            einzug = RAND_LINKS + 13
            breite = TEXTBREITE - 13
            marken_breite = pymupdf.get_text_length(marke + " ", SANS_FETT, 9.8)
            erste = _umbrich(text, SERIF, 9.8, breite - marken_breite)
            rest_text = " ".join(text.split()[len(erste[0].split()):]) if erste else ""
            weitere = _umbrich(rest_text, SERIF, 9.8, breite) if rest_text else []

            self._platz((1 + len(weitere)) * 13.2 + 8)
            self.seite.draw_circle(pymupdf.Point(RAND_LINKS + 3.5, self.y - 3.2), 1.7,
                                   color=AKZENT, fill=AKZENT)
            self.seite.insert_text((einzug, self.y), marke,
                                   fontname=SANS_FETT, fontsize=9.8, color=TINTE)
            if erste:
                self.seite.insert_text((einzug + marken_breite, self.y), erste[0],
                                       fontname=SERIF, fontsize=9.8, color=TINTE)
            self.y += 13.2
            for zeile in weitere:
                self.seite.insert_text((einzug, self.y), zeile,
                                       fontname=SERIF, fontsize=9.8, color=TINTE)
                self.y += 13.2
            self.y += 5

    def merksatz(self, text: str) -> None:
        """Hervorgehobener Kernsatz mit Randbalken."""
        zeilen = _umbrich(text, SERIF_KURSIV, 10, TEXTBREITE - 18)
        hoehe = len(zeilen) * 14 + 12
        self._platz(hoehe + 10)
        oben = self.y - 9
        self.seite.draw_rect(pymupdf.Rect(RAND_LINKS, oben, RAND_LINKS + 2.6, oben + hoehe),
                             color=AKZENT, fill=AKZENT)
        for zeile in zeilen:
            self.seite.insert_text((RAND_LINKS + 14, self.y), zeile,
                                   fontname=SERIF_KURSIV, fontsize=10, color=AKZENT)
            self.y += 14
        self.y += 12

    def tabelle(self, kopf: tuple[str, str, str], zeilen: list[tuple[str, str, str]],
                status_farben: dict[str, tuple[float, float, float]] | None = None) -> None:
        """Dreispaltige Tabelle mit gefülltem Kopfband und Zebrastreifen.

        Die Statusspalte übernimmt die Farbsprache des Zustandsdiagramms auf Seite 1 — das
        Dokument soll EIN Farbsystem haben und nicht zwei, die zufällig nebeneinanderliegen."""
        status_farben = status_farben or {}
        spalten = [132.0, 250.0, TEXTBREITE - 132.0 - 250.0]
        x = [RAND_LINKS, RAND_LINKS + spalten[0], RAND_LINKS + spalten[0] + spalten[1]]
        polster_x = 9.0
        polster_y = 7.0
        zeilenhoehe = 11.6
        rechts = SEITE.width - RAND_RECHTS
        kopf_h = 18.0

        umbrochene = [[_umbrich(z[i], SERIF, 8.8, spalten[i] - 2 * polster_x) for i in range(3)]
                      for z in zeilen]
        hoehen = [max(len(sp) for sp in z) * zeilenhoehe + 2 * polster_y for z in umbrochene]
        self._platz(kopf_h + sum(hoehen) + 14)

        oben = self.y

        # Kopfband: gefüllt statt nur unterstrichen — das ist der eigentliche Unterschied
        # zwischen "Textzeilen untereinander" und "Tabelle".
        self.seite.draw_rect(pymupdf.Rect(RAND_LINKS, oben, rechts, oben + kopf_h),
                             color=None, fill=AKZENT)
        for i in range(3):
            self.seite.insert_text((x[i] + polster_x, oben + 12.2), kopf[i],
                                   fontname=SANS_FETT, fontsize=7.6, color=(1, 1, 1))

        y = oben + kopf_h
        for nr, (zeile, hoehe) in enumerate(zip(umbrochene, hoehen)):
            if nr % 2 == 1:
                self.seite.draw_rect(pymupdf.Rect(RAND_LINKS, y, rechts, y + hoehe),
                                     color=None, fill=(0.960, 0.965, 0.972))
            for i, teile in enumerate(zeile):
                schrift = SANS_FETT if i == 0 else SERIF
                if i == 2:
                    schrift = SANS_FETT
                    farbe = status_farben.get(zeilen[nr][2], TINTE)
                else:
                    farbe = TINTE
                basis = y + polster_y + 8.4
                for teil in teile:
                    self.seite.insert_text((x[i] + polster_x, basis), teil,
                                           fontname=schrift,
                                           fontsize=8.2 if i == 2 else 8.8, color=farbe)
                    basis += zeilenhoehe
            y += hoehe
            if nr < len(umbrochene) - 1:
                self.seite.draw_line(pymupdf.Point(RAND_LINKS, y), pymupdf.Point(rechts, y),
                                     color=LINIE, width=0.4)

        # Feine Umrandung hält die Streifen zusammen, ohne ein Gitter zu zeichnen.
        self.seite.draw_rect(pymupdf.Rect(RAND_LINKS, oben, rechts, y), color=LINIE, width=0.6)
        self.y = y + 14

    def schlussnotiz(self, text: str) -> None:
        """Der Rechtehinweis am Dokumentende, mit engerer Setzregel als der Fliesstext.

        Grund: `_platz` haelt fuer jeden Block Reserve vor, damit nie ein Absatz angeschnitten
        an der Fusszeile klebt. Beim allerletzten Block ist diese Reserve schaedlich — sie
        schiebt einen Zweizeiler auf eine sonst leere Seite, was ein Dokument unfertig
        aussehen laesst. Hier wird deshalb bis 16 pt unter RAND_UNTEN gesetzt; die
        Fusszeilenlinie liegt bei +22, es bleiben also rund 10 pt Luft.

        Gerechnet wird mit der TIEFSTEN GRUNDLINIE plus Unterlaenge, nicht mit dem
        Cursor-Vorschub: nach der letzten Zeile rueckt der Cursor noch eine Zeilenhoehe
        weiter, dort steht aber keine Farbe mehr. Wer diesen Vorschub als belegten Raum
        zaehlt, bricht eine Zeile zu frueh um -- genau daran haengt hier eine ganze Seite."""
        zeilen = _umbrich(text, SANS, 7.5, TEXTBREITE)
        tiefste_grundlinie = self.y + (len(zeilen) - 1) * 10.9
        if tiefste_grundlinie + 3 > SEITE.height - RAND_UNTEN + 14:
            self._neue_seite()
        for zeile in zeilen:
            self.seite.insert_text((RAND_LINKS, self.y), zeile,
                                   fontname=SANS, fontsize=7.5, color=TINTE_MATT)
            self.y += 10.9

    def bildunterschrift(self, text: str) -> None:
        zeilen = _umbrich(text, SANS, 7.4, TEXTBREITE)
        self._platz(len(zeilen) * 10.4 + 10)
        for zeile in zeilen:
            self.seite.insert_text((RAND_LINKS, self.y), zeile,
                                   fontname=SANS, fontsize=7.4, color=TINTE_MATT)
            self.y += 10.4
        self.y += 10

    def _balken(self, null_x: float, laenge: float, y: float, hoehe: float,
                farbe: tuple[float, float, float]) -> None:
        """Balken ab der Nullachse. Rund am Datenende, eckig an der Achse — die Achse ist
        eine Kante, kein Wert, und ein rundes Ende dort würde sie weichzeichnen."""
        if abs(laenge) < 0.4:
            return
        x0, x1 = (null_x + laenge, null_x) if laenge < 0 else (null_x, null_x + laenge)
        radius = min(0.34, 4.0 / hoehe)
        self.seite.draw_rect(pymupdf.Rect(x0, y, x1, y + hoehe),
                             color=None, fill=farbe, radius=radius)
        # Das Ende an der Nullachse wieder eckig überdecken.
        if laenge < 0:
            kappe = pymupdf.Rect(x1 - 5, y, x1, y + hoehe)
        else:
            kappe = pymupdf.Rect(x0, y, x0 + 5, y + hoehe)
        self.seite.draw_rect(kappe, color=None, fill=farbe)

    def kostendiagramm(self) -> None:
        """Die tragende Figur: wohin die Kostendifferenz ging, nach Preisklasse zerlegt.
        Erklärt in einem Bild, warum weniger Token mehr Geld gekostet haben."""
        posten = [("Cache read", -0.2873), ("Cache written", 0.5107), ("Output", 0.1073)]
        netto = ("Net difference", 0.3306)

        label_b = 104.0
        balken_h = 13.0
        schritt = 21.0
        rechts = SEITE.width - RAND_RECHTS
        plot_x0 = RAND_LINKS + label_b
        halb = (rechts - plot_x0) / 2
        null_x = plot_x0 + halb
        skala = (halb - 48) / 0.60          # 48 pt Reserve je Seite für die Wertbeschriftung

        kopf_h = 26.0
        gesamt_h = kopf_h + len(posten) * schritt + 16 + schritt + 8
        self._platz(gesamt_h + 10)
        oben = self.y

        self.seite.insert_text(
            (RAND_LINKS, oben), "Where the cost difference came from",
            fontname=SANS_FETT, fontsize=8.6, color=TINTE)
        self.seite.insert_text(
            (RAND_LINKS, oben + 11),
            "USD, mean of two runs per arm  ·  carry 2.0692  ·  discard 2.3998",
            fontname=SANS, fontsize=7.2, color=TINTE_MATT)

        # Die beiden Farben benennen — damit braucht die Figur keine Legende.
        rechts_wort = "additional cost"
        b = pymupdf.get_text_length(rechts_wort, SANS_FETT, 7.2)
        self.seite.insert_text((null_x + 8, oben + 11), rechts_wort,
                               fontname=SANS_FETT, fontsize=7.2, color=FARBE_MEHRKOSTEN)
        links_wort = "saving"
        b = pymupdf.get_text_length(links_wort, SANS_FETT, 7.2)
        self.seite.insert_text((null_x - 8 - b, oben + 11), links_wort,
                               fontname=SANS_FETT, fontsize=7.2, color=FARBE_ERSPARNIS)

        gitter_oben = oben + kopf_h - 6
        gitter_unten = oben + kopf_h + len(posten) * schritt + 16 + schritt - 4

        for i in range(-3, 4):
            gx = null_x + i * 0.2 * skala
            if i == 0:
                continue
            self.seite.draw_line(pymupdf.Point(gx, gitter_oben), pymupdf.Point(gx, gitter_unten),
                                 color=FARBE_GITTER, width=0.4)

        def zeichne(name: str, wert: float, y: float, fett: bool) -> None:
            farbe = FARBE_MEHRKOSTEN if wert > 0 else FARBE_ERSPARNIS
            self.seite.insert_text((RAND_LINKS, y + balken_h - 3.6), name,
                                   fontname=SANS_FETT if fett else SANS,
                                   fontsize=8.0, color=TINTE)
            self._balken(null_x, wert * skala, y, balken_h, farbe)
            beschriftung = f"{wert:+.4f}"
            bb = pymupdf.get_text_length(beschriftung, SANS_FETT, 7.6)
            bx = null_x + wert * skala + (5 if wert > 0 else -5 - bb)
            self.seite.insert_text((bx, y + balken_h - 3.8), beschriftung,
                                   fontname=SANS_FETT, fontsize=7.6, color=farbe)

        y = oben + kopf_h
        for name, wert in posten:
            zeichne(name, wert, y, fett=False)
            y += schritt

        # Netto abgesetzt: eigene Linie darüber, damit es nicht als vierter Posten gelesen wird.
        y += 6
        self.seite.draw_line(pymupdf.Point(RAND_LINKS, y), pymupdf.Point(rechts, y),
                             color=TINTE_MATT, width=0.6)
        y += 10
        zeichne(netto[0], netto[1], y, fett=True)
        y += schritt

        self.seite.draw_line(pymupdf.Point(null_x, gitter_oben), pymupdf.Point(null_x, gitter_unten),
                             color=FARBE_NULLACHSE, width=0.9)
        self.y = y + 4

    def laufdiagramm(self) -> None:
        """Vier Läufe auf einer Kostenachse: zeigt die Trennung der Arme UND die Streuung
        innerhalb der Arme. Beides gehört ins Bild, sonst ist es Werbung.

        ALLE vier Werte sind beschriftet, nicht nur die Extreme. Auf einer Webseite dürfte
        der Rest im Tooltip oder in einer Tabellenansicht stehen — eine PDF hat beides nicht,
        und ohne gedruckte Zahlen könnte der Leser sie gar nicht erfahren. Das wäre
        ausgerechnet in dem Abschnitt schlecht, der Nachrechenbarkeit als Argument führt."""
        # (Kennung, Wert, Arm, Vermerk). Die Vermerke erklären die Streuung INNERHALB eines
        # Arms: ohne sie liest das Bild sie als Zufall, obwohl sie benennbare Ursachen hat.
        punkte = [
            ("a2", 1.9646, "carry", None),
            ("a1", 2.1737, "carry", "only cold start: ~0.21 of this"),
            ("b2", 2.3204, "discard", None),
            ("b1", 2.4792, "discard", "28 requests, the others 25"),
        ]
        unten, oben_wert = 1.90, 2.55

        rechts = SEITE.width - RAND_RECHTS
        plot_x0 = RAND_LINKS + 104.0
        breite = rechts - plot_x0 - 10
        self._platz(104)
        oben = self.y

        self.seite.insert_text((RAND_LINKS, oben), "The four runs, individually",
                               fontname=SANS_FETT, fontsize=8.6, color=TINTE)
        self.seite.insert_text((RAND_LINKS, oben + 11), "total cost per run, USD",
                               fontname=SANS, fontsize=7.2, color=TINTE_MATT)

        def x_von(wert: float) -> float:
            return plot_x0 + (wert - unten) / (oben_wert - unten) * breite

        achse_y = oben + 46
        self.seite.draw_line(pymupdf.Point(plot_x0, achse_y), pymupdf.Point(plot_x0 + breite, achse_y),
                             color=FARBE_GITTER, width=0.6)
        # Teilstriche ohne Zahlen: jeder Punkt trägt jetzt seinen Wert, Achsenzahlen wären
        # ab hier reine Wiederholung.
        for marke in (2.0, 2.1, 2.2, 2.3, 2.4, 2.5):
            gx = x_von(marke)
            self.seite.draw_line(pymupdf.Point(gx, achse_y - 3), pymupdf.Point(gx, achse_y + 3),
                                 color=FARBE_GITTER, width=0.5)

        for kennung, wert, arm, vermerk in punkte:
            oberhalb = arm == "carry"
            farbe = FARBE_ERSPARNIS if oberhalb else FARBE_MEHRKOSTEN
            px = x_von(wert)
            py = achse_y + (-11 if oberhalb else 11)
            self.seite.draw_circle(pymupdf.Point(px, py), 3.2, color=None, fill=farbe)

            b_kennung = pymupdf.get_text_length(kennung, SANS, 6.2)
            zahl = f"{wert:.4f}"
            b_zahl = pymupdf.get_text_length(zahl, SANS_FETT, 6.6)
            lx = px - (b_kennung + 3 + b_zahl) / 2
            ly = py - 8 if oberhalb else py + 11
            self.seite.insert_text((lx, ly), kennung,
                                   fontname=SANS, fontsize=6.2, color=TINTE_MATT)
            self.seite.insert_text((lx + b_kennung + 3, ly), zahl,
                                   fontname=SANS_FETT, fontsize=6.6, color=farbe)

            if vermerk:
                b_v = pymupdf.get_text_length(vermerk, SANS, 6.2)
                vy = ly - 8.0 if oberhalb else ly + 8.0
                self.seite.insert_text((px - b_v / 2, vy), vermerk,
                                       fontname=SANS, fontsize=6.2, color=TINTE_MATT)

        for arm, farbe in (("carry", FARBE_ERSPARNIS), ("discard", FARBE_MEHRKOSTEN)):
            versatz = -11 if arm == "carry" else 11
            bb = pymupdf.get_text_length(arm, SANS_FETT, 7.2)
            self.seite.insert_text((plot_x0 - bb - 12, achse_y + versatz + 2.6), arm,
                                   fontname=SANS_FETT, fontsize=7.2, color=farbe)

        self.y = achse_y + 40

    # -- Zustandsdiagramm ---------------------------------------------------------------

    def zustandsdiagramm(self) -> None:
        """Der Lebenszyklus als Bild statt als Aufzählung: vier Zustände, die Übergänge
        und — die eigentliche Aussage — welcher Zustand Inhalt herausgibt und welcher nicht."""
        kasten_h = 30.0
        luft = 15.0
        kopf_luft = 30.0          # Platz für den Rückweg OBERHALB der Kästen
        kasten_b = (TEXTBREITE - 3 * luft) / 4
        self._platz(kopf_luft + kasten_h + 46)

        schleife_y = self.y + 4
        oben = self.y + kopf_luft
        zustaende = [
            ("FRESH", FARBE_FRESH, "verified current", "content released"),
            ("DRIFTED", FARBE_DRIFTED, "source moved on", "released + labelled"),
            ("STALE", FARBE_STALE, "anchors lost", "withheld"),
            ("ORPHANED", FARBE_ORPHANED, "source gone", "withheld"),
        ]

        mitten: list[float] = []
        for i, (name, farbe, unterzeile, freigabe) in enumerate(zustaende):
            x0 = RAND_LINKS + i * (kasten_b + luft)
            rechteck = pymupdf.Rect(x0, oben, x0 + kasten_b, oben + kasten_h)
            self.seite.draw_rect(rechteck, color=farbe, width=1.1, radius=0.12)
            mitten.append(x0 + kasten_b / 2)

            b = pymupdf.get_text_length(name, SANS_FETT, 9.5)
            self.seite.insert_text((x0 + (kasten_b - b) / 2, oben + 19),
                                   name, fontname=SANS_FETT, fontsize=9.5, color=farbe)

            b = pymupdf.get_text_length(unterzeile, SANS, 7.2)
            self.seite.insert_text((x0 + (kasten_b - b) / 2, oben + kasten_h + 12),
                                   unterzeile, fontname=SANS, fontsize=7.2, color=TINTE_MATT)

            # Die Freigabezeile ist die Kernaussage — deshalb in der Zustandsfarbe.
            b = pymupdf.get_text_length(freigabe, SANS_FETT, 7.2)
            self.seite.insert_text((x0 + (kasten_b - b) / 2, oben + kasten_h + 24),
                                   freigabe, fontname=SANS_FETT, fontsize=7.2, color=farbe)

        # Übergänge zwischen den Zuständen.
        for i in range(3):
            x0 = RAND_LINKS + i * (kasten_b + luft) + kasten_b
            x1 = x0 + luft
            y = oben + kasten_h / 2
            self.seite.draw_line(pymupdf.Point(x0 + 2, y), pymupdf.Point(x1 - 4, y),
                                 color=TINTE_MATT, width=0.8)
            self.seite.draw_polyline(
                [pymupdf.Point(x1 - 7.5, y - 2.6), pymupdf.Point(x1 - 3, y),
                 pymupdf.Point(x1 - 7.5, y + 2.6)],
                color=TINTE_MATT, fill=TINTE_MATT, width=0.8,
            )

        # Rückweg OBERHALB der Kästen: unterhalb würde die Linie quer durch die
        # Freigabe-Beschriftungen laufen, und genau die sind die Kernaussage des Bildes.
        self.seite.draw_line(pymupdf.Point(mitten[3], oben - 4),
                             pymupdf.Point(mitten[3], schleife_y), color=AKZENT, width=0.8)
        self.seite.draw_line(pymupdf.Point(mitten[3], schleife_y),
                             pymupdf.Point(mitten[0], schleife_y), color=AKZENT, width=0.8)
        self.seite.draw_line(pymupdf.Point(mitten[0], schleife_y),
                             pymupdf.Point(mitten[0], oben - 3), color=AKZENT, width=0.8)
        self.seite.draw_polyline(   # Pfeilspitze zeigt in den FRESH-Kasten hinein
            [pymupdf.Point(mitten[0] - 2.6, oben - 7),
             pymupdf.Point(mitten[0], oben - 1),
             pymupdf.Point(mitten[0] + 2.6, oben - 7)],
            color=AKZENT, fill=AKZENT, width=0.8,
        )
        beschriftung = "re-ingest: the only path back to FRESH"
        b = pymupdf.get_text_length(beschriftung, SANS, 7.2)
        mitte = (mitten[0] + mitten[3]) / 2
        self.seite.draw_rect(
            pymupdf.Rect(mitte - b / 2 - 5, schleife_y - 5.5, mitte + b / 2 + 5, schleife_y + 5.5),
            color=None, fill=(1, 1, 1),
        )
        self.seite.insert_text((mitte - b / 2, schleife_y + 2.6), beschriftung,
                               fontname=SANS, fontsize=7.2, color=AKZENT)

        self.y = oben + kasten_h + 50

    # -- Abschluss ----------------------------------------------------------------------

    def speichern(self, ziel: Path) -> None:
        self._fusszeilen()
        self.doc.set_metadata({
            "title": "Architectural Foundations of Deterministic Agent Memory",
            "author": AUTOR,
            "subject": ("Deterministic long-term state architecture for autonomous AI "
                        "agents: public architectural preview"),
            "keywords": ("agent memory, context rot, indirect prompt injection, "
                         "Harvard architecture, deterministic state, green AI"),
            "creator": "erzeuge_whitepaper.py (PyMuPDF)",
        })
        ziel.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(ziel), garbage=4, deflate=True)
        self.doc.close()


# --------------------------------------------------------------------------------------
# Inhalt
# --------------------------------------------------------------------------------------

def baue(ziel: Path) -> Path:
    s = Satz()
    s.titelblock()

    s.ueberschrift("Abstract")
    s.absatz(
        "Autonomous agents keep their working state in the conversation transcript. The "
        "transcript is simultaneously the plan, the memory and the audit log, and it fails "
        "in all three roles at enterprise scale: it is lost when the context window ends, "
        "it grows more expensive with every step, and it cannot be audited afterwards. It "
        "also carries a structural security defect, in that retrieved material and operator "
        "instructions arrive through the same undifferentiated channel, so anything the "
        "agent reads can, in principle, instruct it."
    )
    s.absatz(
        "This paper describes an architecture that removes state from the transcript "
        "entirely. Knowledge is held as a verified mesh in which every node maintains an "
        "independent link to its physical source and carries a verification verdict that is "
        "re-derived on every read. Execution state (plan position, step outcomes, and an "
        "append-only record of what happened and why) is held outside the context window, "
        "so a run may lose its context at any point and resume. The two are deliberately "
        "not merged: how knowledge evolved and what a given run did are different questions "
        "and are never answered from the same record."
    )
    s.absatz(
        "The architecture is Harvard-decoupled. Material extracted from indexed sources is "
        "data by construction and can never acquire executable authority, regardless of its "
        "content. We argue that this is the only structurally sound answer to indirect "
        "prompt injection in autonomous CI/CD contexts, because it removes the need to "
        "recognize hostile instructions rather than attempting to filter them."
    )

    s.ueberschrift("The State Lifecycle")
    s.absatz(
        "A node is not either valid or invalid. Collapsing verification into a boolean "
        "discards the distinction between material that has moved on and material that has "
        "become unusable, and that distinction is what determines whether work can "
        "continue. The lifecycle is therefore four-valued."
    )
    s.zustandsdiagramm()
    s.absatz(
        "Verification compares a node against its physical source and produces exactly one "
        "of these verdicts. FRESH means the source is unchanged. DRIFTED means the source "
        "changed but every anchored region was located again intact, so the agent may proceed "
        "and receives the material explicitly labelled as the extraction-time state together "
        "with a re-ingest recommendation. STALE means the source changed and the anchored "
        "material could not be located again. ORPHANED means the source no longer exists."
    )
    s.absatz(
        "The decisive property is not the classification but what follows from it. STALE and "
        "ORPHANED nodes release no content: not filtered content, not a warning wrapped "
        "around stale content, but none. There is no override parameter and no degraded "
        "mode, by deliberate design: an emergency exit that exists will eventually be used, "
        "and the entire guarantee rests on its absence. Re-ingestion is the only route back "
        "to FRESH."
    )
    s.merksatz(
        "A run that halts costs time. A run that proceeds on demonstrably outdated material "
        "produces wrong artifacts, which then enter the mesh as new truth. The second "
        "failure is the one that cannot be undone, so the system blocks rather than warns."
    )

    s.ueberschrift("Security and the Harvard Architecture")
    s.absatz(
        "Retrieval-augmented agents share a vulnerability that better prompting does not "
        "address: the material an agent retrieves and the instructions an agent is given "
        "arrive in the same channel. Anyone able to influence an indexed artifact (a "
        "dependency README, a code comment, an issue description, a docstring) is writing "
        "into the instruction stream of every agent that later retrieves it. In an "
        "autonomous CI/CD pipeline, where the agent holds commit or deployment authority, "
        "this is a remote code execution path with a content-management interface."
    )
    s.absatz(
        "MMP separates the two paths architecturally rather than filtering at the boundary:"
    )
    s.aufzaehlung([
        ("Origin is structural. ",
         "Every node carries an origin classification. Material with origin 'extracted', "
         "meaning anything harvested from an indexed source, is data, permanently and by "
         "construction. It can be read, reasoned over and cited. It cannot instruct."),
        ("Authority is explicit and verified. ",
         "Executable authority is reserved to deliberately authored material, and is "
         "additionally conditioned on current verification state. An instruction that "
         "cannot be verified as current is not executed."),
        ("Execution capability stays closed. ",
         "The 'procedure' capability, a node carrying executable behaviour, remains "
         "closed in the current protocol generation. This is sequencing, not oversight: "
         "the separation is proven load-bearing before anything is permitted to execute."),
    ])
    s.absatz(
        "The consequence is that an injected instruction placed in an indexed file lands in "
        "the data path. It is visible, attributable to a specific source, and inert. "
        "Filtering approaches must recognize hostile instructions in order to stop them, "
        "which makes their effectiveness a function of the attacker's creativity. Denying "
        "an entire class of material the authority to instruct does not require recognition "
        "at all."
    )

    s.ueberschrift("Empirical Impact: Measured, Not Asserted")
    # Ab hier woertlich aus messung/entwurf_whitepaper_empirie_kurz.md (dreifach gegengelesen).
    # Der Text ist zweimal daran gescheitert, dass beim Verdichten Bedingungen wegfielen.
    # Wer hier kuerzt, kuerzt GANZE SAETZE - niemals ihre Bedingungen.
    s.absatz(
        "Externalized state makes it structurally possible to discard an agent's context "
        "between steps: the thread of work survives, because it was never in the transcript. "
        "Whether discarding is worth doing is a separate, arithmetic question, and it "
        "belongs to the harness and the workload, not to the state layer. What follows "
        "measures that operating strategy, not the protocol, and it does not depend on the "
        "protocol being present: any system that can externalize its execution state faces "
        "the same arithmetic."
    )
    s.absatz(
        "Two arms, the same task, files, model and machine: one context carrying all six "
        "steps of a plan, against six fresh contexts handing off a small result file on disk "
        "- a property of this test rig, not a constraint of the state layer. Two repetitions "
        "per arm in mirrored order, 14 isolated agent runs, 103 model requests, a corpus of "
        "roughly 11,000 tokens. Two is below the three repetitions per arm our own protocol "
        "required, so this run is a sign check and not a test: the design cannot produce a "
        "statistically significant result at all. Billing was reconstructed per request, "
        "every reading recomputed under three cache-warmth assumptions applied identically "
        "to both arms, and three independent reviews run against the result. The first "
        "version of that warmth normalisation applied the assumptions inconsistently; the "
        "arithmetic review caught it before publication, and correcting it moved the margin "
        "against the discard arm, not for it."
    )
    s.absatz(
        "On total cost the discard arm was more expensive in every run, with no overlap "
        "between the arms under any of the three warmth readings; across the same four runs "
        "the margin spans +9.9 to +89.1 percent depending on how restart warmth is priced, "
        "the expensive end computed from the single cold start observed rather than run. We "
        "decline to reduce this to one number: the spread within the discard arm was 48 "
        "percent of the measured difference between the arms. What the run supports is the "
        "sign, under stated conditions:"
    )
    s.merksatz(
        "On a carried payload of roughly 11,000 tokens, with steps seconds apart, in a "
        "general-purpose agent harness with the cache layout it shipped with in September "
        "2026, discarding context between steps cost more than carrying it, and the work "
        "was indistinguishable."
    )
    s.kostendiagramm()
    s.bildunterschrift(
        "The discard arm did save where it was supposed to: it read 0.2873 USD less out of "
        "cache. It paid that back more than twice over, because five additional preambles "
        "are written into the cache on restart instead of being read from it, at 12.5 times "
        "the price. Roughly 82 percent of that written block is unchanged standing text."
    )
    s.absatz(
        "Every clause in that sentence is load-bearing. Change the payload, the spacing, or "
        "the harness, and the sign is not guaranteed to survive. That matters beyond the "
        "laboratory: the operating case this architecture exists for - a plan whose steps "
        "may be hours apart - is structurally the cold case, the expensive end of the range, "
        "and the case no run with steps seconds apart exercises at all."
    )
    s.absatz(
        "On quality we could measure no difference at n=2. Wall-clock time was measured and "
        "is not reportable: the spread within a single arm was about six times the "
        "difference between the arms."
    )
    s.laufdiagramm()
    s.bildunterschrift(
        "The arms do not overlap: every discard run cost more than every carry run. The same "
        "picture shows why no percentage is quoted - the spread within the discard arm alone "
        "is 48 percent of the difference between the arms. Both within-arm gaps have "
        "identified contributors rather than being unexplained: a1 was the only cold start "
        "observed, which accounts for roughly 0.21 USD of its value, and b1 made 28 model "
        "requests where the other three runs made 25."
    )
    s.absatz(
        "The run falsified three internals of our own pre-run cost model; those corrections "
        "are its most useful output."
    )
    s.aufzaehlung([
        ("One: carrying cost 2.96 times what we predicted, ",
         "because both requests per step and the volume carried were underestimated; the "
         "warm break-even threshold falls from roughly 108,000 carried tokens to roughly "
         "36,500, which moves ordinary engineering tasks from below the line to sitting on it."),
        ("Two: most of the penalty was the harness, not the strategy. ",
         "Roughly 82 percent of what each warm restart cost in this run was an unchanged "
         "block of standing text that the harness re-writes into the cache on every restart "
         "instead of reading it, at 12.5 times the price, as measured in September 2026. "
         "Priced as a read, the discard arm would have won this run, by a margin inside the "
         "run-to-run spread we decline to quote - which moves the answer from a clear loss "
         "to a coin toss. That is a property of a particular execution harness and a "
         "particular cache layout at a particular date. It is not a property of discarding "
         "context, and it is not a property of the protocol."),
        ("Three: chain length does not cancel out. ",
         "At fixed step size the balance is quadratic against carrying, and with warm "
         "restarts discarding wins from roughly nine steps of 5,000 tokens each; cold "
         "restarts move that crossover out into the low twenties."),
    ])
    s.absatz(
        "Break-even is therefore a surface, not a threshold, moving along at least three "
        "axes: payload carried per step, length of the chain, and how the executing harness "
        "partitions its cache, which dominated here. A fourth term belongs in the same "
        "balance and is missing from every figure above: the cost of carrying results "
        "between steps in files, which a discarding arm cannot avoid and which we can size "
        "only by estimate. Cost is also not an energy measure - the discard arm processed "
        "fewer tokens and paid more money, because the tokens moved from a cheap price class "
        "to an expensive one, and we did not measure energy. And where an input rate limit "
        "binds rather than a budget, the sign of the relevant quantity is the opposite of "
        "the sign of the cost: in this run the carry arm needed about 1.3 times the "
        "input-token throughput for the same work."
    )
    s.absatz(
        "By our own pre-registered criteria, this run should have been discarded: we "
        "required three repetitions per arm and ran two, and named 12 model requests per "
        "step as the point below which the expected result flips, where we measured 4.17. "
        "Nothing here is therefore offered as a statistically significant result. Nor does "
        "the run locate the surface: its corpus sits about a factor of three below even the "
        "corrected threshold, so it confirms that a prediction lands on the expected side of "
        "the curve without locating the curve, and a larger corpus prepared for exactly this "
        "question was not the one we ran. We report it because the corrections survive the "
        "sample size even where the percentages do not. The full write-up accompanies this "
        "preview as a separate document; the cost model and the review record are held in "
        "the project archive; the decisive run - a corpus at the threshold, three "
        "repetitions per arm, cold restarts - accompanies the protocol specification."
    )
    s.merksatz(
        "Token reduction is never the sole objective. The objective is the equilibrium of "
        "reduced compute and undiminished output quality: no destructive truncation, no "
        "summarization that discards detail a later query will need."
    )

    s.ueberschrift("Roadmap and Commercial Program")
    s.absatz(
        "Verified state with source anchoring and a fail-closed read path is implemented, as "
        "is externalized execution state with resumption after context loss. The first "
        "empirical run and the three corrections it forced on our own cost model are "
        "published above; the decisive run is open. A public protocol specification is in "
        "preparation and will describe contracts, state semantics and guarantees at a depth "
        "sufficient for independent implementation, without publishing the reference engine."
    )
    s.tabelle(
        ("STAGE", "SCOPE", "STATUS"),
        [
            ("Verified state and anchoring",
             "Source-linked nodes, four-valued lifecycle, fail-closed read path",
             "Implemented"),
            ("Externalized execution state",
             "Plans, step lifecycle, append-only execution record, resumption after "
             "context loss",
             "Implemented"),
            ("First empirical run",
             "Sign check at 11,000 carried tokens; three corrections to our own cost model",
             "Published here"),
            ("Decisive empirical run",
             "Corpus at the threshold, three repetitions per arm, cold restarts",
             "Open"),
            ("Public protocol specification",
             "Contracts and state semantics at implementation depth",
             "In preparation"),
            ("Closed B2B pilot",
             "Selected industry partners, on-premise deployment",
             "Accepting enquiries"),
        ],
        status_farben={
            "Implemented": FARBE_FRESH,
            "Published here": FARBE_FRESH,
            "Open": FARBE_DRIFTED,
            "In preparation": TINTE_MATT,
            "Accepting enquiries": AKZENT,
        },
    )
    s.absatz(
        "The system is architected for single-tenant, on-premise operation. This is a design "
        "commitment rather than a deployment option: verification against a physical source "
        "tree, and an audit record an operator can actually hold, both presuppose that the "
        "operator controls the machine."
    )
    s.absatz(
        "A closed pilot program is open to a small number of selected industry partners, "
        "prioritising organisations running autonomous agents against large proprietary "
        "code or document corpora under audit obligations. The Enterprise Engine and "
        "On-Premise Core are offered under BSL 1.1 or commercial licence terms."
    )
    s.absatz(
        "Enquiries: see the contact section of the accompanying repository README.",
        schrift=SERIF_KURSIV, farbe=TINTE_MATT,
    )

    s.schlussnotiz(
        "This preview communicates architecture and behaviour only. Internal state schemas, "
        "verification and relocation algorithms, and implementation source are not part of "
        "this publication. © 2026, all rights reserved."
    )

    s.speichern(ziel)
    return ziel


def main() -> None:
    zerleger = argparse.ArgumentParser(
        description="Erzeugt die öffentliche Whitepaper-Vorschau als PDF.")
    zerleger.add_argument(
        "--ziel", type=Path,
        default=Path(__file__).resolve().parent / "whitepaper_preview.pdf",
        help="Zieldatei (Vorgabe: whitepaper_preview.pdf neben diesem Skript)")
    argumente = zerleger.parse_args()

    ziel = baue(argumente.ziel)
    groesse_kb = ziel.stat().st_size / 1024
    with pymupdf.open(str(ziel)) as geprueft:
        seiten = geprueft.page_count
    print(f"geschrieben: {ziel}  ({seiten} Seiten, {groesse_kb:.0f} kB)")


if __name__ == "__main__":
    main()
