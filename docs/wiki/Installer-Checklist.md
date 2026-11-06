# Installer Checklist

Everything the integration needs for full operation is enabled at the
controller's **installer level by your heating installer** — the integration
itself never unlocks anything and needs no access code. Print this page
(browser print dialog, *Destination → Save as PDF*) and hand it to your
installer; every item can be ticked off in a few minutes on site.

## 1. Network

| ☐ | Item | Notes / value |
|---|------|---------------|
| ☐ | Fixed IP address for the Navigator (DHCP reservation in the router or static on the controller) | IP: ______________________ |
| ☐ | Navigator and Home Assistant reach each other in the same local network | |
| ☐ | **No** port forwarding or internet exposure for ports 502, 80 and 61220 — everything stays local | |

## 2. Modbus — required, the backbone

| ☐ | Item | Notes / value |
|---|------|---------------|
| ☐ | **Building management system (Gebäudeleittechnik) → Modbus TCP → On / Ein** | |
| ☐ | TCP port left at the default | normally **502** |
| ☐ | Slave/unit ID | normally **1** |
| ☐ | Controller clock shows the correct local date and time | |

## 3. PV / GLT — optional: PV surplus, battery, external room sensors

| ☐ | Item | Notes |
|---|------|-------|
| ☐ | PV signal source set to **Building management / Smartfox** (no native inverter polling by the controller) | |
| ☐ | GLT input registers released (74–86: surplus, PV production, house consumption, battery power, battery SOC) | |
| ☐ | No other energy manager writes to the same GLT registers | |

## 4. Local web interface — optional: web-only fallback and extra values

| ☐ | Item | Notes / value |
|---|------|---------------|
| ☐ | Network/web PIN set on the controller and handed over to you | PIN: ______________________ |
| ☐ | Web interface reachable in the local network (HTTP port 80; Navigator 10 additionally WebSocket port 61220) | |

## 5. Plant information for the setup — the installer reads these off

| Item | Value |
|------|-------|
| Navigator generation (1.0 / 1.7 / 2.0 / Pro / 10) | ______________________ |
| Software/firmware version (service menu or web page) | ______________________ |
| System scheme number (*Anlagenschema*, e.g. L7.1) | ______________________ |
| Active heating circuits (A–G) | ______________________ |
| Zone modules and rooms per module | ______________________ |
| Cascade present? Number of units | ______________________ |
| Solar thermal / ISC module present? | ______________________ |

## What the integration does *not* need

- No cloud access and no myIDM account — control stays 100 % local
- No port forwarding, no DMZ, no external access of any kind
- No unlocking of installer menus during operation

Once your installer has confirmed the items above, continue with
[Installation and Setup](Installation-and-Setup).
