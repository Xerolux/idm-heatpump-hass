"""Human-readable labels for IDM internal message codes."""

from __future__ import annotations

_INTERNAL_MESSAGE_TEXTS: dict[int, str] = {
    0: "Keine Meldung",
    20: "Waermepumpenvorlauf Maximaltemperatur",
    21: "Waermepumpenvorlauf Minimaltemperatur",
    22: "Niederdruckstoerung",
    23: "Niederdruckstoerung",
    24: "Hochdruckstoerung",
    25: "Hochdruckstoerung",
    26: "Stroemungsueberwachung",
    27: "Stroemungsueberwachung",
    28: "Anlaufstrombegrenzer",
    29: "Anlaufstrombegrenzer",
    30: "Motorschutz Waermequellenpumpe",
    31: "Motorschutz Waermequellenpumpe",
    32: "Maximale Abtauzeit ueberschritten",
    33: "Minimale Kondensatortemperatur unterschritten",
    34: "Ventilatorfehler",
    35: "Minimale Waermepumpen- oder Waermespeichertemperatur",
    36: "E-Heizstab Ueberhitzung",
    37: "Stoerung Ladepumpe",
    38: "Ventilatorfehler",
    42: "Stoerung Heissgas",
    43: "Stoerung Heissgas",
    44: "Stoerung Durchflussueberwachung Heizungsseite",
    46: "Stoerung Heissgas",
    47: "Stoerung Heissgas",
    48: "Stroemungsueberwachung",
    49: "Stroemungsueberwachung",
    50: "Taupunktwaechter angesprochen",
    51: "Taupunktwaechter angesprochen",
    54: "Durchflussueberwachung heizungsseitig fehlerhaft",
    55: "Durchflussueberwachung heizungsseitig fehlerhaft",
    56: "Minimale Kondensatortemperatur unterschritten",
    57: "Minimale Waermepumpen- oder Waermespeichertemperatur",
    58: "Hochdruckstoerung im Warmwasserbetrieb mit AQA",
    59: "Hochdruckstoerung im Warmwasserbetrieb mit AQA",
    60: "Waermequellentemperaturfehler",
    61: "Waermequellentemperaturfehler",
    62: "Wicklungsschutz",
    63: "Wicklungsschutz",
    67: "Waermequellentemperaturfehler",
    69: "Waermequellenrueckspeisetemperatur zu hoch",
    74: "Anlaufstrombegrenzer",
    75: "Anlaufstrombegrenzer",
    95: "Einsatzgrenzenstoerung",
    96: "Einsatzgrenzenstoerung",
    203: "Solar-Log Update erforderlich",
    221: "Niederdruckstoerung",
    231: "Niederdruckstoerung",
    232: "Maximale Abtauzeit ueberschritten",
    233: "Minimale Kondensatortemperatur unterschritten",
    234: "Ventilatorfehler",
    235: "Minimale Waermepumpen- oder Waermespeichertemperatur",
    236: "Sicherheitsabtauintervall zu kurz",
    237: "Stoerung Ladepumpe",
    238: "Ventilatorfehler",
    239: "Batteriefehler",
    240: "Stoerung Spannungsversorgung",
    241: "Hochdruckstoerung",
    242: "Stoerung Heissgas",
    243: "Stoerung Heissgas",
    244: "Stoerung Durchflussueberwachung Heizungsseite",
    246: "Stoerung Heissgas",
    247: "Stoerung Heissgas",
    251: "Hochdruckstoerung",
    256: "Minimale Kondensatortemperatur unterschritten",
    257: "Minimale Waermepumpen- oder Waermespeichertemperatur",
    262: "Wicklungsschutz",
    263: "Wicklungsschutz",
    265: "Estrich heizen abgebrochen / Solltemperatur nicht erreicht",
    270: "Waermepumpe verriegelt",
    271: "Bivalenz manuell aktiviert",
    272: "Waermepumpe verriegelt - Bivalenz im Notbetrieb aktiv",
    280: "Kollektor Maximaltemperatur",
    281: "Hygienik Maximaltemperatur",
    282: "Waermespeicher Maximaltemperatur",
    283: "Waermequellen Maximaltemperatur",
    284: "Solarmodul nicht vorhanden",
    285: "Minimale Ladetemperatur unterschritten",
    286: "ISC-Modul nicht gefunden",
    287: "Stoerung Kaeltespeicherpumpe",
    288: "Stoerung Rueckkuehlpumpe",
    289: "Stoerung Rueckkuehlfuehler",
    290: "Stoerung Rueckkuehlfuehler",
    291: "Maximale Rueckkuehltemperatur unterschritten",
    293: "Minimale Waermequellenaustrittstemperatur iDM Systemkuehlung",
    295: "Einsatzgrenzenstoerung",
    296: "Einsatzgrenzenstoerung",
    301: "Boostfunktion - Temperatur nicht erreicht",
    302: "Legionellenfunktion - Temperatur nicht erreicht",
    400: "Kommunikation Kaskade",
}

_INTERNAL_MESSAGE_RANGES: tuple[tuple[range, str], ...] = (
    (range(100, 200), "Fuehlerstoerung"),
    (range(305, 315), "Stoerung bei gemeinsamer Waermequelle"),
    (range(516, 533), "Kommunikations- oder Inverterstoerung"),
)


def _message_code(code: int | float | str | None) -> int | None:
    if code is None:
        return None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def internal_message_text(code: int | float | str | None) -> str | None:
    """Return a readable label for an IDM internal message code."""
    message_code = _message_code(code)
    if message_code is None:
        return None
    if message_code in _INTERNAL_MESSAGE_TEXTS:
        return _INTERNAL_MESSAGE_TEXTS[message_code]
    for code_range, text in _INTERNAL_MESSAGE_RANGES:
        if message_code in code_range:
            return text
    return "Unbekannte Meldung - siehe Navigator-Handbuch"


def format_internal_message(code: int | float | str | None) -> str | None:
    """Return a stable state string for the internal message entity."""
    text = internal_message_text(code)
    if text is None:
        return None
    message_code = _message_code(code)
    if message_code is None:
        return None
    return f"{message_code:03d} - {text}"
