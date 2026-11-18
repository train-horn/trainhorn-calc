"""Onboard air system: tank runtime and compressor recovery.

Free-air volume (Boyle's law)
-----------------------------
A tank of volume ``V`` holding air at absolute pressure ``P`` contains the
same mass of air as ``V * P / P_atm`` of air at atmospheric pressure ("free
air"). Gauge pressures (PSI on a dial, "psig") are converted to absolute by
adding atmospheric pressure ``P_atm`` (14.696 psi at sea level). The free air
released while the tank drops from ``P_start`` to ``P_end`` (both gauge) is::

    V_free = V_tank * (P_start - P_end) / P_atm

Horn consumption and compressor output are rated in CFM of free air (cubic
feet per minute at atmospheric pressure), so::

    horn_seconds = V_free / horn_cfm * 60

Assumptions
-----------
* Isothermal expansion (Boyle's law). Fast blasts cool the air and give a
  little less than this; treat results as an upper estimate.
* The horn consumes its rated CFM at every tank pressure above the cut-off,
  and the compressor is off while the horn sounds (worst case).
* Line, valve and leak losses are ignored.
* 1 US gallon = 231 cubic inches = 0.133680556 cubic feet.
"""

from __future__ import annotations

import math
from typing import Optional

from ._validate import InputError, non_negative, positive

__all__ = [
    "ATMOSPHERIC_PSI",
    "CUBIC_FEET_PER_GALLON",
    "free_air_volume_cuft",
    "tank_runtime_seconds",
    "blast_count",
    "compressor_recovery_seconds",
]

#: Standard atmosphere at sea level in psi.
ATMOSPHERIC_PSI = 14.696
#: Cubic feet in one US liquid gallon (231 in^3 / 1728 in^3).
CUBIC_FEET_PER_GALLON = 231.0 / 1728.0


def _pressures(high_name: str, high: float, low_name: str, low: float) -> "tuple[float, float]":
    high = non_negative(high_name, high)
    low = non_negative(low_name, low)
    if high <= low:
        raise InputError(f"{high_name} ({high:g} psi) must be greater than {low_name} ({low:g} psi)")
    return high, low


def free_air_volume_cuft(
    tank_gallons: float,
    start_psi: float,
    end_psi: float,
    atmospheric_psi: float = ATMOSPHERIC_PSI,
) -> float:
    """Free air (cubic feet at atmospheric pressure) released between two gauge pressures.

    Formula: ``V_free = tank_gallons * 0.13368 * (start_psi - end_psi) / atmospheric_psi``.

    Args:
        tank_gallons: Tank volume in US gallons (> 0).
        start_psi: Starting gauge pressure in psi (> ``end_psi``).
        end_psi: Final gauge pressure in psi (>= 0).
        atmospheric_psi: Ambient absolute pressure (> 0). Lower it for altitude.
    """
    return _free_air(tank_gallons, "start_psi", start_psi, "end_psi", end_psi, atmospheric_psi)


def _free_air(
    tank_gallons: float, high_name: str, high: float, low_name: str, low: float, atmospheric_psi: float
) -> float:
    tank_gallons = positive("tank_gallons", tank_gallons)
    high, low = _pressures(high_name, high, low_name, low)
    atmospheric_psi = positive("atmospheric_psi", atmospheric_psi)
    return tank_gallons * CUBIC_FEET_PER_GALLON * (high - low) / atmospheric_psi


def tank_runtime_seconds(
    tank_gallons: float,
    start_psi: float,
    cutoff_psi: float,
    horn_cfm: float,
    atmospheric_psi: float = ATMOSPHERIC_PSI,
) -> float:
    """Seconds of continuous horn time from a full tank down to ``cutoff_psi``.

    Formula: ``free_air_volume_cuft(...) / horn_cfm * 60``.

    Args:
        tank_gallons: Tank volume in US gallons.
        start_psi: Tank gauge pressure when you start blowing (e.g. 150).
        cutoff_psi: Lowest gauge pressure at which the horn still sounds
            acceptably (e.g. 90). Must be below ``start_psi``.
        horn_cfm: Horn air consumption in CFM of free air (> 0).
        atmospheric_psi: Ambient absolute pressure in psi.

    Example:
        >>> round(tank_runtime_seconds(5, 150, 110, 10), 2)
        10.92
    """
    horn_cfm = positive("horn_cfm", horn_cfm)
    free_air = _free_air(tank_gallons, "start_psi", start_psi, "cutoff_psi", cutoff_psi, atmospheric_psi)
    return free_air / horn_cfm * 60.0


def blast_count(runtime_seconds: float, blast_seconds: float) -> int:
    """Whole blasts of ``blast_seconds`` that fit in ``runtime_seconds``."""
    runtime_seconds = non_negative("runtime_seconds", runtime_seconds)
    blast_seconds = positive("blast_seconds", blast_seconds)
    # Small epsilon so 10.0 / 2.0 style exact divisions are not lost to rounding.
    return int(math.floor(runtime_seconds / blast_seconds + 1e-9))


def compressor_recovery_seconds(
    tank_gallons: float,
    cut_in_psi: float,
    cut_out_psi: float,
    compressor_cfm: float,
    cfm_at_zero_psi: Optional[float] = None,
    rated_psi: Optional[float] = None,
    atmospheric_psi: float = ATMOSPHERIC_PSI,
) -> float:
    """Seconds for a compressor to refill the tank from ``cut_in_psi`` to ``cut_out_psi``.

    Constant-flow model (default): the compressor delivers ``compressor_cfm``
    of free air over the whole range, so::

        t = V_free / compressor_cfm * 60

    Use the CFM the manufacturer rates *at* (or near) your cut-out pressure;
    output falls as pressure rises, so a 0 psi rating gives an optimistic time.

    Linear-flow model (optional): if ``cfm_at_zero_psi`` and ``rated_psi`` are
    given, delivery is taken to fall linearly from ``cfm_at_zero_psi`` at 0 psi
    to ``compressor_cfm`` at ``rated_psi``: ``q(p) = a + b*p``. Integrating
    ``dt = (V_tank / P_atm) dp / q(p)`` gives::

        t = V_tank / P_atm * ln(q(p_out) / q(p_in)) / b * 60     (b != 0)

    Args:
        tank_gallons: Tank volume in US gallons.
        cut_in_psi: Gauge pressure at which the compressor switches on.
        cut_out_psi: Gauge pressure at which it switches off (> cut-in).
        compressor_cfm: Free-air delivery in CFM at the rated pressure (> 0).
        cfm_at_zero_psi: Optional free-air delivery at 0 psi (>= compressor_cfm).
        rated_psi: Pressure at which ``compressor_cfm`` is rated (> 0);
            required together with ``cfm_at_zero_psi``.
        atmospheric_psi: Ambient absolute pressure in psi.

    Example:
        >>> round(compressor_recovery_seconds(2, 110, 150, 1.0), 1)
        43.7
    """
    compressor_cfm = positive("compressor_cfm", compressor_cfm)
    free_air = _free_air(tank_gallons, "cut_out_psi", cut_out_psi, "cut_in_psi", cut_in_psi, atmospheric_psi)

    if cfm_at_zero_psi is None and rated_psi is None:
        return free_air / compressor_cfm * 60.0
    if cfm_at_zero_psi is None or rated_psi is None:
        raise InputError("cfm_at_zero_psi and rated_psi must be given together")

    q0 = positive("cfm_at_zero_psi", cfm_at_zero_psi)
    p_rated = positive("rated_psi", rated_psi)
    if q0 < compressor_cfm:
        raise InputError("cfm_at_zero_psi must be at least compressor_cfm (output falls with pressure)")
    slope = (compressor_cfm - q0) / p_rated  # cfm per psi, <= 0
    q_in = q0 + slope * float(cut_in_psi)
    q_out = q0 + slope * float(cut_out_psi)
    if q_out <= 0:
        raise InputError(
            f"the linear flow model gives no output at {float(cut_out_psi):g} psi; "
            "check cfm_at_zero_psi, compressor_cfm and rated_psi"
        )
    tank_cuft = float(tank_gallons) * CUBIC_FEET_PER_GALLON
    p_atm = float(atmospheric_psi)
    if slope == 0:
        return free_air / q0 * 60.0
    return tank_cuft / p_atm * math.log(q_out / q_in) / slope * 60.0
