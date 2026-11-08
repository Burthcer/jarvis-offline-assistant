# Jarvis V3 — audited requirements and future build plan

Created: 5 November 2026. Status: **PARTIAL PREVIEW ACROSS PHASES 1–4; NOT COMPLETE; LIVE ACCEPTANCE PENDING.**

7 November latest scope: the owner authorized a practical command/workspace/media fixes batch, then a Fable handoff near **10% remaining Codex allowance** (supersedes historical5% instructions). Nearby-phone separation, continuous addressedness and physical arrival remain delegated difficult work. Newly requested camera hand gestures, distant on-screen clicking and a future ring-marked hand are recorded in FABLE_V3_NEXT_WORK.md; not implemented or live-camera-authorized by this batch. Both separate CPU voice-check and20.4MB separation experiments have approval to test, remain OFF, and have no production-integration approval. Consult newest V3_STATUS/checkpoint for evidence, not dated completion assumptions below.

the owner explicitly authorised fixing two V2 issues and then directly beginning V3 on5November. He continues using V2; V3 is a separate preview. Permission to build does not authorise account access, new hardware, browser extensions or unsolicited live microphone/sound tests. He separately approved testing an approximately83MB CPU voice-check model and a local test voice profile; it is a lab experiment, not enabled in the assistant. No other model changes/downloads are authorised.

The Gemini text is requirements material. Statements such as “once Phase 1 is solid” describe dependencies, not completed work. Phase1's live reliability/phone-interference gate has not passed. the owner subsequently explicitly authorised proceeding with the next phases without waiting for manual testing; Phases2–4 now have partial implementations with optional automatic modes off. None is fully accepted. See V3_STATUS.md for measured progress.

## 1. What the owner actually wants

An offline assistant he can trust while tired, speaking casually, walking into the room or listening to other audio. He should know whether it heard him and whether it really acted, without watching the screen. It should understand corrections, short follow-ups and the current task, and control a workspace or visible choices with little effort.

V3 must be a substantial improvement over V2 in measured daily use. A fresh coat of paint, more command patterns or a passing fake test alone does not meet this goal. Preserve useful V2 features and current model quality while fixing the listening, understanding and action pipeline.

The assistant writes and runs the code. the owner tests real use and chooses preferences; he is not expected to implement the plan. Explain progress in short, plain words. Inside Jarvis, address him as “sir”.

## 2. Prompt audit

The four blocks form **Phases 1, 2, 3 and 4**. the owner clarified that the last block was accidentally labelled Phase 5; it is Phase 4. No phase is missing. Phase 1 now has a partial preview; none has passed its full acceptance gate.

| Source wording / gap | Audited requirement |
| --- | --- |
| “100% reliable”, “interference-proof”, “at any millisecond” | These express the desired experience, not guarantees we can honestly make. Define observable timing, first-attempt success, false actions and stress tests. Record the remaining failure conditions. |
| About3 failures in20 attempts | User-reported V2 experience, not a controlled V3 benchmark. Separate missed wake, missing/clipped audio, wrong transcript, wrong interpretation and failed action. Establish a fresh baseline. |
| “The exact moment it catches my wake word” and “command successfully executed” | Two distinct signals. Catching the wake word, accepting a command and verifying an action are different events. Never play success merely because words were transcribed or a call was sent. |
| “Isolate my voice” near a phone | Phone playback is not the laptop's playback reference, so laptop echo cancellation alone does not solve it. Evaluate external-speech rejection and overlapping speech separately; refuse uncertain actions instead of inventing certainty. |
| Automatic arrival detection | Define an available, explicitly enabled signal. Unlock/input after inactivity is a return-to-desk hint, not proof someone physically entered the room. No camera, phone tracking or new sensor assumed. |
| Wake-word-free intent detection | Separate a short follow-up window from continuously accepting name-free commands. The latter is an optional mode needing stronger evidence and false-trigger testing. Normal room speech must not silently become commands. |
| “This”, screen and clipboard awareness | Capture a small, fresh, permitted context for this request. Do not continuously record screens, scrape all tabs or read clipboard content by default. Ask when more than one target fits. |
| “Scratch that” cleanly reverts whatever happened | Reverse only actions with a real, checked reversal. Stop unstarted steps; do not promise to unsend messages, recover unsaved work or undo arbitrary app actions. |
| “Automatically spin up my environment” | Run an editable, user-approved project profile. Do not guess project folders, tools, playlists or browser accounts. Reuse verified existing resources. |
| “DOM control” without vision | Prefer supported browser page structure and Windows accessibility. Their availability and permissions must be proved. Unsupported pages must fail clearly; no invisible fallback to coordinate guessing. |
| Target preview “before or as” selection | Show a target before the effect. Separate safe automatic selection from actions needing confirmation. A highlight does not prove the later action succeeded. |
| Source prompts say “build” now | Initially planning only; the later explicit user instruction now authorises the separate V3 build. Future phase-completion assumptions remain invalid. |

No model, library, browser extension or speaker-identification approach is chosen by these prompts. Technical choices require a later local capability check, measurements and any relevant user approval.

## 3. Version separation — mandatory

### Keep the working versions intact

- V1 remains the legacy version in `jarvis/`. V2 remains the daily-use version in `jarvis2/`. Neither is overwritten to make V3.
- Original V2 baseline was `e5c0e33`; V3's actual private fork is from `49cb25a7cfd74081310fabcca5da7dd4b3cac2cd`, after the two separately requested V2 fixes. Original-source hashes are in `jarvis3/BASELINE.json` and checked by the isolation test.
- Leave the current desktop **Jarvis** shortcut, its icon, executable, startup setting and launch behaviour untouched. Do not rename it to build V3.
- V3 gets a separate **Jarvis V3 (Preview)** shortcut and a purple circular three-bar icon. Its window, tray, pill and diagnostics identify it as V3. Installation must preserve the existing V2 shortcut byte-for-byte.
- Never edit shared V1/V2 modules to support V3. Any reused mutable implementation must be copied into V3-owned code or otherwise isolated without changing V2's runtime behaviour.
- Do not change installed shared dependencies in place to satisfy V3. Plan a separate environment when required; keep existing model files read-only and avoid duplicating large weights unnecessarily.

### Separate layout

| Purpose | V3 location / identity |
| --- | --- |
| Code and UI assets | `jarvis3/engine/`, private `jarvis3/legacy/`, `jarvis3/assets/` |
| Entry point | `Jarvis3.pyw` and a separate V3 launcher |
| Tests | `tests/v3/` with disposable profiles/data |
| Databases, settings, backups and optional clips | `data/v3/data/`, never V2's database |
| Logs and measurements | `data/v3/logs/`; disposable test output in `data/v3-dev-checks/` |
| Packaged desktop runtime | `data/runtime-v3/JarvisV3.exe` |
| Icon | `jarvis3/assets/jarvis-v3.ico`, never overwrite existing ICOs |
| Startup and account credentials | Distinct V3 entries, off/unconnected by default |

The private source, runtime and test paths now exist. No V2 facts/accounts were imported. The optional CPU experiment lives in `data/v3/lab/` with its own environment and weights. An implementation branch/worktree alone would not isolate runtime data or shared imports.

### Known V2 coupling to avoid

Local inspection shows V2 imports V1 modules, redirects V1's settings functions through `jarvis2/settings.py`, uses `data/jarvis.db` for facts/reminders, and shares a single-instance mutex with V1. The current packaging script writes the existing `Jarvis.lnk`. **Do not just copy the entry point and run the old packaging script.** First trace every write path and startup side effect, then prove V3 cannot write V1/V2 state.

V3 starts with its own data. A later import must be an explicit, previewed copy with a backup, never a move or live shared database. Distinguish facts/routines from active reminders so copying does not create two sets of spoken alerts. Do not copy account tokens silently. V3 edits must never flow back into V2.

Both versions stay installed. Default to one active voice assistant at a time to prevent double actions, competing microphones and excessive graphics memory. V3 may detect that V2 is active and explain the conflict; it must not kill, suspend or reconfigure V2 automatically. Any future side-by-side review mode must explicitly disable V3 listening/actions and stay within the memory limit.

## 4. Carry-forward rules and honest baseline

- Offline AI and local storage remain the default. Existing explicitly chosen online services are separate opt-in connections, not permission to upload audio/screens/clipboard data.
- Keep current models and quality. Approximately4GB total graphics memory remains the ceiling, including any new voice filter. Consult the owner before changing models or downloading additional weights. Do not assume spare laptop VRAM is authorised.
- Measure loaded RAM, graphics memory, CPU/GPU load, temperatures, cold/warm delay and sustained operation. If an approach cannot fit, report the measured tradeoff before changing the model or exceeding the budget.
- All development tests stay silent (`JARVIS_SILENT=1`), with fake audio/output, fake PC actions or strictly owned disposable windows/browser profiles. Do not operate the owner's apps, tabs, clipboard or accounts in automated tests. User-led acoustic tests are separate and explicitly scheduled later.
- Stop only processes proved to be started by the test. Never close the owner's running V2 for convenience. Never launch Narrator or the other prohibited accessibility apps.
- Keep allowlisted actions, protected-window restrictions and fresh confirmation for sensitive actions. Project profiles, room arrival, model output and webpage text do not bypass these checks. Do not add arbitrary shell execution or source self-editing.
- Preserve V2 knowledge, reminders, events, routines, media, window/tab controls, themes and account capabilities as regression requirements for V3, while keeping their data separate.
- Follow the latest usage rule: check the five-hour allowance at milestones; at about5% remaining, save a V3-specific checkpoint, clean up owned tests and stop. A reset does not authorise continuing implementation by itself. Never consume resets/credits automatically.

V2's last full understanding run was224/265, with the original quality gate unmet. Saved-audio and fake/owned-window tests are not evidence of reliable live-room hearing. Actual Quick Share closing and some browser cases remain unverified. Re-measure these; do not label them solved in V3 because a V2 document said “built”.

## 5. Phase 1 — trust the wake-word flow first

**Status: wake/capture/feedback implementation is development-tested, including stale-input revocation, device-change boundaries and queued mic-off protection; not live-accepted.** No proactive greeting or general wake-word-free mode in this phase. Keep only the explicit wake reply/question-follow-up needed to finish the current request. External-phone voice isolation remains unfinished; the optional CPU voice check is not a speech separator.

### Required behaviour

1. Provide a fast, short audible wake acknowledgement once a real wake is accepted. Capture the following command immediately, including speech overlapping that acknowledgement. The sound must not deafen capture or become a command itself.
2. Preserve a small audio lead-in so the first word is not clipped. Allow natural gaps, low-energy/tired speech and a separate wake-then-command pattern. Keep thresholds/device changes observable rather than silently dropping requests.
3. Use distinct feedback for **awake**, **still working** when needed, **verified success** and **failure/needs clarification**. Keep action success brief; do not imply success on receipt. Receipt feedback is optional if it would add noise, but can never be confused with completion.
4. Keep capture, transcription, execution and speech independent, with bounded queues and stale-result cancellation. A busy answer must not lose the next eligible command. Never execute a speculative partial command.
5. Handle laptop playback, external phone speech and simultaneous user+phone speech as different cases. Preserve the user's whole command when possible; if words/speaker/target remain uncertain, ask one short question or do nothing. Do not execute another device's spoken instructions as the user.
6. Check the chosen input/output device and muted/quiet state. Zero-look audible confirmation is unavailable when output is deliberately muted; make that mode clear, rather than pretending the user heard a chime.
7. Verify the effect before confirming: committed reminder/time, running timer, exact clipboard write, selected tab, changed window state, media playback, or a supported app outcome. When verification is unavailable, say so.

### Investigation before implementation choices

Instrument wake detected → captured speech bounds → final transcript → checked plan → action start → verified result → feedback start. For each reported miss, identify which boundary failed. Keep original and cleaned words separate; no fabricated timing origin that hides wake-decoding delay.

Evaluate whether current speech processing can acknowledge the wake word early enough without losing the rest. A dedicated wake detector, voice isolation, speaker enrolment or extra microphone is a proposal only, not a preselected fix. Any extra model needs consultation and memory/quality measurements. Speaker similarity is not secure authentication and cannot guarantee rejection of recordings or overlapping phone audio.

### Proposed acceptance targets — not measured results or guarantees

Agree the test set/targets when work begins. Start with at least100 natural commands per condition across multiple sessions, covering quiet, laptop playback, external phone playback, tired/casual delivery and overlap. Record full-command completion on the **first attempt**, not just wake hits. Count user repetitions as failures of the first attempt.

- Provisional target: at least98/100 first-attempt completions in quiet and95/100 with defined phone interference; aim higher. These finite gates do not turn the aspiration of perfect reliability into a universal promise.
- No observed unintended action or false success in the agreed negative cases. Include an hour of user-led ordinary room/media use; report exposure time even with zero false actions.
- Provisional feedback target: wake sound starts within150ms **after accepted detection**; separately measure from the end of the spoken name. Success sound starts within150ms after verified effect, when output is ready. Publish median/p95 and cold-start results; these feedback budgets are not a claim about full command latency.
- Compare V3 against V2 on the same recordings and command sets. Use held-out cases. Preserve or improve understanding accuracy and wrong-action rates; do not make it faster by guessing more.

Phase 2 must not become the default until this gate has real evidence. A feasibility failure is a finding to discuss, not permission to mark the phase complete.

## 6. Phase 2 — fluent conversation and optional arrival greeting

**Status: optional bounded follow-ups and idle-return/observed-unlock greeting are development-tested, including late transcription, stale queued greetings and mic-off suppression. Continuous addressedness, physical arrival and live acceptance remain open.**

### Explicit conversation states

Use a small, inspectable state machine rather than unrelated timeout flags:

| State | Eligible input / exit |
| --- | --- |
| Wake-only standby | Accept the wake word, not arbitrary room commands |
| Capturing request | Keep speech and corrections until a complete request or timeout |
| Checking/executing | Permit eligible interruption; do not execute a second copy of the same request |
| Speaking | Keep capture active; reject own output and unrelated playback |
| Waiting for a detail/confirmation | Bind the reply to this question, with a clear expiry; an unrelated request cancels/replaces context explicitly |
| Short follow-up window | Accept addressed follow-ups without the wake word; return to standby on expiry or dismissal |
| Optional hands-free session | User explicitly enabled name-free interaction; uncertain addressedness asks/abstains; visible status and quick exit |
| Paused/locked/error | No ordinary actions; expose recovery without silently falling into open listening |

Provisional follow-up duration:8seconds after speech ends, with capture already eligible while the reply is finishing. A consumed reply must not re-open itself later. “Nothing right now”, “that's all” or “stop listening” ends the session. Wake-word use remains available in every enabled listening mode.

### Arrival greeting

- Make this optional and off until explicitly enabled. Choose an available signal later; an unlock/return-to-input after inactivity may be a low-cost first option, accurately labelled as such.
- Do not equate idle-to-active with physical arrival. Phone presence/Bluetooth, camera recognition or new hardware needs a separate concrete proposal and consent. No camera or passive movement tracking by default.
- Greet once per genuine return episode, with a configurable cooldown. Suppress during quiet hours, locked screen, calls/presentations or an active conversation where reliably detectable. If call status is unavailable, offer a clear user-controlled do-not-disturb switch.
- After the greeting, immediately accept a reply without the name, including overlap. Silence/dismissal closes the window; no repeated nagging or action from a false arrival hint.

### Intent filtering

Separate “speech was recognised” from “the user addressed Jarvis”. Command-like wording alone is not enough. Combine explicit mode, current question, short-lived session context and available local evidence. Headphones are an option, not proof the user addressed the assistant. Talking to a person/self, a phone video saying commands and a recording saying “Jarvis” are negative tests.

Before enabling continuous name-free use, compare its false-action and first-attempt rates with wake-only mode. If it cannot distinguish them reliably within the current model/resource limits, retain a bounded optional mode and report that limit. Do not quietly weaken the wake-only safeguards to make it feel fluent.

Acceptance: first overlapping replies work once; no stale yes/no; dismissal and expiry work; arrival does not spam; unrelated speech produces no observed action in the agreed negative/long-use tests.

## 7. Phase 3 — low-friction corrections, context and undo

**Status: corrections, minimal feedback, request-scoped title/URL and opt-in clipboard context, local/window ledger are development-tested. Chained corrections and later metadata edits have guards. Live interruption and arbitrary external/mixed-workflow rollback remain open.**

### A. Interruptions and corrections

- An eligible interruption stops queued/current speech promptly, while listening continues. Measure speech-stop delay from the earliest reliable detection, not just from when the final transcript arrives. “Any millisecond” is a responsiveness goal, not a literal timing guarantee.
- “Set a timer for10minutes... actually no, make it15” produces **one15-minute timer**, with no earlier10-minute timer firing into existence first.
- Distinguish partial from committed requests. Use bounded end-of-turn/correction handling; do not add an unlimited wait to every command. Measure the tradeoff between a short correction grace and everyday delay before choosing its duration.
- Once an effect has committed, a later correction is a checked edit/reversal, not retroactive prevention. Interruption never blindly repeats or cancels an already completed side effect.
- Separate “stop talking”, “cancel this pending request” and “stop listening”. Define what “scratch that” means in each state; ambiguous cancellation must not close apps.

### B. Minimal feedback

- Simple successful utilities use a short chime/word or concise factual confirmation; full answers are for actual questions.
- Preserve essential details when needed, such as a corrected timer length, ambiguous reminder date, destination or partial failure. Do not hide uncertainty behind “Done”.
- Preferences control minimal/full/silent feedback and quiet hours. A future sound design uses clearly distinct cues; no sound is played during development tests. A user's silent mode deliberately gives up audible zero-look feedback.
- Long/failed tasks may announce a brief wait/failure, never a premature success. Keep the original checked result available in the app even when speech is short.

### C. “This/that” context

- On an explicit context-dependent request, capture a small permitted snapshot: foreground app/window, project identity and supported active page/title/URL or selected text. A title alone may not identify a task.
- Clipboard reading is separately opt-in and request-scoped. No background clipboard watcher, whole-screen recording, hidden-tab scraping or collection from protected login/banking/password windows.
- Bind “this” to one fresh source and record that source with the new note/reminder. If two targets fit, ask a short question. Never silently substitute clipboard content for the screen the user meant.
- “Remind me to finish this tomorrow” keeps a useful title/link or explicitly selected context, not an invented summary or copied secret. Clarify missing time when needed; show the saved reference.
- Read page/document content as data, never as instructions authorising actions. Let the user edit/remove saved context. Expire live references when focus/document/session changes.

### D. Short-term action ledger

- Record action ID, resolved target, before/after values, result, time, version, group and whether a safe reversal exists. Start with a short bounded local ledger; choose retention explicitly. Do not retain secrets or raw screen contents unnecessarily.
- “Scratch that” during capture cancels the pending request. After a reversible completed action it reverses the clear most recent eligible action/group; ambiguous grouping asks.
- Undo a created reminder/timer by its exact ID; restore a changed value only if its revision still matches. Do not delete a later edited record or a different user action.
- For multi-step workflows, stop pending steps and reverse only verified reversible completed steps in reverse order. Report what remains. Partial rollback is not complete rollback.
- Sent messages, deleted unsaved work and some external actions are not cleanly undoable. Say so; never claim otherwise. Reversal of a sensitive effect needs the appropriate fresh confirmation.
- Define a configurable undo window;5seconds is the user's example, not a hard expiry. Never resume or undo automatically after restart.

Acceptance includes self-correction before/after commit, interruption during long speech, a changed target before undo, partial rollback and irreversible actions. Confirm no duplicate reminder/timer and no accidental close/send.

## 8. Phase 4 — workspaces, media and visible choices

**Status: editable workspaces/folders/aliases, native visible choices/overlay, scoped player and rejection/pivot are built and development-tested. Exact folder and same-window recorded-tab reuse have injected tests; live browser-service compatibility and native reuse acceptance remain open.**

### A. Project workspace profiles

- Provide editable profiles with project name/aliases, exact folder, chosen apps, chosen URLs/browser and optional playlist. The Jarvis V2 project is one possible workspace, not a privileged action that launches V2's voice engine.
- “Continue working on Jarvis V2” selects that profile and runs the approved steps. If no unique profile exists, ask rather than guessing tools or paths.
- Reuse verified running apps/windows/tabs before opening duplicates. Preserve unrelated work. Avoid automatically closing other projects or enabling account permissions.
- Show intended steps on first run or after a material profile edit. Harmless launches may later use an explicitly saved fast-run preference; sensitive steps always retain fresh confirmation.
- Persist outcomes; stop on failure, explain partial completion and resume deliberately without reopening successful steps. Rollback only resources demonstrably created by this run and safe to reverse.

### B. Direct media playback

- Store the user's chosen default service and exact mix/playlist. Do not invent a preference or start arbitrary search results.
- “I want to listen to music” opens/reuses that destination and starts playback through supported controls. Verify an appropriate media session actually plays, not merely that a webpage opened.
- Handle browser autoplay refusal, loading, adverts, sign-in and unavailable content honestly. No bypass of browser/account protections. Test with fake playback; do not play audio on the user's PC during automated checks.

### C. Rejection and pivot

- Track the media session/window/playlist created or explicitly adopted for this task; do not treat every system sound as Jarvis's task.
- “I don't like this” targets that session only when unambiguous. If another task could be meant, ask what to change.
- Safely pause/replace the tracked playback or show relevant alternatives, then ask “Which one do you want instead?” Accept the first reply without the name, even during the question's end.
- Retain the choice snapshot through this exchange; refresh if the page changes. No endless reopen loop, guessed preference update or unrelated app closure. Persist a dislike/preference only if the user asked or approved learning it.

### D. Ordinal and partial-name selection

- Prefer Windows accessibility and, where specifically supported/approved, browser DOM data. A browser extension needs a separate scoped permissions choice. Do not modify the user's browser launch/debug settings silently or expose a remote-control port.
- Start with one small proven adapter for an agreed browser/site. Keep the selection interface general enough for other adapters; do not advertise universal DOM access to every app.
- Index **visible actionable items in the current viewport**, not every hidden/offscreen DOM node. Exclude navigation, unrelated ads and disabled/hidden elements as appropriate to the requested group.
- Group thumbnail/title/buttons for one card as one choice. Specify “mix playlists”, “videos” or another group when needed. Natural reading order is top-to-bottom, then left-to-right within a row for the current English UI; handle layout/scroll changes explicitly.
- Each snapshot has an ID, page/window identity, group, ordered item IDs, titles and bounds. “The2nd one” refers to this offered snapshot, not a fresh differently sorted list. Partial names must identify one item; duplicates ask.
- Before acting, recheck the same item/page/bounds and action eligibility. If the target disappeared, reordered, navigated or moved offscreen, refresh/reconfirm. Never silently use whatever now occupies the old coordinates.
- Unsupported/protected/inaccessible content gets a clear limitation or clarification. No automatic slow vision model or screenshot-based coordinate fallback in this scope.

### E. Target-lock overlay

- V3-owned, lightweight, click-through badges number the candidate group; a highlight and short title preview show the resolved target **before** its effect.
- The overlay must not steal focus, change the target's position, cover needed controls or become a candidate itself. Respect scaling, multi-monitor bounds, dark/light mode and reduced motion. Clear it on expiry/navigation/cancel/exit.
- For clearly requested low-risk navigation/playback, permit a configurable brief preview then verified automatic selection. Offer an explicit-confirm mode; set the delay from usability tests, not an invented guarantee that a voice cancellation can always arrive in time.
- Sensitive actions require explicit confirmation regardless of preview mode. Voice cancel before commit prevents the effect; after commit it invokes only a supported reversal. A preview is never authorisation for sends, purchases or deletion.
- Verify the resulting page/item/playback after selection and give the appropriate completion/failure cue. Never equate a highlighted box, click event or sent shortcut with success.

Acceptance uses disposable pages with duplicate titles, varying rows, adverts, scrolling, virtualised cards, navigation, focus denial and item reorder. Verify the intended item and forbidden side effects, not just that a click was sent. Manual user-led real-site acceptance comes later.

## 9. Build order after explicit permission

1. Re-read this document, current rules and real failure reports. Record remaining allowance and V2 baseline. No assumption that any V3 phase already passed.
2. Create V3-owned code/data/environment/launch identities and isolation checks first. Snapshot V2 files/settings/shortcut properties for a read-only before/after comparison. Do not launch the live V2 as a test fixture.
3. Establish the baseline and classify real misses. Agree the live test conditions, feedback preferences and provisional gates. Prototype the smallest measurable Phase 1 fixes in isolation.
4. Latest user instruction explicitly authorises building the next phases without waiting for manual tests. Broader automatic modes remain optional/off while Phase 1's live gate is open. Keep each mode separately switchable; normal wake mode remains usable. Do not require the owner to run manual tests while busy or invent live acceptance from automated checks.
5. Build/test Phase 2, then Phase 3, then Phase 4 with its dependencies. Do not substitute a new UI or extra feature count for the reliability gate.
6. Create V3's own preview icon/shortcut only once a launchable isolated build exists. Do not replace the V2 icon. Keep a visible status per phase: planned, built in isolation, development-tested, live-tested, accepted.
7. Run full understanding and old-feature regressions, held-out voice replays, owned-window/browser tests and resource/long-use checks. Compare error rates as well as speed. Leave live trial time/conditions and failures in the report.
8. the owner tries V3 while V2 remains available. V3 becomes the daily version only after the owner explicitly chooses it; never infer that choice from installation or a passing test.

## 10. Decisions to settle later — not questions blocking this document

- Wake/success/failure cue sound and output device; minimal versus spoken confirmation details.
- Practical live conditions and acceptable miss/false-action/latency gates; session/undo timeouts.
- Arrival signal available without new tracking/hardware, whether to enable it, and cooldown.
- Whether continuous name-free mode is wanted outside brief sessions; optional speaker enrolment and its privacy/model cost.
- Exact project profiles, folders/apps/URLs and default media mix/playlist.
- Which browser/site gets the first visible-item adapter; whether a narrowly scoped extension is acceptable if accessibility is insufficient.
- Request-scoped clipboard access and what screen context may be saved.
- Which V2 facts/routines/settings, if any, to copy into V3; handling imported active reminders.
- The separate preview now uses its own animated living-spark character/icon. V2's icon stays unchanged.

Existing authorisation to keep the same models and protect V2 persists. Only genuinely missing choices or new permissions need questions; do not make the owner repeat settled requirements.

## 11. Planning record

- 5 November 2026, planning: audited the four Gemini blocks and corrected the last block to Phase4. This initial planning stage changed documentation only.
- 5 November 2026, implementation: user explicitly authorised the two V2 fixes then V3. Private source/data/runtime/icon, wake-only probes, verified completion feedback, cleanup and isolated tests built. No advanced phase is accepted merely because it is in this plan.
- 5 November 2026, separate experiment: user approved evaluating the83MB CPU voice-check candidate. Models already used by V2/V3 remain unchanged. Test profile stays in memory, not automatically enrolled in either app. See V3_STATUS.md for evidence, limitations and next work.
- 5 November 2026, next phases: the owner explicitly authorised fixing speaking speed/blanket completion messages and continuing the next phases without manual tests. Optional conversation/arrival, partial correction/context/ledger/minimal feedback and workspaces now implemented/tested; selection core only, native adapter/overlay/media workflows unfinished. Full status and usability recommendation in V3_STATUS.md; preserve V2.
