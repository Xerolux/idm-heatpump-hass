# Checklist pro instalatéra — IDM Heatpump

Vše, co integrace potřebuje, se aktivuje na úrovni instalatéra regulátoru. Vytiskněte tuto stránku a předejte ji svému instalatérovi.

## 1. Síť

- ☐ Pevná IP adresa pro Navigator (rezervace DHCP nebo staticky) — IP: ____________
- ☐ Navigator a Home Assistant ve stejné místní síti
- ☐ **Žádné** přesměrování portů 502, 80 a 61220

## 2. Modbus (povinné)

- ☐ **Řízení budovy (Gebäudeleittechnik) → Modbus TCP → On**
- ☐ TCP port: obvykle **502**
- ☐ ID slave/jednotky: obvykle **1**
- ☐ Hodiny regulátoru ukazují správný místní čas

## 3. FVE / GLT (volitelné)

- ☐ Zdroj signálu FVE = **Řízení budovy / Smartfox**
- ☐ Vstupní registry GLT uvolněny (74–86: přebytek, výroba FVE, spotřeba, baterie, SOC)
- ☐ Žádný jiný energetický manažer nezapisuje stejné registry

## 4. Místní webové rozhraní (volitelné)

- ☐ Web/síťový PIN nastaven a předán — PIN: ____________
- ☐ Webové rozhraní dostupné (HTTP 80; Navigator 10 navíc WebSocket 61220)

## 5. Údaje o instalaci (přečte instalatér)

| Údaj | Hodnota |
|---|---|
| Generace Navigatoru (1.0 / 1.7 / 2.0 / Pro / 10) | ____________ |
| Verze softwaru/firmware | ____________ |
| Číslo schématu systému (např. L7.1) | ____________ |
| Aktivní topné okruhy (A–G) | ____________ |
| Zónové moduly a místnosti | ____________ |
| Kaskáda? Počet jednotek | ____________ |
| Solární termika / ISC? | ____________ |

Integrace **nevyžaduje**: přístup do cloudu ani účet myIDM, přesměrování portů ani odemykání instalatérských menu.
