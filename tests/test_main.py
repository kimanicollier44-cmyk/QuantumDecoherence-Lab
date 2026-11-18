"""Tests for QuantumDecoherence-Lab: Kraus channels, T1/T2 bookkeeping,
pointer states, the finite-environment mechanism, the Markov comparison,
the regime classifier, and the HOLD gates."""
import math

import main


# ---- Kraus machinery -------------------------------------------------
def test_kraus_completeness_both_channels():
    for g in (0.0, 0.3, 0.632121, 1.0):
        assert main._kraus_completeness_error(
            main.amplitude_damping_kraus(g)) < 1e-12
    for p in (0.0, 0.2, 0.5):
        assert main._kraus_completeness_error(
            main.dephasing_kraus(p)) < 1e-12


def test_channels_preserve_trace_and_positivity():
    for t in (0.0, 13.7, 50.0, 123.4):
        rho = main.composed(main.RHO_PLUS, t)
        assert abs(main._trace(rho) - 1.0) < 1e-12
        det = rho[0][0].real * rho[1][1].real - abs(rho[0][1]) ** 2
        assert det > -1e-12


def test_invalid_channel_parameters_raise():
    for bad in (-0.1, 1.1):
        try:
            main.amplitude_damping_kraus(bad)
            raise AssertionError("gamma out of range accepted")
        except ValueError:
            pass
    try:
        main.dephasing_kraus(0.75)
        raise AssertionError("phase-flip p out of range accepted")
    except ValueError:
        pass


# ---- amplitude damping ----------------------------------------------
def test_ad_ground_state_is_fixed_point():
    out = main.damped(main.RHO_GROUND, 100.0)
    for i in range(2):
        for j in range(2):
            assert abs(out[i][j] - main.RHO_GROUND[i][j]) < 1e-12


def test_ad_full_damping_lands_on_ground():
    out = main._apply_kraus(main.RHO_EXCITED,
                            main.amplitude_damping_kraus(1.0))
    assert abs(out[0][0] - 1.0) < 1e-12
    assert abs(out[1][1]) < 1e-12


def test_ad_coherence_sqrt_law():
    for g in (0.1, 0.36, 0.75):
        out = main._apply_kraus(main.RHO_PLUS,
                                main.amplitude_damping_kraus(g))
        assert abs(main.coherence(out) / 0.5 - math.sqrt(1.0 - g)) < 1e-12
        assert abs(out[1][1].real / 0.5 - (1.0 - g)) < 1e-12


def test_ad_at_T1_coherence_half_rate():
    out = main.damped(main.RHO_PLUS, main.T1_US)
    assert abs(main.coherence(out) / 0.5 - math.exp(-0.5)) < 1e-12
    assert abs(out[1][1].real / 0.5 - math.exp(-1.0)) < 1e-12


# ---- pure dephasing ---------------------------------------------------
def test_pd_populations_never_move():
    for t in (11.0, 37.5, 80.0, 400.0):
        out = main.dephased(main.RHO_MIXTURE, t)
        assert abs(out[0][0].real - 0.7) < 1e-12
        assert abs(out[1][1].real - 0.3) < 1e-12


def test_pd_coherence_exponential_law():
    for t in (20.0, 80.0, 160.0):
        out = main.dephased(main.RHO_PLUS, t)
        assert abs(main.coherence(out) / 0.5
                   - math.exp(-t / main.T_PHI_US)) < 1e-12


def test_pd_basis_states_untouched():
    for rho in (main.RHO_GROUND, main.RHO_EXCITED):
        out = main.dephased(rho, main.T_PHI_US)
        for i in range(2):
            for j in range(2):
                assert abs(out[i][j] - rho[i][j]) < 1e-12


# ---- T1/T2 bookkeeping -------------------------------------------------
def test_t2_relation_value():
    assert abs(main.T2_US - 44.44444444444444) < 1e-9


def test_composed_at_T2_coherence_is_half_over_e():
    out = main.composed(main.RHO_PLUS, main.T2_US)
    assert abs(main.coherence(out) - 0.5 / math.e) < 1e-12


def test_t2_fit_recovers_relation():
    report = main.lifetime_report()
    assert report["fit_relative_error"] < 1e-9
    assert report["T2_predicted_us"] == 44.444444


def test_kraus_coherence_monotone_decay():
    values = [main.coherence(main.composed(main.RHO_PLUS, 5.0 * i))
              for i in range(21)]
    assert all(b <= a + 1e-15 for a, b in zip(values, values[1:]))


# ---- pointer states -----------------------------------------------------
def test_pointer_report_superposition_factor():
    states = main.pointer_report()["states"]
    assert abs(states["superposition_|+>"]["coherence_out"] / 0.5
               - math.exp(-1.0)) < 1e-5
    assert abs(states["superposition_|+i>"]["coherence_out"] / 0.5
               - math.exp(-1.0)) < 1e-5


def test_pointer_report_mixture():
    row = main.pointer_report()["states"]["partial_mixture_0.7/0.3"]
    assert abs(row["excited_population_out"] - 0.3) < 1e-6
    assert abs(row["coherence_out"] / 0.2 - math.exp(-1.0)) < 1e-5


def test_pointer_report_basis_rows():
    states = main.pointer_report()["states"]
    assert states["ground_|0>"]["coherence_out"] == 0.0
    assert abs(states["excited_|1>"]["excited_population_out"] - 1.0) < 1e-6


# ---- finite environment --------------------------------------------------
def test_env_statevector_normalised():
    for t in (0.0, 3.3, 9.24, 25.9):
        amps = main.env_statevector(t)
        assert len(amps) == 16
        assert abs(sum(abs(a) ** 2 for a in amps) - 1.0) < 1e-12


def test_env_rho01_matches_overlap_formula():
    for t in (0.7, 2.5, 9.24, 17.3, 25.9):
        rho = main.env_reduced_rho(t)
        assert abs(rho[0][1] - 0.5 * main.env_overlap(t)) < 1e-12


def test_env_populations_pinned_and_start_pure():
    for t in (1.1, 9.24, 25.9):
        rho = main.env_reduced_rho(t)
        assert abs(rho[0][0].real - 0.5) < 1e-12
        assert abs(rho[1][1].real - 0.5) < 1e-12
    assert abs(main._purity(main.env_reduced_rho(0.0)) - 1.0) < 1e-12


def test_env_collapse_and_recoherence():
    scan = main.env_scan()
    assert scan["min_factor"] < 1e-4
    assert scan["recoherence_factor"] > 0.9
    assert scan["t_recoherence"] > scan["t_min"]
    assert main._purity(main.env_reduced_rho(scan["t_min"])) < 0.51


def test_environment_report_samples_consistent():
    report = main.environment_report()
    assert report["samples"]["t=0"]["coherence_factor"] == 1.0
    assert all(row["rho01_matches_overlap"]
               for row in report["samples"].values())


# ---- Markovian vs finite environment --------------------------------------
def test_markov_kraus_deviation_tiny():
    report = main.markov_report()
    assert report["kraus_max_deviation_from_exponential"] < 1e-12


def test_markov_env_residual_exposes_recoherence():
    report = main.markov_report()
    assert report["env_max_residual"] > 0.5
    assert report["env_fit_predicted_at_recoherence"] < 1e-9
    assert report["env_actual_at_recoherence"] > 0.9


# ---- classifier -------------------------------------------------------------
def test_classifier_scenarios():
    rep = main.classifier_report()
    assert rep["fresh_qubit_short_time"] == "coherent"
    assert rep["dephasing_heavy_device"] == "dephasing-dominated"
    assert rep["relaxation_heavy_device"] == "relaxation-dominated"
    assert rep["pointer_state_regime"] == "pointer-stable"
    assert rep["aged_state_25_25_100"] == "dephasing-dominated"


def test_classifier_matches_policy_on_scenarios():
    for features in ((200.0, 200.0, 1.0), (200.0, 10.0, 20.0),
                     (10.0, 200.0, 20.0), (200.0, 10.0, 75.0),
                     (25.0, 25.0, 100.0)):
        assert main.classify_regime(*features) == main.model_label(*features)


def test_classifier_grid_self_consistent():
    for features, label in main.TRAINING_GRID:
        assert main._knn(features, 1) == label


# ---- gates, seats, checks ---------------------------------------------------
def test_hold_gates():
    assert len(main.HOLD_GATES) == 14
    assert all(v.startswith("HOLD") for v in main.HOLD_GATES.values())
    assert main.gate("real_hardware_control") == "HOLD"
    assert main.gate("coherence_record_claim") == "HOLD"
    assert main.gate("recoherence_recovery_claim") == "HOLD"
    assert main.gate("run_simulation") == "PROCEED"


def test_hold_demo_exit_code():
    assert main.main(["hold-demo"]) == 2
    assert main.main(["hold-demo", "run_simulation"]) == 0


def test_seats_never_override_hold():
    brains = main.brains_report()
    assert brains["decider"]["seat"] == "Gemini Argon 4 Extended Thinking"
    assert brains["decider"]["can_override_hold"] is False
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False
    assert brains["flow"]["live"] == 0


def test_run_checks_all_pass():
    checks = main.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]


def test_cli_json_commands(capsys):
    for cmd in ("channels", "lifetimes", "pointer", "environment",
                "markov", "classify", "brains"):
        assert main.main([cmd]) == 0
    out = capsys.readouterr().out
    assert "T2_predicted_us" in out
    assert "recoherence_factor" in out
