# Local Navigator Web Interface

## Purpose and boundaries

The optional web connection supplements Modbus with local, read-only Navigator
metadata and diagnostics. It never uses the myIDM cloud and it does not replace
Modbus for normal register monitoring or control.

| Operating mode | Modbus | Local web | Available functions |
|----------------|--------|-----------|---------------------|
| Modbus only | yes | no | Full Modbus entities, controls and actions |
| Modbus + web supplement | yes | yes | Full Modbus functions plus additional web sensors |
| Web-only fallback | no | yes | Web sensor platform only; no Modbus entities or writes |

In web-only mode there are no Modbus register reads, binary sensors, numbers,
selects, switches, raw register writes, system-mode actions or error
acknowledgement. Only values returned by the local web interface are available.

## Supported local login variants

Navigator generations use different local protocols. The internal variant
names describe the protocol client and are not user-selectable settings.

| Navigator family | Internal variant | Local transport | Authentication |
|------------------|------------------|-----------------|----------------|
| Navigator 2.0 | `nav20` | HTTP, normally port 80 | Login form with CSRF token and local network code |
| Navigator 10 | `nav10` | WebSocket, port 61220 | Authorization frame using the local network code as `auth_code` |
| Navigator Pro | `nav10` | Navigator-10 WebSocket family | Same local authorization mechanism as Navigator 10 |

These transports are local controller interfaces. No cloud password, myIDM
account login or two-factor code is accepted.

## Local network code

The value entered in Home Assistant is the Navigator's **local network code**.
On a German Navigator 2.0 display it is normally located under:

**Einstellungen → Allgemeine Einstellungen → Netzwerkeinstellungen → Code
lokales Netzwerk**

Menu names can differ by generation and firmware. Leading and trailing spaces
are removed. An empty value or exactly `0` means that local web access is
disabled, so the integration stays in Modbus-only mode.

The code is entered through a masked Home Assistant password selector. It is
never logged and is redacted from diagnostics together with the Modbus host,
web host, port and slave ID. Web error diagnostics expose only an error
category, not a URL, query string or authorization value.

## Detection and runtime lifecycle

The integration separates initial protocol discovery from normal runtime
recovery:

1. **Setup, reconfiguration or repair:** The Modbus-detected model is used as a
   hint so the most likely web protocol is tried first. If it fails, the other
   supported protocol is also tried before the PIN or connection is rejected.
2. **First successful login:** The actual `nav20` or `nav10` result is stored in
   the config entry. The result comes from the successful client, not merely
   from the model hint.
3. **Normal polling:** The successful client and authenticated session are
   reused across web polling cycles.
4. **Expired session or transport failure:** The failed session is closed and
   the same known protocol is rebuilt immediately. Normal runtime recovery does
   not probe the other Navigator generation.
5. **New discovery:** Reconfiguration or repair validates the connection again
   and can test both protocols. This is appropriate after replacing the
   Navigator, changing the web host or making a controller/firmware change that
   affects the local interface.

This prevents repeated timeouts on the wrong port and avoids a temporary
failure silently changing a previously working Navigator generation.

## Model and value precedence

Modbus remains authoritative for register-backed operating values. Web data is
additive: it supplies metadata and extra diagnostics that have no equivalent
Modbus entity. A duplicate register-backed value is not exposed a second time.

Web model and firmware metadata may complete an unknown Modbus result. If a
web-reported Navigator family conflicts with a definite Modbus detection, the
conflicting web model and firmware are ignored. Optional Navigator 10
infosystem notifications are read separately; failure of that optional read
does not discard the rest of a valid web snapshot.

## Polling and recovery behavior

- Web polling has its own interval, 30 seconds by default.
- It starts slightly after Modbus polling to avoid simultaneous requests.
- A web authentication or connection problem creates a separate Home Assistant
  repair issue and does not stop Modbus updates.
- Missing values from a successful web snapshot remain unavailable; old values
  are not invented.
- The cached client is closed when the config entry unloads or when its session
  must be rebuilt.

## Troubleshooting checklist

1. Confirm that the code is the local network code, not cloud credentials.
2. Confirm that the code is neither empty nor `0`.
3. With direct Modbus access, use the Navigator address as the web host. With a
   Modbus proxy, configure the original Navigator address separately.
4. Run **Settings → Devices & Services → IDM Heatpump → Reconfigure → Test
   current connection**.
5. If the Navigator or its local web protocol changed, use **Change connection
   settings** so protocol discovery runs again.
6. Download redacted diagnostics and include the integration version, API
   version, Navigator model and firmware when reporting a problem.

See [Troubleshooting](Troubleshooting) for categorized errors and
[Configuration](Configuration) for all web options.

## Version pairing

The sticky protocol selection is implemented by integration version
`0.8.1-beta.29`. Integration `0.8.3` ships the tested
`idm-heatpump-api[web]==0.8.1` web clients, which additionally expose Navigator
10 heating-circuit data for circuits B–G.
