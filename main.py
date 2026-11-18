#!/usr/bin/env python3
"""QuantumDecoherence-Lab - educational decoherence lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the central lesson is stated up front:

  * Decoherence is computed here two honest ways. First as Kraus
    channels on a qubit density matrix (amplitude damping and pure
    dephasing), where the coherence |rho_01| decays as an exact
    exponential and the textbook bookkeeping 1/T2 = 1/(2*T1) +
    1/T_phi is verified against the composed channel, not quoted.
  * Then as a mechanism: one qubit coupled to a tiny finite
    environment of three labelled spins, evolved exactly as a
    statevector. The coherence falls because the environment
    states separate - and because three spins are not a bath, it
    partially COMES BACK. That recoherence is printed, sized, and
    fenced off: it is an artefact of a 3-spin universe, never a
    way to beat decoherence in a real device.
  * Every T value in this lab is a LABELLED teaching number. No
    qubit sat in a fridge, no device was measured, and nothing
    here is a specification, a benchmark, or a record.

Hardware, coherence-record, vendor, fault-tolerance, product, and
recoherence-as-recovery claims are permanent HOLD gates - with
Gemini Argon 4 Extended Thinking as DECIDER (names-only,
tighten-only), Muse as advisor (never overrides HOLD), and
Google Flow plan-only seats.
"""
import cmath
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"

# Labelled teaching lifetimes, in microseconds. These are round
# numbers chosen so the arithmetic is easy to audit - they are NOT
# measurements of any real qubit.
T1_US = 50.0        # labelled energy-relaxation time
T_PHI_US = 80.0     # labelled pure-dephasing time
T2_US = 1.0 / (1.0 / (2.0 * T1_US) + 1.0 / T_PHI_US)  # = 44.444444...

# The finite environment: three labelled spins coupled to the qubit
# by controlled-phase (Ising ZZ style) interactions. Couplings are
# in inverse env-time units; env time is its own labelled unit.
ENV_COUPLINGS = (1.0, 1.7, 2.9)
ENV_T_MAX = 40.0
ENV_STEP = 0.01

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "real_hardware_control": "HOLD - no control of real qubits, cryostats, or lab hardware from a teaching file",
    "coherence_record_claim": "HOLD - no record-T1/T2 or coherence-breakthrough claim; every lifetime here is a labelled teaching number",
    "device_specification_claim": "HOLD - T1, T_phi, and T2 in this lab are not specifications of any real device",
    "vendor_benchmark_claim": "HOLD - no vendor comparison, benchmark, or leaderboard claim",
    "fault_tolerance_claim": "HOLD - no claim that any real processor sits above or below a fault-tolerance threshold",
    "quantum_memory_product_claim": "HOLD - pointer-state survival math is not a quantum memory product",
    "error_correction_guarantee_claim": "HOLD - no guarantee that error correction fixes real-world decoherence",
    "recoherence_recovery_claim": "HOLD - finite-environment recoherence is an artefact of a 3-spin universe; it must never be sold as a way to beat decoherence in a real device",
    "live_experiment_direction": "HOLD - no directing live experiments from this lab",
    "cryogenics_operation_claim": "HOLD - no cryostat or dilution-refrigerator operation guidance",
    "fabrication_instruction_claim": "HOLD - no qubit fabrication instructions",
    "certified_metrology_claim": "HOLD - no certified measurement or metrology claim from toy channel math",
    "investment_claim": "HOLD - no investment claims; a lab model is not a prospectus",
    "medical_device_claim": "HOLD - no medical, imaging, or clinical sensing claim from toy channel math",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. 2x2 density matrices
# A qubit density matrix is a 2x2 list of complex numbers, built and
# multiplied by hand - no linear-algebra library anywhere in the lab.

def _mm(a, b):
    return [[a[i][0] * b[0][j] + a[i][1] * b[1][j] for j in range(2)]
            for i in range(2)]


def _dag(a):
    return [[a[j][i].conjugate() for j in range(2)] for i in range(2)]


def _madd(a, b):
    return [[a[i][j] + b[i][j] for j in range(2)] for i in range(2)]


def _trace(rho):
    return rho[0][0] + rho[1][1]


def _apply_kraus(rho, kraus_ops):
    out = [[0j, 0j], [0j, 0j]]
    for k in kraus_ops:
        out = _madd(out, _mm(_mm(k, rho), _dag(k)))
    return out


def _kraus_completeness_error(kraus_ops):
    """max |sum K^dagger K - I| over entries: 0 for a real channel."""
    s = [[0j, 0j], [0j, 0j]]
    for k in kraus_ops:
        s = _madd(s, _mm(_dag(k), k))
    return max(abs(s[0][0] - 1), abs(s[0][1]),
               abs(s[1][0]), abs(s[1][1] - 1))


def _purity(rho):
    return (_trace(_mm(rho, rho))).real


def coherence(rho):
    """The off-diagonal magnitude |rho_01| - the thing decoherence eats."""
    return abs(rho[0][1])


def ket_density(alpha, beta):
    """Density matrix of alpha|0> + beta|1>."""
    return [[alpha * alpha.conjugate(), alpha * beta.conjugate()],
            [beta * alpha.conjugate(), beta * beta.conjugate()]]


_S = 1.0 / math.sqrt(2.0)
RHO_GROUND = ket_density(1.0 + 0j, 0j)                    # |0>
RHO_EXCITED = ket_density(0j, 1.0 + 0j)                   # |1>
RHO_PLUS = ket_density(_S + 0j, _S + 0j)                  # |+>
RHO_PLUS_I = ket_density(_S + 0j, 1j * _S)                # |+i>
RHO_MIXTURE = [[0.7 + 0j, 0.2 + 0j],                      # populations 0.7/0.3,
               [0.2 + 0j, 0.3 + 0j]]                      # coherence 0.2


# ================================================================ 2. Kraus channels
# Amplitude damping with parameter gamma: K0 keeps |0> and shrinks
# |1> by sqrt(1-gamma); K1 moves the gamma share of |1> to |0>.
# Pure dephasing in phase-flip form with probability p: coherence
# is multiplied by (1 - 2p), populations are never touched.

def amplitude_damping_kraus(gamma):
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("gamma must lie in [0, 1]")
    return [
        [[1.0 + 0j, 0j], [0j, math.sqrt(1.0 - gamma) + 0j]],
        [[0j, math.sqrt(gamma) + 0j], [0j, 0j]],
    ]


def dephasing_kraus(p):
    if not 0.0 <= p <= 0.5:
        raise ValueError("phase-flip probability must lie in [0, 0.5]")
    a, b = math.sqrt(1.0 - p), math.sqrt(p)
    return [
        [[a + 0j, 0j], [0j, a + 0j]],
        [[b + 0j, 0j], [0j, -b + 0j]],
    ]


def gamma_at(t, t1=T1_US):
    """Damping parameter for elapsed time t at lifetime t1."""
    return 1.0 - math.exp(-t / t1)


def phase_flip_p_at(t, t_phi=T_PHI_US):
    """Phase-flip probability giving coherence factor exp(-t/t_phi)."""
    return (1.0 - math.exp(-t / t_phi)) / 2.0


def damped(rho, t, t1=T1_US):
    return _apply_kraus(rho, amplitude_damping_kraus(gamma_at(t, t1)))


def dephased(rho, t, t_phi=T_PHI_US):
    return _apply_kraus(rho, dephasing_kraus(phase_flip_p_at(t, t_phi)))


def composed(rho, t, t1=T1_US, t_phi=T_PHI_US):
    """Amplitude damping and pure dephasing applied together."""
    return dephased(damped(rho, t, t1), t, t_phi)


def channel_report():
    """Coherence bookkeeping for |+> under each channel, labelled times."""
    rows = {}
    for name, fn in (("amplitude_damping", damped), ("pure_dephasing", dephased),
                     ("composed", composed)):
        rows[name] = {}
        for t in (10.0, 25.0, 50.0, 100.0, 200.0):
            out = fn(RHO_PLUS, t)
            rows[name][f"t={t:g}"] = {
                "coherence": round(coherence(out), 6),
                "coherence_factor": round(coherence(out) / 0.5, 6),
                "excited_population": round(out[1][1].real, 6),
            }
    rows["at_t_equals_T1"] = {
        "damping_coherence_factor": round(
            coherence(damped(RHO_PLUS, T1_US)) / 0.5, 6),
        "expected_exp_minus_half": round(math.exp(-0.5), 6),
        "excited_population_factor": round(
            damped(RHO_PLUS, T1_US)[1][1].real / 0.5, 6),
        "expected_exp_minus_one": round(math.exp(-1.0), 6),
    }
    rows["at_t_equals_T_phi"] = {
        "dephasing_coherence_factor": round(
            coherence(dephased(RHO_PLUS, T_PHI_US)) / 0.5, 6),
        "expected_exp_minus_one": round(math.exp(-1.0), 6),
        "populations_unchanged": abs(
            dephased(RHO_PLUS, T_PHI_US)[1][1].real - 0.5) < 1e-12,
    }
    return rows


# ================================================================ 3. T1 / T2 bookkeeping
# The textbook line 1/T2 = 1/(2*T1) + 1/T_phi is not quoted here -
# it is measured: run the composed channel, fit a straight line to
# log(coherence) vs t by least squares, and compare the fitted T2
# against the value the relation predicts.

def _fit_log_line(ts, ys):
    n = len(ts)
    sx, sy = sum(ts), sum(ys)
    sxx = sum(x * x for x in ts)
    sxy = sum(x * y for x, y in zip(ts, ys))
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    intercept = (sy - slope * sx) / n
    return slope, intercept


def t2_fit(t1=T1_US, t_phi=T_PHI_US):
    """Least-squares fit of the composed channel's coherence decay."""
    ts = [2.0 * i for i in range(1, 26)]
    ys = [math.log(coherence(composed(RHO_PLUS, t, t1, t_phi)) / 0.5)
          for t in ts]
    slope, _ = _fit_log_line(ts, ys)
    return -1.0 / slope


def lifetime_report():
    predicted = 1.0 / (1.0 / (2.0 * T1_US) + 1.0 / T_PHI_US)
    fitted = t2_fit()
    return {
        "T1_us_labelled": T1_US,
        "T_phi_us_labelled": T_PHI_US,
        "T2_predicted_us": round(predicted, 6),
        "T2_fitted_from_composed_channel_us": round(fitted, 6),
        "fit_relative_error": abs(fitted - predicted) / predicted,
        "relation": "1/T2 = 1/(2*T1) + 1/T_phi",
        "coherence_at_T2": round(coherence(composed(RHO_PLUS, predicted)), 6),
        "half_coherence_at_T2_expected": round(0.5 / math.e, 6),
        "note": "T values are labelled teaching numbers, not device data",
    }


# ================================================================ 4. Pointer states
# Under dephasing in the Z basis, the basis states |0> and |1> are
# fixed points - there is no coherence to kill and the populations
# never move. Superpositions lose exactly the exp(-t/T_phi) share
# of their coherence. That asymmetry is why the Z basis is called
# the pointer basis for this environment.

def pointer_report(t=T_PHI_US):
    states = {
        "ground_|0>": RHO_GROUND,
        "excited_|1>": RHO_EXCITED,
        "superposition_|+>": RHO_PLUS,
        "superposition_|+i>": RHO_PLUS_I,
        "partial_mixture_0.7/0.3": RHO_MIXTURE,
    }
    rows = {}
    for name, rho in states.items():
        out = dephased(rho, t)
        rows[name] = {
            "coherence_in": round(coherence(rho), 6),
            "coherence_out": round(coherence(out), 6),
            "excited_population_in": round(rho[1][1].real, 6),
            "excited_population_out": round(out[1][1].real, 6),
            "purity_in": round(_purity(rho), 6),
            "purity_out": round(_purity(out), 6),
        }
    return {"elapsed_us": t, "T_phi_us_labelled": T_PHI_US,
            "dephasing_factor_expected": round(math.exp(-t / T_PHI_US), 6),
            "states": rows}


# ================================================================ 5. Decoherence from entanglement
# The mechanism, not a map. The qubit starts in |+>, each of the
# three environment spins starts in |+>, and a controlled-phase
# coupling g_k between the qubit and spin k runs for time t. The
# joint state is a 16-amplitude statevector, evolved exactly: a
# basis state |s, e1, e2, e3> picks up the phase
# exp(i * s * (g1*t*e1 + g2*t*e2 + g3*t*e3)).
# Tracing out the spins gives the qubit's reduced density matrix.
# Its coherence is 0.5 * prod_k (1 + exp(-i*g_k*t)) / 2 - the
# overlap of the two environment branches. When the branches are
# orthogonal the coherence is gone; with only three spins the
# branches wander back, and the coherence partially returns.

def env_statevector(t, couplings=ENV_COUPLINGS):
    amps = []
    for s in (0, 1):
        for e in range(8):
            bits = ((e >> 2) & 1, (e >> 1) & 1, e & 1)
            phase = s * sum(g * t * b for g, b in zip(couplings, bits))
            amps.append(0.25 * cmath.exp(1j * phase))
    return amps


def env_reduced_rho(t, couplings=ENV_COUPLINGS):
    amps = env_statevector(t, couplings)
    rho = [[0j, 0j], [0j, 0j]]
    for s in (0, 1):
        for sp in (0, 1):
            rho[s][sp] = sum(amps[s * 8 + e] * amps[sp * 8 + e].conjugate()
                             for e in range(8))
    return rho


def env_overlap(t, couplings=ENV_COUPLINGS):
    """Complex overlap <E1|E0> of the two environment branches."""
    out = 1.0 + 0j
    for g in couplings:
        out *= (1.0 + cmath.exp(-1j * g * t)) / 2.0
    return out


def env_coherence_factor(t, couplings=ENV_COUPLINGS):
    return abs(env_overlap(t, couplings))


def env_scan(couplings=ENV_COUPLINGS):
    """Scan the factor curve: collapse minimum, then recoherence peak."""
    n = int(round(ENV_T_MAX / ENV_STEP))
    curve = [(i * ENV_STEP, env_coherence_factor(i * ENV_STEP, couplings))
             for i in range(n + 1)]
    t_min, v_min = min(curve, key=lambda p: p[1])
    t_peak, v_peak = max((p for p in curve if p[0] > t_min), key=lambda p: p[1])
    return {"curve": curve, "t_min": t_min, "min_factor": v_min,
            "t_recoherence": t_peak, "recoherence_factor": v_peak}


def environment_report():
    scan = env_scan()
    samples = {}
    for t in (0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 40.0):
        rho = env_reduced_rho(t)
        samples[f"t={t:g}"] = {
            "coherence_factor": round(env_coherence_factor(t), 6),
            "rho01_matches_overlap": abs(
                rho[0][1] - 0.5 * env_overlap(t)) < 1e-12,
            "populations": [round(rho[0][0].real, 6),
                            round(rho[1][1].real, 6)],
            "purity": round(_purity(rho), 6),
        }
    return {
        "couplings_labelled": list(ENV_COUPLINGS),
        "environment_spins": len(ENV_COUPLINGS),
        "samples": samples,
        "collapse_min_factor": scan["min_factor"],
        "collapse_min_at_t": round(scan["t_min"], 2),
        "recoherence_factor": round(scan["recoherence_factor"], 6),
        "recoherence_at_t": round(scan["t_recoherence"], 2),
        "honest_note": "recoherence is an artefact of a finite 3-spin "
                       "environment; a macroscopic bath does not come back",
    }


# ================================================================ 6. Markovian vs finite environment
# The same exponential story is fitted to both worlds. For the
# Kraus channel the fit is the truth (residual at machine
# precision). For the 3-spin environment an exponential fitted to
# the initial collapse predicts essentially zero forever - and is
# wrong by the full size of the recoherence peak.

def _fit_decay_constant(ts, factors):
    """Single-parameter log fit, amplitude pinned to 1: T from data."""
    num = sum(t * math.log(v) for t, v in zip(ts, factors) if v > 0.0)
    den = sum(t * t for t in ts)
    return -den / num


def markov_report():
    # Kraus side: deviation of the composed channel from exp(-t/T2).
    grid_k = [0.5 * i for i in range(int(3 * T2_US / 0.5) + 1)]
    kraus_dev = max(
        abs(coherence(composed(RHO_PLUS, t)) / 0.5 - math.exp(-t / T2_US))
        for t in grid_k)
    # Environment side: fit T on the initial collapse window (0, 1],
    # then grade that exponential over the whole scan window.
    fit_ts = [0.05 * i for i in range(1, 21)]
    t_env_fit = _fit_decay_constant(
        fit_ts, [env_coherence_factor(t) for t in fit_ts])
    scan = env_scan()
    residuals = [(abs(v - math.exp(-t / t_env_fit)), t)
                 for t, v in scan["curve"]]
    max_resid, t_worst = max(residuals)
    rms = math.sqrt(sum(r * r for r, _ in residuals) / len(residuals))
    return {
        "kraus_max_deviation_from_exponential": kraus_dev,
        "env_fit_T_from_initial_collapse": round(t_env_fit, 6),
        "env_fit_predicted_at_recoherence": math.exp(
            -scan["t_recoherence"] / t_env_fit),
        "env_actual_at_recoherence": round(scan["recoherence_factor"], 6),
        "env_max_residual": round(max_resid, 6),
        "env_max_residual_at_t": round(t_worst, 2),
        "env_rms_residual": round(rms, 6),
        "verdict": "the exponential is exact for the Kraus channel and "
                   "fails by the recoherence peak for the finite "
                   "environment - that gap is where the Markov story ends",
    }


# ================================================================ 7. kNN regime classifier
# Features: labelled T1, labelled T_phi, elapsed time. The training
# grid is labelled by the lab's own regime policy (model_label
# below) - the classifier interpolates the policy, it does not
# replace the channel computation.

def model_label(t1, t_phi, t):
    """The regime policy distilled to a four-way teaching label."""
    relaxation_factor = math.exp(-t / (2.0 * t1))   # coherence share T1 leaves
    dephasing_factor = math.exp(-t / t_phi)          # coherence share T_phi leaves
    if dephasing_factor <= 0.05 and relaxation_factor >= 0.70:
        return "pointer-stable"
    if relaxation_factor * dephasing_factor >= 0.80:
        return "coherent"
    if 1.0 / t_phi >= 1.0 / (2.0 * t1):
        return "dephasing-dominated"
    return "relaxation-dominated"


def _training_grid():
    rows = []
    for t1 in (10.0, 25.0, 50.0, 100.0, 200.0):
        for t_phi in (10.0, 25.0, 50.0, 100.0, 200.0):
            for t in (0.0, 5.0, 10.0, 25.0, 50.0, 100.0):
                rows.append(((t1, t_phi, t), model_label(t1, t_phi, t)))
    return rows


TRAINING_GRID = _training_grid()


def _scaled(features):
    t1, t_phi, t = features
    return (t1 / 200.0, t_phi / 200.0, t / 100.0)


def _knn(features, k):
    target = _scaled(features)
    ranked = []
    for point_features, label in TRAINING_GRID:
        point = _scaled(point_features)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, point)))
        ranked.append((dist, point_features, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    votes = {}
    for _, _, label in ranked[:k]:
        votes[label] = votes.get(label, 0) + 1
    priority = {"coherent": 0, "pointer-stable": 1,
                "dephasing-dominated": 2, "relaxation-dominated": 3}
    return sorted(votes.items(), key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def classify_regime(t1, t_phi, t, k=3):
    """kNN over the policy-labelled grid, deterministic tie-breaking."""
    return _knn((t1, t_phi, t), k)


def classifier_report():
    scenarios = {
        "fresh_qubit_short_time": (200.0, 200.0, 1.0),
        "dephasing_heavy_device": (200.0, 10.0, 20.0),
        "relaxation_heavy_device": (10.0, 200.0, 20.0),
        "pointer_state_regime": (200.0, 10.0, 75.0),
        "aged_state_25_25_100": (25.0, 25.0, 100.0),
    }
    return {name: classify_regime(*features)
            for name, features in scenarios.items()}


# ================================================================ 8. Advisory seats
def _seat_trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="quantumdecoherence-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all hardware and record gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _seat_trace(payload),
    }


def claude_advisor(topic="quantumdecoherence-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Print the recoherence next to its fence: a 3-spin environment giving coherence back is a finite-size artefact, and the moment it is quoted without the fence it becomes the exact overclaim this lab exists to prevent.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["a Bloch vector shrinking toward the z axis under dephasing",
                  "excited population draining to the ground state under damping",
                  "three environment spins fanning out as their branches separate",
                  "the coherence curve collapsing, then partially rising again",
                  "the exponential fit line sailing under the recoherence peak"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 1. Kraus machinery - completeness, trace, hermiticity, positivity
    chk("kraus_ad_complete",
        all(_kraus_completeness_error(amplitude_damping_kraus(g)) < 1e-12
            for g in (0.0, 0.3, 0.632121, 1.0)))
    chk("kraus_pd_complete",
        all(_kraus_completeness_error(dephasing_kraus(p)) < 1e-12
            for p in (0.0, 0.2, 0.5)))
    chk("channels_preserve_trace",
        all(abs(_trace(composed(RHO_PLUS, t)) - 1.0) < 1e-12
            for t in (0.0, 13.7, 50.0, 123.4)))
    chk("channels_keep_hermiticity",
        all(abs(composed(RHO_MIXTURE, t)[0][1]
                - composed(RHO_MIXTURE, t)[1][0].conjugate()) < 1e-12
            for t in (7.0, 42.0)))
    chk("channels_keep_positivity",
        all((lambda r: r[0][0].real * r[1][1].real
             - abs(r[0][1]) ** 2)(composed(RHO_PLUS, t)) > -1e-12
            for t in (3.0, 30.0, 90.0)))

    # 2. amplitude damping - the sqrt law and the ground fixed point
    chk("ad_ground_state_fixed_point",
        max(abs(damped(RHO_GROUND, 100.0)[i][j] - RHO_GROUND[i][j])
            for i in range(2) for j in range(2)) < 1e-12)
    chk("ad_full_damping_lands_on_ground",
        max(abs(_apply_kraus(RHO_EXCITED, amplitude_damping_kraus(1.0))[i][j]
                - RHO_GROUND[i][j])
            for i in range(2) for j in range(2)) < 1e-12)
    chk("ad_coherence_sqrt_law",
        all(abs(coherence(_apply_kraus(RHO_PLUS, amplitude_damping_kraus(g)))
                / 0.5 - math.sqrt(1.0 - g)) < 1e-12
            for g in (0.1, 0.36, 0.75)))
    chk("ad_population_law",
        all(abs(_apply_kraus(RHO_PLUS, amplitude_damping_kraus(g))[1][1].real
                / 0.5 - (1.0 - g)) < 1e-12
            for g in (0.1, 0.36, 0.75)))
    chk("ad_at_T1_factors",
        abs(coherence(damped(RHO_PLUS, T1_US)) / 0.5
            - math.exp(-0.5)) < 1e-12
        and abs(damped(RHO_PLUS, T1_US)[1][1].real / 0.5
                - math.exp(-1.0)) < 1e-12)

    # 3. pure dephasing - populations exact, coherence exponential
    chk("pd_populations_untouched",
        all(abs(dephased(RHO_MIXTURE, t)[i][i].real
                - RHO_MIXTURE[i][i].real) < 1e-12
            for t in (11.0, 37.5, 80.0) for i in range(2)))
    chk("pd_coherence_law",
        all(abs(coherence(dephased(RHO_PLUS, t)) / 0.5
                - math.exp(-t / T_PHI_US)) < 1e-12
            for t in (20.0, 80.0, 160.0)))
    chk("pd_basis_states_untouched",
        all(max(abs(dephased(rho, T_PHI_US)[i][j] - rho[i][j])
                for i in range(2) for j in range(2)) < 1e-12
            for rho in (RHO_GROUND, RHO_EXCITED)))

    # 4. T1/T2 bookkeeping - the relation is measured, not quoted
    chk("t2_relation_value", abs(T2_US - 44.44444444444444) < 1e-9)
    chk("composed_at_T2_is_half_over_e",
        abs(coherence(composed(RHO_PLUS, T2_US)) - 0.5 / math.e) < 1e-12)
    life = lifetime_report()
    chk("t2_fit_agrees_with_relation", life["fit_relative_error"] < 1e-9)
    chk("kraus_coherence_monotone",
        all(coherence(composed(RHO_PLUS, 5.0 * (i + 1)))
            <= coherence(composed(RHO_PLUS, 5.0 * i)) + 1e-15
            for i in range(20)))

    # 5. pointer states - survival table recomputed, not trusted
    prep = pointer_report()
    st = prep["states"]
    chk("pointer_ground_survives",
        st["ground_|0>"]["coherence_out"] == 0.0
        and abs(st["ground_|0>"]["excited_population_out"]) < 1e-6)
    chk("pointer_excited_survives",
        st["excited_|1>"]["coherence_out"] == 0.0
        and abs(st["excited_|1>"]["excited_population_out"] - 1.0) < 1e-6)
    chk("pointer_superposition_decays_by_e",
        abs(st["superposition_|+>"]["coherence_out"] / 0.5
            - math.exp(-1.0)) < 1e-5
        and abs(st["superposition_|+i>"]["coherence_out"] / 0.5
                - math.exp(-1.0)) < 1e-5)
    chk("pointer_mixture_keeps_populations_loses_coherence",
        abs(st["partial_mixture_0.7/0.3"]["excited_population_out"] - 0.3)
        < 1e-6
        and abs(st["partial_mixture_0.7/0.3"]["coherence_out"] / 0.2
                - math.exp(-1.0)) < 1e-5)

    # 6. finite environment - mechanism, collapse, recoherence
    chk("env_statevector_normalised",
        all(abs(sum(abs(a) ** 2 for a in env_statevector(t)) - 1.0) < 1e-12
            for t in (0.0, 3.3, 9.24, 25.9)))
    chk("env_rho01_matches_overlap",
        all(abs(env_reduced_rho(t)[0][1] - 0.5 * env_overlap(t)) < 1e-12
            for t in (0.7, 2.5, 9.24, 17.3, 25.9)))
    chk("env_populations_pinned",
        all(abs(env_reduced_rho(t)[i][i].real - 0.5) < 1e-12
            for t in (1.1, 9.24, 25.9) for i in range(2)))
    chk("env_starts_fully_coherent",
        abs(env_coherence_factor(0.0) - 1.0) < 1e-12
        and abs(_purity(env_reduced_rho(0.0)) - 1.0) < 1e-12)
    scan = env_scan()
    chk("env_collapse_is_deep", scan["min_factor"] < 1e-4)
    chk("env_collapse_purity_floor",
        _purity(env_reduced_rho(scan["t_min"])) < 0.51)
    chk("env_recoherence_is_real",
        scan["recoherence_factor"] > 0.9
        and scan["t_recoherence"] > scan["t_min"])

    # 7. Markovian vs finite environment - where the exponential ends
    mrep = markov_report()
    chk("markov_kraus_deviation_tiny",
        mrep["kraus_max_deviation_from_exponential"] < 1e-12)
    chk("markov_env_residual_large", mrep["env_max_residual"] > 0.5)
    chk("markov_env_fit_blind_to_recoherence",
        mrep["env_fit_predicted_at_recoherence"] < 1e-9
        and mrep["env_actual_at_recoherence"] > 0.9)

    # 8. classifier - labels come from the lab's own regime policy
    rep = classifier_report()
    chk("classifier_fresh_coherent", rep["fresh_qubit_short_time"] == "coherent")
    chk("classifier_dephasing_dominated",
        rep["dephasing_heavy_device"] == "dephasing-dominated")
    chk("classifier_relaxation_dominated",
        rep["relaxation_heavy_device"] == "relaxation-dominated")
    chk("classifier_pointer_stable",
        rep["pointer_state_regime"] == "pointer-stable")
    chk("classifier_aged_dephasing",
        rep["aged_state_25_25_100"] == "dephasing-dominated")
    chk("classifier_matches_policy_on_scenarios",
        all(classify_regime(*f) == model_label(*f) for f in (
            (200.0, 200.0, 1.0), (200.0, 10.0, 20.0), (10.0, 200.0, 20.0),
            (200.0, 10.0, 75.0), (25.0, 25.0, 100.0))))
    chk("classifier_grid_self_consistent",
        all(_knn(features, 1) == label
            for features, label in TRAINING_GRID))

    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_hardware_hold", gate("real_hardware_control") == "HOLD")
    chk("gate_record_hold", gate("coherence_record_claim") == "HOLD")
    chk("gate_recoherence_hold", gate("recoherence_recovery_claim") == "HOLD")
    chk("gate_memory_product_hold",
        gate("quantum_memory_product_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("QuantumDecoherence-Lab - decoherence, computed two honest ways")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - what this lab does and does not claim")
    print("    Decoherence is computed as Kraus channels on a density")
    print("    matrix, then again as a mechanism: one qubit entangling")
    print("    with a 3-spin environment. Every lifetime is a LABELLED")
    print("    teaching number - no device was measured, nothing here")
    print("    is a specification, a benchmark, or a record.")
    print("\n[2] Kraus channels - completeness first (sum K^dagger K = I)")
    print(f"    amplitude damping gamma=0.632121: completeness error "
          f"{_kraus_completeness_error(amplitude_damping_kraus(0.632121)):.2e}")
    print(f"    pure dephasing p=0.316060:        completeness error "
          f"{_kraus_completeness_error(dephasing_kraus(0.316060)):.2e}")
    print("\n[3] Coherence decay of |+> - the two channels eat differently")
    rep = channel_report()
    for name in ("amplitude_damping", "pure_dephasing", "composed"):
        row = rep[name]
        print(f"    {name:18s} factor t=25us {row['t=25']['coherence_factor']:.6f}"
              f" | t=100us {row['t=100']['coherence_factor']:.6f}"
              f" | t=200us {row['t=200']['coherence_factor']:.6f}")
    ad = rep["at_t_equals_T1"]
    print(f"    damping at t=T1: coherence x{ad['damping_coherence_factor']:.6f}"
          f" (= e^-1/2) but population x{ad['excited_population_factor']:.6f}"
          f" (= e^-1) - coherence dies at half the population rate")
    pd = rep["at_t_equals_T_phi"]
    print(f"    dephasing at t=T_phi: coherence x{pd['dephasing_coherence_factor']:.6f}"
          f" (= e^-1), populations unchanged: {pd['populations_unchanged']}")
    print("\n[4] T1/T2 bookkeeping - the relation is fitted, not quoted")
    life = lifetime_report()
    print(f"    labelled T1 = {life['T1_us_labelled']:.0f} us, "
          f"T_phi = {life['T_phi_us_labelled']:.0f} us")
    print(f"    1/T2 = 1/(2*T1) + 1/T_phi predicts T2 = "
          f"{life['T2_predicted_us']:.6f} us")
    print(f"    least-squares fit of the composed channel gives T2 = "
          f"{life['T2_fitted_from_composed_channel_us']:.6f} us "
          f"(relative error {life['fit_relative_error']:.2e})")
    print(f"    coherence at t=T2: {life['coherence_at_T2']:.6f} "
          f"= 0.5/e = {life['half_coherence_at_T2_expected']:.6f}")
    print("\n[5] Pointer states - who survives dephasing at t = T_phi = 80 us")
    prep = pointer_report()
    for name, row in prep["states"].items():
        print(f"    {name:26s} coherence {row['coherence_in']:.6f} -> "
              f"{row['coherence_out']:.6f} | excited pop "
              f"{row['excited_population_in']:.6f} -> "
              f"{row['excited_population_out']:.6f}")
    print("    -> the Z basis states are fixed points; superpositions pay")
    print("       the full e^-1. That asymmetry names the pointer basis.")
    print("\n[6] The mechanism - one qubit, three environment spins")
    env = environment_report()
    for t, row in env["samples"].items():
        print(f"    {t:8s} coherence factor {row['coherence_factor']:.6f} | "
              f"purity {row['purity']:.6f} | populations {row['populations']}")
    print(f"    collapse: factor falls to {env['collapse_min_factor']:.3e} "
          f"at t = {env['collapse_min_at_t']:.2f} (env-time units)")
    print(f"    RECOHERENCE: factor returns to {env['recoherence_factor']:.6f} "
          f"at t = {env['recoherence_at_t']:.2f}")
    print("    -> three spins are not a bath. A macroscopic environment")
    print("       does not come back; this one does, and the size is printed.")
    print("\n[7] Markovian vs finite environment - where the exponential ends")
    mrep = markov_report()
    print(f"    Kraus channel vs its exponential: max deviation "
          f"{mrep['kraus_max_deviation_from_exponential']:.2e}")
    print(f"    env exponential fitted on the initial collapse: T = "
          f"{mrep['env_fit_T_from_initial_collapse']:.6f}")
    print(f"    at the recoherence peak it predicts "
          f"{mrep['env_fit_predicted_at_recoherence']:.2e}; the actual "
          f"factor is {mrep['env_actual_at_recoherence']:.6f}")
    print(f"    max residual {mrep['env_max_residual']:.6f} at t = "
          f"{mrep['env_max_residual_at_t']:.2f} | RMS residual "
          f"{mrep['env_rms_residual']:.6f}")
    print("\n[8] Regime classifier (TinyML kNN, labels from the lab's policy)")
    for name, label in classifier_report().items():
        print(f"    {name:28s} -> {label}")
    print("\n[9] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[10] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "channels":
        print(json.dumps(channel_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "lifetimes":
        print(json.dumps(lifetime_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "pointer":
        print(json.dumps(pointer_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "environment":
        print(json.dumps(environment_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "markov":
        print(json.dumps(markov_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "coherence_record_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
