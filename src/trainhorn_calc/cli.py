"""Command-line interface: ``trainhorn-calc <subcommand> ...``.

Every subcommand prints a short human-readable answer, or JSON with ``--json``.
Invalid input prints ``error: ...`` to stderr and exits with status 2.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .acoustics import combine_levels, db_doubling_loss, distance_for_spl, spl_at_distance
from .airsystem import blast_count, compressor_recovery_seconds, free_air_volume_cuft, tank_runtime_seconds
from .electrical import suggest_awg


def _emit(args: argparse.Namespace, data: Dict[str, Any], text: str) -> None:
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(text)


def _cmd_spl(args: argparse.Namespace) -> None:
    level = spl_at_distance(args.source_db, args.distance, args.ref_distance, args.unit, args.absorption)
    _emit(
        args,
        {"spl_db": level, "distance": args.distance, "unit": args.unit},
        f"{level:.1f} dB at {args.distance:g} {args.unit}",
    )


def _cmd_distance(args: argparse.Namespace) -> None:
    dist = distance_for_spl(args.source_db, args.target_db, args.ref_distance, args.unit, args.absorption)
    _emit(
        args,
        {"distance": dist, "target_db": args.target_db, "unit": args.unit},
        f"{args.target_db:g} dB is reached at about {dist:,.1f} {args.unit}",
    )


def _cmd_doubling(args: argparse.Namespace) -> None:
    loss = db_doubling_loss()
    _emit(args, {"db_per_doubling": loss}, f"{loss:.2f} dB lost per doubling of distance (free field)")


def _cmd_combine(args: argparse.Namespace) -> None:
    total = combine_levels(args.levels)
    _emit(args, {"combined_db": total}, f"{total:.1f} dB combined")


def _cmd_runtime(args: argparse.Namespace) -> None:
    secs = tank_runtime_seconds(args.tank_gal, args.start_psi, args.cutoff_psi, args.horn_cfm, args.atm_psi)
    free_air = free_air_volume_cuft(args.tank_gal, args.start_psi, args.cutoff_psi, args.atm_psi)
    data: Dict[str, Any] = {"runtime_seconds": secs, "free_air_cuft": free_air}
    text = f"{secs:.1f} s of horn time ({free_air:.2f} cu ft of free air)"
    if args.blast is not None:
        n = blast_count(secs, args.blast)
        data["blasts"] = n
        text += f"; {n} blasts of {args.blast:g} s"
    _emit(args, data, text)


def _cmd_recovery(args: argparse.Namespace) -> None:
    secs = compressor_recovery_seconds(
        args.tank_gal,
        args.cut_in_psi,
        args.cut_out_psi,
        args.compressor_cfm,
        cfm_at_zero_psi=args.cfm_at_zero,
        rated_psi=args.rated_psi,
        atmospheric_psi=args.atm_psi,
    )
    _emit(
        args,
        {"recovery_seconds": secs},
        f"{secs:.1f} s to refill from {args.cut_in_psi:g} to {args.cut_out_psi:g} psi",
    )


def _cmd_wire(args: argparse.Namespace) -> None:
    result = suggest_awg(args.amps, args.length, args.volts, args.max_drop, args.unit, args.temp_c)
    _emit(
        args,
        result.as_dict(),
        f"{result.awg} AWG copper: {result.voltage_drop_v:.2f} V drop "
        f"({result.voltage_drop_pct:.2f}% of {result.system_voltage:g} V, limit {result.allowed_drop_pct:g}%)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trainhorn-calc",
        description="Train horn calculators: SPL vs distance, air tank runtime, "
        "compressor recovery and wire gauge. Web versions: https://train-horn.com/tools/",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print JSON instead of text")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    def unit_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ref-distance", type=float, default=10.0, help="distance of the rated level (default 10)")
        p.add_argument("--unit", choices=("ft", "m"), default="ft", help="distance unit (default ft)")
        p.add_argument("--absorption", type=float, default=0.0, metavar="DB_PER_KM",
                       help="optional air absorption in dB/km (default 0)")

    p = sub.add_parser("spl", parents=[common], help="SPL at a distance from a rated level")
    p.add_argument("source_db", type=float, help="rated level in dB at --ref-distance")
    p.add_argument("distance", type=float, help="distance to estimate the level at")
    unit_opts(p)
    p.set_defaults(func=_cmd_spl)

    p = sub.add_parser("distance", parents=[common], help="distance at which a target SPL is reached")
    p.add_argument("source_db", type=float, help="rated level in dB at --ref-distance")
    p.add_argument("target_db", type=float, help="target level in dB")
    unit_opts(p)
    p.set_defaults(func=_cmd_distance)

    p = sub.add_parser("doubling", parents=[common], help="dB lost per doubling of distance")
    p.set_defaults(func=_cmd_doubling)

    p = sub.add_parser("combine", parents=[common], help="combine levels of several horns")
    p.add_argument("levels", type=float, nargs="+", help="levels in dB")
    p.set_defaults(func=_cmd_combine)

    p = sub.add_parser("runtime", parents=[common], help="air tank horn runtime (Boyle's law)")
    p.add_argument("tank_gal", type=float, help="tank volume in US gallons")
    p.add_argument("start_psi", type=float, help="starting gauge pressure")
    p.add_argument("cutoff_psi", type=float, help="lowest usable gauge pressure")
    p.add_argument("horn_cfm", type=float, help="horn consumption in CFM of free air")
    p.add_argument("--blast", type=float, help="also count blasts of this many seconds")
    p.add_argument("--atm-psi", type=float, default=14.696, help="ambient pressure (default 14.696)")
    p.set_defaults(func=_cmd_runtime)

    p = sub.add_parser("recovery", parents=[common], help="compressor refill time")
    p.add_argument("tank_gal", type=float, help="tank volume in US gallons")
    p.add_argument("cut_in_psi", type=float, help="compressor cut-in gauge pressure")
    p.add_argument("cut_out_psi", type=float, help="compressor cut-out gauge pressure")
    p.add_argument("compressor_cfm", type=float, help="free-air CFM at the rated pressure")
    p.add_argument("--cfm-at-zero", type=float, help="free-air CFM at 0 psi (linear model)")
    p.add_argument("--rated-psi", type=float, help="pressure at which compressor_cfm is rated")
    p.add_argument("--atm-psi", type=float, default=14.696, help="ambient pressure (default 14.696)")
    p.set_defaults(func=_cmd_recovery)

    p = sub.add_parser("wire", parents=[common], help="copper AWG for a voltage-drop budget")
    p.add_argument("amps", type=float, help="load current in A")
    p.add_argument("length", type=float, help="one-way run length")
    p.add_argument("--volts", type=float, default=12.0, help="system voltage (default 12)")
    p.add_argument("--max-drop", type=float, default=3.0, help="allowed drop in %% (default 3)")
    p.add_argument("--unit", choices=("ft", "m"), default="ft", help="length unit (default ft)")
    p.add_argument("--temp-c", type=float, default=20.0, help="conductor temperature (default 20)")
    p.set_defaults(func=_cmd_wire)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
