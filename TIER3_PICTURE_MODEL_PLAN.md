# V4 Tier 3: picture model for unnamed icons (parked, 8 Nov 2026)

Status: **researched, NOT downloaded, NOT built.** the owner parked it on 8 Nov 2026 ("not the right time to test it"). Come back here to resume.

## What it is for
Buttons/icons with **no name** at all (some apps draw plain pictures). When the normal screen index (Windows accessibility names) finds nothing, Jarvis would take a picture of **only the window in front**, ask a small local vision model "where is the <thing>?", and get a point back.

## The two options found
| | A. Moondream 2 (2B), graphics card | B. Moondream 0.5B, processor |
|---|---|---|
| Points at things | Yes, officially (`model.point(image, "thing")`) | Not confirmed for 0.5B |
| Accuracy | Better | Makers say limited out of the box |
| Download | Several GB (official local engine "Photon" via `pip install moondream`, plus ~2B-parameter weights from Hugging Face; exact size to check before downloading) | ~480-590 MB (int8) |
| Memory while used | Graphics memory, likely ~4 GB (4B chat model unloaded meanwhile; the owner's limit is 5 GB, hard 7 GB) | ~1 GB RAM, no graphics memory |
| Speed | Likely under 1 s (unmeasured) | Likely 1-3 s (unmeasured) |
| Hardware | NVIDIA Ampere or newer (RTX 4070 OK), Windows supported | Any CPU |
| Licence | Apache-2.0 | Apache-2.0 |

Recommendation at the time: **A**. Caveat: Moondream is a general picture model, not trained on app screenshots, so small-icon accuracy is unknown until measured.

## Agreed trial process (nothing is enabled until it passes)
1. Install into a **separate trial folder** (no change to V2/V3/V4 Python setup). Tell the owner the exact size first; he approves the download.
2. Test only on pictures of **owned** test windows (tests/v3/owned_edge.py: muted, signed-out, temporary profile). Measure right/wrong, speed, VRAM, temperature.
3. Enable only if mostly right and **never clicks the wrong thing**. First use of a picture-found spot shows a marker and asks "Shall I click here, sir?"; before clicking, the control under the point is re-checked through accessibility.
4. Load only when needed, unload right after (one model on the GPU at a time, as now).
5. If it fails: delete it and report. V4 works without it.

## Where it would plug in
`jarvis3/screen_index.py`: `ScreenIndex.target()` / `visible()` after `_patient()` finds nothing -> new `picture_point(label)` -> confirm -> press via `ControlFromPoint` (or a click at the point if no control is there).

## Sources (checked 8 Nov 2026)
- https://huggingface.co/vikhyatk/moondream2 (Apache-2.0, 2B, `point()`, revision 2025-06-21)
- https://docs.moondream.ai/running-locally/ (Photon, Ampere+ GPUs, Windows AMD64, Python 3.10-3.14)
- https://pypi.org/project/moondream/ (official client 2.6.x with Photon local engine)
- https://moondream.ai/blog/introducing-moondream-0-5b (0.5B: 479 MiB int8 compressed, ~996 MiB to run)
- https://moondream.ai/models (0.5B described as a distillation target; limited accuracy out of the box)
