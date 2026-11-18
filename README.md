# trainhorn-calc

Small, dependency-free Python calculators for planning a vehicle train horn setup:

- **acoustics**: sound pressure level (SPL) at a distance with the inverse-square law, the inverse (distance for a target dB), optional air absorption, dB lost per doubling of distance, and combining several horns.
- **airsystem**: air tank horn runtime and compressor refill time from Boyle's law (free-air volume).
- **electrical**: the smallest copper AWG size that keeps a 12 V / 24 V run within a voltage-drop budget (3 % by default).
- **cli**: a `trainhorn-calc` command with one subcommand per calculator.

Pure Python 3.8+, no dependencies, type hints included (`py.typed`). MIT licensed.

Results are engineering estimates from simple physical models. They are not measurements, and they are not legal advice about horn use.

## Install

```bash
conda install -c trainhorn trainhorn-calc     # from the anaconda.org user channel
# or, from a source checkout:
pip install .
```

## Command line

```console
$ trainhorn-calc spl 150 100
130.0 dB at 100 ft

$ trainhorn-calc distance 150 90 --absorption 1.9
90 dB is reached at about 6,491.3 ft

$ trainhorn-calc runtime 5 150 110 10 --blast 2
10.9 s of horn time (1.82 cu ft of free air); 5 blasts of 2 s

$ trainhorn-calc recovery 2 110 150 1.0
43.7 s to refill from 110 to 150 psi

$ trainhorn-calc wire 30 10
6 AWG copper: 0.24 V drop (1.98% of 12 V, limit 3%)

$ trainhorn-calc combine 150 150
153.0 dB combined

$ trainhorn-calc wire 30 10 --volts 24 --json
{ "awg": "10", "voltage_drop_pct": 2.497..., ... }
```

Subcommands: `spl`, `distance`, `doubling`, `combine`, `runtime`, `recovery`, `wire`. Run `trainhorn-calc <subcommand> --help` for every option (`--unit ft|m`, `--ref-distance`, `--absorption`, `--atm-psi`, `--cfm-at-zero`, `--rated-psi`, `--volts`, `--max-drop`, `--temp-c`). Every subcommand accepts `--json`. Invalid input prints `error: ...` and exits with status 2. `python -m trainhorn_calc` works too.

## Python API

```python
from trainhorn_calc import (
    spl_at_distance, distance_for_spl, db_doubling_loss, combine_levels,
    tank_runtime_seconds, compressor_recovery_seconds, blast_count,
    suggest_awg, voltage_drop, InputError,
)

spl_at_distance(150, 100)                     # 130.0  (150 dB at 10 ft -> 100 ft)
spl_at_distance(120, 50, ref_distance=1, unit="m", absorption_db_per_km=1.9)
distance_for_spl(150, 130)                    # 100.0 ft
db_doubling_loss()                            # 6.0206 dB
combine_levels([150, 150])                    # 153.01 dB

secs = tank_runtime_seconds(tank_gallons=5, start_psi=150, cutoff_psi=110, horn_cfm=10)  # 10.92
blast_count(secs, 2)                          # 5
compressor_recovery_seconds(2, cut_in_psi=110, cut_out_psi=150, compressor_cfm=1.0)    # 43.7
compressor_recovery_seconds(2, 110, 150, 1.0, cfm_at_zero_psi=2.0, rated_psi=150)       # 38.7

s = suggest_awg(amps=30, one_way_length=10, system_voltage=12)  # WireSuggestion(awg='6', ...)
s.voltage_drop_pct, s.as_dict()
```

All functions raise `trainhorn_calc.InputError` (a `ValueError`) with a clear message for bad input: non-numbers, NaN/inf, zero or negative distances, a start pressure below the cut-off, unknown units or gauges, or a load no gauge up to 4/0 can carry within the budget.

### Formulas and assumptions

| Calculator | Formula | Main assumptions |
|---|---|---|
| SPL at distance | `L = L_ref - 20*log10(d/d_ref) - a*(d - d_ref)/1000` (a in dB/km, distances in m for that term) | Point source, free field, no ground reflection or wind |
| Distance for SPL | `d = d_ref * 10**((L_ref - L)/20)`; bisection when `a > 0` | Same as above |
| Free air | `V_free = V_tank * (P_start - P_end) / P_atm` (gauge psi, P_atm = 14.696) | Isothermal (Boyle's law); slight overestimate for fast blasts |
| Horn runtime | `t = V_free / horn_CFM * 60` | Constant consumption above the cut-off; compressor off |
| Compressor recovery | `t = V_free / CFM * 60`; optional linear CFM-vs-pressure model, integrated in closed form | Rated CFM is free-air delivery |
| Wire gauge | `V_drop = I * R(AWG) * 2 * L_one_way`; R from the AWG diameter formula and copper at 1.7241e-8 ohm*m | Voltage drop only: check ampacity and fuse size separately |

`AIR_ABSORPTION_DB_PER_KM` in `trainhorn_calc.acoustics` gives rounded octave-band absorption values (ISO 9613-2 reference condition, 10 degC / 70 % RH). Train horn chords sit around 250 to 600 Hz, where absorption is roughly 1 to 2 dB/km.

## Tests

```bash
python -m unittest discover -s tests -v
```

49 tests (unittest plus the docstring examples): known values, inverse round-trips, CLI output and edge cases. No pytest required.

## Conda package

The package on the anaconda.org `trainhorn` channel is a standard `noarch: python` build of this source. Its build script and recipe are not part of this repository; to use the library from a checkout, run `pip install .`.

## Documentation

Full documentation with derivations and worked examples: https://docs.page/train-horn/trainhorn-calc

## Related

- [Train Horn calculators](https://train-horn.com/tools/): web versions of these calculators (decibel distance, air tank runtime, compressor recovery, wire gauge and more) that run in the browser.
- [train-horn.com](https://train-horn.com/): an independent reference on train horns, including state laws and install guides.

## License

MIT. See [LICENSE](LICENSE).
