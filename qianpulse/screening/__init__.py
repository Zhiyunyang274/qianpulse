"""Baseline comparison and persistent response screening."""

from qianpulse.engine import bootstrap_baseline_divergence, fingerprint_divergence


def screen_response(baseline_fingerprint, current_fingerprint, threshold):
    """Return an explainable screening decision from two Bridge Pulse fingerprints."""
    divergence = fingerprint_divergence(baseline_fingerprint, current_fingerprint)
    return {"divergence": divergence, "threshold": float(threshold),
            "status": "RESPONSE SHIFT" if divergence > threshold else "NORMAL",
            "recommendation": "Recommend targeted engineering inspection" if divergence > threshold else "Continue routine monitoring"}


__all__ = ["bootstrap_baseline_divergence", "fingerprint_divergence", "screen_response"]
