"""IDM KNX communication-object catalogue.

The IDM Navigator speaks KNX through a Weinzierl ``KNX IP BAOS 774``
gateway. IDM ships an ETS example project for it whose 726 communication
objects carry the Navigator's values; object numbers, labels, datapoint
types and the read/write direction are defined there. This module holds
the subset of those objects that this integration can serve from the
Modbus register map, keyed by the ``idm-heatpump-api`` register name.

Group addresses are deliberately *not* part of the catalogue: the example
project ships with an empty ``GroupRanges`` section, so every installation
assigns its own. :func:`resolve_group_addresses` derives them from a base
address plus the object number, which is exactly how the objects are laid
out on the bus, and accepts per-object overrides for installations whose
ETS project already uses different addresses.

The object numbers here are the same ID space as
``controller_stats_reference.ControllerStatReference.knx_object``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

# Maximum raw KNX group address (16 bit address space).
MAX_RAW_GROUP_ADDRESS: Final[int] = 0xFFFF

# Highest object number in the catalogue; a base address must leave room
# for this many addresses above it.
MAX_OBJECT_NUMBER: Final[int] = 999


class InvalidGroupAddressError(ValueError):
    """Raised when a group address cannot be parsed or is out of range."""


@dataclass(frozen=True, slots=True)
class KnxObject:
    """One IDM KNX communication object.

    ``number`` is the object number from the IDM ETS example project.
    ``register`` is the ``idm-heatpump-api`` register name carrying the
    value, and doubles as the stable key for group-address overrides.
    ``dpt`` is the KNX datapoint type passed to ``knx.send``; ``None``
    means a 1-bit object that is sent as a raw ``0``/``1`` payload.
    ``writable`` marks objects the bus may write back into the heat pump.
    ``group`` is the coarse category used to filter what gets exported.
    """

    number: int
    register: str
    dpt: str | None
    writable: bool
    group: str


# Object groups offered as export filters, in display order.
OBJECT_GROUPS: Final[tuple[str, ...]] = (
    "system",
    "heat_pump",
    "dhw",
    "heating_circuits",
    "zones",
    "glt",
    "energy",
    "solar",
    "isc",
    "cascade",
    "booster",
    "pv",
)


# Generated from the IDM "KNX NAVIGATOR 2.0" ETS example project
# (Weinzierl KNX IP BAOS 774, manufacturer M-00C5, application
# A-0715-10-EAC9) and cross-checked against the idm-heatpump-api
# register map. Sorted by object number.
KNX_OBJECTS: Final[tuple[KnxObject, ...]] = (
    KnxObject(1, "outdoor_temp", "9.001", False, "system"),
    KnxObject(2, "outdoor_temp_avg", "9.001", False, "system"),
    KnxObject(3, "internal_message", "7.001", False, "system"),
    KnxObject(4, "system_mode", "5.010", True, "system"),
    KnxObject(5, "smart_grid_status", "7.001", False, "system"),
    KnxObject(6, "storage_temp", "9.001", False, "system"),
    KnxObject(7, "cold_storage_temp", "9.001", False, "system"),
    KnxObject(8, "dhw_temp_bottom", "9.001", False, "dhw"),
    KnxObject(9, "dhw_temp_top", "9.001", False, "dhw"),
    KnxObject(20, "dhw_tapping_temp", "9.001", False, "dhw"),
    KnxObject(21, "dhw_setpoint", "9.001", True, "dhw"),
    KnxObject(30, "hp_flow_temp", "9.001", False, "heat_pump"),
    KnxObject(31, "hp_return_temp", "9.001", False, "heat_pump"),
    KnxObject(32, "hgl_flow_temp", "9.001", False, "heat_pump"),
    KnxObject(33, "heat_source_inlet_temp", "9.001", False, "heat_pump"),
    KnxObject(34, "heat_source_outlet_temp", "9.001", False, "heat_pump"),
    KnxObject(35, "air_intake_temp", "9.001", False, "heat_pump"),
    KnxObject(36, "air_heat_exchanger_temp", "9.001", False, "heat_pump"),
    KnxObject(38, "charging_sensor_temp", "9.001", False, "heat_pump"),
    KnxObject(40, "heat_sink_flow_temp", "9.001", False, "heat_pump"),
    KnxObject(41, "heat_sink_flow_rate", "7.001", False, "heat_pump"),
    KnxObject(42, "heat_sink_charging_pump_signal", "5.001", False, "heat_pump"),
    KnxObject(48, "groundwater_inlet_temp_1", "9.001", False, "heat_pump"),
    KnxObject(49, "groundwater_inlet_temp_2", "9.001", False, "heat_pump"),
    KnxObject(50, "hp_operating_mode", "7.001", False, "heat_pump"),
    KnxObject(51, "heating_demand", "7.001", False, "heat_pump"),
    KnxObject(52, "cooling_demand", "7.001", False, "heat_pump"),
    KnxObject(53, "dhw_demand", "7.001", False, "heat_pump"),
    KnxObject(60, "compressor_status_1", "7.001", False, "heat_pump"),
    KnxObject(61, "compressor_status_2", "7.001", False, "heat_pump"),
    KnxObject(62, "compressor_status_3", "7.001", False, "heat_pump"),
    KnxObject(63, "compressor_status_4", "7.001", False, "heat_pump"),
    KnxObject(78, "circulation_pump", "7.001", False, "heat_pump"),
    KnxObject(80, "bivalence_point_1_2nd_gen", "8.001", True, "heat_pump"),
    KnxObject(81, "bivalence_point_2_2nd_gen", "8.001", True, "heat_pump"),
    KnxObject(82, "bivalence_point_1_3rd_gen", "8.001", True, "heat_pump"),
    KnxObject(83, "bivalence_point_2_3rd_gen", "8.001", True, "heat_pump"),
    KnxObject(97, "cascade_available_heating", "7.001", False, "cascade"),
    KnxObject(98, "cascade_available_cooling", "7.001", False, "cascade"),
    KnxObject(99, "cascade_available_dhw", "7.001", False, "cascade"),
    KnxObject(100, "cascade_running_heating", "7.001", False, "cascade"),
    KnxObject(101, "cascade_running_cooling", "7.001", False, "cascade"),
    KnxObject(102, "cascade_running_dhw", "7.001", False, "cascade"),
    KnxObject(150, "cascade_req_heating_temp", "9.001", False, "cascade"),
    KnxObject(151, "cascade_req_cooling_temp", "9.001", False, "cascade"),
    KnxObject(152, "cascade_req_dhw_temp", "9.001", False, "cascade"),
    KnxObject(153, "cascade_avg_flow_heating", "9.001", False, "cascade"),
    KnxObject(154, "cascade_avg_flow_cooling", "9.001", False, "cascade"),
    KnxObject(155, "cascade_avg_flow_dhw", "9.001", False, "cascade"),
    KnxObject(160, "cascade_min_power_heating", "5.001", True, "cascade"),
    KnxObject(161, "cascade_max_power_heating", "5.001", True, "cascade"),
    KnxObject(162, "cascade_min_power_cooling", "5.001", True, "cascade"),
    KnxObject(163, "cascade_max_power_cooling", "5.001", True, "cascade"),
    KnxObject(164, "cascade_min_power_dhw", "5.001", True, "cascade"),
    KnxObject(165, "cascade_max_power_dhw", "5.001", True, "cascade"),
    KnxObject(166, "cascade_bivalence_heating_parallel", "8.001", True, "cascade"),
    KnxObject(167, "cascade_bivalence_heating_alternative", "8.001", True, "cascade"),
    KnxObject(168, "cascade_bivalence_cooling_parallel", "8.001", True, "cascade"),
    KnxObject(169, "cascade_bivalence_cooling_alternative", "8.001", True, "cascade"),
    KnxObject(170, "cascade_bivalence_dhw_parallel", "8.001", True, "cascade"),
    KnxObject(171, "cascade_bivalence_dhw_alternative", "8.001", True, "cascade"),
    KnxObject(200, "hc_a_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(201, "hc_b_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(202, "hc_c_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(203, "hc_d_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(204, "hc_e_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(205, "hc_f_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(206, "hc_g_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(207, "hc_a_room_temp", "9.001", False, "heating_circuits"),
    KnxObject(208, "hc_b_room_temp", "9.001", False, "heating_circuits"),
    KnxObject(209, "hc_c_room_temp", "9.001", False, "heating_circuits"),
    KnxObject(210, "hc_d_room_temp", "9.001", False, "heating_circuits"),
    KnxObject(211, "hc_e_room_temp", "9.001", False, "heating_circuits"),
    KnxObject(212, "hc_f_room_temp", "9.001", False, "heating_circuits"),
    KnxObject(213, "hc_g_room_temp", "9.001", False, "heating_circuits"),
    KnxObject(214, "hc_a_setpoint_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(215, "hc_b_setpoint_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(216, "hc_c_setpoint_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(217, "hc_d_setpoint_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(218, "hc_e_setpoint_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(219, "hc_f_setpoint_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(220, "hc_g_setpoint_flow_temp", "9.001", False, "heating_circuits"),
    KnxObject(221, "humidity_sensor", "9.007", False, "heating_circuits"),
    KnxObject(222, "hc_a_mode", "7.001", True, "heating_circuits"),
    KnxObject(223, "hc_b_mode", "7.001", True, "heating_circuits"),
    KnxObject(224, "hc_c_mode", "7.001", True, "heating_circuits"),
    KnxObject(225, "hc_d_mode", "7.001", True, "heating_circuits"),
    KnxObject(226, "hc_e_mode", "7.001", True, "heating_circuits"),
    KnxObject(227, "hc_f_mode", "7.001", True, "heating_circuits"),
    KnxObject(228, "hc_g_mode", "7.001", True, "heating_circuits"),
    KnxObject(229, "hc_a_room_setpoint_heat_normal", "9.001", True, "heating_circuits"),
    KnxObject(230, "hc_b_room_setpoint_heat_normal", "9.001", True, "heating_circuits"),
    KnxObject(231, "hc_c_room_setpoint_heat_normal", "9.001", True, "heating_circuits"),
    KnxObject(232, "hc_d_room_setpoint_heat_normal", "9.001", True, "heating_circuits"),
    KnxObject(233, "hc_e_room_setpoint_heat_normal", "9.001", True, "heating_circuits"),
    KnxObject(234, "hc_f_room_setpoint_heat_normal", "9.001", True, "heating_circuits"),
    KnxObject(235, "hc_g_room_setpoint_heat_normal", "9.001", True, "heating_circuits"),
    KnxObject(236, "hc_a_room_setpoint_heat_eco", "9.001", True, "heating_circuits"),
    KnxObject(237, "hc_b_room_setpoint_heat_eco", "9.001", True, "heating_circuits"),
    KnxObject(238, "hc_c_room_setpoint_heat_eco", "9.001", True, "heating_circuits"),
    KnxObject(239, "hc_d_room_setpoint_heat_eco", "9.001", True, "heating_circuits"),
    KnxObject(240, "hc_e_room_setpoint_heat_eco", "9.001", True, "heating_circuits"),
    KnxObject(241, "hc_f_room_setpoint_heat_eco", "9.001", True, "heating_circuits"),
    KnxObject(242, "hc_g_room_setpoint_heat_eco", "9.001", True, "heating_circuits"),
    KnxObject(243, "hc_a_heating_curve", "9.001", True, "heating_circuits"),
    KnxObject(244, "hc_b_heating_curve", "9.001", True, "heating_circuits"),
    KnxObject(245, "hc_c_heating_curve", "9.001", True, "heating_circuits"),
    KnxObject(246, "hc_d_heating_curve", "9.001", True, "heating_circuits"),
    KnxObject(247, "hc_e_heating_curve", "9.001", True, "heating_circuits"),
    KnxObject(248, "hc_f_heating_curve", "9.001", True, "heating_circuits"),
    KnxObject(249, "hc_g_heating_curve", "9.001", True, "heating_circuits"),
    KnxObject(250, "hc_a_heating_limit", "7.001", True, "heating_circuits"),
    KnxObject(251, "hc_b_heating_limit", "7.001", True, "heating_circuits"),
    KnxObject(252, "hc_c_heating_limit", "7.001", True, "heating_circuits"),
    KnxObject(253, "hc_d_heating_limit", "7.001", True, "heating_circuits"),
    KnxObject(254, "hc_e_heating_limit", "7.001", True, "heating_circuits"),
    KnxObject(255, "hc_f_heating_limit", "7.001", True, "heating_circuits"),
    KnxObject(256, "hc_g_heating_limit", "7.001", True, "heating_circuits"),
    KnxObject(257, "hc_a_setpoint_flow_constant", "7.001", True, "heating_circuits"),
    KnxObject(258, "hc_b_setpoint_flow_constant", "7.001", True, "heating_circuits"),
    KnxObject(259, "hc_c_setpoint_flow_constant", "7.001", True, "heating_circuits"),
    KnxObject(260, "hc_d_setpoint_flow_constant", "7.001", True, "heating_circuits"),
    KnxObject(261, "hc_e_setpoint_flow_constant", "7.001", True, "heating_circuits"),
    KnxObject(262, "hc_f_setpoint_flow_constant", "7.001", True, "heating_circuits"),
    KnxObject(263, "hc_g_setpoint_flow_constant", "7.001", True, "heating_circuits"),
    KnxObject(264, "hc_a_room_setpoint_cool_normal", "9.001", True, "heating_circuits"),
    KnxObject(265, "hc_b_room_setpoint_cool_normal", "9.001", True, "heating_circuits"),
    KnxObject(266, "hc_c_room_setpoint_cool_normal", "9.001", True, "heating_circuits"),
    KnxObject(267, "hc_d_room_setpoint_cool_normal", "9.001", True, "heating_circuits"),
    KnxObject(268, "hc_e_room_setpoint_cool_normal", "9.001", True, "heating_circuits"),
    KnxObject(269, "hc_f_room_setpoint_cool_normal", "9.001", True, "heating_circuits"),
    KnxObject(270, "hc_g_room_setpoint_cool_normal", "9.001", True, "heating_circuits"),
    KnxObject(271, "hc_a_room_setpoint_cool_eco", "9.001", True, "heating_circuits"),
    KnxObject(272, "hc_b_room_setpoint_cool_eco", "9.001", True, "heating_circuits"),
    KnxObject(273, "hc_c_room_setpoint_cool_eco", "9.001", True, "heating_circuits"),
    KnxObject(274, "hc_d_room_setpoint_cool_eco", "9.001", True, "heating_circuits"),
    KnxObject(275, "hc_e_room_setpoint_cool_eco", "9.001", True, "heating_circuits"),
    KnxObject(276, "hc_f_room_setpoint_cool_eco", "9.001", True, "heating_circuits"),
    KnxObject(277, "hc_g_room_setpoint_cool_eco", "9.001", True, "heating_circuits"),
    KnxObject(278, "hc_a_cooling_limit", "7.001", True, "heating_circuits"),
    KnxObject(279, "hc_b_cooling_limit", "7.001", True, "heating_circuits"),
    KnxObject(280, "hc_c_cooling_limit", "7.001", True, "heating_circuits"),
    KnxObject(281, "hc_d_cooling_limit", "7.001", True, "heating_circuits"),
    KnxObject(282, "hc_e_cooling_limit", "7.001", True, "heating_circuits"),
    KnxObject(283, "hc_f_cooling_limit", "7.001", True, "heating_circuits"),
    KnxObject(284, "hc_g_cooling_limit", "7.001", True, "heating_circuits"),
    KnxObject(285, "hc_a_setpoint_flow_cooling", "7.001", True, "heating_circuits"),
    KnxObject(286, "hc_b_setpoint_flow_cooling", "7.001", True, "heating_circuits"),
    KnxObject(287, "hc_c_setpoint_flow_cooling", "7.001", True, "heating_circuits"),
    KnxObject(288, "hc_d_setpoint_flow_cooling", "7.001", True, "heating_circuits"),
    KnxObject(289, "hc_e_setpoint_flow_cooling", "7.001", True, "heating_circuits"),
    KnxObject(290, "hc_f_setpoint_flow_cooling", "7.001", True, "heating_circuits"),
    KnxObject(291, "hc_g_setpoint_flow_cooling", "7.001", True, "heating_circuits"),
    KnxObject(292, "hc_a_active_mode", "7.001", False, "heating_circuits"),
    KnxObject(293, "hc_b_active_mode", "7.001", False, "heating_circuits"),
    KnxObject(294, "hc_c_active_mode", "7.001", False, "heating_circuits"),
    KnxObject(295, "hc_d_active_mode", "7.001", False, "heating_circuits"),
    KnxObject(296, "hc_e_active_mode", "7.001", False, "heating_circuits"),
    KnxObject(297, "hc_f_active_mode", "7.001", False, "heating_circuits"),
    KnxObject(298, "hc_g_active_mode", "7.001", False, "heating_circuits"),
    KnxObject(299, "hc_a_parallel_shift", "7.001", True, "heating_circuits"),
    KnxObject(300, "hc_b_parallel_shift", "7.001", True, "heating_circuits"),
    KnxObject(301, "hc_c_parallel_shift", "7.001", True, "heating_circuits"),
    KnxObject(302, "hc_d_parallel_shift", "7.001", True, "heating_circuits"),
    KnxObject(303, "hc_e_parallel_shift", "7.001", True, "heating_circuits"),
    KnxObject(304, "hc_f_parallel_shift", "7.001", True, "heating_circuits"),
    KnxObject(305, "hc_g_parallel_shift", "7.001", True, "heating_circuits"),
    KnxObject(350, "hc_a_ext_room_temp", "9.001", True, "heating_circuits"),
    KnxObject(351, "hc_b_ext_room_temp", "9.001", True, "heating_circuits"),
    KnxObject(352, "hc_c_ext_room_temp", "9.001", True, "heating_circuits"),
    KnxObject(353, "hc_d_ext_room_temp", "9.001", True, "heating_circuits"),
    KnxObject(354, "hc_e_ext_room_temp", "9.001", True, "heating_circuits"),
    KnxObject(355, "hc_f_ext_room_temp", "9.001", True, "heating_circuits"),
    KnxObject(356, "hc_g_ext_room_temp", "9.001", True, "heating_circuits"),
    KnxObject(359, "fault_charging_pump_1_intermediate", "7.001", False, "heat_pump"),
    KnxObject(360, "fault_charging_pump_2_intermediate", "7.001", False, "heat_pump"),
    KnxObject(370, "ext_outdoor_temp", "9.001", True, "glt"),
    KnxObject(371, "ext_humidity", "9.007", True, "glt"),
    KnxObject(372, "ext_demand_temp_heating", "7.001", True, "glt"),
    KnxObject(373, "ext_demand_temp_cooling", "7.001", True, "glt"),
    KnxObject(374, "glt_temp_demand_heating", "9.001", True, "glt"),
    KnxObject(375, "glt_temp_demand_cooling", "9.001", True, "glt"),
    KnxObject(380, "demand_heating", None, True, "glt"),
    KnxObject(381, "demand_cooling", None, True, "glt"),
    KnxObject(382, "demand_dhw_charging", None, True, "glt"),
    KnxObject(383, "demand_onetime_dhw", None, True, "glt"),
    KnxObject(386, "glt_heat_storage_temp", "9.001", True, "glt"),
    KnxObject(387, "glt_cold_storage_temp", "9.001", True, "glt"),
    KnxObject(388, "glt_dhw_temp_bottom", "9.001", True, "glt"),
    KnxObject(389, "glt_dhw_temp_top", "9.001", True, "glt"),
    KnxObject(400, "energy_heating", "14.031", False, "energy"),
    KnxObject(401, "energy_cooling", "14.031", False, "energy"),
    KnxObject(402, "energy_dhw", "14.031", False, "energy"),
    KnxObject(403, "energy_defrost", "14.031", False, "energy"),
    KnxObject(404, "energy_passive_cooling", "14.031", False, "energy"),
    KnxObject(405, "energy_solar", "14.031", False, "energy"),
    KnxObject(406, "energy_electric_heater", "14.031", False, "energy"),
    KnxObject(420, "current_power", "9.024", False, "energy"),
    KnxObject(421, "current_power_solar", "9.024", False, "energy"),
    KnxObject(450, "solar_collector_temp", "9.001", False, "solar"),
    KnxObject(451, "solar_return_temp", "9.001", False, "solar"),
    KnxObject(452, "solar_charging_temp", "9.001", False, "solar"),
    KnxObject(453, "solar_mode", "7.001", True, "solar"),
    KnxObject(454, "solar_wq_pool_temp", "9.001", False, "solar"),
    KnxObject(460, "isc_charging_temp_cooling", "9.001", False, "isc"),
    KnxObject(461, "isc_recooling_temp", "9.001", False, "isc"),
    KnxObject(462, "isc_mode", "7.001", False, "isc"),
    KnxObject(499, "error_acknowledge", "7.001", True, "system"),
    KnxObject(500, "zm1_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(501, "zm1_dehumidification", "7.001", False, "zones"),
    KnxObject(502, "zm1_room1_temp", "9.001", True, "zones"),
    KnxObject(503, "zm1_room1_setpoint", "9.001", True, "zones"),
    KnxObject(504, "zm1_room1_humidity", "9.007", True, "zones"),
    KnxObject(505, "zm1_room1_mode", "7.001", True, "zones"),
    KnxObject(506, "zm1_room1_relay", "7.001", False, "zones"),
    KnxObject(507, "zm1_room2_temp", "9.001", True, "zones"),
    KnxObject(508, "zm1_room2_setpoint", "9.001", True, "zones"),
    KnxObject(509, "zm1_room2_humidity", "9.007", True, "zones"),
    KnxObject(510, "zm1_room2_mode", "7.001", True, "zones"),
    KnxObject(511, "zm1_room2_relay", "7.001", False, "zones"),
    KnxObject(512, "zm1_room3_temp", "9.001", True, "zones"),
    KnxObject(513, "zm1_room3_setpoint", "9.001", True, "zones"),
    KnxObject(514, "zm1_room3_humidity", "9.007", True, "zones"),
    KnxObject(515, "zm1_room3_mode", "7.001", True, "zones"),
    KnxObject(516, "zm1_room3_relay", "7.001", False, "zones"),
    KnxObject(517, "zm1_room4_temp", "9.001", True, "zones"),
    KnxObject(518, "zm1_room4_setpoint", "9.001", True, "zones"),
    KnxObject(519, "zm1_room4_humidity", "9.007", True, "zones"),
    KnxObject(520, "zm1_room4_mode", "7.001", True, "zones"),
    KnxObject(521, "zm1_room4_relay", "7.001", False, "zones"),
    KnxObject(522, "zm1_room5_temp", "9.001", True, "zones"),
    KnxObject(523, "zm1_room5_setpoint", "9.001", True, "zones"),
    KnxObject(524, "zm1_room5_humidity", "9.007", True, "zones"),
    KnxObject(525, "zm1_room5_mode", "7.001", True, "zones"),
    KnxObject(526, "zm1_room5_relay", "7.001", False, "zones"),
    KnxObject(527, "zm1_room6_temp", "9.001", True, "zones"),
    KnxObject(528, "zm1_room6_setpoint", "9.001", True, "zones"),
    KnxObject(529, "zm1_room6_humidity", "9.007", True, "zones"),
    KnxObject(530, "zm1_room6_mode", "7.001", True, "zones"),
    KnxObject(531, "zm1_room6_relay", "7.001", False, "zones"),
    KnxObject(532, "zm1_room7_temp", "9.001", True, "zones"),
    KnxObject(533, "zm1_room7_setpoint", "9.001", True, "zones"),
    KnxObject(534, "zm1_room7_humidity", "9.007", True, "zones"),
    KnxObject(535, "zm1_room7_mode", "7.001", True, "zones"),
    KnxObject(536, "zm1_room7_relay", "7.001", False, "zones"),
    KnxObject(537, "zm1_room8_temp", "9.001", True, "zones"),
    KnxObject(538, "zm1_room8_setpoint", "9.001", True, "zones"),
    KnxObject(539, "zm1_room8_humidity", "9.007", True, "zones"),
    KnxObject(540, "zm1_room8_mode", "7.001", True, "zones"),
    KnxObject(541, "zm1_room8_relay", "7.001", False, "zones"),
    KnxObject(547, "zm2_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(548, "zm2_dehumidification", "7.001", False, "zones"),
    KnxObject(549, "zm2_room1_temp", "9.001", True, "zones"),
    KnxObject(550, "zm2_room1_setpoint", "9.001", True, "zones"),
    KnxObject(551, "zm2_room1_humidity", "9.007", True, "zones"),
    KnxObject(552, "zm2_room1_mode", "7.001", True, "zones"),
    KnxObject(553, "zm2_room1_relay", "7.001", False, "zones"),
    KnxObject(554, "zm2_room2_temp", "9.001", True, "zones"),
    KnxObject(555, "zm2_room2_setpoint", "9.001", True, "zones"),
    KnxObject(556, "zm2_room2_humidity", "9.007", True, "zones"),
    KnxObject(557, "zm2_room2_mode", "7.001", True, "zones"),
    KnxObject(558, "zm2_room2_relay", "7.001", False, "zones"),
    KnxObject(559, "zm2_room3_temp", "9.001", True, "zones"),
    KnxObject(560, "zm2_room3_setpoint", "9.001", True, "zones"),
    KnxObject(561, "zm2_room3_humidity", "9.007", True, "zones"),
    KnxObject(562, "zm2_room3_mode", "7.001", True, "zones"),
    KnxObject(563, "zm2_room3_relay", "7.001", False, "zones"),
    KnxObject(564, "zm2_room4_temp", "9.001", True, "zones"),
    KnxObject(565, "zm2_room4_setpoint", "9.001", True, "zones"),
    KnxObject(566, "zm2_room4_humidity", "9.007", True, "zones"),
    KnxObject(567, "zm2_room4_mode", "7.001", True, "zones"),
    KnxObject(568, "zm2_room4_relay", "7.001", False, "zones"),
    KnxObject(569, "zm2_room5_temp", "9.001", True, "zones"),
    KnxObject(570, "zm2_room5_setpoint", "9.001", True, "zones"),
    KnxObject(571, "zm2_room5_humidity", "9.007", True, "zones"),
    KnxObject(572, "zm2_room5_mode", "7.001", True, "zones"),
    KnxObject(573, "zm2_room5_relay", "7.001", False, "zones"),
    KnxObject(574, "zm2_room6_temp", "9.001", True, "zones"),
    KnxObject(575, "zm2_room6_setpoint", "9.001", True, "zones"),
    KnxObject(576, "zm2_room6_humidity", "9.007", True, "zones"),
    KnxObject(577, "zm2_room6_mode", "7.001", True, "zones"),
    KnxObject(578, "zm2_room6_relay", "7.001", False, "zones"),
    KnxObject(579, "zm2_room7_temp", "9.001", True, "zones"),
    KnxObject(580, "zm2_room7_setpoint", "9.001", True, "zones"),
    KnxObject(581, "zm2_room7_humidity", "9.007", True, "zones"),
    KnxObject(582, "zm2_room7_mode", "7.001", True, "zones"),
    KnxObject(583, "zm2_room7_relay", "7.001", False, "zones"),
    KnxObject(584, "zm2_room8_temp", "9.001", True, "zones"),
    KnxObject(585, "zm2_room8_setpoint", "9.001", True, "zones"),
    KnxObject(586, "zm2_room8_humidity", "9.007", True, "zones"),
    KnxObject(587, "zm2_room8_mode", "7.001", True, "zones"),
    KnxObject(588, "zm2_room8_relay", "7.001", False, "zones"),
    KnxObject(594, "zm3_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(595, "zm3_dehumidification", "7.001", False, "zones"),
    KnxObject(596, "zm3_room1_temp", "9.001", True, "zones"),
    KnxObject(597, "zm3_room1_setpoint", "9.001", True, "zones"),
    KnxObject(598, "zm3_room1_humidity", "9.007", True, "zones"),
    KnxObject(599, "zm3_room1_mode", "7.001", True, "zones"),
    KnxObject(600, "zm3_room1_relay", "7.001", False, "zones"),
    KnxObject(601, "zm3_room2_temp", "9.001", True, "zones"),
    KnxObject(602, "zm3_room2_setpoint", "9.001", True, "zones"),
    KnxObject(603, "zm3_room2_humidity", "9.007", True, "zones"),
    KnxObject(604, "zm3_room2_mode", "7.001", True, "zones"),
    KnxObject(605, "zm3_room2_relay", "7.001", False, "zones"),
    KnxObject(606, "zm3_room3_temp", "9.001", True, "zones"),
    KnxObject(607, "zm3_room3_setpoint", "9.001", True, "zones"),
    KnxObject(608, "zm3_room3_humidity", "9.007", True, "zones"),
    KnxObject(609, "zm3_room3_mode", "7.001", True, "zones"),
    KnxObject(610, "zm3_room3_relay", "7.001", False, "zones"),
    KnxObject(611, "zm3_room4_temp", "9.001", True, "zones"),
    KnxObject(612, "zm3_room4_setpoint", "9.001", True, "zones"),
    KnxObject(613, "zm3_room4_humidity", "9.007", True, "zones"),
    KnxObject(614, "zm3_room4_mode", "7.001", True, "zones"),
    KnxObject(615, "zm3_room4_relay", "7.001", False, "zones"),
    KnxObject(616, "zm3_room5_temp", "9.001", True, "zones"),
    KnxObject(617, "zm3_room5_setpoint", "9.001", True, "zones"),
    KnxObject(618, "zm3_room5_humidity", "9.007", True, "zones"),
    KnxObject(619, "zm3_room5_mode", "7.001", True, "zones"),
    KnxObject(620, "zm3_room5_relay", "7.001", False, "zones"),
    KnxObject(621, "zm3_room6_temp", "9.001", True, "zones"),
    KnxObject(622, "zm3_room6_setpoint", "9.001", True, "zones"),
    KnxObject(623, "zm3_room6_humidity", "9.007", True, "zones"),
    KnxObject(624, "zm3_room6_mode", "7.001", True, "zones"),
    KnxObject(625, "zm3_room6_relay", "7.001", False, "zones"),
    KnxObject(626, "zm3_room7_temp", "9.001", True, "zones"),
    KnxObject(627, "zm3_room7_setpoint", "9.001", True, "zones"),
    KnxObject(628, "zm3_room7_humidity", "9.007", True, "zones"),
    KnxObject(629, "zm3_room7_mode", "7.001", True, "zones"),
    KnxObject(630, "zm3_room7_relay", "7.001", False, "zones"),
    KnxObject(631, "zm3_room8_temp", "9.001", True, "zones"),
    KnxObject(632, "zm3_room8_setpoint", "9.001", True, "zones"),
    KnxObject(633, "zm3_room8_humidity", "9.007", True, "zones"),
    KnxObject(634, "zm3_room8_mode", "7.001", True, "zones"),
    KnxObject(635, "zm3_room8_relay", "7.001", False, "zones"),
    KnxObject(641, "zm4_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(642, "zm4_dehumidification", "7.001", False, "zones"),
    KnxObject(643, "zm4_room1_temp", "9.001", True, "zones"),
    KnxObject(644, "zm4_room1_setpoint", "9.001", True, "zones"),
    KnxObject(645, "zm4_room1_humidity", "9.007", True, "zones"),
    KnxObject(646, "zm4_room1_mode", "7.001", True, "zones"),
    KnxObject(647, "zm4_room1_relay", "7.001", False, "zones"),
    KnxObject(648, "zm4_room2_temp", "9.001", True, "zones"),
    KnxObject(649, "zm4_room2_setpoint", "9.001", True, "zones"),
    KnxObject(650, "zm4_room2_humidity", "9.007", True, "zones"),
    KnxObject(651, "zm4_room2_mode", "7.001", True, "zones"),
    KnxObject(652, "zm4_room2_relay", "7.001", False, "zones"),
    KnxObject(653, "zm4_room3_temp", "9.001", True, "zones"),
    KnxObject(654, "zm4_room3_setpoint", "9.001", True, "zones"),
    KnxObject(655, "zm4_room3_humidity", "9.007", True, "zones"),
    KnxObject(656, "zm4_room3_mode", "7.001", True, "zones"),
    KnxObject(657, "zm4_room3_relay", "7.001", False, "zones"),
    KnxObject(658, "zm4_room4_temp", "9.001", True, "zones"),
    KnxObject(659, "zm4_room4_setpoint", "9.001", True, "zones"),
    KnxObject(660, "zm4_room4_humidity", "9.007", True, "zones"),
    KnxObject(661, "zm4_room4_mode", "7.001", True, "zones"),
    KnxObject(662, "zm4_room4_relay", "7.001", False, "zones"),
    KnxObject(663, "zm4_room5_temp", "9.001", True, "zones"),
    KnxObject(664, "zm4_room5_setpoint", "9.001", True, "zones"),
    KnxObject(665, "zm4_room5_humidity", "9.007", True, "zones"),
    KnxObject(666, "zm4_room5_mode", "7.001", True, "zones"),
    KnxObject(667, "zm4_room5_relay", "7.001", False, "zones"),
    KnxObject(668, "zm4_room6_temp", "9.001", True, "zones"),
    KnxObject(669, "zm4_room6_setpoint", "9.001", True, "zones"),
    KnxObject(670, "zm4_room6_humidity", "9.007", True, "zones"),
    KnxObject(671, "zm4_room6_mode", "7.001", True, "zones"),
    KnxObject(672, "zm4_room6_relay", "7.001", False, "zones"),
    KnxObject(673, "zm4_room7_temp", "9.001", True, "zones"),
    KnxObject(674, "zm4_room7_setpoint", "9.001", True, "zones"),
    KnxObject(675, "zm4_room7_humidity", "9.007", True, "zones"),
    KnxObject(676, "zm4_room7_mode", "7.001", True, "zones"),
    KnxObject(677, "zm4_room7_relay", "7.001", False, "zones"),
    KnxObject(678, "zm4_room8_temp", "9.001", True, "zones"),
    KnxObject(679, "zm4_room8_setpoint", "9.001", True, "zones"),
    KnxObject(680, "zm4_room8_humidity", "9.007", True, "zones"),
    KnxObject(681, "zm4_room8_mode", "7.001", True, "zones"),
    KnxObject(682, "zm4_room8_relay", "7.001", False, "zones"),
    KnxObject(688, "zm5_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(689, "zm5_dehumidification", "7.001", False, "zones"),
    KnxObject(690, "zm5_room1_temp", "9.001", True, "zones"),
    KnxObject(691, "zm5_room1_setpoint", "9.001", True, "zones"),
    KnxObject(692, "zm5_room1_humidity", "9.007", True, "zones"),
    KnxObject(693, "zm5_room1_mode", "7.001", True, "zones"),
    KnxObject(694, "zm5_room1_relay", "7.001", False, "zones"),
    KnxObject(695, "zm5_room2_temp", "9.001", True, "zones"),
    KnxObject(696, "zm5_room2_setpoint", "9.001", True, "zones"),
    KnxObject(697, "zm5_room2_humidity", "9.007", True, "zones"),
    KnxObject(698, "zm5_room2_mode", "7.001", True, "zones"),
    KnxObject(699, "zm5_room2_relay", "7.001", False, "zones"),
    KnxObject(700, "zm5_room3_temp", "9.001", True, "zones"),
    KnxObject(701, "zm5_room3_setpoint", "9.001", True, "zones"),
    KnxObject(702, "zm5_room3_humidity", "9.007", True, "zones"),
    KnxObject(703, "zm5_room3_mode", "7.001", True, "zones"),
    KnxObject(704, "zm5_room3_relay", "7.001", False, "zones"),
    KnxObject(705, "zm5_room4_temp", "9.001", True, "zones"),
    KnxObject(706, "zm5_room4_setpoint", "9.001", True, "zones"),
    KnxObject(707, "zm5_room4_humidity", "9.007", True, "zones"),
    KnxObject(708, "zm5_room4_mode", "7.001", True, "zones"),
    KnxObject(709, "zm5_room4_relay", "7.001", False, "zones"),
    KnxObject(710, "zm5_room5_temp", "9.001", True, "zones"),
    KnxObject(711, "zm5_room5_setpoint", "9.001", True, "zones"),
    KnxObject(712, "zm5_room5_humidity", "9.007", True, "zones"),
    KnxObject(713, "zm5_room5_mode", "7.001", True, "zones"),
    KnxObject(714, "zm5_room5_relay", "7.001", False, "zones"),
    KnxObject(715, "zm5_room6_temp", "9.001", True, "zones"),
    KnxObject(716, "zm5_room6_setpoint", "9.001", True, "zones"),
    KnxObject(717, "zm5_room6_humidity", "9.007", True, "zones"),
    KnxObject(718, "zm5_room6_mode", "7.001", True, "zones"),
    KnxObject(719, "zm5_room6_relay", "7.001", False, "zones"),
    KnxObject(720, "zm5_room7_temp", "9.001", True, "zones"),
    KnxObject(721, "zm5_room7_setpoint", "9.001", True, "zones"),
    KnxObject(722, "zm5_room7_humidity", "9.007", True, "zones"),
    KnxObject(723, "zm5_room7_mode", "7.001", True, "zones"),
    KnxObject(724, "zm5_room7_relay", "7.001", False, "zones"),
    KnxObject(725, "zm5_room8_temp", "9.001", True, "zones"),
    KnxObject(726, "zm5_room8_setpoint", "9.001", True, "zones"),
    KnxObject(727, "zm5_room8_humidity", "9.007", True, "zones"),
    KnxObject(728, "zm5_room8_mode", "7.001", True, "zones"),
    KnxObject(729, "zm5_room8_relay", "7.001", False, "zones"),
    KnxObject(735, "zm6_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(736, "zm6_dehumidification", "7.001", False, "zones"),
    KnxObject(737, "zm6_room1_temp", "9.001", True, "zones"),
    KnxObject(738, "zm6_room1_setpoint", "9.001", True, "zones"),
    KnxObject(739, "zm6_room1_humidity", "9.007", True, "zones"),
    KnxObject(740, "zm6_room1_mode", "7.001", True, "zones"),
    KnxObject(741, "zm6_room1_relay", "7.001", False, "zones"),
    KnxObject(742, "zm6_room2_temp", "9.001", True, "zones"),
    KnxObject(743, "zm6_room2_setpoint", "9.001", True, "zones"),
    KnxObject(744, "zm6_room2_humidity", "9.007", True, "zones"),
    KnxObject(745, "zm6_room2_mode", "7.001", True, "zones"),
    KnxObject(746, "zm6_room2_relay", "7.001", False, "zones"),
    KnxObject(747, "zm6_room3_temp", "9.001", True, "zones"),
    KnxObject(748, "zm6_room3_setpoint", "9.001", True, "zones"),
    KnxObject(749, "zm6_room3_humidity", "9.007", True, "zones"),
    KnxObject(750, "zm6_room3_mode", "7.001", True, "zones"),
    KnxObject(751, "zm6_room3_relay", "7.001", False, "zones"),
    KnxObject(752, "zm6_room4_temp", "9.001", True, "zones"),
    KnxObject(753, "zm6_room4_setpoint", "9.001", True, "zones"),
    KnxObject(754, "zm6_room4_humidity", "9.007", True, "zones"),
    KnxObject(755, "zm6_room4_mode", "7.001", True, "zones"),
    KnxObject(756, "zm6_room4_relay", "7.001", False, "zones"),
    KnxObject(757, "zm6_room5_temp", "9.001", True, "zones"),
    KnxObject(758, "zm6_room5_setpoint", "9.001", True, "zones"),
    KnxObject(759, "zm6_room5_humidity", "9.007", True, "zones"),
    KnxObject(760, "zm6_room5_mode", "7.001", True, "zones"),
    KnxObject(761, "zm6_room5_relay", "7.001", False, "zones"),
    KnxObject(762, "zm6_room6_temp", "9.001", True, "zones"),
    KnxObject(763, "zm6_room6_setpoint", "9.001", True, "zones"),
    KnxObject(764, "zm6_room6_humidity", "9.007", True, "zones"),
    KnxObject(765, "zm6_room6_mode", "7.001", True, "zones"),
    KnxObject(766, "zm6_room6_relay", "7.001", False, "zones"),
    KnxObject(767, "zm6_room7_temp", "9.001", True, "zones"),
    KnxObject(768, "zm6_room7_setpoint", "9.001", True, "zones"),
    KnxObject(769, "zm6_room7_humidity", "9.007", True, "zones"),
    KnxObject(770, "zm6_room7_mode", "7.001", True, "zones"),
    KnxObject(771, "zm6_room7_relay", "7.001", False, "zones"),
    KnxObject(772, "zm6_room8_temp", "9.001", True, "zones"),
    KnxObject(773, "zm6_room8_setpoint", "9.001", True, "zones"),
    KnxObject(774, "zm6_room8_humidity", "9.007", True, "zones"),
    KnxObject(775, "zm6_room8_mode", "7.001", True, "zones"),
    KnxObject(776, "zm6_room8_relay", "7.001", False, "zones"),
    KnxObject(782, "zm7_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(783, "zm7_dehumidification", "7.001", False, "zones"),
    KnxObject(784, "zm7_room1_temp", "9.001", True, "zones"),
    KnxObject(785, "zm7_room1_setpoint", "9.001", True, "zones"),
    KnxObject(786, "zm7_room1_humidity", "9.007", True, "zones"),
    KnxObject(787, "zm7_room1_mode", "7.001", True, "zones"),
    KnxObject(788, "zm7_room1_relay", "7.001", False, "zones"),
    KnxObject(789, "zm7_room2_temp", "9.001", True, "zones"),
    KnxObject(790, "zm7_room2_setpoint", "9.001", True, "zones"),
    KnxObject(791, "zm7_room2_humidity", "9.007", True, "zones"),
    KnxObject(792, "zm7_room2_mode", "7.001", True, "zones"),
    KnxObject(793, "zm7_room2_relay", "7.001", False, "zones"),
    KnxObject(794, "zm7_room3_temp", "9.001", True, "zones"),
    KnxObject(795, "zm7_room3_setpoint", "9.001", True, "zones"),
    KnxObject(796, "zm7_room3_humidity", "9.007", True, "zones"),
    KnxObject(797, "zm7_room3_mode", "7.001", True, "zones"),
    KnxObject(798, "zm7_room3_relay", "7.001", False, "zones"),
    KnxObject(799, "zm7_room4_temp", "9.001", True, "zones"),
    KnxObject(800, "zm7_room4_setpoint", "9.001", True, "zones"),
    KnxObject(801, "zm7_room4_humidity", "9.007", True, "zones"),
    KnxObject(802, "zm7_room4_mode", "7.001", True, "zones"),
    KnxObject(803, "zm7_room4_relay", "7.001", False, "zones"),
    KnxObject(804, "zm7_room5_temp", "9.001", True, "zones"),
    KnxObject(805, "zm7_room5_setpoint", "9.001", True, "zones"),
    KnxObject(806, "zm7_room5_humidity", "9.007", True, "zones"),
    KnxObject(807, "zm7_room5_mode", "7.001", True, "zones"),
    KnxObject(808, "zm7_room5_relay", "7.001", False, "zones"),
    KnxObject(809, "zm7_room6_temp", "9.001", True, "zones"),
    KnxObject(810, "zm7_room6_setpoint", "9.001", True, "zones"),
    KnxObject(811, "zm7_room6_humidity", "9.007", True, "zones"),
    KnxObject(812, "zm7_room6_mode", "7.001", True, "zones"),
    KnxObject(813, "zm7_room6_relay", "7.001", False, "zones"),
    KnxObject(814, "zm7_room7_temp", "9.001", True, "zones"),
    KnxObject(815, "zm7_room7_setpoint", "9.001", True, "zones"),
    KnxObject(816, "zm7_room7_humidity", "9.007", True, "zones"),
    KnxObject(817, "zm7_room7_mode", "7.001", True, "zones"),
    KnxObject(818, "zm7_room7_relay", "7.001", False, "zones"),
    KnxObject(819, "zm7_room8_temp", "9.001", True, "zones"),
    KnxObject(820, "zm7_room8_setpoint", "9.001", True, "zones"),
    KnxObject(821, "zm7_room8_humidity", "9.007", True, "zones"),
    KnxObject(822, "zm7_room8_mode", "7.001", True, "zones"),
    KnxObject(823, "zm7_room8_relay", "7.001", False, "zones"),
    KnxObject(829, "zm8_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(830, "zm8_dehumidification", "7.001", False, "zones"),
    KnxObject(831, "zm8_room1_temp", "9.001", True, "zones"),
    KnxObject(832, "zm8_room1_setpoint", "9.001", True, "zones"),
    KnxObject(833, "zm8_room1_humidity", "9.007", True, "zones"),
    KnxObject(834, "zm8_room1_mode", "7.001", True, "zones"),
    KnxObject(835, "zm8_room1_relay", "7.001", False, "zones"),
    KnxObject(836, "zm8_room2_temp", "9.001", True, "zones"),
    KnxObject(837, "zm8_room2_setpoint", "9.001", True, "zones"),
    KnxObject(838, "zm8_room2_humidity", "9.007", True, "zones"),
    KnxObject(839, "zm8_room2_mode", "7.001", True, "zones"),
    KnxObject(840, "zm8_room2_relay", "7.001", False, "zones"),
    KnxObject(841, "zm8_room3_temp", "9.001", True, "zones"),
    KnxObject(842, "zm8_room3_setpoint", "9.001", True, "zones"),
    KnxObject(843, "zm8_room3_humidity", "9.007", True, "zones"),
    KnxObject(844, "zm8_room3_mode", "7.001", True, "zones"),
    KnxObject(845, "zm8_room3_relay", "7.001", False, "zones"),
    KnxObject(846, "zm8_room4_temp", "9.001", True, "zones"),
    KnxObject(847, "zm8_room4_setpoint", "9.001", True, "zones"),
    KnxObject(848, "zm8_room4_humidity", "9.007", True, "zones"),
    KnxObject(849, "zm8_room4_mode", "7.001", True, "zones"),
    KnxObject(850, "zm8_room4_relay", "7.001", False, "zones"),
    KnxObject(851, "zm8_room5_temp", "9.001", True, "zones"),
    KnxObject(852, "zm8_room5_setpoint", "9.001", True, "zones"),
    KnxObject(853, "zm8_room5_humidity", "9.007", True, "zones"),
    KnxObject(854, "zm8_room5_mode", "7.001", True, "zones"),
    KnxObject(855, "zm8_room5_relay", "7.001", False, "zones"),
    KnxObject(856, "zm8_room6_temp", "9.001", True, "zones"),
    KnxObject(857, "zm8_room6_setpoint", "9.001", True, "zones"),
    KnxObject(858, "zm8_room6_humidity", "9.007", True, "zones"),
    KnxObject(859, "zm8_room6_mode", "7.001", True, "zones"),
    KnxObject(860, "zm8_room6_relay", "7.001", False, "zones"),
    KnxObject(861, "zm8_room7_temp", "9.001", True, "zones"),
    KnxObject(862, "zm8_room7_setpoint", "9.001", True, "zones"),
    KnxObject(863, "zm8_room7_humidity", "9.007", True, "zones"),
    KnxObject(864, "zm8_room7_mode", "7.001", True, "zones"),
    KnxObject(865, "zm8_room7_relay", "7.001", False, "zones"),
    KnxObject(866, "zm8_room8_temp", "9.001", True, "zones"),
    KnxObject(867, "zm8_room8_setpoint", "9.001", True, "zones"),
    KnxObject(868, "zm8_room8_humidity", "9.007", True, "zones"),
    KnxObject(869, "zm8_room8_mode", "7.001", True, "zones"),
    KnxObject(870, "zm8_room8_relay", "7.001", False, "zones"),
    KnxObject(876, "zm9_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(877, "zm9_dehumidification", "7.001", False, "zones"),
    KnxObject(878, "zm9_room1_temp", "9.001", True, "zones"),
    KnxObject(879, "zm9_room1_setpoint", "9.001", True, "zones"),
    KnxObject(880, "zm9_room1_humidity", "9.007", True, "zones"),
    KnxObject(881, "zm9_room1_mode", "7.001", True, "zones"),
    KnxObject(882, "zm9_room1_relay", "7.001", False, "zones"),
    KnxObject(883, "zm9_room2_temp", "9.001", True, "zones"),
    KnxObject(884, "zm9_room2_setpoint", "9.001", True, "zones"),
    KnxObject(885, "zm9_room2_humidity", "9.007", True, "zones"),
    KnxObject(886, "zm9_room2_mode", "7.001", True, "zones"),
    KnxObject(887, "zm9_room2_relay", "7.001", False, "zones"),
    KnxObject(888, "zm9_room3_temp", "9.001", True, "zones"),
    KnxObject(889, "zm9_room3_setpoint", "9.001", True, "zones"),
    KnxObject(890, "zm9_room3_humidity", "9.007", True, "zones"),
    KnxObject(891, "zm9_room3_mode", "7.001", True, "zones"),
    KnxObject(892, "zm9_room3_relay", "7.001", False, "zones"),
    KnxObject(893, "zm9_room4_temp", "9.001", True, "zones"),
    KnxObject(894, "zm9_room4_setpoint", "9.001", True, "zones"),
    KnxObject(895, "zm9_room4_humidity", "9.007", True, "zones"),
    KnxObject(896, "zm9_room4_mode", "7.001", True, "zones"),
    KnxObject(897, "zm9_room4_relay", "7.001", False, "zones"),
    KnxObject(898, "zm9_room5_temp", "9.001", True, "zones"),
    KnxObject(899, "zm9_room5_setpoint", "9.001", True, "zones"),
    KnxObject(900, "zm9_room5_humidity", "9.007", True, "zones"),
    KnxObject(901, "zm9_room5_mode", "7.001", True, "zones"),
    KnxObject(902, "zm9_room5_relay", "7.001", False, "zones"),
    KnxObject(903, "zm9_room6_temp", "9.001", True, "zones"),
    KnxObject(904, "zm9_room6_setpoint", "9.001", True, "zones"),
    KnxObject(905, "zm9_room6_humidity", "9.007", True, "zones"),
    KnxObject(906, "zm9_room6_mode", "7.001", True, "zones"),
    KnxObject(907, "zm9_room6_relay", "7.001", False, "zones"),
    KnxObject(908, "zm9_room7_temp", "9.001", True, "zones"),
    KnxObject(909, "zm9_room7_setpoint", "9.001", True, "zones"),
    KnxObject(910, "zm9_room7_humidity", "9.007", True, "zones"),
    KnxObject(911, "zm9_room7_mode", "7.001", True, "zones"),
    KnxObject(912, "zm9_room7_relay", "7.001", False, "zones"),
    KnxObject(913, "zm9_room8_temp", "9.001", True, "zones"),
    KnxObject(914, "zm9_room8_setpoint", "9.001", True, "zones"),
    KnxObject(915, "zm9_room8_humidity", "9.007", True, "zones"),
    KnxObject(916, "zm9_room8_mode", "7.001", True, "zones"),
    KnxObject(917, "zm9_room8_relay", "7.001", False, "zones"),
    KnxObject(923, "zm10_mode_heat_cool", "7.001", False, "zones"),
    KnxObject(924, "zm10_dehumidification", "7.001", False, "zones"),
    KnxObject(925, "zm10_room1_temp", "9.001", True, "zones"),
    KnxObject(926, "zm10_room1_setpoint", "9.001", True, "zones"),
    KnxObject(927, "zm10_room1_humidity", "9.007", True, "zones"),
    KnxObject(928, "zm10_room1_mode", "7.001", True, "zones"),
    KnxObject(929, "zm10_room1_relay", "7.001", False, "zones"),
    KnxObject(930, "zm10_room2_temp", "9.001", True, "zones"),
    KnxObject(931, "zm10_room2_setpoint", "9.001", True, "zones"),
    KnxObject(932, "zm10_room2_humidity", "9.007", True, "zones"),
    KnxObject(933, "zm10_room2_mode", "7.001", True, "zones"),
    KnxObject(934, "zm10_room2_relay", "7.001", False, "zones"),
    KnxObject(935, "zm10_room3_temp", "9.001", True, "zones"),
    KnxObject(936, "zm10_room3_setpoint", "9.001", True, "zones"),
    KnxObject(937, "zm10_room3_humidity", "9.007", True, "zones"),
    KnxObject(938, "zm10_room3_mode", "7.001", True, "zones"),
    KnxObject(939, "zm10_room3_relay", "7.001", False, "zones"),
    KnxObject(940, "zm10_room4_temp", "9.001", True, "zones"),
    KnxObject(941, "zm10_room4_setpoint", "9.001", True, "zones"),
    KnxObject(942, "zm10_room4_humidity", "9.007", True, "zones"),
    KnxObject(943, "zm10_room4_mode", "7.001", True, "zones"),
    KnxObject(944, "zm10_room4_relay", "7.001", False, "zones"),
    KnxObject(945, "zm10_room5_temp", "9.001", True, "zones"),
    KnxObject(946, "zm10_room5_setpoint", "9.001", True, "zones"),
    KnxObject(947, "zm10_room5_humidity", "9.007", True, "zones"),
    KnxObject(948, "zm10_room5_mode", "7.001", True, "zones"),
    KnxObject(949, "zm10_room5_relay", "7.001", False, "zones"),
    KnxObject(950, "zm10_room6_temp", "9.001", True, "zones"),
    KnxObject(951, "zm10_room6_setpoint", "9.001", True, "zones"),
    KnxObject(952, "zm10_room6_humidity", "9.007", True, "zones"),
    KnxObject(953, "zm10_room6_mode", "7.001", True, "zones"),
    KnxObject(954, "zm10_room6_relay", "7.001", False, "zones"),
    KnxObject(955, "zm10_room7_temp", "9.001", True, "zones"),
    KnxObject(956, "zm10_room7_setpoint", "9.001", True, "zones"),
    KnxObject(957, "zm10_room7_humidity", "9.007", True, "zones"),
    KnxObject(958, "zm10_room7_mode", "7.001", True, "zones"),
    KnxObject(959, "zm10_room7_relay", "7.001", False, "zones"),
    KnxObject(960, "zm10_room8_temp", "9.001", True, "zones"),
    KnxObject(961, "zm10_room8_setpoint", "9.001", True, "zones"),
    KnxObject(962, "zm10_room8_humidity", "9.007", True, "zones"),
    KnxObject(963, "zm10_room8_mode", "7.001", True, "zones"),
    KnxObject(964, "zm10_room8_relay", "7.001", False, "zones"),
    KnxObject(970, "booster_fault", "7.001", False, "booster"),
    KnxObject(971, "booster_interlock", "7.001", False, "booster"),
    KnxObject(975, "booster_a_source_inlet_temp", "9.001", False, "booster"),
    KnxObject(976, "booster_a_source_outlet_temp", "9.001", False, "booster"),
    KnxObject(977, "booster_a_storage_temp", "9.001", False, "booster"),
    KnxObject(978, "booster_a_flow_temp", "9.001", False, "booster"),
    KnxObject(979, "booster_a_return_temp", "9.001", False, "booster"),
    KnxObject(980, "booster_a_source_pump", "5.001", False, "booster"),
    KnxObject(981, "booster_a_charging_pump", "5.001", False, "booster"),
    KnxObject(982, "booster_a_compressor", "7.001", False, "booster"),
    KnxObject(983, "booster_b_compressor", "7.001", False, "booster"),
    KnxObject(985, "booster_b_source_inlet_temp", "9.001", False, "booster"),
    KnxObject(986, "booster_b_source_outlet_temp", "9.001", False, "booster"),
    KnxObject(987, "booster_b_storage_temp", "9.001", False, "booster"),
    KnxObject(988, "booster_b_flow_temp", "9.001", False, "booster"),
    KnxObject(989, "booster_b_return_temp", "9.001", False, "booster"),
    KnxObject(990, "booster_b_source_pump", "5.001", False, "booster"),
    KnxObject(991, "booster_b_charging_pump", "5.001", False, "booster"),
    KnxObject(992, "house_consumption", "9.024", True, "pv"),
    KnxObject(993, "battery_discharge", "9.024", True, "pv"),
    KnxObject(994, "battery_soc", "5.001", True, "pv"),
    KnxObject(995, "pv_surplus", "9.024", True, "pv"),
    KnxObject(996, "pv_production", "9.024", True, "pv"),
    KnxObject(997, "power_consumption_hp", "9.024", False, "pv"),
    KnxObject(998, "thermal_power_flow_sensor", "9.024", False, "pv"),
    KnxObject(999, "total_heat_energy", "14.031", False, "pv"),
)


OBJECTS_BY_REGISTER: Final[Mapping[str, KnxObject]] = {obj.register: obj for obj in KNX_OBJECTS}
OBJECTS_BY_NUMBER: Final[Mapping[int, KnxObject]] = {obj.number: obj for obj in KNX_OBJECTS}


def object_for_register(register: str) -> KnxObject | None:
    """Return the catalogue entry for ``register``, or ``None``."""
    return OBJECTS_BY_REGISTER.get(register)


def parse_group_address(value: str) -> int:
    """Parse a KNX group address into its raw 16-bit form.

    Accepts three-level (``8/1/12``), two-level (``8/268``) and free
    (``16652``) notation, mirroring what ETS and xknx accept.
    """
    text = str(value).strip()
    if not text:
        raise InvalidGroupAddressError("empty group address")
    parts = text.split("/")
    try:
        numbers = [int(part) for part in parts]
    except ValueError as err:
        raise InvalidGroupAddressError(f"not a group address: {value!r}") from err
    if any(number < 0 for number in numbers):
        raise InvalidGroupAddressError(f"negative group address: {value!r}")

    if len(numbers) == 3:
        main, middle, sub = numbers
        if main > 31 or middle > 7 or sub > 255:
            raise InvalidGroupAddressError(f"group address out of range: {value!r}")
        raw = (main << 11) + (middle << 8) + sub
    elif len(numbers) == 2:
        main, sub = numbers
        if main > 31 or sub > 2047:
            raise InvalidGroupAddressError(f"group address out of range: {value!r}")
        raw = (main << 11) + sub
    elif len(numbers) == 1:
        raw = numbers[0]
    else:
        raise InvalidGroupAddressError(f"not a group address: {value!r}")

    if raw > MAX_RAW_GROUP_ADDRESS:
        raise InvalidGroupAddressError(f"group address out of range: {value!r}")
    if raw == 0:
        # 0/0/0 is the broadcast address and must never carry data.
        raise InvalidGroupAddressError("0/0/0 is reserved for broadcast")
    return raw


def format_group_address(raw: int) -> str:
    """Render a raw group address in three-level notation."""
    if not 0 < raw <= MAX_RAW_GROUP_ADDRESS:
        raise InvalidGroupAddressError(f"group address out of range: {raw}")
    return f"{(raw >> 11) & 0x1F}/{(raw >> 8) & 0x07}/{raw & 0xFF}"


def validate_base_address(value: str) -> int:
    """Parse a base group address and check the catalogue fits above it."""
    raw = parse_group_address(value)
    if raw + MAX_OBJECT_NUMBER > MAX_RAW_GROUP_ADDRESS:
        raise InvalidGroupAddressError(
            f"base address {value!r} leaves less than {MAX_OBJECT_NUMBER} addresses "
            "below the end of the KNX address space"
        )
    return raw


def resolve_group_addresses(
    base_address: str,
    *,
    overrides: Mapping[str, str] | None = None,
    registers: Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
) -> dict[str, str]:
    """Map register names to group addresses.

    Every object gets ``base_address + object_number`` — the layout the
    objects already have in the BAOS gateway, so one base address is
    enough for a fresh ETS project. ``overrides`` replaces individual
    addresses for installations whose project already uses others; an
    override with an empty value excludes that object entirely.

    ``registers`` restricts the result to registers the controller
    actually exposes, ``groups`` to selected catalogue groups. Both
    default to the whole catalogue.

    Raises :class:`InvalidGroupAddressError` when two served objects
    would end up on the same group address — either two overrides, or an
    override claiming the derived address of another object. The bridge
    keys its routing by address, so one of them would silently shadow
    the other.
    """
    base_raw = validate_base_address(base_address)
    override_map = dict(overrides or {})
    allowed_registers = None if registers is None else set(registers)
    allowed_groups = None if groups is None else set(groups)

    resolved: dict[str, str] = {}
    claimed_by: dict[str, str] = {}
    for obj in KNX_OBJECTS:
        if allowed_registers is not None and obj.register not in allowed_registers:
            continue
        if allowed_groups is not None and obj.group not in allowed_groups:
            continue
        if obj.register in override_map:
            override = str(override_map[obj.register]).strip()
            if not override:
                continue
            address = format_group_address(parse_group_address(override))
        else:
            address = format_group_address(base_raw + obj.number)
        if (other := claimed_by.get(address)) is not None:
            raise InvalidGroupAddressError(
                f"group address {address} is assigned to both {other!r} and {obj.register!r}"
            )
        claimed_by[address] = obj.register
        resolved[obj.register] = address
    return resolved


def validate_overrides(overrides: Mapping[str, str]) -> dict[str, str]:
    """Normalize an override map, dropping empty entries.

    Raises :class:`InvalidGroupAddressError` for unknown register names,
    unparsable addresses and addresses assigned to more than one object —
    a duplicate would silently make two objects share one group address.
    """
    normalized: dict[str, str] = {}
    seen: dict[str, str] = {}
    for register, address in overrides.items():
        text = str(address).strip()
        if not text:
            continue
        if register not in OBJECTS_BY_REGISTER:
            raise InvalidGroupAddressError(f"unknown IDM KNX object: {register!r}")
        formatted = format_group_address(parse_group_address(text))
        if (other := seen.get(formatted)) is not None:
            raise InvalidGroupAddressError(f"group address {formatted} is assigned to both {other!r} and {register!r}")
        seen[formatted] = register
        normalized[register] = formatted
    return normalized


__all__ = [
    "KNX_OBJECTS",
    "MAX_OBJECT_NUMBER",
    "MAX_RAW_GROUP_ADDRESS",
    "OBJECTS_BY_NUMBER",
    "OBJECTS_BY_REGISTER",
    "OBJECT_GROUPS",
    "InvalidGroupAddressError",
    "KnxObject",
    "format_group_address",
    "object_for_register",
    "parse_group_address",
    "resolve_group_addresses",
    "validate_base_address",
    "validate_overrides",
]
