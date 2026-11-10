# RezeptKammer für Home Assistant

Verbindet [RezeptKammer](https://rezeptkammer.de) – dein digitales Kochbuch – mit Home Assistant.

- **Einkaufslisten als To-do-Listen**: deine private Liste und jede gemeinsame Kammer, in beide Richtungen synchron. Mit Assist auch per Sprache: „Füge Milch zur RezeptKammer Einkaufsliste hinzu“ (Tipp: in Home Assistant den Alias „Einkaufsliste“ vergeben).
- **Kochmodus-Ereignisse**: Timer gestartet/abgelaufen/gestoppt, Ofen vorheizen (mit Temperatur und Heizart), Kochmodus gestartet, aktueller Kochschritt – als Ereignis-Entität `event.rezeptkammer_kochen` und als Bus-Ereignis `rezeptkammer_event`.
- **Timer-Sensor** mit dem Endzeitpunkt des laufenden Timers – das Ende wird lokal in Home Assistant ausgelöst, auch wenn das Internet kurz weg ist.
- **Kochmodus als Zustand**: „Kocht gerade“ (an, solange ein Rezept im Kochmodus offen ist), Kochrezept, aktueller Kochschritt und Fortschritt in Prozent – z. B. für ein Küchentablet oder „solange gekocht wird, Dunstabzug an“.
- **Rezeptvorschlag des Tages** aus deinen eigenen Rezepten (Sensor + Bild, mit Zubereitungszeit und Kalorien als Attribute) fürs Dashboard, dazu der Knopf **„Vorschlag auf die Einkaufsliste“** (auch per Assist).
- **Prisen**: dein Guthaben als Sensor mit Verlauf und der Binärsensor „Prisen knapp“ (unter 5). Bei unbegrenztem Guthaben werden beide nicht angelegt.

**Funktioniert mit jeder Installation** (OS, Container, Core), auch ohne Nabu Casa, ohne Portfreigabe und nur lokal bzw. per VPN: Home Assistant baut die Verbindung selbst auf.

## Installation

[![In Home Assistant öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=massa007&repository=rezeptkammer-homeassistant&category=integration)

Am einfachsten über diesen Button: Er öffnet die Integration direkt in deinem Home Assistant (Marketplace bzw. HACS), dort auf „Herunterladen“ tippen.

**Home Assistant 2026.11 und neuer (Marketplace), von Hand:** Einstellungen → Marketplace → „Aus Link hinzufügen“ → die Adresse dieses Repositorys einfügen, Kategorie „Integration“ → installieren → neu starten.

**Ältere Versionen mit HACS:** HACS → ⋮ → Benutzerdefinierte Repositories → Adresse dieses Repositorys, Typ „Integration“ → installieren → neu starten.

**Manuell:** unter rezeptkammer.de → Konto → Home Assistant die ZIP-Datei laden, in den `config`-Ordner entpacken (`custom_components/rezeptkammer`), neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → **RezeptKammer** → „Mit meinem Konto verbinden“. Home Assistant zeigt einen Link mit Code – öffnen, mit deinem RezeptKammer-Konto bestätigen, fertig. Einen Schlüssel abtippen musst du nicht. Alternativ geht ein unter Konto erzeugter Zugangsschlüssel.

## Fertige Automationen (Blueprints)

Unter rezeptkammer.de → Konto → Home Assistant mit einem Klick übernehmen:

- **Timer-Ansage** – Ansage auf Lautsprechern, Handy-Benachrichtigung, Licht blinken
- **Ofen vorheizen (Home Connect)** – startet Bosch/Siemens/Neff/Gaggenau-Öfen mit der Rezept-Temperatur
- **Küchenlicht beim Kochen**
- **Prisen werden knapp** – Handy-Nachricht, sobald dein Guthaben unter eine Grenze fällt

## Eigene Automationen

```yaml
triggers:
  - trigger: event
    event_type: rezeptkammer_event
    event_data:
      type: timer_finished   # timer_started, timer_cancelled, oven_preheat, cooking_started, cooking_step, cooking_finished, credits_changed
actions:
  - action: notify.mobile_app_mein_handy
    data:
      message: "{{ trigger.event.data.label }} – {{ trigger.event.data.recipe }}"
```

Felder je nach Ereignis: `label`, `duration`, `ends_at`, `recipe`, `recipe_url`, `temperature`, `mode` (`hot_air`, `top_bottom`, `grill`), `step`, `total`, `text`, `credits`.

„Kocht gerade“ geht aus, sobald du den Kochmodus verlässt, oder nach 90 Minuten ohne Aktivität (Tab einfach geschlossen; ein laufender Timer zählt als Aktivität).

## Datenschutz

Home Assistant bekommt Zugriff auf deine Einkaufslisten, dein Prisen-Guthaben und auf Ereignisse aus dem Kochmodus. Die Verbindung kannst du jederzeit unter Konto → Home Assistant trennen; beim Entfernen der Integration wird der Schlüssel automatisch widerrufen.
