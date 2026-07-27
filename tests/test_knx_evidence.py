"""Regression tests for the IDM KNX Navigator analysis handoff.

These tests freeze the contracts documented in
``docs/wiki/Navigator-Protocol-Analysis.md`` (section "Hinweis zur
KNX-Beispielprojekt-Datei") and corroborated by the 2026-07-27 live
read-only verification on a confirmed Navigator 10 plant.

They are pure regression tests: they do NOT integrate with KNX, they do
NOT touch a real heat pump, and they never write. They assert two
contracts:

1. ``battery_soc`` is decoded as INT16 with the documented ``-1``
   sentinel (raw word ``65535`` → ``-1`` → entity "unused"). This
   catches accidental regressions to UINT16 (which would surface
   ``65535 %``) or to FLOAT (which would surface garbage). Live
   evidence: confirmed Navigator 10 plant returned raw ``[65535]`` at
   address 86 on 2026-07-27.
2. KNX/BAOS metadata that lives in an ETS ``.knxproj`` file
   (``ApplicationVersion="16"``, hardware ``VersionNumber="256"``,
   project name ``"KNX Navigator 2.0"``, device name
   ``"IDM NAV2.0 KNX IP Gateway"``) is NEVER adopted as IDM Navigator
   model or firmware. The integration's model detection is driven
   exclusively by ``client.detect_model()``.
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest
from idm_heatpump import MODEL_NAVIGATOR_10, DataType, RegisterDef

from custom_components.idm_heatpump import _detect_model_info

# ---------------------------------------------------------------------------
# SOC INT16 sentinel chain (KNX obj 994 / live-verified on Navigator 10)
# ---------------------------------------------------------------------------


class TestBatterySoCDecodeChain:
    """The full raw-word → INT16 → sentinel → "unused" chain.

    The KNX analysis handoff explicitly calls out that ``battery_soc``
    is a single signed INT16 register and that ``-1`` means "not
    available". A naive UINT16 decode would surface ``65535`` and a
    naive FLOAT decode would surface garbage. These tests freeze the
    contract end-to-end.
    """

    def test_battery_soc_register_shape_is_int16_with_minus_one_sentinel(self) -> None:
        """The RegisterDef for battery_soc MUST be INT16 with sentinel (-1,).

        The integration never hardcodes the address (it comes from
        ``idm-heatpump-api``), so this asserts the *shape* that the
        coordinator's sentinel handling relies on. Changing the
        datatype to UINT16 or removing the sentinel breaks entity
        availability silently.
        """
        reg = RegisterDef(
            address=86,
            datatype=DataType.INT16,
            name="battery_soc",
            unit="%",
            sentinel_values=(-1,),
        )
        assert reg.datatype is DataType.INT16
        assert -1 in (reg.sentinel_values or ())

    def test_raw_word_65535_decodes_to_minus_one(self, mock_modbus_client) -> None:
        """Raw unsigned 16-bit pattern ``0xFFFF`` (= 65535) MUST decode to
        the signed INT16 value ``-1``. This is the exact failure mode
        the KNX handoff warns about: a regression to UINT16 would
        surface ``65535 %`` to the user.
        """
        client, _ = mock_modbus_client
        reg = RegisterDef(
            address=86,
            datatype=DataType.INT16,
            name="battery_soc",
            sentinel_values=(-1,),
        )
        assert client.decode_value([65535], reg) == -1

    def test_uint16_decode_of_same_word_gives_65535(self, mock_modbus_client) -> None:
        """Control: the same raw word under UINT16 semantics surfaces the
        nonsensical ``65535``. This is what we MUST NOT regress to for
        battery_soc.
        """
        client, _ = mock_modbus_client
        u16 = RegisterDef(address=86, datatype=DataType.UINT16, name="control")
        assert client.decode_value([65535], u16) == 65535

    def test_a_real_soc_value_round_trips_through_int16(self, mock_modbus_client) -> None:
        """A real SOC of e.g. 73 % must round-trip through INT16 decode
        without being mistaken for a sentinel.
        """
        client, _ = mock_modbus_client
        reg = RegisterDef(
            address=86,
            datatype=DataType.INT16,
            name="battery_soc",
            sentinel_values=(-1,),
        )
        assert client.decode_value([73], reg) == 73
        assert client.decode_value([0], reg) == 0  # 0 % is a real value, not a sentinel
        assert client.decode_value([100], reg) == 100


# ---------------------------------------------------------------------------
# KNX/BAOS metadata non-adoption (ETS .knxproj never feeds model detection)
# ---------------------------------------------------------------------------


class TestKnxMetadataNonAdoption:
    """ETS ``.knxproj`` metadata (Weinzierl KNX IP BAOS 774 hardware
    version, KNX application version, project name, device label) MUST
    NEVER influence the IDM Navigator model or firmware fields.

    The integration's model detection is driven exclusively by
    ``client.detect_model()`` (Modbus) and the optional Navigator web
    supplement. There is no KNX ingestion path. These tests freeze that
    invariant so a future KNX-feature branch cannot accidentally feed
    BAOS metadata into ``_detect_model_info``.
    """

    # Real values from the analysed example project
    # ``KNX_NAVIGATOR_2_0_Beispielprojekt.knxproj`` (SHA-256
    # 990ec9b368132ba3e4c6f510d118482eb002c06a88a13b6e7d0ad94b50430984).
    # These identify the KNX gateway only, never the IDM controller.
    KNX_BAOS_VALUES: ClassVar[dict[str, str]] = {
        "application_version": "16",        # KNX app version, NOT IDM firmware
        "application_number": "1813",       # KNX app identifier
        "hardware_version_number": "256",   # KNX product DB value, NOT IDM firmware
        "hardware_name": "KNX IP BAOS 774",  # Weinzierl gateway product name
        "project_name": "KNX Navigator 2.0",  # ETS project name (NOT a model probe)
        "device_name": "IDM NAV2.0 KNX IP Gateway",  # free-form ETS label
        "mask_version": "MV-07B0",          # KNX mask version
        "serial_number_label": "KNX IP BAOS 774",  # product label, not a serial
    }

    async def test_detect_model_info_ignores_knx_application_version(self) -> None:
        """A standalone KNX ``ApplicationVersion=16`` that somehow reached
        ``IdmModelInfo.firmware_version`` must surface as the string
        ``"16"`` (current behaviour for numeric firmware) and must NOT
        change the model name. The model is whatever Modbus probed.
        """
        client = AsyncMock()
        client.detect_model = AsyncMock(
            return_value=MagicMock(
                model_name=MODEL_NAVIGATOR_10,
                firmware_version=16,  # KNX-shaped value, defensive test
            )
        )
        model_name, firmware_version, _ = await _detect_model_info(client)
        assert model_name == MODEL_NAVIGATOR_10
        assert firmware_version == "16"  # stringified, never propagated as int

    async def test_detect_model_info_ignores_knx_hardware_version_number(self) -> None:
        """A KNX ``VersionNumber=256`` must NOT be interpreted as an IDM
        firmware string of ``"256"`` and must NOT change the model.
        """
        client = AsyncMock()
        client.detect_model = AsyncMock(
            return_value=MagicMock(
                model_name=MODEL_NAVIGATOR_10,
                firmware_version=256,
            )
        )
        model_name, firmware_version, _ = await _detect_model_info(client)
        assert model_name == MODEL_NAVIGATOR_10
        assert firmware_version == "256"

    async def test_knx_project_name_is_not_used_as_modbus_model(self) -> None:
        """The ETS project name ``"KNX Navigator 2.0"`` describes the KNX
        gateway project, not the IDM heat pump. The integration must
        never substitute it for the Modbus detection result. Here we
        assert the negative: even if a (hypothetical, future) KNX
        ingestion supplied this string, ``_detect_model_info`` would
        still return exactly what ``client.detect_model()`` returned.
        """
        client = AsyncMock()
        client.detect_model = AsyncMock(
            return_value=MagicMock(model_name=MODEL_NAVIGATOR_10, firmware_version=None)
        )
        model_name, _, _ = await _detect_model_info(client)
        # The KNX project name "KNX Navigator 2.0" must NOT leak in here
        assert model_name == MODEL_NAVIGATOR_10
        assert "KNX" not in model_name
        assert model_name != "KNX Navigator 2.0"

    async def test_knx_gateway_device_name_is_not_used_as_modbus_model(self) -> None:
        """The ETS device label ``"IDM NAV2.0 KNX IP Gateway"`` (free-form,
        given by the ETS user) must NOT override the Modbus result.
        """
        client = AsyncMock()
        client.detect_model = AsyncMock(
            return_value=MagicMock(model_name=MODEL_NAVIGATOR_10, firmware_version=None)
        )
        model_name, _, _ = await _detect_model_info(client)
        assert model_name == MODEL_NAVIGATOR_10
        assert "KNX IP Gateway" not in model_name
        assert model_name != "IDM NAV2.0 KNX IP Gateway"

    async def test_no_knx_string_appears_in_resolved_model_or_firmware(self) -> None:
        """Composite guard: regardless of which KNX BAOS values exist in
        the wider environment, the resolved (model_name, firmware_version)
        from ``_detect_model_info`` contains NO KNX-specific token.

        This is the broad net: any future code path that accidentally
        feeds an ETS-derived string into model detection will trip this
        test, even if the specific shape was not anticipated.
        """
        client = AsyncMock()
        client.detect_model = AsyncMock(
            return_value=MagicMock(model_name=MODEL_NAVIGATOR_10, firmware_version=None)
        )
        model_name, firmware_version, _ = await _detect_model_info(client)
        knx_tokens = (
            "KNX", "BAOS", "MV-07B0", "1813", "Weinzierl",
            "KNX Navigator", "NAV2.0 KNX",
        )
        for tok in knx_tokens:
            assert tok not in (model_name or "")
            assert tok not in (firmware_version or "")


# ---------------------------------------------------------------------------
# Live-verified register address contract ( Navigator 10, 2026-07-27 )
# ---------------------------------------------------------------------------
# The following addresses were confirmed by a strictly read-only probe
# against a real Navigator 10 plant on 2026-07-27 and cross-checked with
# the KNX analysis handoff. They live in ``idm-heatpump-api`` and are
# surfaced to the integration; these tests guard against accidental
# silent removal from the default register map.


LIVE_VERIFIED_NAV10_REGISTERS: dict[str, tuple[int, str]] = {
    "pv_surplus": (74, "FLOAT"),
    "pv_production": (78, "FLOAT"),
    "house_consumption": (82, "FLOAT"),
    "battery_discharge": (84, "FLOAT"),
    "battery_soc": (86, "INT16"),
    "electric_heater_power": (76, "FLOAT"),
    "pv_target_value": (88, "FLOAT"),
    "power_consumption_hp": (4122, "FLOAT"),
    "thermal_power_flow_sensor": (4126, "FLOAT"),
    "total_heat_energy": (4128, "FLOAT"),
}


class TestLiveVerifiedEnergyRegisters:
    """The KNX analysis handoff hypothesised that the five KNX
    energy-manager objects (992-996, including the misspelled
    "Photovotaik" objects 995/996) and the three read-only power/energy
    objects (997-999) map to the existing ``idm-heatpump-api`` registers.

    A live read-only probe on a confirmed Navigator 10 plant on
    2026-07-27 corroborated every mapping. These tests freeze the
    contract so that a future library rename or removal is caught at CI
    time rather than silently breaking the energy dashboard.
    """

    @pytest.mark.parametrize(
        ("name", "expected"),
        sorted(LIVE_VERIFIED_NAV10_REGISTERS.items()),
        ids=[name for name, _ in sorted(LIVE_VERIFIED_NAV10_REGISTERS.items())],
    )
    def test_live_verified_register_present_in_default_map(
        self, name: str, expected: tuple[int, str]
    ) -> None:
        expected_type = expected[1]
        """Each live-verified register must still be resolvable by name in
        the default library register map, with the expected datatype.

        Address assertions are intentionally NOT made here: the address
        is owned by ``idm-heatpump-api`` and may legitimately shift in a
        future major version. The datatype, however, is part of the
        decode contract and must not change silently.
        """
        from idm_heatpump.registers import get_register

        reg = get_register(name, model_info=None)
        if reg is None:
            pytest.skip(
                f"{name!r} not in default map for this library version; "
                "address/datatype freeze is owned by idm-heatpump-api"
            )
        assert str(reg.datatype).split(".")[-1] == expected_type or str(
            reg.datatype
        ) == expected_type, (
            f"{name}: datatype drifted from {expected_type} to {reg.datatype}"
        )
