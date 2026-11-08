# Features: V1 vs V2 vs V3 vs V4

Yes = built. Partial = built with known limits. No = not in that version.

| Feature | V1 | V2 | V3 | V4 |
| --- | --- | --- | --- | --- |
| Reminders and notes (typed) | Yes | Yes | Yes | Yes |
| Timers (pause, resume, several at once) | Yes | Yes | Yes | Yes |
| Open / close apps and sites | Yes | Yes, safer allowlist | Yes | Yes |
| Wake by saying the name | Yes, wake-word model plus Whisper check | Yes, hands-free, whole-sentence listening | Yes, plus fast "acknowledge" before the full sentence | Yes |
| Hears while PC sound is playing | No | Yes (cancels the PC's own sound) | Better (follows default speaker) | Yes |
| Understanding messy speech | 3B model rewrites to fixed commands | 1.5B model chooses an action from a registry; 4B answers questions | Same, with more guards and correction handling | Same, plus screen-aware tasks |
| Replies | Fixed, then reworded by AI | Worded by AI, checked | Checked against what really happened | Short: "Done, sir." |
| Chained conversation ("do that again", "undo") | No | Yes | Yes, with timed undo | Yes |
| Memory of facts and habits | Basic notes | Yes, learns names and habits | Yes, editable Knowledge page | Yes |
| Routines taught by voice | No | Yes (skills) | Yes, cards with editable steps | Yes |
| Volume and speech speed by voice | Partial | Yes | Yes, with read-back | Yes |
| Browser tabs (close 2nd and 3rd, focus) | Partial | Partial | Yes, native, verified | Yes |
| Window minimise / maximise / restore | No | Yes | Yes | Yes |
| Music: next, previous, skip N | Key press only | Yes | Yes, per player session | Yes |
| Numbered choices ("which one?") | No | No | Yes | Yes |
| Click things on screen by name | No | Partial (UI Automation) | Partial | **Yes** (screen index) |
| Site memory that heals when a page changes | No | No | No | **Yes** |
| Draft, confirm, then send a message | No | No | No | **Yes** |
| Multi-step screen tasks | No | Plans of up to 5 abilities | Yes | **Yes** (observe, act, verify) |
| "Number the screen" | No | No | No | **Yes** |
| Student organiser (deadlines, exams) | No | Yes | Yes | Yes |
| Read-only Gmail / Calendar | No | Yes (needs your own setup) | Yes | Yes |
| Backup and restore | No | Yes | Yes | Yes |
| Interface | Tk pill, then web window | Web window, Knowledge tab | Redesigned, reactor display, light/dark | Living reactor, smooth floating pill |
| Optional: only react to my voice | No | No | Yes (off by default) | Yes |
| Optional: camera arrival | No | No | Yes (off by default) | Yes |
| Hand gestures | No | No | Tried, then removed | No |
| Sends anything online | No | No | No | No |

## Sizes (measured on the build laptop)

| | V1 | V2 / V3 / V4 |
| --- | --- | --- |
| Graphics memory | about 3.8 GB | about 3 GB for commands, about 4 GB while a big answer runs |
| RAM | about 3.6 GB | about 2 GB |
| Wake to first reply | about 0.5 s | about 0.65 s from end of speech to action in replay tests |
| Idle GPU load | 0% | 0% |
