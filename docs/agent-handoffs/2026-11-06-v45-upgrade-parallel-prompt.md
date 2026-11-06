# Parallel follow-up: V45 migration readiness and Calendar usability

Baseline: master `e3d9ff4`, clean at inspection. The owner explicitly starts the
second chat; this document does not spawn agents. A owns Calendar/Google/Web and
Calendar tests, ADR 0039, shared overview updates and its result report. B owns new
migration tooling/tests, a dedicated migration rehearsal, ADR 0040 if needed and
its own report/runbook additions. No new SQL migration is expected.

Both chats retain the [existing single-checkout rules](2026-11-06-parallel-home-and-gateway.md):
master only, explicit owned staging, Git/Core exclusive FileShare.None locks,
coordinated frozen Core checks, no deployment/live migration/restart/provider or
device writes, no private export and no automatic button authorization.

## Prompt to paste into Chat B

```text
Setze als Chat B fort. Ausgangspunkt ist master e3d9ff4 oder ein neuerer geprüfter Stand.

Aktuell integriert:
- 157a399 / ce10573: dein Gateway-Fix, Abnahmewerkzeuge und Rollout-Bericht.
- 1ed89e1: persönliche Kalenderfreigaben, V44.
- e3d9ff4: manuelle Übertragung gemeinsamer Termine, V45.
Letzte kombinierte Prüfung:410 Core-Tests,225 Web-Tests, Builds/Lint/Typecheck erfolgreich.
Windows läuft bislang auf V39, Pi auf V41. Deine bisherige Migrationsprobe endet bei V43.

Schließe die technische Lücke für eine spätere Aktualisierung auf V45:

1. Lies AGENTS.md, README.md, deine Übergaben, docs/gateway-authority-rollout.md,
   ADR0037/0038 und den aktuellen Kalender-Ergebnisbericht. Prüfe Branch, Status
   und tatsächlichen Migrationskatalog erneut.
2. Erstelle einen reproduzierbaren Migrationsweg, der ausschließlich die Schema-
   Migration aus einem eindeutig geprüften Core-Artefakt ausführt, ohne Core,
   Scheduler, Provider- oder Geräteaktionen zu starten. Verwende vorhandene
   Flyway-Versionen und Migrationsdateien; keine eigene History-Nachbildung.
   Prüfen/Planen standardmäßig ohne Änderungen. Späterer Apply explizit an
   Artefakt, Zielidentität und geprüften Ausgangsstand binden. Keine Zugangsdaten
   in Argumentlisten, Logs oder Git ausgeben. Keine neuen Abhängigkeiten ohne Bedarf.
3. Prüfe den Weg auf wegwerfbaren synthetischen Datenbanken:
   V39/V41/V43/V44 -> V45, Daten-/Checksummerhalt, default-private V44, keine
   automatischen V45-Zielkalender, Konten/Rollen/Audit/verschlüsselte Metadaten
   und unverändert sichere Gateway-Provenienz. Echte Dump/Restore-Proben nutzen.
   Auch unabhängigen Restore von V45 mit Freigaben, Zielkalendern und
   Übertragungszuständen prüfen. Ungültige oder unpassende Artefakte/Ziele
   abweisen. Produktive Datenbanken sind keine Testziele.
4. Ergänze einen konkreten Windows-/Pi-Ablauf und Rollback-Grenzen. Originaldaten-/
   Schlüssel-Restore, geschützte Agent-Zielprüfung, persönliche Prüfung alter
   Button-Bindungen und Hardware-Abnahme bleiben offen, soweit nicht nachgewiesen.
   Synthetische Tests sind keine produktive Abnahme.

Dateigrenzen:
- Neue Tools/Tests unter infrastructure/dev, ein neuer dedizierter Migration-
  Rehearsal-Test und eigene neue Dokumentation gehören dir.
- ADR0040 reserviert, falls nötig; keine neue SQL-Migration, V1–V45 nicht ändern.
- A übernimmt Kalender-Duplikate und Kalender-Abnahme, ADR0039 reserviert.
  Kalender-/Google-Produktcode, Kalender-Web, Auth/RBAC, Core-Buildkonfiguration
  und gemeinsame Übersichten nicht ohne konkrete Abstimmung ändern.

Koordination:
- Derselbe Checkout auf master; keine Branchwechsel/Branches/Worktrees.
- Statusdateien unter .run/dev-recovery/coordination und FileShare.None-Sperren:
  git.lock für Git-Mutationen, core-checks.lock für ganze Core-Prüfungen.
  Vor vollständigen Core-Läufen mit A ein stabiles Quellcodefenster vereinbaren.
- Ausschließlich eigene explizite Dateien/Hunks stagen, niemals git add -A.
- Keine Deployments, produktiven Migrationen, Neustarts, Provider-Schreibzugriffe,
  Geräteaktionen, privaten Backup-Exporte oder automatischen Button-Freigaben.

Bis zu einem konkreten, getesteten und committeten isolierten Ergebnis arbeiten.
Commit-IDs, Reproduktionsbefehle, Prüfungen und reale Restabnahme dokumentieren.
```

## Completion boundary

Implemented/tested source is not activation. Essential remaining release work is
an exact V45 artifact/catalog, original-data/key restore, protected target checks,
controlled migration/activation and real browser/provider/hardware acceptance.
Business expansion, multi-HOME identity, new providers and recurrence authoring
are separately planned product work, not prerequisites for the first HOME slice.
