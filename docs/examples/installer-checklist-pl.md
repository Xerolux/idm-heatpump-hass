# Checklista dla instalatora — IDM Heatpump

Wszystko, czego potrzebuje integracja, włącza się na poziomie instalatora regulatora. Wydrukuj tę stronę i przekaż ją swojemu instalatorowi.

## 1. Sieć

- ☐ Stały adres IP dla Navigatora (rezerwacja DHCP lub statycznie) — IP: ____________
- ☐ Navigator i Home Assistant w tej samej sieci lokalnej
- ☐ **Bez** przekierowania portów 502, 80 i 61220

## 2. Modbus (wymagane)

- ☐ **Zarządzanie budynkiem (Gebäudeleittechnik) → Modbus TCP → On**
- ☐ Port TCP: zwykle **502**
- ☐ ID slave/jednostki: zwykle **1**
- ☐ Zegar regulatora pokazuje poprawny czas lokalny

## 3. PV / GLT (opcjonalne)

- ☐ Źródło sygnału PV = **Zarządzanie budynkiem / Smartfox**
- ☐ Rejestry wejściowe GLT zwolnione (74–86: nadmiar, produkcja PV, zużycie, bateria, SOC)
- ☐ Żaden inny menedżer energii nie zapisuje tych samych rejestrów

## 4. Lokalny interfejs web (opcjonalny)

- ☐ PIN web/sieciowy ustawiony i przekazany — PIN: ____________
- ☐ Interfejs web osiągalny (HTTP 80; Navigator 10 dodatkowo WebSocket 61220)

## 5. Dane instalacji (odczytuje instalator)

| Dana | Wartość |
|---|---|
| Generacja Navigatora (1.0 / 1.7 / 2.0 / Pro / 10) | ____________ |
| Wersja oprogramowania/firmware | ____________ |
| Numer schematu instalacji (np. L7.1) | ____________ |
| Aktywne obiegi grzewcze (A–G) | ____________ |
| Moduły strefowe i pomieszczenia | ____________ |
| Kaskada? Liczba jednostek | ____________ |
| Solar termiczny / ISC? | ____________ |

Integracja **nie wymaga**: dostępu do chmury ani konta myIDM, przekierowania portów ani odblokowywania menu instalatora.
