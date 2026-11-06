# IDM Heatpump pro Home Assistant — Česky

> 🇬🇧 [English README](README.md) · 🇩🇪 [Deutsche README](README_de.md) · 🇪🇸 [Español](README_es.md) · 🇮🇹 [Italiano](README_it.md) · 🇷🇴 [Română](README_ro.md) · 🇨🇿 Čeština · 🇵🇱 [Polski](README_pl.md)

Místní a bezplatná integrace pro Home Assistant pro tepelná čerpadla IDM s regulátorem **Navigator 1.0 / 1.7 / 2.0 / 10 / Pro**, přes **Modbus TCP** a místní webové rozhraní Navigatoru. Bez cloudu, 100 % lokálně.

**Rozhraní integrace je k dispozici v jazycích:** Deutsch, English, Español, Italiano, Română, Čeština, Polski — Home Assistant jazyk vybere automaticky. (Úplná webová dokumentace existuje v angličtině a němčině; tato stránka je shrnutí.)

## Hlavní funkce

| | Funkce |
|---|---|
| 🌡️ | **Kompletní telemetrie** přes Modbus: teploty, stavy, čerpadla, energetické měřiče |
| 🎛️ | **Řízení**: režim systému, nastavení teplé vody, otopné křivky, režimy per okruh a místnost |
| 🔋 | **Přeposílání vnějšího výkonu** (přebytek FVE, výroba, spotřeba, baterie) do registrů GLT Navigatoru |
| 🧠 | **Prediktivní poradce** (jen čtení): vysvětluje, proč čerpadlo běží, detekuje anomálie, doporučuje kroky křivky |
| 🌐 | **Místní webový doplněk**: hodnoty, které Modbus nemá (důvod požadavku, texty zpráv, statistiky) |
| 🖨️ | **KNX**: obsluhuje všech 654 objektů KNX IDM přes integraci KNX v Home Assistant |
| 🔒 | **Bezpečnost zápisu**: validace rozsahů, ochrana EEPROM, žádné nedokumentované zápisy |

## Instalace (HACS)

1. Přidejte tento repozitář do HACS jako vlastní integraci.
2. Váš instalatér zapne **Modbus TCP** na Navigatoru (*Řízení budovy → Modbus TCP → On*, pevná IP, port 502).
3. Home Assistant → *Nastavení → Zařízení a služby → Přidat integraci* → **IDM Heatpump**.
4. Průvodce detekuje instalaci (model, okruhy, zóny) a vše nastaví průvodcem.

## Poznámky

- Vyžaduje Home Assistant **2026.11** nebo novější.
- Úplná dokumentace: [docs.xerolux.dev → IDM Heatpump](https://xerolux.github.io/idm-heatpump-hass/) (EN/DE).
- Problémy? Otevřete [issue](https://github.com/Xerolux/idm-heatpump-hass/issues) s diagnostickou zprávou.

---

*Neoficiální komunitní projekt, nepříbuzný se společností iDM Energiesysteme GmbH. IDM a Navigator jsou ochranné známky příslušných vlastníků.*
