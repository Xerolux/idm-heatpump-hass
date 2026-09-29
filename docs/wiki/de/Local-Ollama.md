# Lokale Ollama-Einrichtung

Diese Seite ist die Schritt-für-Schritt-Anleitung, um den
[experimentellen KI-Anlagenberater](Experimental-AI-Adviser) auf **deinem
eigenen Ollama-Server** zu betreiben: kein API-Schlüssel, kein Cloud-Konto,
nichts verlässt dein Heimnetz. Behandelt werden das Ollama-Home-Assistant-Add-on,
Docker auf einem separaten Rechner und bestehende Server, die Modellwahl und
die exakten Integrationseinstellungen.

Der Add-on-Weg wurde Ende-to-End auf Home Assistant OS 2026.9 validiert
(Add-on v0.34.4, `gemma3:4b`): Ein Tagesbericht entstand auf dem lokalen
Modell in rund einer Minute mit sauberem Qualitäts-Guard. Der Weg über einen
dedizierten Server wurde genauso mit `gemma3:12b` auf einem separaten
Proxmox-LXC validiert.

## Was du brauchst

| Komponente | Minimum | Hinweise |
|-----------|---------|----------|
| Ollama-Runtime | 0.34.x | Add-on, Docker oder bestehende Installation |
| Freier RAM für das Modell | ~6 GB für ein 4B-Modell, ~11 GB für ein 12B-Modell | Zusätzlich zu dem, was Home Assistant selbst braucht |
| Freier Speicher für das Modell | ~4 GB (4B) / ~9 GB (12B) | Plus ~5 GB für das Docker-Image |
| Modell | GGUF-**Completion**-Modell | Embedding-Modelle können keine Berichte schreiben |

Berichte laufen mit einer Gesamt-Frist von fünf Minuten, die Modellvalidierung,
Modellladen und Generierung einschließt. Auf reiner CPU rechne mit etwa einer
Minute für ein 4B-Modell auf vier Kernen und rund drei Minuten für ein 12B-
Modell auf sechs Kernen. Der erste Bericht ist langsamer, weil das Modell
geladen wird; je nach Keep-Alive-Einstellung wird es bei langer Ruhe wieder
entladen.

## Weg A — das Ollama-Add-on (Home Assistant OS)

Das Community-Add-on [SirUli/homeassistant-ollama-addon](https://github.com/SirUli/homeassistant-ollama-addon)
betreibt das offizielle `ollama/ollama`-Image innerhalb von Home Assistant OS
und veröffentlicht die Ollama-API auf Host-Port 11434.

1. **Zuerst die Ressourcen prüfen.** Ein 4B-Modell braucht einen Host mit
   mindestens ~6 GB freiem RAM nach Abzug von Home Assistant und ~9 GB freiem
   Speicher (Image plus Modell). Vergrößere bei einer Proxmox-/ESXi-VM Disk
   und Arbeitsspeicher vorher — siehe die Fehlertabelle unten für das exakte
   Symptom, das du sonst bekommst.
2. Öffne in Home Assistant **Einstellungen → Add-ons → Add-on Store → ⋮ →
   Repositorys**, füge `https://github.com/SirUli/homeassistant-ollama-addon`
   hinzu und öffne den Store erneut.
3. Installiere das **Ollama**-Add-on. Der Image-Download umfasst mehrere
   Gigabyte; die Installation läuft auch dann im Hintergrund weiter, wenn eine
   UI-Anfrage abbricht.
4. Öffne die Add-on-**Konfiguration** und stelle ein:
   - **FlashAttention**: `1` — mit dem voreingestellten quantisierten V-Cache
     (`q8_0`) verweigern aktuelle Ollama-Versionen den Modellstart ohne ihn.
   - **Cloud**: `OLLAMA_NO_CLOUD` aktivieren, damit der Server nach dem
     Modell-Download niemals ollama.com kontaktieren kann.
   - Keep-alive `-1` hält das Modell dauerhaft im RAM (schnelle Berichte,
     konstanter höherer RAM-Verbrauch); ein positiver Wert in Sekunden entlädt
     es nach Ruhephasen.
5. **Starte** das Add-on.
6. **Ziehe ein Modell.** Das Add-on hat keine Modell-Verwaltungsoberfläche;
   nutze die API von einem beliebigen Rechner im Heimnetz (IP durch die deines
   Home-Assistant-Hosts ersetzen):

   ```bash
   curl -X POST http://192.0.2.20:11434/api/pull \
     -d '{"name": "gemma3:4b", "stream": false}'
   ```

   Unter Windows PowerShell:
   `Invoke-RestMethod -Method Post -Uri http://192.0.2.20:11434/api/pull -Body '{"name":"gemma3:4b"}'`.
   Der Download ist ~3,3 GB. Prüfe das Ergebnis mit
   `curl http://192.0.2.20:11434/api/tags`.

7. Fahre fort bei [Integration verbinden](#integration-verbinden) und nutze
   `http://<home-assistant-host-ip>:11434` als Basis-URL. Eine literale
   Heimnetz-IP ist Pflicht — siehe unten.

## Weg B — Docker auf einem anderen Rechner

Betreib Ollama dort, wo der RAM ist, auf jedem dauerhaft laufenden Rechner im
Heimnetz:

```bash
docker run -d --name ollama --restart unless-stopped \
  -p 11434:11434 \
  -e OLLAMA_NO_CLOUD=1 \
  -v ollama:/root/.ollama \
  ollama/ollama

docker exec -it ollama ollama pull gemma3:4b
```

Die Integration verbindet sich mit `http://<rechner-ip>:11434`. Publiziere
den Port auf der LAN-Schnittstelle (`-p 11434:11434`); Ollama bindet innerhalb
des Containers standardmäßig `0.0.0.0`.

## Weg C — ein bestehender Ollama-Server

Jede bestehende Installation funktioniert — Bare-Metal-Server, LXC-Container
auf Proxmox oder ein NAS-Paket. Zwei Dinge sind zu prüfen:

- **Lauschadresse:** Der Server muss Verbindungen vom Home-Assistant-Host
  annehmen, nicht nur von `127.0.0.1`. Der Systemd-Override ist
  `Environment="OLLAMA_HOST=0.0.0.0"` in
  `/etc/systemd/system/ollama.service.d/override.conf`.
- **Modell:** Ziehe dasselbe GGUF-Completion-Modell, das du in der Integration
  einträgst, z. B. `ollama pull gemma3:12b`.

## Modellwahl

| Modell | RAM-Bedarf | Tempo (CPU) | Qualität | Hinweise |
|--------|-----------|-------------|----------|----------|
| `gemma3:4b` | ~5 GB | ~1 Minute pro Bericht | Gut, schlichte Formulierungen | Integrations-Standard; passt in kleine VMs |
| `gemma3:12b` | ~9 GB | ~3 Minuten pro Bericht | Besseres Deutsch, bessere Struktur | Braucht einen eigenen Rechner |

Der Integrations-Standard ist `gemma3:4b`. Der eingetragene Modellname muss
exakt dem installierten Tag aus `/api/tags` entsprechen. Jedes GGUF-Modell mit
der Fähigkeit `completion` funktioniert; reine Embedding-Modelle werden mit
`ai_local_model_required` abgelehnt. Ein größeres Modell garantiert keine
zutreffenderen Erklärungen — der Zahlen-Guard prüft Werte, nicht Bedeutung.

## Integration verbinden

1. Öffne **Einstellungen → Geräte & Dienste → IDM Heatpump → Konfigurieren**.
2. Wähle **Experimenteller KI-Anlagenberater (schreibgeschützt)** und aktiviere
   ihn.
3. Stelle den **Berichts-Anbieter** auf `Ollama`, die **Lokale Ollama-
   Basis-URL** auf deinen Server und das **Installierte lokale Modell** auf den
   exakten Modell-Tag.
4. Aktiviere **freie, nicht vollständig überprüfbare KI-Erklärungen** — ohne
   diesen Schalter bleibt der Berater im Messwert-Modus und ruft nie ein
   Modell auf.
5. Speichern und auf dem Gerät *iDM KI-Anlagenberater* einen Berichts-Knopf
   drücken.

**Die Basis-URL muss eine literale private IP-Adresse sein** (`192.168.x.x`,
`10.x.x.x`, `172.16–31.x.x`) oder Loopback. Hostnamen wie
`http://myserver:11434` werden mit `invalid_ai_endpoint` abgelehnt, weil die
Integration niemals DNS auflöst — sonst würde aus einer geprüften Adresse
nachträglich eine ungeprüfte. Loopback (`http://127.0.0.1:11434`) bedeutet den
Home-Assistant-Host selbst und funktioniert nur, wenn HA direkt auf dem
Ollama-Server läuft (zum Beispiel Home Assistant Core im Docker neben
Ollama). Beim Add-on nutze die Heimnetz-IP des Home-Assistant-Hosts.

Berichte, Zeitpläne, Benachrichtigungen und der Qualitäts-Guard verhalten sich
genau wie auf der [Berater-Seite](Experimental-AI-Adviser) beschrieben; nur
der Modell-Endpunkt unterscheidet sich. Alles, was das Modell erhält, bleibt
in deinem Heimnetz.

## Fehlerbehebung

| Symptom | Ursache und Lösung |
|---------|--------------------|
| Add-on-Installation schlägt fehl, Log zeigt `no space left on device` | Die HAOS-Datenpartition ist zu klein: Image plus Modell brauchen ~9 GB. Disk vergrößern (z. B. `qm resize <vm> scsi0 +16G` auf Proxmox) und VM neu starten — HAOS vergrößert die Partition beim Boot automatisch. |
| Modellanfrage schlägt mit `quantized V cache requires flash_attn to be enabled` fehl | Die Add-on-Option **FlashAttention** steht auf `0`, während der V-Cache `q8_0` ist. FlashAttention auf `1` setzen (oder den Cache auf `f16`) und das Add-on neu starten. |
| `invalid_ai_endpoint` | Die Basis-URL ist keine literale LAN-/Loopback-IP oder enthält einen Pfad, Query, Port 0 oder Zugangsdaten. |
| `ai_local_model_required` | Das eingestellte Modell ist ein Embedding-Modell oder als Remote markiert; ein lokales GGUF-Completion-Modell ziehen und den exakten Tag übernehmen. |
| Bericht bricht nach fünf Minuten ab | Modell zu groß für die Hardware. Kleineres Modell verwenden, Modell resident halten (Keep-alive `-1`) oder CPU-Kerne ergänzen. |
| Erster Bericht deutlich langsamer als spätere | Modell-Ladezeit; mit dem Standard-Keep-alive entlädt Ollama Modelle nach fünf Minuten Ruhe. |
| Verbindung von HA abgewiesen, von anderem Rechner funktioniert | Ollama lauscht nur auf `127.0.0.1` — `OLLAMA_HOST=0.0.0.0` setzen (Docker: Port veröffentlichen). |

## Datenschutz-Zusammenfassung

Der Berater sendet nur die auf der [Berater-Seite](Experimental-AI-Adviser)
beschriebenen, allowlisteten Zahlenfakten an den konfigurierten Endpunkt —
einen Server in deinem Heimnetz. Setze `OLLAMA_NO_CLOUD=1` (Add-on-Option
**Cloud**), damit der Ollama-Server selbst nach dem Modell-Download nicht ins
Internet kann. Auf diesem Weg sind keine API-Schlüssel, Konten oder
Cloud-Dienste beteiligt.
