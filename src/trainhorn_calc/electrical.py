"""Copper wire gauge (AWG) selection for 12 V / 24 V horn and compressor circuits.

Resistance per AWG size
-----------------------
Resistances are *computed* from the AWG definition rather than typed in from
a table:

* AWG diameter (ASTM B258): ``d(n) = 0.005 in * 92 ** ((36 - n) / 39)``,
  where 1/0, 2/0, 3/0, 4/0 are n = 0, -1, -2, -3.
* Annealed copper resistivity at 20 degC (International Annealed Copper
  Standard, 100 % IACS): ``rho = 1.7241e-8 ohm*m``.
* ``R = rho * L / A`` with ``A = pi * d**2 / 4``.
* Optional temperature correction: ``R_T = R_20 * (1 + 0.00393 * (T - 20))``.

The computed values agree with published solid-copper AWG tables (for
example NEC Chapter 9 Table 8 or the NIST Copper Wire Tables, Handbook 100)
to within about 1 %; e.g. 10 AWG is 0.999 ohm per 1000 ft and 4 AWG is
0.249 ohm per 1000 ft. Stranded wire of the same gauge is a few percent
higher, which the default 3 % budget comfortably absorbs.

Voltage drop
------------
Current flows out and back, so the conductor length is twice the one-way
run (a ground return through the chassis is usually *worse* than a wire,
not better)::

    V_drop = I * R_per_length * 2 * one_way_length
    drop_% = V_drop / V_system * 100

Scope
-----
This suggests the *smallest* gauge that meets a voltage-drop budget. It does
not check ampacity (insulation temperature rating, bundling, engine-bay
heat) or fuse sizing. Always size the fuse to protect the wire you choose.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Union

from ._validate import InputError, length_unit, positive, number, to_meters

__all__ = [
    "AWG_SIZES",
    "COPPER_RESISTIVITY_OHM_M",
    "awg_diameter_mm",
    "awg_area_mm2",
    "awg_resistance_ohm_per_1000ft",
    "voltage_drop",
    "WireSuggestion",
    "suggest_awg",
]

#: Annealed copper, 100 % IACS, at 20 degC.
COPPER_RESISTIVITY_OHM_M = 1.7241e-8
#: Temperature coefficient of resistance of annealed copper near 20 degC.
COPPER_TEMP_COEFF_PER_C = 0.00393

#: Gauges considered by :func:`suggest_awg`, thinnest to thickest. These are the
#: sizes commonly sold as automotive/primary and battery cable (even sizes,
#: plus 1 AWG and the aught sizes). Odd sizes still work in the other functions.
AWG_SIZES: List[str] = ["18", "16", "14", "12", "10", "8", "6", "4", "2", "1", "1/0", "2/0", "3/0", "4/0"]

AwgLike = Union[int, str]


def _awg_number(awg: AwgLike) -> int:
    """Map an AWG label to its formula index (1/0 -> 0, 4/0 -> -3)."""
    if isinstance(awg, bool):
        raise InputError("awg must be a gauge like 10, '10', '1/0' or '4/0'")
    text = str(awg).strip().upper().replace("AWG", "").strip()
    aught = {"1/0": 0, "0": 0, "2/0": -1, "00": -1, "3/0": -2, "000": -2, "4/0": -3, "0000": -3}
    if text in aught:
        return aught[text]
    try:
        n = int(text)
    except ValueError:
        raise InputError(f"unknown AWG size {awg!r}; use 1-40 or 1/0..4/0") from None
    if not 1 <= n <= 40:
        raise InputError(f"AWG size must be between 4/0 and 40, got {awg!r}")
    return n


def awg_diameter_mm(awg: AwgLike) -> float:
    """Bare conductor diameter in millimetres for a solid AWG size."""
    n = _awg_number(awg)
    return 0.127 * 92.0 ** ((36 - n) / 39.0)  # 0.005 in = 0.127 mm


def awg_area_mm2(awg: AwgLike) -> float:
    """Conductor cross-section area in mm^2."""
    d = awg_diameter_mm(awg)
    return math.pi * d * d / 4.0


def awg_resistance_ohm_per_1000ft(awg: AwgLike, temperature_c: float = 20.0) -> float:
    """Copper resistance in ohms per 1000 ft at ``temperature_c`` (default 20 degC)."""
    temperature_c = number("temperature_c", temperature_c)
    if not -60.0 <= temperature_c <= 200.0:
        raise InputError("temperature_c must be between -60 and 200 degC")
    area_m2 = awg_area_mm2(awg) * 1e-6
    r20 = COPPER_RESISTIVITY_OHM_M * 304.8 / area_m2  # 1000 ft = 304.8 m
    return r20 * (1.0 + COPPER_TEMP_COEFF_PER_C * (temperature_c - 20.0))


def voltage_drop(
    amps: float,
    one_way_length: float,
    awg: AwgLike,
    unit: str = "ft",
    temperature_c: float = 20.0,
) -> float:
    """Voltage lost in a two-conductor copper run: ``I * R * 2 * one_way_length``."""
    amps = positive("amps", amps)
    one_way_length = positive("one_way_length", one_way_length)
    unit = length_unit(unit)
    feet = to_meters(one_way_length, unit) / 0.3048
    ohms = awg_resistance_ohm_per_1000ft(awg, temperature_c) * (2.0 * feet) / 1000.0
    return amps * ohms


@dataclass(frozen=True)
class WireSuggestion:
    """Result of :func:`suggest_awg`."""

    awg: str
    voltage_drop_v: float
    voltage_drop_pct: float
    allowed_drop_pct: float
    system_voltage: float
    amps: float
    one_way_length: float
    unit: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def suggest_awg(
    amps: float,
    one_way_length: float,
    system_voltage: float = 12.0,
    max_drop_pct: float = 3.0,
    unit: str = "ft",
    temperature_c: float = 20.0,
) -> WireSuggestion:
    """Smallest copper AWG whose round-trip voltage drop stays within ``max_drop_pct``.

    Args:
        amps: Continuous load current in amperes (> 0), e.g. a compressor's draw.
        one_way_length: Distance from the power source to the load (> 0).
        system_voltage: Nominal system voltage, typically 12 or 24 (> 0).
        max_drop_pct: Allowed voltage drop in percent (0 < x <= 50). Default 3.
        unit: ``"ft"`` (default) or ``"m"`` for ``one_way_length``.
        temperature_c: Conductor temperature for the resistance (default 20).

    Raises:
        InputError: on invalid input, or if even 4/0 cannot meet the budget.

    Example:
        >>> suggest_awg(30, 10).awg
        '6'
    """
    amps = positive("amps", amps)
    one_way_length = positive("one_way_length", one_way_length)
    system_voltage = positive("system_voltage", system_voltage)
    max_drop_pct = positive("max_drop_pct", max_drop_pct)
    if max_drop_pct > 50:
        raise InputError("max_drop_pct must be 50 or less")
    unit = length_unit(unit)

    allowed_v = system_voltage * max_drop_pct / 100.0
    for awg in AWG_SIZES:
        drop = voltage_drop(amps, one_way_length, awg, unit, temperature_c)
        if drop <= allowed_v:
            return WireSuggestion(
                awg=awg,
                voltage_drop_v=drop,
                voltage_drop_pct=drop / system_voltage * 100.0,
                allowed_drop_pct=max_drop_pct,
                system_voltage=system_voltage,
                amps=amps,
                one_way_length=one_way_length,
                unit=unit,
            )
    raise InputError(
        f"no gauge up to 4/0 keeps the drop within {max_drop_pct:g}% "
        f"({amps:g} A over {one_way_length:g} {unit}); shorten the run, "
        "raise the system voltage or use parallel conductors"
    )
