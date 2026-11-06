# IDM Heatpump per Home Assistant — Italiano

> 🇬🇧 [English README](README.md) · 🇩🇪 [Deutsche README](README_de.md) · 🇪🇸 [Español](README_es.md) · 🇮🇹 Italiano · 🇷🇴 [Română](README_ro.md) · 🇨🇿 [Čeština](README_cs.md) · 🇵🇱 [Polski](README_pl.md)

Integrazione locale e gratuita per Home Assistant per pompe di calore IDM con regolatore **Navigator 1.0 / 1.7 / 2.0 / 10 / Pro**, tramite **Modbus TCP** e l'interfaccia web locale del Navigator. Nessuna nube, 100 % locale.

**L'interfaccia dell'integrazione è disponibile in:** Deutsch, English, Español, Italiano, Română, Čeština, Polski — Home Assistant sceglie la lingua automaticamente. (La documentazione web completa esiste in inglese e tedesco; questa pagina è un riassunto.)

## Funzioni principali

| | Funzione |
|---|---|
| 🌡️ | **Telemetria completa** via Modbus: temperature, stati, pompe, contatori di energia |
| 🎛️ | **Controllo**: modalità di sistema, consegne acqua calda, curve di riscaldamento, modalità per circuito e per ambiente |
| 🔋 | **Inoltro energia esterna** (surplus FV, produzione, consumo, batteria) verso i registri GLT del Navigator |
| 🧠 | **Consulente predittivo** (sola lettura): spiega perché funziona, rileva anomalie, consiglia interventi sulla curva |
| 🌐 | **Supplemento web locale**: valori che Modbus non ha (motivo della richiesta, testi dei messaggi, statistiche) |
| 🖨️ | **KNX**: serve i 654 oggetti KNX di IDM tramite l'integrazione KNX di Home Assistant |
| 🔒 | **Sicurezza in scrittura**: validazione degli intervalli, protezione EEPROM, nessuna scrittura non documentata |

## Installazione (HACS)

1. Aggiungi questo repository a HACS come integrazione personalizzata.
2. Il tuo installatore attiva **Modbus TCP** sul Navigator (*Gestione edificio → Modbus TCP → On*, IP fissa, porta 502).
3. Home Assistant → *Impostazioni → Dispositivi e servizi → Aggiungi integrazione* → **IDM Heatpump**.
4. La procedura rileva l'impianto (modello, circuiti, zone) e configura tutto in modo guidato.

## Note

- Richiede Home Assistant **2026.11** o successivo.
- Documentazione completa: [docs.xerolux.dev → IDM Heatpump](https://xerolux.github.io/idm-heatpump-hass/) (EN/DE).
- Problemi? Apri un'[issue](https://github.com/Xerolux/idm-heatpump-hass/issues) allegando il rapporto diagnostico.

---

*Progetto comunitario non ufficiale, non affiliato a iDM Energiesysteme GmbH. IDM e Navigator sono marchi dei rispettivi proprietari.*
