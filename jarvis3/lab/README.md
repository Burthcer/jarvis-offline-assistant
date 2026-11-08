# Separate CPU voice-check lab

Approved by the owner on 5 November 2026 for testing only. This package is never imported by the production V3 listening path. It does not change existing models, automatically enrol a user or save a voice profile.

`V3_STATUS.md` contains results and limits. In particular, voice similarity does not separate overlapping speech and is not secure authentication. The fixed 0.25 threshold is an experiment setting, not a product acceptance rule.

## Reproducing the experiment

The coding assistant runs these steps; the owner should not need to run commands.

1. `py -3.12 tools/setup_voice_check_lab.py` creates the separate environment and retrieves the pinned, checksum-verified 83,316,686-byte official weight file. Network is needed only for this explicit setup. Do not download another model as an automatic fallback.
2. Use `data/v3/lab/env/Scripts/python.exe` for subsequent lab commands. The tested environment reuses global NumPy 2.5.2 / ONNX Runtime 1.31.0 and reads existing Wisperno Torch/Torchaudio 2.6.0+cu124 packages. CPU devices are selected explicitly; CUDA visibility is disabled. No Wisperno/global packages are installed or edited.
3. Run `tests/v3/evaluate_voice_check.py` for the original CPU path. It enrols from three existing quiet clips, holds the profile in memory and evaluates the other 103 owner clips plus 11 existing synthetic other-voice samples. No mic or sound output is opened.
4. Run `tools/export_voice_check.py` for the same-weight float32 CPU export, then `tests/v3/evaluate_voice_check.py --onnx`. Decision parity against the reference results is required; score drift above 0.001 refuses the result. No quantisation is used.

Existing local recordings are required at `data/gold/audio/`, `data/feedback-audio/` and `voice_samples/`; missing recordings are not permission to record new audio. Outputs, weights, caches and the environment remain under ignored `data/v3/lab/`. These scripts must not enable the candidate in V2/V3.

The tensor-weight revision is `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`; SHA-256 `0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2`. The export manifest records its own hash and sample validation. A pure-tone diagnostic has larger spectral/log round-off than real speech; retained in `tests/v3/diagnose_voice_export.py`, not hidden by relaxed test decisions.
