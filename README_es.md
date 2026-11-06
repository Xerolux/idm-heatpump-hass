# IDM Heatpump für Home Assistant — Español

> 🇬🇧 [English README](README.md) · 🇩🇪 [Deutsche README](README_de.md) · 🇪🇸 Español · 🇮🇹 [Italiano](README_it.md) · 🇷🇴 [Română](README_ro.md) · 🇨🇿 [Čeština](README_cs.md) · 🇵🇱 [Polski](README_pl.md)

Integración local y gratuita de Home Assistant para bombas de calor IDM con control **Navigator 1.0 / 1.7 / 2.0 / 10 / Pro**, vía **Modbus TCP** y la interfaz web local del Navigator. Sin nube, 100 % local.

**La interfaz de la integración está disponible en:** Deutsch, English, Español, Italiano, Română, Čeština, Polski — Home Assistant elige el idioma automáticamente. (La documentación web completa existe en inglés y alemán; esta página es un resumen.)

## Funciones principales

| | Función |
|---|---|
| 🌡️ | **Telemetría completa** por Modbus: temperaturas, estados, bombas, contadores de energía |
| 🎛️ | **Control**: modo del sistema, consignas de agua caliente, curvas de calefacción, modos por circuito y por sala |
| 🔋 | **Reenvío de energía exterior** (excedente FV, producción, consumo, batería) a los registros GLT del Navigator |
| 🧠 | **Asesor predictivo** (solo lectura): explica por qué funciona, detecta anomalías, recomienda pasos de curva |
| 🌐 | **Suplemento web local**: valores que Modbus no tiene (motivo de demanda, textos de mensajes, estadísticas) |
| 🖨️ | **KNX**: sirve los 654 objetos KNX de IDM a través de la integración KNX de Home Assistant |
| 🔒 | **Seguridad de escritura**: validación de rangos, protección EEPROM, sin escrituras no documentadas |

## Instalación (HACS)

1. Añade este repositorio a HACS como integración personalizada.
2. Tu instalador activa **Modbus TCP** en el Navigator (*Gestión del edificio → Modbus TCP → On*, IP fija, puerto 502).
3. Home Assistant → *Ajustes → Dispositivos y servicios → Añadir integración* → **IDM Heatpump**.
4. El asistente detecta la instalación (modelo, circuitos, zonas) y configura todo guiado.

## Notas

- Requiere Home Assistant **2026.11** o más reciente.
- Configuración y documentación completas: [docs.xerolux.dev → IDM Heatpump](https://xerolux.github.io/idm-heatpump-hass/) (EN/DE).
- ¿Problemas? Abre un [issue](https://github.com/Xerolux/idm-heatpump-hass/issues) con el informe de diagnóstico.

---

*Proyecto comunitario no oficial sin relación con iDM Energiesysteme GmbH. IDM y Navigator son marcas de sus respectivos propietarios.*
