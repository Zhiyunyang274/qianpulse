"""Analysis pipeline for controlled physical-validation Sensor Logger runs."""

import numpy as np

from qianpulse.engine import fingerprint_divergence, preprocess, welch_psd

_trapz = getattr(np, "trapezoid", np.trapz)


ANALYSIS_BAND = (5.0, 25.0)


def _normalise_density(values, grid):
    values = np.nan_to_num(np.asarray(values, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    values = np.maximum(values, 0.0)
    area = float(_trapz(values, grid))
    return values / area if area > 0 else np.zeros_like(values)


def analyse_run(run, grid, band=ANALYSIS_BAND):
    """Detrend, band-pass, calculate Welch PSD and a normalized fingerprint."""
    processed = preprocess(run["acc"], fs=run["fs"], low=band[0], high=band[1])
    frequencies, psd = welch_psd(processed, fs=run["fs"])
    fingerprint = _normalise_density(
        np.interp(grid, frequencies, psd, left=0.0, right=0.0), grid
    )
    peak = float(grid[np.argmax(fingerprint)]) if np.any(fingerprint) else np.nan
    return {**run, "processed": processed, "frequencies": grid,
            "fingerprint": fingerprint, "dominant_frequency": peak}


def _group_summary(runs, grid):
    fingerprints = np.asarray([run["fingerprint"] for run in runs])
    fused = _normalise_density(np.mean(fingerprints, axis=0), grid)
    peak = float(grid[np.argmax(fused)]) if np.any(fused) else np.nan
    return {"fingerprint": fused, "dominant_frequency": peak}


def _band_energy(fingerprint, grid, band):
    mask = (grid >= band[0]) & (grid <= band[1])
    total = float(_trapz(fingerprint, grid))
    selected = float(_trapz(fingerprint[mask], grid[mask])) if np.count_nonzero(mask) > 1 else 0.0
    return selected / total if total > 0 else np.nan


def analyse_physical_experiment(discovered, band=ANALYSIS_BAND, grid_points=801):
    """Calculate all per-run, fused, divergence and energy-shift results."""
    grid = np.linspace(band[0], band[1], grid_points)
    baseline = [analyse_run(run, grid, band) for run in discovered.get("baseline", [])]
    perturbed = [analyse_run(run, grid, band) for run in discovered.get("perturbed", [])]
    if not baseline or not perturbed:
        raise ValueError("Physical validation needs at least one baseline and one perturbed run")

    base_group = _group_summary(baseline, grid)
    pert_group = _group_summary(perturbed, grid)
    all_runs = baseline + perturbed
    matrix = np.zeros((len(all_runs), len(all_runs)), dtype=float)
    for i, run_a in enumerate(all_runs):
        for j, run_b in enumerate(all_runs):
            matrix[i, j] = fingerprint_divergence(run_a["fingerprint"], run_b["fingerprint"])

    within_baseline = matrix[:len(baseline), :len(baseline)][np.triu_indices(len(baseline), 1)]
    within_perturbed = matrix[len(baseline):, len(baseline):][np.triu_indices(len(perturbed), 1)]
    cross_state = matrix[:len(baseline), len(baseline):].reshape(-1)
    fused_divergence = fingerprint_divergence(
        base_group["fingerprint"], pert_group["fingerprint"]
    )
    base_peak, pert_peak = base_group["dominant_frequency"], pert_group["dominant_frequency"]
    shift_percent = (pert_peak - base_peak) / base_peak * 100.0

    return {
        "grid": grid,
        "baseline": baseline,
        "perturbed": perturbed,
        "baseline_group": base_group,
        "perturbed_group": pert_group,
        "divergence_matrix": matrix,
        "within_baseline": within_baseline,
        "within_perturbed": within_perturbed,
        "cross_state": cross_state,
        "fused_divergence": fused_divergence,
        "shift_percent": float(shift_percent),
        "baseline_energy_11_16": _band_energy(base_group["fingerprint"], grid, (11.0, 16.0)),
        "perturbed_energy_8_11": _band_energy(pert_group["fingerprint"], grid, (8.0, 11.0)),
    }
