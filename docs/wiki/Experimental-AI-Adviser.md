# Experimental local AI adviser

**Upcoming feature: not included in v0.17.2-b6.** This adviser is off by default
and must be activated separately, even when Smart is enabled.

It explains selected measurements using a local Ollama model. It has no
Home Assistant control tools, Modbus connection or plant write path. It does
not expose the plant to Assist, Google Assistant or Alexa. Generated text
may be incorrect: verify it against the accompanying facts. This is not a
fault diagnosis or an automatic optimization controller.

## Setup

1. Run Ollama on a local server and install a local completion model, such as
   `gemma3:4b`. The integration does not install or download models.
2. Open **Settings → Devices & services → IDM Heatpump → Reconfigure → Features**.
3. At any setup depth, select **AI adviser (experimental, read-only)**, enable it,
   and enter the local base URL, installed model name and report language
   (`de` or `en`). Use your own address, for example `http://192.168.1.20:11434`.
4. Review and save. A report sensor and four report buttons are created.

Only literal private LAN or loopback IP addresses are accepted. Hostnames,
public addresses, embedded credentials, URL paths and redirects are rejected.
Loopback means the Home Assistant host/container, not another server. HTTPS
uses certificate validation. The Ollama endpoint must be reachable from HA.
Cloud model names and remote model metadata are rejected before measurements
are sent. Keep the server trusted and local; also consider disabling cloud
features on that server using `OLLAMA_NO_CLOUD=1`, as documented in the
[Ollama FAQ](https://docs.ollama.com/faq). An administrator-controlled proxy
can forward traffic outside the LAN; HA cannot inspect the server internally.

## Available reports

| Report | Scope |
|--------|-------|
| Daily | Rolling last 24 hours, with the preceding 24 hours for context |
| Weekly | Rolling last seven days, with the preceding seven days |
| Health | Current diagnostic flags and missing evidence, with 24-hour context |
| Efficiency | Observed electrical/thermal energy and calculated COP, with 24-hour context |

Reports explain observations and uncertainty. They do not recommend setpoint
changes, guarantee savings or execute actions. The health flags are the
existing rule-based checks, not diagnoses invented by an AI model.

## History and data quality

The adviser keeps at most one numeric sample every five minutes and at most
fourteen days of local history while enabled and its report sensor is loaded.
It stores temperatures and cumulative electrical/thermal counters. It does
not import Recorder history, so a new installation cannot immediately provide
a complete day or week. Energy counters require Smart statistics; without
them energy and COP totals are explicitly missing.

Only counter intervals up to fifteen minutes with valid, increasing counters
are included. Gaps, counter resets and unavailable data are excluded without
extrapolation. The coverage percentage describes observed **counter intervals**,
not proof of continuous power readings: the underlying energy statistics also
exclude invalid polling gaps. Current readings older than fifteen minutes are
excluded. Periods are rolling UTC intervals, not local calendar days. Heating
and DHW energy are not separated. There are no weather or tariff predictions.

Requests contain only selected numeric measurements, boolean health flags,
calculated period summaries and fixed limitations. They never include the
heat-pump address, PIN, serial number, entity names, other HA devices,
documents or arbitrary user questions. The server address is redacted from
diagnostics. Model output is text only and is never executed.

## Display and actions

The **AI report (experimental)** sensor uses `idle`, `generating`, `ready` or
`error` as its state. Attributes include `report`, `generated_at`, `report_type`,
`facts`, `error` and `history_samples`. Four buttons request the respective
reports; they do not change heat-pump settings. In web-only mode, use the action
below because the button platform is not loaded.

The `idm_heatpump.generate_ai_report` action requires an explicit `entry_id`
and accepts `report_type`: `daily`, `weekly`, `health` or `efficiency` (default
`daily`). Select the IDM entry in the action editor. The optional response
contains the report, timestamp and input facts.

At most one request runs per entry, with a minimum sixty-second interval and a
180-second timeout. No automatic inference is enabled. Scheduled reports
require a separately created Home Assistant automation calling this action.

Add the sensor and buttons to your dashboard using the entity picker. An
optional Markdown card can display the output as escaped plain text:

```yaml
type: markdown
title: AI plant report — experimental
content: >-
  <pre>{{ state_attr('sensor.REPLACE_WITH_YOUR_AI_REPORT', 'report')
  | default('No report yet', true) | e }}</pre>
```

Replace the example entity ID with the actual report sensor. Keep its state
and timestamp visible: after a failed request, the previous successful report
remains with its original timestamp. Reports are held in memory and cleared
on reload; numeric history survives restarts. Report text and facts are
excluded from Recorder to avoid duplicating large outputs.

Disabling the feature stops collection and cancels an in-progress request.
The saved numeric history remains locally available if re-enabled within its
retention window. The heat pump continues independently of the AI server.

## Troubleshooting

If no report appears, check the feature toggle, reachability from HA, the exact
installed model name and the sensor error attribute. A local GGUF completion
model is required; an embedding model cannot write reports. Responses with
tools, malformed content, excessive size or token-limit truncation are
rejected. Wait for an active request to finish before trying again. Do not
treat an old retained report or incomplete history as a fresh, full assessment.
