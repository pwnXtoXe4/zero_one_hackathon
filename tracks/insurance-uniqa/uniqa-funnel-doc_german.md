# UNIQA Online-Rechner Krankenversicherung — Strecken-Dokumentation

**Quelle**: [uniqa.at/rechner/krankenversicherung](https://www.uniqa.at/rechner/krankenversicherung/)
**Stand**: Captured Mai 2026 (das Live-Verhalten kann sich ändern — Teams sollten zur Verifikation selbst durchlaufen)
**Drop-off Daten**: Zeitraum 10.12.2025 – 01.02.2026 (Quelle UNIQA Funnel-Analyse)

---

## Funnel-Übersicht

Die Strecke gliedert sich für die Person in vier sichtbare Phasen (Progress Bar):
**Angaben → Produkt → Empfehlung → Abschluss**

Aus dem Funnel-Tracking sind 15 Steps bekannt, von denen 4 die kritischen Drop-off-Punkte sind. Die wichtigsten Verzweigungen passieren früh — wer "im Krankenhaus" wählt, läuft in einen anderen Pfad als bei "bei Arztbesuchen".

Die Conversion-Logik des Rechners endet auf zwei Wegen:
1. **Online-Abschluss** möglich für die Tarife **Start** und **Optimal** (Privatarzt-Tarif "bei Arztbesuchen")
2. **Beratung erforderlich** für **Opt. Plus**, **Premium** sowie für alle Krankenhaus-Tarife und alle Konstellationen mit "andere Personen" → der Funnel mündet in eine Terminbuchung statt einem Online-Kauf

Das ist wichtig zu verstehen: **Der Rechner ist kein reiner Sales-Funnel — er ist auch ein Beratungs-Routing-Werkzeug.** Conversion bedeutet hier entweder Vertragsabschluss oder Beratungstermin. Beides ist Erfolg für UNIQA, nur ersteres ist im 5,6%-Online-Abschluss enthalten.

---

## Die wichtigsten Steps im Detail

### Step 1 — Wo möchten Sie abgesichert sein?

**Phase**: Angaben
**Frage**: "Wo möchten Sie abgesichert sein?"
**UI**: Zwei große Cards, Mehrfachauswahl möglich
**Optionen**:
- **Bei Arztbesuchen** (Kassen-/Wahl-/Privatärzt:in, Schul- und Alternativmedizin, Telemedizin)
- **Im Krankenhaus** (Öffentliches Spital oder Privatklinik, Komfort im Zweibettzimmer, OP-Termin flexibel planen)

**Verzweigung**: Die Auswahl bestimmt komplett unterschiedliche Folgepfade. "Arztbesuche" führt in die Privatarzt-Tarif-Logik (4 Tarife mit Online-Abschluss-Option), "Krankenhaus" in den Sonderklasse-Pfad (komplexer, fast immer Beratung erforderlich).

**UX-Beobachtung**: Keine Erklärung was die Konsequenz der Auswahl ist. Person:innen, die "alles" wollen, klicken vermutlich beide an — was den Pfad noch komplexer macht.

---

### Step 2 — Für wen?

**Phase**: Angaben
**Frage**: "Wer soll versichert werden?"
**Optionen**:
- **Ich selbst** → Online-Abschluss möglich
- **Andere Personen** → automatisch Beratungspfad ("Der Abschluss für andere Personen ist komplexer")

**Verzweigung**: "Andere Personen" beendet die Online-Strecke effektiv und routet direkt in die Terminbuchung.

---

### Step 3 — Personendaten für Prämienschätzung

**Phase**: Angaben
**Frage**: "Um eine voraussichtliche individuelle Prämie für Sie zu berechnen, benötigen wir:"
**Pflichtfelder**:
- Geburtsdatum
- Sozialversicherung

**Kritischer Punkt**: Hier werden zum ersten Mal echte personenbezogene Daten abgefragt, bevor irgendein Preis gezeigt wurde. Das ist ein klassischer Vertrauens-Schwelle.

---

### Step 4 — ⚠️ Tarifauswahl: Erste Preisanzeige (Drop-off 66%)

**Phase**: Produkt
**Frage**: "Welche Leistungen soll Ihre Privatarzt-Versicherung abdecken?"

**Hinweisbox** (oberhalb der Tarife):
> "Denken Sie an Ihren heutigen Bedarf, nicht an den in 20 Jahren. Nach 3 Jahren können Sie in einen anderen unserer vier Tarife wechseln, ohne erneute Gesundheitsprüfung!"

**UI**: Vergleichstabelle mit 4 Tarifen nebeneinander:

| Tarif         | Höchstbetrag/Jahr | Voraussichtliche Prämie | Status              |
| ------------- | ----------------- | ----------------------- | ------------------- |
| **Start**     | 1.400 EUR         | **38,74 EUR**           | Online abschließbar |
| **Optimal**   | 2.800 EUR         | **68,14 EUR**           | Online abschließbar |
| **Opt. Plus** | 4.200 EUR         | **96,66 EUR**           | Nur nach Beratung   |
| **Premium**   | 8.400 EUR         | **140,16 EUR**          | Nur nach Beratung   |

Aufgeschlüsselt nach Leistungsbereichen: Arztleistungen, Medikamente/Impfungen, Therapeutische Behandlungen, Heilbehelfe, refraktive Augen-OP.

**Warum so hoher Drop-off (66%)?** Mehrere plausible Gründe:
- Erste konkrete Zahl im Funnel — Preis-Schock
- Vier Optionen mit fünf verschiedenen Preis-Achsen = kognitive Überlast
- Die zwei attraktiveren Tarife (Opt. Plus, Premium) sind nur nach Beratung verfügbar → Frust bei Person:innen, die online abschließen wollten
- ROPO-Effekt: "Preis online angeschaut, kaufe ich später beim Berater" — nicht trackbar, aber laut UNIQA real
- Informationsbedarf zu unbekannten Begriffen ("refraktive Augen-OP", "Heilbehelfe")

**Conversion-Coach-Aufgabe**: Hier ist der **wichtigste Interventionsmoment**. Mögliche Hooks:
- Vergleich zum Markt aufzeigen ("Ihr Tarif ist günstiger als 80% der Privatarzt-Tarife")
- Begriffsboxen einblenden bei Hover/Klick
- Tarif-Empfehlung statt vollständiger Vergleichsmatrix für unsichere Person:innen
- Bei langer Verweildauer proaktiv Beratungsoption anbieten
- "Was kostet das pro Tag?" — psychologische Umrechnung (€ 38,74/Monat = € 1,27/Tag)

---

### Step 5 — Auswahl Zusatzdeckungen (Drop-off 24%)

**Phase**: Produkt (Krankenhaus-Pfad)
**Frage**: "Für welchen Versicherungsschutz interessieren Sie sich?"

**Optionen (Auswahl der vorhandenen)**:
- Sonderklasse nach Unfall
- Sonderklasse Select Kompakt
- Sonderklasse Select Optimal
- Sonderklassebehandlungen nach Unfall
- Sonderklassebehandlungen nach Unfall und schweren Erkrankungen
- Sonderklassebehandlungen für alle med. notwendigen Behandlungen mit Selbstbehalt
- Krankenhaus-Tagegeld
- Ersatz von Transportkosten
- Kinderbegleitkosten
- Ärztliche Zweitmeinung
- Psychologische Betreuung in Notfallsituationen
- Pauschale bei bösartigen Neubildungen (Krebs)
- Ambulante Diagnostik
- Hebamme (selbständig)

**Zusatzservices**:
- VitalPlan Vorsorge und Fitness
- Tagegeld

**UX-Beobachtung**: Bei "Krankenhaus" wird die Person mit ~15 möglichen Bausteinen konfrontiert, mit Fußnoten und Querverweisen. Niedrigerer Drop-off als bei Step 4 (24% vs 66%), aber wer hier ankommt, hat Step 4 schon überlebt und ist tendenziell entschlossener.

---

### Step 6 — Gesundheitsfragen

**Phase**: Angaben (Detailerhebung)
**Frage**: (Detail nicht final gecaptured — Teams sollten dies live verifizieren)

**Aus dem Briefing bekannt**: An dieser Stelle erhebt UNIQA die Gesundheitsdaten, die zur Berechnung der **finalen** Prämie nötig sind (vs. der "voraussichtlichen Prämie" aus Step 4).

---

### Step 7 — ⚠️ Finaler Preis nach Personenangabe (Drop-off 78%)

**Phase**: Empfehlung
**Frage**: Finalisierte Prämie nach Gesundheitsprüfung
**Konsequenz**: Hier zeigt sich der echte, individualisierte Preis. Kann signifikant von der voraussichtlichen Prämie aus Step 4 abweichen.

**Warum noch höherer Drop-off (78%)?**
- Preis hat sich vermutlich verändert — meist nach oben (Risikoaufschlag)
- Wenn der finale Preis deutlich höher ist als die initiale Schätzung, fühlt sich die Person "vorgeführt"
- Vertrauensverlust: "warum stand vorher was anderes?"
- Bei Selbstbehalt-Optionen muss eine zusätzliche Entscheidung getroffen werden

**Conversion-Coach-Aufgabe**: Hier ist Schadensbegrenzung gefragt. Mögliche Hooks:
- Transparenz wieso sich der Preis verändert hat
- Alternative Tarif-Empfehlung wenn der finale Preis nicht passt
- Berater-Übergabe als smoother Exit-Pfad statt "Abbrechen"
- "Sie können trotzdem online abschließen" — viele wissen das nicht mehr

---

### Steps 8–11 — Beratungsanfrage-Pfad (wenn aktiviert)

Wenn die Person in den Beratungspfad geroutet wird, folgen mehrere Steps:

**Step "Wo soll die Beratung stattfinden?"**
- Online-Videoberatung (NEU)
- Persönlich an einem UNIQA-Standort
- Per Telefon
- Persönlich zu Hause

**Step "Kundenstatus"**
- Neuer Kunde ohne Berater
- Bestandskunde, Online-Consulting-Team
- Bestandskunde, eigene:r Berater:in

**Step "Bundesland"** (Dropdown)

**Step "Service-Auswahl"** (welche Versicherungssparte)
- Health Insurance, Pension/Life, Household, Accident, Car, Leasing, Legal Protection, Travel, Leisure, Insurance Policy Review

**Step "Datumsauswahl"** (Kalender)

**Step "Terminvorschlag"**

**Step "Persönliche Daten"** (Name, Email, Telefon, Adresse, Geburtsdatum, Beruf, Sozialversicherung, Beratungsanliegen)

**Step "Summary & Bestätigung"**

**Beobachtung**: Auch der Beratungs-Pfad ist 7+ Steps lang und hat mehrere Stellen, an denen Person:innen aussteigen könnten — der Funnel verlagert das Drop-off-Risiko, eliminiert es nicht.

---

### Step 12+ — Abschluss (nur Tarife "Start" / "Optimal")

**Phase**: Abschluss
Die letzten Steps für Online-Abschluss decken vermutlich ab:
- Persönliche Daten (Name, Adresse, Kontakt)
- Versicherungsbeginn / Vertragslaufzeit
- Zahlungsdaten
- Einwilligungen (AGB, Datenschutz)
- Abschluss-Bestätigung

**Diese Steps wurden in der Strecken-Begehung nicht vollständig durchlaufen** (würde echte Personendaten erfordern). Teams sollten dies bei Bedarf selbst verifizieren.

---

## Beobachtete Conversion-Killer (Hypothesen für Teams)

Die folgenden Hypothesen ergeben sich aus der Streckenstruktur und sollen den Teams als Ausgangspunkt dienen — nicht als Fakten:

1. **Preis-Schock bei erster Preisanzeige** (Step 4 → 66% weg)
2. **Beratung-Notwendigkeit bei den attraktivsten Tarifen** schafft Frust bei online-affinen Person:innen
3. **Gap zwischen voraussichtlicher und finaler Prämie** zerstört Vertrauen
4. **Kognitive Überlast** durch 4 Tarife × 6 Leistungskategorien × Fußnoten
5. **Fehlende Erklärung von Fachbegriffen** ("refraktive Augen-OP", "Selbstbehalt", "Sonderklasse")
6. **Keine Vergleichsmöglichkeit zum Markt** — Person:innen verlassen die Seite, um zu vergleichen, und kommen nicht zurück
7. **Sozialversicherungsnummer-Abfrage** als Vertrauensschwelle
8. **"Nur nach Beratung" als Sackgasse** für die Person:innen, die explizit online abschließen wollten
