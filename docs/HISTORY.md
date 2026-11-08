# History: V1 to V4

Everything below happened between 31 October and 8 November 2026. Dates are from the git history and the project log.

## V1 (31 Oct to 3 Nov): make it work

Built in milestones, in plain Python first.

- **M1 (31 Oct):** a reminder and memory engine you type to. Then 75,000+ automatic checks and more than 20 bug fixes in one day.
- **M2:** PC actions (open, search, volume, media, timers) behind an allowlist. Volume matched Windows to the percent.
- **M3:** a small pill and tray icon. Moved up the plan because the owner wanted to see and judge the interface early.
- **M4 (voice):** wake word, speech-to-text with a large Whisper model on the GPU, British text-to-speech. Live testing found many problems (see BUGS.md), and several rounds fixed them: two-step wake check, recording through the wake reply, whole-sentence listening, a better voice (Kokoro).
- **M5, brought forward:** a small local AI (Llama 3.2 3B) rewrites messy speech into clean commands.
- **1 Nov:** open and close desktop apps, "shut down", faster replies, back-to-back commands, a new web-based window and a floating pill that does not steal focus.
- **3 Nov:** V1 declared complete. The owner's verdict after daily use: it felt "hard-coded, not smart", and it was bad at hearing him.

## V2 (3 to 5 Nov): measure first, then rebuild

- **Stage 1:** instead of guessing, record the owner saying 40+ real commands in three conditions (quiet, music on speakers, earphones) and measure. Result: transcribing the whole sentence beat V1's piece-by-piece listening, so the listening front end was rewritten.
- **Plan:** a written rebuild plan (V2_REBUILD_PLAN.md) with a design contract, phases 0 to 7, and a sample set of 265 "gold" sentences to score understanding.
- **Phases 2 to 7:** a registry of safe actions, a small AI that picks one, hands-free ears that cancel the PC's own sound, many abilities, memory and learning, a new window with a Knowledge page. Score on the gold sentences: 224 of 265.
- **Daily-use fixes (4 Nov):** the owner said V2 felt worse than V1. Root causes were found and fixed (see BUGS.md). Then: skills taught by voice, a wish list, new look, student organiser, checked task plans.
- **Improvement programme (4 to 5 Nov):** ten areas approved (verified actions, better conversations, speed, knowledge, browser control, app control, routines, organiser, connections, visible learning). Done in the offline form; live acceptance left to the owner.

## V3 (5 to 8 Nov): a separate, safer rebuild of the voice pipeline

Built as a separate preview next to V2, so the daily tool never broke.

- **Phase 1:** reliable hearing: wake acknowledged early, one wake equals one action, real success/error sounds, actions confirmed by reading state back.
- **Phase 2 to 4:** optional follow-ups, undo, corrections, workspaces (open all the apps for a project), numbered choices, music sessions, a living logo.
- **Experiments:** voice-check model (kept off by default), a speech-separation trial (not adopted), camera arrival (opt-in), hand gestures (built, tested, then removed).
- **Daily log fixes (7 Nov):** many fixes driven by the owner's real logs (see BUGS.md).
- **UI:** reactor display with 11 modes, Settings regrouped, Knowledge page, Routines cards, floating pill with a level-driven logo.
- **8 Nov:** released as Jarvis V3 3.0.0 (tag `v3.0.0`).

## V4 (8 Nov): Jarvis can see the screen

Started from the V3 3.0.0 release in a new folder, with its own identity (name, shortcut, data, startup key).

1. **Identity:** copied V3 and renamed everything visible; V2 and V3 shortcuts verified unchanged.
2. **Silent screen index:** one cached Windows accessibility scan of the front window, with plain word matching. "Click Shorts" works; two close matches give badges and "which one?".
3. **Self-healing site memory:** remembers where a control was, and checks the spot still matches before pressing. If the page changed, it rescans and relearns.
4. **Draft, confirm, send:** writes a message, reads it back, holds it, and sends only on "send".
5. **Multi-step tasks:** up to five steps, each verified by a visible change.
6. **Fixes from live tests (twice):** see BUGS.md.
7. **Extras:** "open/start X" clicks X if it is on screen; "number the screen"; short replies ("Done, sir."); a living reactor; a smooth 60/30 fps floating pill.
8. **Parked:** a picture model for unnamed icons, until the owner approves a download.

## How the work was done

An AI assistant wrote and ran all code and tests; the owner tested by using it and reporting. Work was checkpointed when the AI allowance ran low, so another assistant could continue. Every milestone reported memory, graphics memory and temperature, because the laptop runs hot.
