# Installation & Setup

## Requirements

- **Home Assistant** 2026.5.0 or newer
- **HACS** ([Installation guide](https://hacs.xyz/docs/setup/download))
- **IDM Navigator 2.0 / 10 / Pro** heat pump with Modbus TCP enabled
- Modbus TCP must be enabled in the Navigator controller (Port 502, Slave ID 1)

## Installation via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click **⋮ (Three Dots)** → **Custom Repositories**
4. Enter the URL: `https://github.com/Xerolux/idm-heatpump-hass`
5. Select **Category: Integration**
6. Click **Add**
7. Search for **"IDM Heatpump"**
8. Click **Download**
9. **Restart Home Assistant**

## Manual Installation

1. Download the latest [release](https://github.com/Xerolux/idm-heatpump-hass/releases) (`idm_heatpump.zip`)
2. Extract the ZIP file
3. Copy the `idm_heatpump` folder to your `custom_components/` directory:
   ```
   <ha-config>/custom_components/idm_heatpump/
   ```
4. Restart Home Assistant

## Enable Modbus TCP on the IDM heat pump

> **Required:** Full integration operation is only possible when Modbus TCP is
> enabled on the IDM Navigator/controller. Installing the Home Assistant
> integration cannot enable this controller setting remotely.

The official iDM documentation describes the relevant Navigator setting as
**Building management system / Gebäudeleittechnik → Modbus TCP → On / Ein**.
A practical setup sequence is:

1. Open the local IDM Navigator/controller display.
2. Sign in to installer/technician level if the controller requires it.
3. Open **Building management system** (German: **Gebäudeleittechnik**).
4. Set **Modbus TCP** to **On / Enabled** (German: **Ein / Aktiv**).
5. Save the setting. Restart the Navigator/controller if the interface does
   not become available immediately.
6. Connect the Navigator to the local Ethernet network and note its IP address.
7. Use **TCP port 502** and normally **slave/unit ID 1** in this integration.

Menu names and permissions can differ between Navigator 2.0, Navigator 10,
Navigator Pro and firmware versions. If **Gebäudeleittechnik** or **Modbus TCP**
is missing, read-only, or locked, ask your heating installer or iDM service to
enable the interface. Do not change unrelated heating or safety parameters.

The required setting belongs to the **IDM heat pump/Navigator**. A Modbus TCP
option on a PV inverter is a separate interface and does not enable Home
Assistant access to the heat pump.

Network checklist:

- Home Assistant and the Navigator must be able to reach each other locally.
- Prefer wired Ethernet; do not expose port 502 to the internet.
- Reserve the Navigator IP in the router or configure it consistently so it
  does not unexpectedly change.
- Test the address from Home Assistant's network, not only from a phone on a
  different Wi-Fi/VLAN.

Source: [official iDM technical documentation (PDF)](https://www.idm-energie.at/wp-content/uploads/2021/04/PV_Nutzung_GLT-Smartfox.pdf),
which specifies that **Modbus TCP** must be **On** in the Navigator's
**Gebäudeleittechnik** menu; iDM also documents TCP port 502 for Navigator
Modbus communication in its [technical PV/GLT documentation](https://www.idm-energie.at/wp-content/uploads/2021/04/tu_de_812184_myiDMenergy_PV_Variable-Stromtarife_Navigator-2.0-1.pdf).

## Setup

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **"IDM Heatpump"**
4. Follow the configuration wizard:
   - **Prerequisite shown in the flow**: Confirm that Navigator **Building management system → Modbus TCP** is enabled
   - **Connection**: Enter a name, the heat pump IP/hostname, port 502, and slave ID 1
   - **Optional web access**: Enter the local Navigator web PIN; when using a Modbus proxy, also enable the proxy option and enter the original heat pump address as web host
   - **Components**: Select scan interval, heating circuits (A-G), and number of zones
   - **Optional features**: Configure web data, cascade, room-temperature forwarding, and advanced Modbus timeout/retries in the grouped sections
   - **Zones**: Configure the number of active rooms for each selected zone module
5. Click **Finish**

### Local Navigator web PIN (not cloud 2FA)

The optional web PIN is the **local network code configured on the Navigator
display**. It is separate from the myIDM app/cloud account, its password and
two-factor authentication.

On a German Navigator 2.0 display, configure it under:

**Einstellungen → Allgemeine Einstellungen → Netzwerkeinstellungen → Code
lokales Netzwerk**

Menu wording can vary by Navigator generation and firmware. An empty value or
`0` disables the local web interface. Entering cloud credentials or a temporary
two-factor code in Home Assistant will therefore be rejected.

## Setup validation and error messages

The setup and reconfigure flows read a known IDM register. If that fails, a
short DNS/TCP check separates network failures from a reachable endpoint that
does not provide usable Modbus data. This allows Home Assistant to provide a
more useful cause instead of a generic connection error:

| Message | Meaning | What to check |
|---------|---------|---------------|
| Hostname not found | Local DNS/mDNS cannot resolve the entered name | Typing, local DNS, or use the heat pump IP |
| Connection refused | A device answered but rejected TCP | Modbus TCP is usually disabled, or the port is not 502 |
| Connection timed out | No TCP answer within 5 seconds | Wrong IP, powered-off controller, firewall, VLAN, or routing |
| Endpoint unreachable | The operating system cannot route to the address | Network/subnet/gateway configuration |
| No valid IDM register response | TCP works, but the Modbus probe failed | Slave ID (usually 1), proxy target, Modbus permission/activation |
| Web PIN rejected | Navigator web authentication failed | Correct the local PIN directly in the flow |
| Web interface unavailable | A PIN was supplied but web data cannot be read | Original web host, network access; clear PIN for Modbus-only mode |

The logs include host, port, slave ID, error class, and the recommended checks.
PIN values are never written to the log.

## Test the saved connection later

Open **Settings → Devices & Services → IDM Heatpump → Reconfigure → Test
current connection**. The test checks the saved Modbus endpoint and, when a
local web PIN is configured, the Navigator web endpoint. It is read-only: no
settings are saved and no heat-pump registers are written. The result can be
submitted again to repeat the test after correcting a network or controller
setting.

## Uninstallation

1. Go to **Settings → Devices & Services**
2. Find the **IDM Heatpump** integration
3. Click the three dots → **Delete**
4. (Optional) Delete the `custom_components/idm_heatpump/` folder
5. Restart Home Assistant

## Upgrade

Via HACS: Go to HACS → Integrations → IDM Heatpump → "Update" → Restart HA.

Manually: Repeat the manual installation (overwrites the old files).
