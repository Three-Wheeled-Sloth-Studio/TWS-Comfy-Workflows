from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_nodes/comfyui_audio_duration_plan/local_visualizer_nodes.py"


def _module():
    specification = importlib.util.spec_from_file_location("infra_choir_test_module", MODULE_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def main() -> int:
    import numpy as np
    import torch

    module = _module()
    sample_rate = 48000
    seconds = 3.0
    time = torch.arange(round(sample_rate * seconds), dtype=torch.float32) / sample_rate
    pulse = (0.35 + 0.65 * (torch.sin(math.tau * 2.0 * time) > 0.92).float())
    waveform = pulse * (
        0.28 * torch.sin(math.tau * 72.0 * time)
        + 0.16 * torch.sin(math.tau * 900.0 * time)
        + 0.08 * torch.sin(math.tau * 7800.0 * time)
    )
    audio = {"waveform": waveform[None, None, :], "sample_rate": sample_rate}
    arguments = (audio, 16, seconds, 128, 8192, 2048, "log", 20.0, 20000.0, 66.0, -72.0, 1.0, 0.22)
    first = module._enhanced_audio_features(*arguments)
    second = module._enhanced_audio_features(*arguments)
    assert first["spectrum_bands"].shape == (48, 128)
    assert second["cache_status"] == "hit"
    for name in ("energy", "low", "mid", "high", "kick", "snare", "hihat", "onset", "beat", "beat_phase", "beat_confidence", "phrase"):
        values = first[name]
        assert values.shape == (48,), name
        assert np.isfinite(values).all(), name
        assert float(values.min()) >= 0.0 and float(values.max()) <= 1.0001, name

    shaped = module._shape_audio_response(
        first["kick"], 16,
        {"group_delay_ms": 125.0, "response_attack_ms": 20.0, "response_decay_ms": 120.0,
         "response_hold_ms": 40.0, "response_sustain": 0.1, "response_release_ms": 240.0,
         "response_smoothing": 0.1, "response_min": 0.0, "response_max": 1.0,
         "response_sensitivity": 1.0, "response_curve": 1.0, "rhythmic_subdivision": 1,
         "accent_weight": 0.0, "group_gain": 1.0},
    )
    assert shaped.shape == (48,) and np.isfinite(shaped).all()
    curve, report = module._section_override_curve('[{"start": 1, "end": 2, "gain": 0.5}]', 48, 16)
    assert report == "1 override(s)" and np.allclose(curve[16:32], 0.5)

    legacy_light = module._lighting_luminance_amount(0.12, 0.20, 0.05, False)
    enhanced_light = module._lighting_luminance_amount(0.22, 0.20, 0.05, True)
    assert 0.0 < legacy_light < 0.05
    assert 0.04 < enhanced_light < 0.08
    assert module._lighting_luminance_amount(0.22, 0.0, 0.0, True) == 0.0
    assert module._lighting_luminance_amount(0.16, 2.0, 0.0, True) == 0.16
    assert module._lighting_glow_amount(0.55, 0.40, 0.05, True) > 0.10

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    before = frame.copy()
    module._apply_high_resolution_eq(
        frame, first["spectrum_bands"][20], first["spectrum_bands"][20],
        "fine_spectrum_bars", 10.5, 0.4, (142, 19, 37),
    )
    changed = np.any(frame != before, axis=2)
    assert changed[-100:].any()
    assert not changed[:-100].any()
    print("Infra Choir enhanced analysis, cache, envelope, section, and EQ tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
