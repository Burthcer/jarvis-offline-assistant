# Plan (one milestone at a time; stop after each and wait for the owner's results)

- [x] **M1 Reminders + memory (text only, no AI).** SQLite store, time parsing, duplicate-merge (repeat item updates the entry), "today / yesterday / missed / upcoming" queries, due-reminder check. Text prompt to try it.
- [x] **M2 Rules engine + PC actions.** `handle(text)` entry point; open apps/sites in the right browser, search ("search lo-fi on YouTube"), volume/media keys, timers, default-browser settings page. Allowlist + confirm for risky. Text-tested. (jarvis/actions.py)
- [x] **M3 (moved up by the owner, 2026-10-31) Pill UI, tray, settings window** (typed commands for now; voice plugs in later).
- [x] **M4 Voice (was M3).** Wake word ("Hey Jarvis"), speech-to-text, British TTS, pre-made "Yes" clips, auto mic follow, spoken reminders, voice volume/speed commands. Measure ms, RAM/VRAM, temps.
- [x] **M5 Local LLM** (was M4; brought forward 2026-10-31, jarvis/brain.py) for loose phrasing -> structured action. Test 20-30 messy sentences; accuracy + speed. Load on demand / unload idle. Tell the owner size + licence before any large download.
- [ ] **M5b Later UI additions** once voice/LLM exist (voice, speed/volume, mic, model pickers).
- [ ] **M6 Draft mode** (stretch).
- [ ] **M7 Packaging** (launcher/installer, startup option, final resource report).
