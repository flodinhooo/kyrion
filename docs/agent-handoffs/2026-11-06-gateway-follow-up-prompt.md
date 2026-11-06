# Follow-up prompt for Chat B

Paste the following into the existing second chat. Assignment A continues HOME-03
personal calendar disclosure (V44, ADR 0037), including Google read boundaries and
Calendar Web. The existing checkout/lock rules remain in force.

```text
Setze Paket B fort. Dein bisheriger Abschluss ist bestätigt:
c398402 = Gateway Authority, ADR 0036 und V42
fba7cbb = Abschlussbericht
Chat A hat 69cee10 (gemeinsame Haushaltstermine, V43) abgeschlossen und übernimmt
jetzt HOME-03: persönliche Kalenderfreigaben, V44 und ADR 0037.

Deine Aufgabe: Bereite die Gateway-Abnahme und den späteren Rollout konkret vor.

1. Lies AGENTS.md, README.md, deinen Abschlussbericht,
   docs/gateway-command-authority.md und die aktuellen Status-/Pi-Dokumente.
   Prüfe den aktuellen Git- und Laufzeitstand, statt alte Angaben vorauszusetzen.
2. Untersuche verbleibende Gateway-TODOs und vorhandene Abnahme-/Recovery-Werkzeuge.
   Ergänze eine reproduzierbare Prüfung für Migration, fehlende alte Provenienz,
   widerrufene Berechtigungen und Button-Freigaben. Nutze isolierte Testdaten;
   keine echten Geräteaktionen.
3. Erstelle einen konkreten Rollout-/Rollback-Plan für Windows und Pi einschließlich
   V42/V43 und des kommenden V44, Datensicherung, Kompatibilität und anschließendem
   explizitem Neuspeichern alter Button-Bindungen. Prüfe anhand der Implementierung,
   welche Rückkehr nach Migration tatsächlich möglich ist.
4. Behebe nachgewiesene Gateway-Probleme innerhalb deines Bereichs und prüfe sie.

Koordination:
- Beide Chats arbeiten im selben Checkout auf master. Keine Branchwechsel,
  neuen Branches oder Worktrees.
- Kalender, Google-Kalenderlesezugriffe, persönliche Freigaben und Kalender-UI
  gehören Chat A. Ändere diese Dateien nicht.
- Verwende die vorhandenen Statusdateien und Sperrkonventionen in
  .run/dev-recovery/coordination; lies zuerst die bisherige Übergabe.
  Git-Mutationen und vollständige Core-Testläufe koordinieren.
- V44/ADR0037 sind für A reserviert. Reserviere weitere Migrationsnummern vorab
  über die Koordinationsdateien. Vorzugsweise benötigt deine Aufgabe keine Migration.
- Kein git add -A; ausschließlich eigene Dateien/Hunks stagen. Fremde Änderungen
  erhalten. Gemeinsame Übersichtsdateien erst nach Abstimmung ändern;
  eigenen neuen Ergebnisbericht bevorzugen.
- Keine Deployments, produktiven Migrationen, Neustarts, Provider-Schreibzugriffe,
  Geräteaktionen oder automatischen Neufreigaben alter Bindungen.

Liefere konkrete Befunde, behobene Probleme, Prüfungen, verbleibende Abnahmeschritte
und Commit-IDs. Hardwareabhängige Prüfung klar als offen dokumentieren.
```
