# Lista de comprobación para el instalador — IDM Heatpump

Todo lo que la integración necesita se activa en el nivel de instalador del regulador. Imprime esta página y entrégasela a tu instalador.

## 1. Red

- ☐ Dirección IP fija para el Navigator (reserva DHCP o estática) — IP: ____________
- ☐ Navigator y Home Assistant en la misma red local
- ☐ **Sin** port forwarding para los puertos 502, 80 y 61220

## 2. Modbus (obligatorio)

- ☐ **Gestión del edificio (Gebäudeleittechnik) → Modbus TCP → On**
- ☐ Puerto TCP: normalmente **502**
- ☐ Slave/Unit ID: normalmente **1**
- ☐ El reloj del regulador muestra la hora local correcta

## 3. PV / GLT (opcional)

- ☐ Fuente de señal PV = **Gestión del edificio / Smartfox**
- ☐ Registros de entrada GLT liberados (74–86: excedente, producción FV, consumo, batería, SOC)
- ☐ Ningún otro gestor de energía escribe los mismos registros

## 4. Interfaz web local (opcional)

- ☐ PIN web/red configurado y entregado — PIN: ____________
- ☐ Interfaz web accesible (HTTP 80; Navigator 10 además WebSocket 61220)

## 5. Datos de la instalación (los lee el instalador)

| Dato | Valor |
|---|---|
| Generación del Navigator (1.0 / 1.7 / 2.0 / Pro / 10) | ____________ |
| Versión de software/firmware | ____________ |
| Número de esquema del sistema (p. ej. L7.1) | ____________ |
| Circuitos de calefacción activos (A–G) | ____________ |
| Módulos de zona y habitaciones | ____________ |
| ¿Cascada? Número de unidades | ____________ |
| ¿Solar térmica / ISC? | ____________ |

La integración **no** necesita: acceso a la nube ni cuenta myIDM, port forwarding ni desbloqueo de menús de instalador.
