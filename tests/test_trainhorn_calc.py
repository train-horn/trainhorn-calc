"""unittest suite for trainhorn_calc. Run: python -m unittest discover -s tests"""

import contextlib
import doctest
import io
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import trainhorn_calc  # noqa: E402
from trainhorn_calc import acoustics, airsystem, cli, electrical  # noqa: E402
from trainhorn_calc import InputError  # noqa: E402


class TestAcoustics(unittest.TestCase):
    def test_150db_at_10ft_gives_130_at_100ft(self):
        self.assertAlmostEqual(acoustics.spl_at_distance(150, 100), 130.0, places=9)

    def test_same_distance_returns_source(self):
        self.assertAlmostEqual(acoustics.spl_at_distance(118, 10), 118.0)

    def test_closer_than_reference_is_louder(self):
        self.assertAlmostEqual(acoustics.spl_at_distance(150, 5), 150 + 20 * math.log10(2))

    def test_metres_and_custom_reference(self):
        # 120 dB at 1 m -> 100 dB at 10 m
        self.assertAlmostEqual(acoustics.spl_at_distance(120, 10, ref_distance=1, unit="m"), 100.0)

    def test_unit_does_not_matter_without_absorption(self):
        self.assertAlmostEqual(
            acoustics.spl_at_distance(140, 300, unit="ft"), acoustics.spl_at_distance(140, 300, unit="m")
        )

    def test_absorption_reduces_level(self):
        # 1000 m past a 10 m reference at 2 dB/km -> extra 2.0 dB loss
        plain = acoustics.spl_at_distance(150, 1010, ref_distance=10, unit="m")
        absorbed = acoustics.spl_at_distance(150, 1010, ref_distance=10, unit="m", absorption_db_per_km=2.0)
        self.assertAlmostEqual(plain - absorbed, 2.0, places=9)

    def test_absorption_converts_feet(self):
        plain = acoustics.spl_at_distance(150, 3290.84, unit="ft")
        absorbed = acoustics.spl_at_distance(150, 3290.84, unit="ft", absorption_db_per_km=10.0)
        self.assertAlmostEqual(plain - absorbed, 10.0 * (3290.84 - 10) * 0.3048 / 1000, places=9)

    def test_distance_for_spl_known_value(self):
        self.assertAlmostEqual(acoustics.distance_for_spl(150, 130), 100.0, places=9)
        self.assertAlmostEqual(acoustics.distance_for_spl(150, 90), 10000.0, places=6)

    def test_round_trip_without_absorption(self):
        for src, d in [(150, 37.5), (118, 2.0), (153.2, 2500), (100, 10)]:
            target = acoustics.spl_at_distance(src, d)
            self.assertAlmostEqual(acoustics.distance_for_spl(src, target), d, places=6)

    def test_round_trip_with_absorption(self):
        for d in (3.0, 50.0, 800.0, 5000.0):
            target = acoustics.spl_at_distance(150, d, unit="m", absorption_db_per_km=3.7)
            back = acoustics.distance_for_spl(150, target, unit="m", absorption_db_per_km=3.7)
            self.assertAlmostEqual(back, d, delta=d * 1e-9)

    def test_absorption_shortens_distance(self):
        self.assertLess(
            acoustics.distance_for_spl(150, 90, absorption_db_per_km=1.9),
            acoustics.distance_for_spl(150, 90),
        )

    def test_doubling_loss(self):
        self.assertAlmostEqual(acoustics.db_doubling_loss(), 6.0206, places=4)
        self.assertAlmostEqual(acoustics.distance_ratio_loss(10), 20.0)

    def test_combine_levels(self):
        self.assertAlmostEqual(acoustics.combine_levels([100, 100]), 100 + 10 * math.log10(2))
        self.assertAlmostEqual(acoustics.combine_levels([150]), 150.0)
        self.assertAlmostEqual(acoustics.combine_levels([120, 90]), 120.0, places=2)

    def test_invalid_inputs(self):
        with self.assertRaises(InputError):
            acoustics.spl_at_distance(150, 0)
        with self.assertRaises(InputError):
            acoustics.spl_at_distance(150, -5)
        with self.assertRaises(InputError):
            acoustics.spl_at_distance(150, 10, ref_distance=0)
        with self.assertRaises(InputError):
            acoustics.spl_at_distance(150, 10, unit="yd")
        with self.assertRaises(InputError):
            acoustics.spl_at_distance("loud", 10)
        with self.assertRaises(InputError):
            acoustics.spl_at_distance(float("nan"), 10)
        with self.assertRaises(InputError):
            acoustics.spl_at_distance(150, 10, absorption_db_per_km=-1)
        with self.assertRaises(InputError):
            acoustics.combine_levels([])
        with self.assertRaises(InputError):
            acoustics.spl_at_distance(True, 10)

    def test_input_error_is_value_error(self):
        self.assertTrue(issubclass(InputError, ValueError))

    def test_numeric_strings_are_accepted(self):
        self.assertAlmostEqual(acoustics.spl_at_distance("150", "100"), 130.0)
        self.assertAlmostEqual(acoustics.spl_at_distance(150, 100, unit=" FT "), 130.0)


class TestAirSystem(unittest.TestCase):
    def test_free_air_known_value(self):
        # 1 gallon from 14.696 psig to 0 psig releases exactly 1 gallon of free air
        self.assertAlmostEqual(airsystem.free_air_volume_cuft(1, 14.696, 0), 231 / 1728)

    def test_runtime_known_value(self):
        # 5 gal, 150 -> 110 psi, 10 CFM: 0.668403 ft3 * 40 / 14.696 / 10 * 60
        expected = 5 * 231 / 1728 * 40 / 14.696 / 10 * 60
        self.assertAlmostEqual(airsystem.tank_runtime_seconds(5, 150, 110, 10), expected)
        self.assertAlmostEqual(expected, 10.916, places=3)

    def test_runtime_scales_linearly(self):
        base = airsystem.tank_runtime_seconds(2, 150, 120, 5)
        self.assertAlmostEqual(airsystem.tank_runtime_seconds(4, 150, 120, 5), 2 * base)
        self.assertAlmostEqual(airsystem.tank_runtime_seconds(2, 150, 120, 10), base / 2)
        self.assertAlmostEqual(airsystem.tank_runtime_seconds(2, 150, 90, 5), 2 * base)

    def test_altitude_gives_more_free_air(self):
        sea = airsystem.tank_runtime_seconds(5, 150, 110, 10)
        high = airsystem.tank_runtime_seconds(5, 150, 110, 10, atmospheric_psi=12.2)
        self.assertGreater(high, sea)

    def test_blast_count(self):
        self.assertEqual(airsystem.blast_count(10.0, 2.0), 5)
        self.assertEqual(airsystem.blast_count(10.9, 2.0), 5)
        self.assertEqual(airsystem.blast_count(0, 1.5), 0)
        self.assertEqual(airsystem.blast_count(0.3 * 3, 0.3), 3)

    def test_recovery_constant_flow(self):
        expected = 2 * 231 / 1728 * 40 / 14.696 / 1.0 * 60
        self.assertAlmostEqual(airsystem.compressor_recovery_seconds(2, 110, 150, 1.0), expected)

    def test_recovery_equals_runtime_with_same_cfm(self):
        # Refilling at X CFM takes as long as draining at X CFM over the same band.
        self.assertAlmostEqual(
            airsystem.compressor_recovery_seconds(3, 120, 150, 2.5),
            airsystem.tank_runtime_seconds(3, 150, 120, 2.5),
        )

    def test_recovery_linear_model(self):
        # Flat curve degenerates to the constant model.
        flat = airsystem.compressor_recovery_seconds(2, 110, 150, 1.0, cfm_at_zero_psi=1.0, rated_psi=150)
        self.assertAlmostEqual(flat, airsystem.compressor_recovery_seconds(2, 110, 150, 1.0))
        # Falling curve: closed form vs. numeric integration.
        t = airsystem.compressor_recovery_seconds(2, 110, 150, 1.0, cfm_at_zero_psi=2.0, rated_psi=150)
        v = 2 * 231 / 1728 / 14.696
        steps = 20000
        dp = 40 / steps
        numeric = sum(v * dp / (2.0 - (110 + (i + 0.5) * dp) / 150) for i in range(steps)) * 60
        self.assertAlmostEqual(t, numeric, places=4)
        self.assertLess(t, airsystem.compressor_recovery_seconds(2, 110, 150, 1.0))

    def test_invalid_air_inputs(self):
        with self.assertRaises(InputError):
            airsystem.tank_runtime_seconds(0, 150, 110, 10)
        with self.assertRaises(InputError):
            airsystem.tank_runtime_seconds(5, 110, 150, 10)  # start below cut-off
        with self.assertRaises(InputError):
            airsystem.tank_runtime_seconds(5, 150, 150, 10)
        with self.assertRaises(InputError):
            airsystem.tank_runtime_seconds(5, 150, -1, 10)
        with self.assertRaises(InputError):
            airsystem.tank_runtime_seconds(5, 150, 110, 0)
        with self.assertRaises(InputError):
            airsystem.compressor_recovery_seconds(2, 110, 150, 1.0, cfm_at_zero_psi=2.0)
        with self.assertRaises(InputError):
            airsystem.compressor_recovery_seconds(2, 110, 150, 1.0, cfm_at_zero_psi=0.5, rated_psi=150)
        with self.assertRaises(InputError):
            airsystem.compressor_recovery_seconds(2, 110, 150, 0.1, cfm_at_zero_psi=5.0, rated_psi=100)
        with self.assertRaises(InputError):
            airsystem.blast_count(10, 0)


class TestElectrical(unittest.TestCase):
    def test_resistance_matches_published_tables(self):
        # Reference solid-copper values (ohm / 1000 ft at 20 C), within 1 %.
        published = {"14": 2.525, "12": 1.588, "10": 0.9989, "8": 0.6282, "4": 0.2485, "1/0": 0.09827}
        for awg, ohms in published.items():
            self.assertAlmostEqual(electrical.awg_resistance_ohm_per_1000ft(awg), ohms, delta=ohms * 0.01)

    def test_three_gauges_doubles_area(self):
        ratio = electrical.awg_area_mm2(7) / electrical.awg_area_mm2(10)
        self.assertAlmostEqual(ratio, 2.0, delta=0.01)

    def test_awg_label_forms(self):
        self.assertEqual(electrical.awg_diameter_mm("1/0"), electrical.awg_diameter_mm("0"))
        self.assertEqual(electrical.awg_diameter_mm("4/0"), electrical.awg_diameter_mm("0000"))
        self.assertEqual(electrical.awg_diameter_mm(10), electrical.awg_diameter_mm("10 AWG"))
        self.assertAlmostEqual(electrical.awg_diameter_mm("4/0"), 11.684, places=2)

    def test_temperature_raises_resistance(self):
        r20 = electrical.awg_resistance_ohm_per_1000ft(10)
        self.assertAlmostEqual(electrical.awg_resistance_ohm_per_1000ft(10, 70), r20 * (1 + 0.00393 * 50))

    def test_voltage_drop_known_value(self):
        # 20 A over 10 ft one-way of 10 AWG: 20 * 0.99884 * 20 / 1000
        drop = electrical.voltage_drop(20, 10, 10)
        self.assertAlmostEqual(drop, 20 * electrical.awg_resistance_ohm_per_1000ft(10) * 0.02)
        self.assertAlmostEqual(drop, 0.3995, places=3)

    def test_voltage_drop_metres(self):
        self.assertAlmostEqual(electrical.voltage_drop(20, 3.048, 10, unit="m"), electrical.voltage_drop(20, 10, 10))

    def test_suggest_awg_known_values(self):
        self.assertEqual(electrical.suggest_awg(30, 10).awg, "6")
        self.assertEqual(electrical.suggest_awg(30, 10, system_voltage=24).awg, "10")
        self.assertEqual(electrical.suggest_awg(5, 3).awg, "18")

    def test_suggestion_is_minimal_and_within_budget(self):
        for amps, length, volts in [(30, 10, 12), (15, 20, 12), (40, 6, 24), (100, 15, 12)]:
            s = electrical.suggest_awg(amps, length, system_voltage=volts)
            self.assertLessEqual(s.voltage_drop_pct, 3.0)
            idx = electrical.AWG_SIZES.index(s.awg)
            if idx > 0:
                thinner = electrical.voltage_drop(amps, length, electrical.AWG_SIZES[idx - 1])
                self.assertGreater(thinner / volts * 100, 3.0)

    def test_suggestion_as_dict(self):
        d = electrical.suggest_awg(30, 10).as_dict()
        self.assertEqual(d["awg"], "6")
        self.assertEqual(d["unit"], "ft")

    def test_impossible_load_raises(self):
        with self.assertRaises(InputError):
            electrical.suggest_awg(1000, 200)

    def test_invalid_electrical_inputs(self):
        for bad in ("5/0", "abc", -1, 41, True):
            with self.assertRaises(InputError):
                electrical.awg_diameter_mm(bad)
        with self.assertRaises(InputError):
            electrical.suggest_awg(0, 10)
        with self.assertRaises(InputError):
            electrical.suggest_awg(10, 10, max_drop_pct=0)
        with self.assertRaises(InputError):
            electrical.suggest_awg(10, 10, max_drop_pct=60)
        with self.assertRaises(InputError):
            electrical.suggest_awg(10, 10, system_voltage=-12)
        with self.assertRaises(InputError):
            electrical.awg_resistance_ohm_per_1000ft(10, temperature_c=500)


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestCli(unittest.TestCase):
    def test_spl_text(self):
        code, out, _ = run_cli("spl", "150", "100")
        self.assertEqual(code, 0)
        self.assertIn("130.0 dB at 100 ft", out)

    def test_distance_json(self):
        code, out, _ = run_cli("distance", "150", "130", "--json")
        self.assertEqual(code, 0)
        self.assertAlmostEqual(json.loads(out)["distance"], 100.0)

    def test_runtime_with_blasts(self):
        code, out, _ = run_cli("runtime", "5", "150", "110", "10", "--blast", "2", "--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["blasts"], 5)
        self.assertAlmostEqual(data["runtime_seconds"], 10.916, places=3)

    def test_recovery_and_wire(self):
        code, out, _ = run_cli("recovery", "2", "110", "150", "1.0")
        self.assertEqual(code, 0)
        self.assertIn("43.7 s", out)
        code, out, _ = run_cli("wire", "30", "10", "--volts", "24", "--max-drop", "2", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["awg"], "8")

    def test_doubling_and_combine(self):
        self.assertIn("6.02 dB", run_cli("doubling")[1])
        self.assertIn("103.0 dB", run_cli("combine", "100", "100")[1])

    def test_cli_error_exit_code(self):
        code, out, err = run_cli("runtime", "5", "100", "150", "10")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("error: start_psi", err)

    def test_missing_subcommand_exits(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.main([])


class TestPackage(unittest.TestCase):
    def test_public_api_exports(self):
        for name in trainhorn_calc.__all__:
            self.assertTrue(hasattr(trainhorn_calc, name), name)
        self.assertRegex(trainhorn_calc.__version__, r"^\d+\.\d+\.\d+$")


def load_tests(loader, tests, ignore):
    for module in (acoustics, airsystem, electrical):
        tests.addTests(doctest.DocTestSuite(module))
    return tests


if __name__ == "__main__":
    unittest.main()
