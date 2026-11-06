# IDM Heatpump dla Home Assistant — Polski

> 🇬🇧 [English README](README.md) · 🇩🇪 [Deutsche README](README_de.md) · 🇪🇸 [Español](README_es.md) · 🇮🇹 [Italiano](README_it.md) · 🇷🇴 [Română](README_ro.md) · 🇨🇿 [Čeština](README_cs.md) · 🇵🇱 Polski

Lokalna i bezpłatna integracja dla Home Assistant dla pomp ciepła IDM z regulatorem **Navigator 1.0 / 1.7 / 2.0 / 10 / Pro**, przez **Modbus TCP** i lokalny interfejs web Navigatora. Bez chmury, 100 % lokalnie.

**Interfejs integracji jest dostępny w językach:** Deutsch, English, Español, Italiano, Română, Čeština, Polski — Home Assistant wybiera język automatycznie. (Pełna dokumentacja web istnieje po angielsku i niemiecku; ta strona to podsumowanie.)

## Główne funkcje

| | Funkcja |
|---|---|
| 🌡️ | **Pełna telemetria** przez Modbus: temperatury, stany, pompy, liczniki energii |
| 🎛️ | **Sterowanie**: tryb systemu, nastawy ciepłej wody, krzywe grzewcze, tryby per obieg i pomieszczenie |
| 🔋 | **Przekazywanie zewnętrznej mocy** (nadmiar PV, produkcja, zużycie, bateria) do rejestrów GLT Navigatora |
| 🧠 | **Predykcyjny doradca** (tylko odczyt): wyjaśnia, dlaczego pompa pracuje, wykrywa anomalie, zaleca kroki krzywej |
| 🌐 | **Lokalny dodatek web**: wartości, których Modbus nie ma (powód żądania, teksty komunikatów, statystyki) |
| 🖨️ | **KNX**: obsługuje wszystkie 654 obiekty KNX IDM przez integrację KNX w Home Assistant |
| 🔒 | **Bezpieczeństwo zapisu**: walidacja zakresów, ochrona EEPROM, żadnych nieudokumentowanych zapisów |

## Instalacja (HACS)

1. Dodaj to repozytorium do HACS jako integrację niestandardową.
2. Twój instalator włącza **Modbus TCP** na Navigatorze (*Zarządzanie budynkiem → Modbus TCP → On*, stały adres IP, port 502).
3. Home Assistant → *Ustawienia → Urządzenia i usługi → Dodaj integrację* → **IDM Heatpump**.
4. Kreator wykrywa instalację (model, obiegi, strefy) i konfiguruje wszystko krok po kroku.

## Uwagi

- Wymaga Home Assistant **2026.11** lub nowszego.
- Pełna dokumentacja: [docs.xerolux.dev → IDM Heatpump](https://xerolux.github.io/idm-heatpump-hass/) (EN/DE).
- Problemy? Otwórz [issue](https://github.com/Xerolux/idm-heatpump-hass/issues) z raportem diagnostycznym.

---

*Nieoficjalny projekt społecznościowy, niezwiązany z iDM Energiesysteme GmbH. IDM i Navigator są znakami towarowymi odpowiednich właścicieli.*
