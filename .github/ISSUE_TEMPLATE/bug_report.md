---
name: Bug report
about: Report reproducible incorrect behavior
title: "[BUG] "
labels: bug
assignees: ""

---

**Describe the bug**
Describe the problem and what you expected instead.

**To Reproduce**
Steps to reproduce the behavior:
1.
2.
3.

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment**
- Home Assistant version:
- Integration version:
- `idm-heatpump-api` version:
- `pymodbus` version, if known:
- Heat-pump model (e.g. IDM Navigator 2.0 / 10 / Pro):
- Controller or Navigator version:
- Firmware version:
- Active heating circuits:
- Zone modules and rooms:
- Operating system: HA OS / Container / Core / Supervised / other:
- Connection path: direct / proxy / other:

**Error Logs**
Please enable debug logging and paste relevant log entries:
```yaml
logger:
  default: info
  logs:
    custom_components.idm_heatpump: debug
```

```
Paste logs here...
```

**Diagnostics**
Please download the diagnostics data from the integration page and attach it.
Remove credentials, hostnames, IP addresses, and serial numbers before posting.

**Additional context**
Add any other context about the problem here.
