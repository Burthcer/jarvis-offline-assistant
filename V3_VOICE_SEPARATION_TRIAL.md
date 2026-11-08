# Approved separate offline two-voice trial — not enabled

## Latest measured result — 7 November

7 November 2026 checkpoint: separate CPU separation trial remains OFF. No V1/V2/product runtime/model/shortcut changes. Safe tensor-only load and audited official-reference graph parity passed (maximum difference 0.0). Effective input rate is 16 kHz: upstream training recipe omitted the sample-rate model argument, leaving misleading 8 kHz metadata; convolution does not resample. No installed dependencies/global/Wisperno edits.

CPU-only separator p95 at 0.8/1.6/3/6 s input: 106.57/322.80/606.42/1159.20 ms. Full frozen45 pilot completed in112.31s, peak2641MB combined RSS/3135MiB GPU/75C; separator/checker CPU, separator CUDA allocation0. All owned tests/models closed. Added CPU separation+selection p95 by group about1.4–3.2s, failing200ms target. Clean prompt word-distance worsened in heldout (.125 -> .1875). Constructed overlaps showed improvements, but clean regression and delay independently mean keep OFF.

Pilot report data/v3/lab/separation/evaluation-full.json is preserved. Its strict expected-call grader had article-equivalence and extra-argument flaws: do NOT treat pilot correct/wrong-action counts as accepted semantic statistics. Grader now follows established V2 harness criteria, parity-tested; word-distance unchanged. The lab worker also now blocks every unsupported compound before effects using one fixed seven-capability allowlist, retaining blocked attempts for grading. Corrected full45 rerun is PENDING: use run_model_check.py evaluate_separation_trial.py --label corrected-grade after checking allowance/user workloads. Never overwrite pilot, tune heldout, or change frozen thresholds/matrix. New four silent suites (cases/policy/grader/ASR worker) pass after corrections. No live mic/playback/user app/clipboard/account tests.

the owner's latest stop threshold is about10%. Last allowance11% before checkpoint; no credits/reset used. Codex remains editor until the owner transfers to Fable. No automatic resume active. V3 usable PREVIEW only; V2 recommended daily. Original understanding and real-room acceptance gates remain open; no phase claimed fully accepted. Resume from CHECKPOINT_V3_2026-11-07_SEPARATION.md.

## Historical proposal and earlier checkpoints


6 November2026 update: the owner explicitly answered “Yes, test it separately.” The20.4MB weights are downloaded only to data/v3/lab/separation and verified against the pinned publisher revision/size/SHA below. No model has been loaded, no architecture/dependencies installed and no separation evaluation has run yet. Trial remains OFF in Jarvis. At4% allowance, continuation saved in CHECKPOINT_V3_2026-11-06_CPU_TRIAL.md and scheduled once after reset.

Pinned revision:e1ef95ab7a037950f3a606b9a56760cf94701d3d; file:pytorch_model.bin; size:20394640bytes; SHA256:8d97f012f7b2f22bb79cb0d0983a7ba27a52c1796ee3f63cbf25b4d28630adce. Manifest and upstream README retained in the separate ignored lab folder. Publisher metadata license:cc-by-sa-4.0; retain/read card before any distribution. Fetch script:tests/v3/prepare_separation_trial.py. It downloads/verifies only and executes no repository/checkpoint code. Earlier approval-boundary paragraphs below are historical proposal context; separate CPU testing is now approved, production integration is not.

6 November 2026. This is a concrete proposal for the remaining nearby-phone overlap problem, not a claim it is solved. the owner asked to consult before model changes. Existing speech/action/answer models stay unchanged. The separately approved83MB voice-check lab identifies voices; it does not unmix them.

## Candidate and evidence

- Candidate: [Joris Cosentino's ConvTasNet Libri2Mix clean16k model](https://huggingface.co/JorisCos/ConvTasNet_Libri2Mix_sepclean_16k). It is trained to output two speech streams from a mixture at16kHz. This suggests a test candidate; the card does not prove nearby-phone robustness or speed on this laptop.
- Publisher's [file listing](https://huggingface.co/JorisCos/ConvTasNet_Libri2Mix_sepclean_16k/tree/main) reports20.4MB weights, revision displayed as e1ef95a. Resolve/pin the full revision and weight SHA-256 before any approved download.
- Model card metadata and prose differ on license version; check/retain the upstream attribution before distributing anything. This proposal adds nothing to the app or its release.

## Approval boundary

User approval is needed for this separate additional-model trial. No weights/dependencies have been downloaded for it. If approved: use CPU only, a separate ignored `data/v3/lab/separation` environment, existing Torch read-only where compatible, no global/Wisperno installs. Load tensor-only weights with size/hash checks; do not execute repository code or unsafe checkpoint constructors. V1/V2/current V3 models and settings remain unchanged. The trial stays OFF in Jarvis even if it looks promising.

## Test before any enablement proposal

1. Freeze a mixture matrix from existing saved owner recordings and existing synthetic other-speaker recordings. No live microphone, playback or new voice profile saved. Include clean owner, other-only, silence, separate speech and overlapping voices at multiple loudness ratios; keep a held-out split.
2. Establish current Whisper + separately approved voice-check decisions on exactly those buffers. No real PC effects: use the fake PC and frozen expected intents.
3. Separate the same buffers, identify the owner's candidate stream using the existing lab checker, and reject ambiguous/tied speakers. Transcribe with the unchanged Whisper. Measure missing/changed words, missed commands, false owner acceptance, wrong target/action and clean-speech regressions. Never pick a stream using known ground truth in the actual decision path.
4. Measure elapsed time at0.8/1.6/3/6second input lengths, p50/p95 overhead, CPU/RAM and temperature. GPU allocation of the extra model must be zero; total assistant budget remains about4GB. Target added p95 work under200ms; this is a test target, not a measured capability.
5. Keep OFF if clean speech loses quality, other-only input becomes actionable, overlap gains are inconsistent or latency/heat are unsuitable. A recording of the owner still cannot be treated as secure identity. Report limits honestly, including telephone compression, reverberation and music/noise outside the training task.
6. Save only aggregate JSON/report and close every owned process. No audio upload or real app/tab/clipboard/account action. Any later production integration/enablement requires a separate concrete result and user decision.

Other unfinished gates remain: real-room acceptance, continuous addressedness, physical arrival sensing, live YouTube player compatibility, and the original command-understanding accuracy target. This trial cannot stand in for those gates.
