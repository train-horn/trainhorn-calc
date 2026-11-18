"""trainhorn_calc: small, dependency-free calculators for train horn setups.

Modules:

* :mod:`trainhorn_calc.acoustics`  - SPL versus distance (inverse-square law)
* :mod:`trainhorn_calc.airsystem`  - air tank runtime and compressor recovery
* :mod:`trainhorn_calc.electrical` - copper AWG choice by voltage drop
* :mod:`trainhorn_calc.cli`        - the ``trainhorn-calc`` command

Browser versions of these calculators: https://train-horn.com/tools/
"""

from __future__ import annotations

__version__ = "1.0.0"

from ._validate import InputError
from .acoustics import combine_levels, db_doubling_loss, distance_for_spl, distance_ratio_loss, spl_at_distance
from .airsystem import blast_count, compressor_recovery_seconds, free_air_volume_cuft, tank_runtime_seconds
from .electrical import WireSuggestion, awg_resistance_ohm_per_1000ft, suggest_awg, voltage_drop

__all__ = [
    "__version__",
    "InputError",
    "spl_at_distance",
    "distance_for_spl",
    "distance_ratio_loss",
    "db_doubling_loss",
    "combine_levels",
    "free_air_volume_cuft",
    "tank_runtime_seconds",
    "blast_count",
    "compressor_recovery_seconds",
    "awg_resistance_ohm_per_1000ft",
    "voltage_drop",
    "suggest_awg",
    "WireSuggestion",
]
