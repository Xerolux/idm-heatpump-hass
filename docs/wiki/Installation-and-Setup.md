# Installation & Setup

## Requirements

- **Home Assistant** 2026.5.0 or newer
- **HACS** ([Installation guide](https://hacs.xyz/docs/setup/download))
- **IDM Navigator 2.0** heat pump with Modbus TCP enabled
- Modbus TCP must be enabled in the Navigator controller (Port 502, Slave ID 1)

## Enable Modbus TCP on the Navigator

1. Open the Navigator web interface (ip-of-your-navigator)
2. Go to **Settings → Communication → Modbus TCP**
3. Enable Modbus TCP
4. Note the **IP address** and **port** (default: 502)
5. Slave ID is usually **1**

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

## Setup

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **"IDM Heatpump"**
4. Follow the configuration wizard:
   - **Step 1**: Enter IP address, port (502), and name
   - **Step 2**: Scan interval, heating circuits (A-G), number of zones
   - **Step 3**: Configure room names for zones
5. Click **Finish**

## Uninstallation

1. Go to **Settings → Devices & Services**
2. Find the **IDM Heatpump** integration
3. Click the three dots → **Delete**
4. (Optional) Delete the `custom_components/idm_heatpump/` folder
5. Restart Home Assistant

## Upgrade

Via HACS: Go to HACS → Integrations → IDM Heatpump → "Update" → Restart HA.

Manually: Repeat the manual installation (overwrites the old files).
