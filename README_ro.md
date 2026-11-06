# IDM Heatpump pentru Home Assistant — Română

> 🇬🇧 [English README](README.md) · 🇩🇪 [Deutsche README](README_de.md) · 🇪🇸 [Español](README_es.md) · 🇮🇹 [Italiano](README_it.md) · 🇷🇴 Română · 🇨🇿 [Čeština](README_cs.md) · 🇵🇱 [Polski](README_pl.md)

Integrare locală și gratuită pentru Home Assistant pentru pompe de căldură IDM cu regulator **Navigator 1.0 / 1.7 / 2.0 / 10 / Pro**, prin **Modbus TCP** și interfața web locală a Navigator. Fără cloud, 100 % local.

**Interfața integrării este disponibilă în:** Deutsch, English, Español, Italiano, Română, Čeština, Polski — Home Assistant alege limba automat. (Documentația web completă există în engleză și germană; această pagină este un rezumat.)

## Funcții principale

| | Funcție |
|---|---|
| 🌡️ | **Telemetrie completă** prin Modbus: temperaturi, stări, pompe, contori de energie |
| 🎛️ | **Control**: modul sistemului, consecințe apă caldă, curbe de încălzire, moduri pe circuit și pe cameră |
| 🔋 | **Redirecționare energie exterioară** (surplus FV, producție, consum, baterie) către registrele GLT ale Navigator |
| 🧠 | **Consultant predictiv** (doar citire): explică de ce funcționează, detectează anomalii, recomandă pași ai curbei |
| 🌐 | **Supliment web local**: valori pe care Modbus nu le are (motivul cererii, textele mesajelor, statistici) |
| 🖨️ | **KNX**: servește cele 654 de obiecte KNX IDM prin integrarea KNX din Home Assistant |
| 🔒 | **Siguranța scrierii**: validarea intervalelor, protecție EEPROM, fără scrieri nedocumentate |

## Instalare (HACS)

1. Adaugă acest repositoriu în HACS ca integrare personalizată.
2. Instalatorul tău activează **Modbus TCP** pe Navigator (*Managementul clădirii → Modbus TCP → On*, IP fix, portul 502).
3. Home Assistant → *Setări → Dispozitive și servicii → Adaugă integrare* → **IDM Heatpump**.
4. Asistentul detectează instalația (model, circuite, zone) și configurează totul ghidat.

## Note

- Necesită Home Assistant **2026.11** sau mai nou.
- Documentația completă: [docs.xerolux.dev → IDM Heatpump](https://xerolux.github.io/idm-heatpump-hass/) (EN/DE).
- Probleme? Deschide un [issue](https://github.com/Xerolux/idm-heatpump-hass/issues) cu raportul de diagnostic.

---

*Proiect comunitar neoficial, neafiliat iDM Energiesysteme GmbH. IDM și Navigator sunt mărci ale proprietarilor respectivi.*
