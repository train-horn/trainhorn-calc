"""Sound pressure level (SPL) versus distance for a horn in open air.

Model
-----
A horn is treated as a point source radiating into a free field. Sound
intensity falls with the square of distance (inverse-square law), so the
sound pressure level falls by ``20 * log10(d2 / d1)`` decibels::

    L(d) = L_ref - 20 * log10(d / d_ref) - alpha * (d - d_ref)

where

* ``L_ref``  is the level measured (or rated) at the reference distance
  ``d_ref`` (horn ratings are commonly quoted "at 10 ft" or "at 1 m"),
* ``alpha``  is an optional atmospheric absorption coefficient in dB per
  kilometre, applied to the extra path beyond ``d_ref`` (default 0).

Assumptions and limits
----------------------
* Free field: no ground reflection, walls, wind, temperature gradients or
  barriers. Real outdoor levels can be several dB higher or lower.
* The source is small compared with the distances involved. Very close to
  the horn (inside roughly one or two horn lengths) the law does not hold.
* Absorption depends strongly on frequency, temperature and humidity. The
  values in :data:`AIR_ABSORPTION_DB_PER_KM` are rounded, typical figures
  for 10 degC and 70 % relative humidity (one of the conditions tabulated
  in ISO 9613-2, computed from ISO 9613-1). Use them as a rough guide only.
* Results are estimates, not measurements, and are not a legal noise
  assessment.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable

from ._validate import InputError, length_unit, non_negative, number, positive, to_meters

__all__ = [
    "AIR_ABSORPTION_DB_PER_KM",
    "spl_at_distance",
    "distance_for_spl",
    "distance_ratio_loss",
    "db_doubling_loss",
    "combine_levels",
]

#: Approximate atmospheric absorption in dB/km at 10 degC and 70 % RH
#: (ISO 9613-2 Table 2 condition, from the ISO 9613-1 equations). Keys are octave
#: band centre frequencies in Hz. Train horn chords sit mostly between about
#: 250 Hz and 600 Hz, where absorption is only 1-2 dB/km, so it matters only
#: at long range.
AIR_ABSORPTION_DB_PER_KM: Dict[int, float] = {
    63: 0.1,
    125: 0.4,
    250: 1.0,
    500: 1.9,
    1000: 3.7,
    2000: 9.7,
    4000: 32.8,
    8000: 117.0,
}


def _absorption_term(distance_m: float, ref_m: float, absorption_db_per_km: float) -> float:
    return absorption_db_per_km * (distance_m - ref_m) / 1000.0


def spl_at_distance(
    source_db: float,
    distance: float,
    ref_distance: float = 10,
    unit: str = "ft",
    absorption_db_per_km: float = 0.0,
) -> float:
    """Estimate the SPL at ``distance`` from a level known at ``ref_distance``.

    Formula: ``L = source_db - 20*log10(distance/ref_distance)
    - absorption_db_per_km * (distance - ref_distance) / 1000`` with the
    distances converted to metres for the absorption term.

    Args:
        source_db: Level in dB at ``ref_distance`` (e.g. 150 for "150 dB at 10 ft").
        distance: Distance at which to estimate the level (> 0).
        ref_distance: Distance at which ``source_db`` applies (> 0). Default 10.
        unit: ``"ft"`` (default) or ``"m"``; applies to both distances.
        absorption_db_per_km: Optional air absorption in dB/km (>= 0). See
            :data:`AIR_ABSORPTION_DB_PER_KM`. Default 0 (pure inverse-square).

    Returns:
        Estimated level in dB.

    Example:
        >>> round(spl_at_distance(150, 100), 1)
        130.0
    """
    source_db = number("source_db", source_db)
    distance = positive("distance", distance)
    ref_distance = positive("ref_distance", ref_distance)
    unit = length_unit(unit)
    absorption_db_per_km = non_negative("absorption_db_per_km", absorption_db_per_km)

    level = source_db - 20.0 * math.log10(distance / ref_distance)
    if absorption_db_per_km:
        level -= _absorption_term(
            to_meters(distance, unit), to_meters(ref_distance, unit), absorption_db_per_km
        )
    return level


def distance_for_spl(
    source_db: float,
    target_db: float,
    ref_distance: float = 10,
    unit: str = "ft",
    absorption_db_per_km: float = 0.0,
) -> float:
    """Distance at which the level falls to ``target_db``; inverse of :func:`spl_at_distance`.

    Without absorption the closed form is
    ``d = ref_distance * 10 ** ((source_db - target_db) / 20)``.
    With absorption the equation has no elementary closed form, so it is
    solved by bisection (the level is strictly decreasing with distance).

    Args:
        source_db: Level in dB at ``ref_distance``.
        target_db: Level you want to find the distance for. May be higher
            than ``source_db`` (the answer is then closer than ``ref_distance``).
        ref_distance: Distance at which ``source_db`` applies (> 0).
        unit: ``"ft"`` or ``"m"``; the result is in the same unit.
        absorption_db_per_km: Optional air absorption in dB/km (>= 0).

    Returns:
        Distance in ``unit``.

    Example:
        >>> round(distance_for_spl(150, 130), 6)
        100.0
    """
    source_db = number("source_db", source_db)
    target_db = number("target_db", target_db)
    ref_distance = positive("ref_distance", ref_distance)
    unit = length_unit(unit)
    absorption_db_per_km = non_negative("absorption_db_per_km", absorption_db_per_km)

    free_field = ref_distance * 10.0 ** ((source_db - target_db) / 20.0)
    if free_field == 0.0 or math.isinf(free_field):
        raise InputError("source_db and target_db are too far apart to give a usable distance")
    if not absorption_db_per_km or free_field == ref_distance:
        return free_field

    # The root lies between the free-field answer and the reference distance:
    # absorption lowers the level beyond d_ref and raises it inside d_ref.
    lo, hi = sorted((free_field, ref_distance))

    def excess(d: float) -> float:
        return spl_at_distance(source_db, d, ref_distance, unit, absorption_db_per_km) - target_db

    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if excess(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * hi:
            break
    return 0.5 * (lo + hi)


def distance_ratio_loss(ratio: float) -> float:
    """Level change in dB when the distance is multiplied by ``ratio`` (free field).

    Formula: ``20 * log10(ratio)``. A ratio of 10 gives 20 dB.
    """
    ratio = positive("ratio", ratio)
    return 20.0 * math.log10(ratio)


def db_doubling_loss() -> float:
    """Free-field loss for each doubling of distance: ``20*log10(2)`` = about 6.02 dB."""
    return distance_ratio_loss(2.0)


def combine_levels(levels_db: Iterable[float]) -> float:
    """Combine incoherent sources (e.g. two horns) into one level.

    Formula: ``L = 10 * log10(sum(10 ** (L_i / 10)))``. Two equal sources add
    about 3.01 dB, not double the decibels.
    """
    values = [number("level", v) for v in levels_db]
    if not values:
        raise InputError("combine_levels needs at least one level")
    peak = max(values)
    # Factor out the peak to avoid overflow with very large dB values.
    return peak + 10.0 * math.log10(sum(10.0 ** ((v - peak) / 10.0) for v in values))
