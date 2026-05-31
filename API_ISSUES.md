# API Issues (idm-heatpump library)

Issues found during live testing against IDM Navigator 10 at 192.168.178.103.

## 1. firmware_version Register (Address 4120) - Permanently Fails

**Severity**: Low (cosmetic)

The library's register map includes `firmware_version` at address 4120. On our Navigator 10 device, this register fails to read every time and gets marked as permanently failed after 3 attempts.

```
WARNING [idm_heatpump.client] Register firmware_version (address 4120) has failed 3 times. Marking as permanently failed.
```

This may be a Navigator-10-specific address that differs from Navigator 2.0, or the register simply doesn't exist on this firmware version. The HA integration already has this entity disabled by default, so it's not user-facing.

**Possible fix**: Consider making this register optional or adjusting the address for Navigator 10.

---

## 2. ISC_MODE_OPTIONS Missing Value 255

**Severity**: Low

`ISC_MODE_OPTIONS` in the library maps:
```python
{0: 'No Waste Heat', 1: 'Heating', 4: 'DHW', 8: 'Heat Source'}
```

Our Navigator 10 returns `255` for the ISC mode register (address 1874). This likely means "not configured" or "no ISC hardware installed". The value 255 is not in the options map, causing the HA select entity to show "unknown".

The HA integration handles this gracefully (entity shows "unknown"), but adding `255: 'Not configured'` (or similar) to the options would be cleaner.

**Same issue applies to**: `CIRCUIT_MODE_OPTIONS` / `ACTIVE_HC_MODE_OPTIONS` - heating circuits B-G return 255 for `active_mode_hk_X` which decodes as "Unbekannt (255)".

---

## 3. Library Public API Surface

**Severity**: Info (design observation)

During testing we noted:
- `build_register_map()` returns `dict[str, RegisterDef]` (keyed by name), not by address
- `get_all_registers()` takes no arguments and returns all core registers
- `IdmModelInfo` uses `active_heating_circuits: list[str]` (e.g. `["a", "b", ...]`)
- `read_batch()` accepts `list[RegisterDef]` and returns `dict[str, Any]` keyed by register name
- No `read_all_registers(model_info)` convenience method - callers must build the register list themselves

This is all fine, just documenting for reference.

---

## 4. Device Detection Results (for reference)

Our Navigator 10 at 192.168.178.103 reports:
- **Model**: Navigator 10
- **Active heating circuits**: 7 (A through G)
- **Zone modules**: 0
- **has_solar**: True
- **has_isc**: True  
- **has_pv**: True
- **has_cascade**: True
- **Total registers read successfully**: 263/264 (firmware_version fails)
- **ISC mode raw value**: 255 (not installed/configured)
- **Solar mode**: returns valid data (Automatik)
- **HK B-G sensors**: return 255 / unavailable (registered but no physical hardware connected)
- **HK A sensors**: all working with live temperature data
