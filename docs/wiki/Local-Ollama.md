# Local Ollama setup

This page is the step-by-step recipe for running the
[experimental AI adviser](Experimental-AI-Adviser) on **your own Ollama server**:
no API key, no cloud account, nothing leaves your LAN. It covers the Ollama
Home Assistant add-on, Docker on a separate machine and existing servers, model
choice, and the exact integration settings.

The add-on path below was validated end-to-end on Home Assistant OS 2026.9
(add-on v0.34.4, `gemma3:4b`): a daily report generated on the local model in
about one minute with a clean quality guard. The dedicated-server path was
validated the same way with `gemma3:12b` on a separate Proxmox LXC.

## What you need

| Component | Minimum | Notes |
|-----------|---------|-------|
| Ollama runtime | 0.34.x | Add-on, Docker or existing installation |
| Free RAM for the model | ~6 GB for a 4B model, ~11 GB for a 12B model | Besides what Home Assistant itself needs |
| Free disk for the model | ~4 GB (4B) / ~9 GB (12B) | Plus ~5 GB for the Docker image |
| Model | GGUF **completion** model | Embedding models cannot write reports |

Reports run with a five-minute total deadline that includes model validation,
model loading and generation. On CPU-only hardware expect roughly one minute
for a 4B model on four cores, and around three minutes for a 12B model on six
cores. First reports are slower while the model loads; a long idle time can
unload it again depending on your keep-alive setting.

## Path A — the Ollama add-on (Home Assistant OS)

The community add-on [SirUli/homeassistant-ollama-addon](https://github.com/SirUli/homeassistant-ollama-addon)
runs the official `ollama/ollama` image inside Home Assistant OS and publishes
the Ollama API on host port 11434.

1. **Check resources first.** A 4B model needs a host with at least ~6 GB of
   RAM free after Home Assistant, and ~9 GB of free disk (image plus model).
   On a Proxmox/ESXi VM, grow the disk and memory before you start — see the
   troubleshooting table below for the exact failure you get otherwise.
2. In Home Assistant open **Settings → Add-ons → Add-on Store → ⋮ → Repositories**,
   add `https://github.com/SirUli/homeassistant-ollama-addon` and open the
   store again.
3. Install the **Ollama** add-on. The image download is several gigabytes; the
   installation silently continues in the background even if a UI request
   times out.
4. Open the add-on **Configuration** and adjust:
   - **FlashAttention**: `1` — with the default quantized V cache (`q8_0`)
     current Ollama releases refuse to start the model without it.
   - **Cloud**: enable `OLLAMA_NO_CLOUD` so the server can never contact
     ollama.com after the model download.
   - Keep-alive `-1` keeps the model in RAM permanently (fast reports, more
     constant RAM use); a positive value in seconds unloads it after idle.
5. **Start** the add-on.
6. **Pull a model.** The add-on has no model manager UI; use the API from any
   machine on your LAN (replace the IP with your Home Assistant host):

   ```bash
   curl -X POST http://192.0.2.20:11434/api/pull \
     -d '{"name": "gemma3:4b", "stream": false}'
   ```

   On Windows PowerShell use
   `Invoke-RestMethod -Method Post -Uri http://192.0.2.20:11434/api/pull -Body '{"name":"gemma3:4b"}'`.
   The download is ~3.3 GB. Verify it with
   `curl http://192.0.2.20:11434/api/tags`.

7. Continue with [connecting the integration](#connect-the-integration) and
   use `http://<home-assistant-host-ip>:11434` as the base URL. A literal LAN
   IP is required — see below.

## Path B — Docker on another machine

Run Ollama where the RAM is, on any always-on machine in your LAN:

```bash
docker run -d --name ollama --restart unless-stopped \
  -p 11434:11434 \
  -e OLLAMA_NO_CLOUD=1 \
  -v ollama:/root/.ollama \
  ollama/ollama

docker exec -it ollama ollama pull gemma3:4b
```

The integration connects to `http://<that-machine-ip>:11434`. Keep the
container's port published on the LAN interface (`-p 11434:11434`); Ollama
inside Docker binds `0.0.0.0` inside the container by default.

## Path C — an existing Ollama server

Any existing installation works — a bare-metal server, an LXC container on
Proxmox or a NAS package. Two things to check:

- **Listen address:** the server must accept connections from the Home
  Assistant host, not only `127.0.0.1`. The systemd override is
  `Environment="OLLAMA_HOST=0.0.0.0"` in
  `/etc/systemd/system/ollama.service.d/override.conf`.
- **Model:** pull the same GGUF completion model you configure in the
  integration, e.g. `ollama pull gemma3:12b`.

## Choosing a model

| Model | RAM needed | Speed (CPU) | Quality | Notes |
|-------|-----------|-------------|---------|-------|
| `gemma3:4b` | ~5 GB | ~1 min per report | Good, plain phrasing | Integration default; fits small VMs |
| `gemma3:12b` | ~9 GB | ~3 min per report | Better German and structure | Needs a dedicated machine |

The integration default is `gemma3:4b`. The model name you enter must exactly
match the installed tag from `/api/tags`. Any GGUF model with the `completion`
capability works; embedding-only models are rejected with
`ai_local_model_required`. A larger model does not guarantee more accurate
explanations — the numeric guard checks values, not meaning.

## Connect the integration

1. Open **Settings → Devices & services → IDM Heatpump → Configure**.
2. Select **Experimental AI adviser (read-only)** and enable it.
3. Set **Report provider** to `Ollama`, the **Local Ollama base URL** to your
   server and **Installed local model** to the exact model tag.
4. Enable **free-form, not fully verifiable AI explanations** — without this
   switch the adviser stays in measured-data mode and never calls the model.
5. Save and press a report button on the *iDM KI-Anlagenberater* device.

**The base URL must be a literal private IP address** (`192.168.x.x`,
`10.x.x.x`, `172.16–31.x.x`) or loopback. Hostnames like
`http://myserver:11434` are rejected with `invalid_ai_endpoint` because the
integration never resolves DNS — that would make an unvalidated address out of
a validated one. Loopback (`http://127.0.0.1:11434`) means the Home Assistant
host itself and only works when HA runs directly on the Ollama server (for
example Home Assistant Core in Docker next to Ollama). With the add-on, use
the Home Assistant host's LAN IP.

Reports, schedules, notifications and the quality guard behave exactly as
described on the [adviser page](Experimental-AI-Adviser); only the model
endpoint differs. Everything the model receives stays inside your LAN.

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| Add-on install fails, log shows `no space left on device` | HAOS data partition too small: the image plus model needs ~9 GB. Grow the disk (e.g. `qm resize <vm> scsi0 +16G` on Proxmox) and reboot the VM — HAOS grows the partition automatically at boot. |
| Model request fails with `quantized V cache requires flash_attn to be enabled` | Add-on option **FlashAttention** is `0` while the KV cache is `q8_0`. Set FlashAttention to `1` (or the cache to `f16`) and restart the add-on. |
| `invalid_ai_endpoint` | The base URL is not a literal LAN/loopback IP, or it contains a path, query, port 0 or credentials. |
| `ai_local_model_required` | The configured model is an embedding model or marked remote; pull a local GGUF completion model and copy the exact tag. |
| Report aborts after five minutes | Model too large for the hardware. Use a smaller model, keep the model resident (keep-alive `-1`) or add CPU cores. |
| First report much slower than later ones | Model load time; with the default keep-alive Ollama unloads idle models after five minutes. |
| Connection refused from HA, works from another machine | Ollama listens on `127.0.0.1` only — set `OLLAMA_HOST=0.0.0.0` (Docker: publish the port). |

## Privacy summary

The adviser sends only the allowlisted numeric facts described on the
[adviser page](Experimental-AI-Adviser) to the configured endpoint — one
server on your LAN. Set `OLLAMA_NO_CLOUD=1` (add-on option **Cloud**) so the
Ollama server itself cannot reach the internet after the model download. No
API keys, accounts or cloud services are involved on this path.
