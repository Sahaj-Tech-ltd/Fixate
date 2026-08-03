"""
Per-type ADHD adaptation defaults — research-backed.

Applied at reader init and settings save time. Each subtype gets
different noise, nudge, comprehension check, and theme defaults.

References:
  - Soderlund et al. (2024): ADHD-I benefits from noise, ADHD-H may worsen
  - Nigg et al. (2024): non-ADHD impaired by noise (g=-0.212)
  - WashU (2025): stimulants work through reward, not attention
  - Moussaoui et al. (2025): RSVP boosts ADHD comprehension by 13%
"""


def get_profile_defaults(adhd_subtype, sensory_sensitivity="medium"):
    """
    Return a dict of research-backed defaults for the given profile.

    Args:
        adhd_subtype: 'none', 'inattentive', 'hyperactive', 'combined'
        sensory_sensitivity: 'low', 'medium', 'high'

    Returns dict with keys:
        noise_enabled, default_noise_slug, noise_volume,
        nudge_enabled, nudge_intensity,
        comprehension_checks_enabled, comprehension_check_interval_seconds,
        suggested_theme, suggested_font
    """
    base = {
        "noise_enabled": False,
        "default_noise_slug": None,
        "noise_volume": 0.35,
        "nudge_enabled": False,
        "nudge_intensity": "subtle",  # subtle, moderate, strong
        "comprehension_checks_enabled": False,
        "comprehension_check_interval_seconds": 180,
        "suggested_theme": "dark",
        "suggested_font": "inter",
        # Noise customization defaults (EQ + LFO per subtype)
        "noise_lfo_speed": 0.18,      # Hz — modulation rate
        "noise_lfo_depth": 0.03,      # 0.01-0.10 — modulation depth
        "noise_brightness": 0.0,      # -1.0 (dark/bassy) to +1.0 (bright/hissy)
    }

    # ── Per-subtype defaults ──

    if adhd_subtype == "inattentive":
        # Benefits most from noise (g=0.249). High DMN intrusion.
        # Needs frequent re-engagement. Sensory sensitivity common.
        # Moderate LFO keeps the noise "alive" without being distracting.
        # Slightly brighter EQ for alertness boost.
        base.update({
            "noise_enabled": True,
            "default_noise_slug": "pink-noise",
            "noise_volume": 0.40,
            "nudge_enabled": True,
            "nudge_intensity": "moderate",
            "comprehension_checks_enabled": True,
            "comprehension_check_interval_seconds": 150,
            "suggested_theme": "warm-night",
            "suggested_font": "lexend",
            "noise_lfo_speed": 0.18,
            "noise_lfo_depth": 0.04,
            "noise_brightness": 0.15,
        })

    elif adhd_subtype == "hyperactive":
        # Noise may worsen performance (Soderlund 2024).
        # Already overstimulated. If noise is on: very slow LFO,
        # minimal depth, darker/warmer EQ for calming effect.
        base.update({
            "noise_enabled": False,
            "default_noise_slug": None,
            "noise_volume": 0.0,
            "nudge_enabled": False,
            "nudge_intensity": "subtle",
            "comprehension_checks_enabled": True,
            "comprehension_check_interval_seconds": 240,
            "suggested_theme": "low-stim",
            "suggested_font": "inter",
            "noise_lfo_speed": 0.08,
            "noise_lfo_depth": 0.02,
            "noise_brightness": -0.2,
        })

    elif adhd_subtype == "combined":
        # Mixed. Balanced defaults.
        base.update({
            "noise_enabled": True,
            "default_noise_slug": "white-noise",
            "noise_volume": 0.35,
            "nudge_enabled": True,
            "nudge_intensity": "moderate",
            "comprehension_checks_enabled": True,
            "comprehension_check_interval_seconds": 180,
            "suggested_theme": "dark",
            "suggested_font": "atkinson",
            "noise_lfo_speed": 0.18,
            "noise_lfo_depth": 0.03,
            "noise_brightness": 0.0,
        })

    else:  # 'none' — no ADHD
        # Noise IMPAIRS performance (Nigg 2024, g=-0.212).
        # Flat, no modulation.
        base.update({
            "noise_enabled": False,
            "default_noise_slug": None,
            "noise_volume": 0.0,
            "nudge_enabled": False,
            "comprehension_checks_enabled": False,
            "suggested_theme": "dark",
            "suggested_font": "inter",
            "noise_lfo_speed": 0.0,
            "noise_lfo_depth": 0.0,
            "noise_brightness": 0.0,
        })

    # ── Sensory sensitivity overrides ──

    if sensory_sensitivity == "high":
        base["noise_volume"] = min(base["noise_volume"], 0.25)
        base["nudge_intensity"] = "subtle"
        base["suggested_theme"] = "low-stim" if adhd_subtype != "none" else "dark"
        base["suggested_font"] = "opendyslexic" if adhd_subtype != "none" else "inter"

    elif sensory_sensitivity == "low":
        base["noise_volume"] = min(base["noise_volume"] + 0.10, 0.60)

    return base
