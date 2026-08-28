"""Small, explainable signal-processing pipeline used by the demo."""

import numpy as np
from scipy import signal
from scipy.stats import gaussian_kde
from scipy.spatial.distance import jensenshannon


def preprocess(acc, fs=100, low=0.8, high=20.0):
    acc = np.asarray(acc, dtype=float).reshape(-1)
    if acc.size == 0:
        return acc
    good = np.isfinite(acc)
    if not np.all(good):
        acc = np.where(good, acc, np.nanmedian(acc[good]) if np.any(good) else 0.0)
    if acc.size >= 2:
        x = np.linspace(-1.0, 1.0, acc.size)
        acc = acc - np.polyval(np.polyfit(x, acc, 1), x)
    nyq = fs / 2.0
    low_n, high_n = max(low / nyq, 1e-4), min(high / nyq, 0.999)
    if high_n <= low_n or acc.size < 32:
        return acc
    sos = signal.butter(4, [low_n, high_n], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, acc)


def welch_psd(acc, fs=100):
    nperseg = min(512, max(16, len(acc)))
    return signal.welch(acc, fs=fs, nperseg=nperseg, noverlap=nperseg // 2,
                        scaling="density")


def extract_candidate_peaks(f, pxx, band=(3.0, 15.0), top_k=5, min_prominence_ratio=0.03):
    mask = (f >= band[0]) & (f <= band[1])
    fb, pb = np.asarray(f)[mask], np.asarray(pxx)[mask]
    if len(fb) < 3 or not np.any(np.isfinite(pb)) or np.nanmax(pb) <= 0:
        return np.array([]), np.array([])
    pb = np.nan_to_num(pb, nan=0.0, posinf=0.0, neginf=0.0)
    peaks, props = signal.find_peaks(pb, prominence=np.max(pb) * min_prominence_ratio)
    if len(peaks) == 0:
        selected = np.argsort(pb)[-top_k:][::-1]
        return np.sort(fb[selected]), pb[selected][np.argsort(fb[selected])]
    order = np.argsort(props["prominences"])[::-1][:top_k]
    selected = peaks[order]
    order2 = np.argsort(fb[selected])
    return fb[selected][order2], props["prominences"][order][order2]


def crossing_to_peaks(crossing, band=(3.0, 15.0), top_k=5):
    fs = float(crossing.get("fs", 100))
    processed = preprocess(crossing.get("acc", []), fs=fs)
    f, pxx = welch_psd(processed, fs=fs)
    peaks, scores = extract_candidate_peaks(f, pxx, band=band, top_k=top_k)
    quality = float(np.max(pxx) / (np.median(pxx) + 1e-12)) if len(pxx) else 0.0
    return {"f": f, "pxx": pxx, "peaks": peaks, "peak_scores": scores,
            "processed": processed, "quality": quality}


def fuse_crossings(crossings, band=(3.0, 15.0), top_k=5, grid_points=800, bandwidth=0.10):
    all_peaks, all_scores, crossing_results = [], [], []
    for crossing in crossings:
        result = crossing_to_peaks(crossing, band=band, top_k=top_k)
        crossing_results.append(result)
        all_peaks.extend(result["peaks"].tolist())
        all_scores.extend(result["peak_scores"].tolist())
    all_peaks, all_scores = np.asarray(all_peaks, dtype=float), np.asarray(all_scores, dtype=float)
    grid = np.linspace(band[0], band[1], grid_points)
    if len(all_peaks) == 0:
        density, dominant = np.zeros_like(grid), np.nan
    elif len(all_peaks) >= 2 and np.ptp(all_peaks) > 1e-9:
        weights = np.maximum(all_scores, np.finfo(float).eps)
        weights /= weights.sum()
        try:
            density = gaussian_kde(all_peaks, bw_method=bandwidth, weights=weights)(grid)
        except (np.linalg.LinAlgError, ValueError):
            density = np.zeros_like(grid)
        if not np.any(density):
            sigma = max((band[1] - band[0]) / 80.0, 0.08)
            density = np.sum(np.exp(-0.5 * ((grid[:, None] - all_peaks) / sigma) ** 2), axis=1)
        dominant = float(grid[np.argmax(density)])
    else:
        sigma = max((band[1] - band[0]) / 80.0, 0.08)
        density = np.exp(-0.5 * ((grid - all_peaks[0]) / sigma) ** 2)
        dominant = float(all_peaks[0])
    fingerprint = density / np.max(density) if np.max(density) > 0 else density
    concentration = float(np.mean(np.abs(all_peaks - dominant) <= 0.25)) if len(all_peaks) and np.isfinite(dominant) else 0.0
    stability = float(np.clip(concentration * (1.0 - 1.0 / np.sqrt(max(len(crossings), 1))), 0.0, 1.0))
    return {"grid": grid, "density": density, "fingerprint": fingerprint,
            "dominant_frequency": dominant, "all_peaks": all_peaks,
            "all_scores": all_scores, "crossing_results": crossing_results,
            "pulse_stability": stability, "crossing_concentration": concentration}


def fingerprint_divergence(fp_a, fp_b, eps=1e-12):
    a, b = np.asarray(fp_a, dtype=float) + eps, np.asarray(fp_b, dtype=float) + eps
    a, b = a / a.sum(), b / b.sum()
    return float(jensenshannon(a, b, base=2.0) ** 2)


def bootstrap_baseline_divergence(crossings, n_iter=40, sample_frac=0.55, seed=123):
    rng, vals, n = np.random.default_rng(seed), [], len(crossings)
    if n < 8:
        return {"values": np.array([]), "threshold95": np.nan}
    m = max(4, int(n * sample_frac))
    for _ in range(n_iter):
        ia, ib = rng.choice(n, size=m, replace=False), rng.choice(n, size=m, replace=False)
        fa, fb = fuse_crossings([crossings[i] for i in ia])["fingerprint"], fuse_crossings([crossings[i] for i in ib])["fingerprint"]
        vals.append(fingerprint_divergence(fa, fb))
    vals = np.asarray(vals)
    return {"values": vals, "threshold95": float(np.quantile(vals, 0.95))}


def convergence_curve(crossings, counts=(1, 5, 10, 20, 30, 50), seed=123):
    """Return pulse and bootstrap stability at progressively larger counts.

    Stability is the inverse of the spread of dominant frequencies obtained
    from repeated half-sample bootstraps, not an arbitrary visual score.
    """
    rng = np.random.default_rng(seed)
    out = []
    for count in counts:
        subset = list(crossings[:count])
        fused = fuse_crossings(subset)
        estimates = []
        if len(subset) > 1:
            sample_size = max(1, len(subset) // 2)
            for _ in range(16):
                indices = rng.choice(len(subset), size=sample_size, replace=True)
                estimate = fuse_crossings([subset[i] for i in indices])["dominant_frequency"]
                if np.isfinite(estimate):
                    estimates.append(estimate)
        spread = float(np.std(estimates)) if len(estimates) >= 2 else np.inf
        stability = 0.0 if not np.isfinite(spread) else float(np.clip(np.exp(-spread / 0.20), 0.0, 1.0))
        out.append({"n": count, "dominant_frequency": fused["dominant_frequency"],
                    "stability": stability, "bootstrap_std_hz": spread})
    return out
