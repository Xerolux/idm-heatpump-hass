# Listă de verificare pentru instalator — IDM Heatpump

Tot ce are nevoie integrarea se activează la nivelul de instalator al regulatorului. Printează această pagină și predă-o instalatorului tău.

## 1. Rețea

- ☐ Adresă IP fixă pentru Navigator (rezervare DHCP sau statică) — IP: ____________
- ☐ Navigator și Home Assistant în aceeași rețea locală
- ☐ **Fără** port forwarding pentru porturile 502, 80 și 61220

## 2. Modbus (obligatoriu)

- ☐ **Managementul clădirii (Gebäudeleittechnik) → Modbus TCP → On**
- ☐ Port TCP: de regulă **502**
- ☐ ID slave/unitate: de regulă **1**
- ☐ Ceasul regulatorului arată ora locală corectă

## 3. FV / GLT (opțional)

- ☐ Sursa semnalului FV = **Managementul clădirii / Smartfox**
- ☐ Registrele de intrare GLT eliberate (74–86: surplus, producție FV, consum, baterie, SOC)
- ☐ Niciun alt manager de energie nu scrie aceleași registre

## 4. Interfața web locală (opțional)

- ☐ PIN web/rețea setat și predat — PIN: ____________
- ☐ Interfața web accesibilă (HTTP 80; Navigator 10 suplimentar WebSocket 61220)

## 5. Datele instalației (le citește instalatorul)

| Date | Valoare |
|---|---|
| Generația Navigator (1.0 / 1.7 / 2.0 / Pro / 10) | ____________ |
| Versiunea software/firmware | ____________ |
| Numărul schemei instalației (ex. L7.1) | ____________ |
| Circuite de încălzire active (A–G) | ____________ |
| Module de zonă și camere | ____________ |
| Cascadă? Număr de unități | ____________ |
| Solar termic / ISC? | ____________ |

Integrarea **nu** necesită: acces cloud sau cont myIDM, port forwarding sau deblocarea meniurilor de instalator.
