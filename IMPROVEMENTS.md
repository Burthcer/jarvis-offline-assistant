# Approved improvements — 4 November 2026

## Authorisation and timing
The user has now said **“begin with all the improvements”** after the reset. The entire recorded list is authorised and work has started. This supersedes the older waiting notes below; do not ask for the same approval again. Connections still require concrete account/permission choices and sending remains separately controlled.

Keep the current models and quality. Model changes still require consultation. Tests must remain silent and use fake apps/data or owned disposable windows. Check the five-hour allowance at milestones; at about 5% remaining, save a checkpoint, close owned processes, and stop until the user explicitly resumes. Do not use resets or credits automatically.

## Work order
1. **Verify actions before reporting success.** Verify clipboard content, selected browser tab, and closed windows where possible. Report unverifiable or failed actions honestly. Prioritise the user's reported false successes.
2. **Improve voice conversations.** Speaking over Jarvis, short pauses, corrections, follow-ups, and accurate listening/processing/waiting status. Keep room speech and Jarvis's own voice from triggering actions. Establish live evidence; recordings alone are insufficient.
3. **Measure and reduce delays.** Separate hearing, understanding, action and speech timings. Common commands act first, speech follows. Use measurements to identify delays; preserve accuracy and resource limits.
4. **Improve knowledge generally.** Arbitrary headings, alternate names, search, editing and conflicting facts. Connect related labels only with sufficient evidence. Saved websites should act as usable links. Preserve user data and secret handling.
5. **Improve browser control.** Select tabs by position/title/site; navigate; reuse an existing page instead of creating duplicates. Verify selection and handle duplicate titles, multiple windows and missing positions.
6. **Improve app control.** Different display/program/package names, background/tray windows, and truthful handling of unsaved-document prompts. Verify app-specific fixes without operating user apps in tests.
7. **Useful editable routines.** Study mode and other user-taught routines, inspection, editing and natural teaching. Retain allowlisted actions and sensitive-step confirmations.
8. **Student organiser.** Assignments, exam preparation, event registration, recurring reminders and optional daily briefing. Ask about missing dates, never invent them. Clarify notification preferences when needed.
9. **Deeper connections.** Calendar, email, documents, coding tools and other apps with clear access and sending controls. This approval covers development, not blanket access to accounts, sending messages, spending, or new model downloads. Decide concrete connections with the user when needed; retain offline defaults.
10. **Visible learning.** Show what Jarvis learned and why; allow correcting and forgetting it. Explain limitations of learned routines versus new program abilities.

## First round after resume
Start with 1–4, then browser/app control. Read CLAUDE.md, V2_REBUILD_PLAN.md section 11 and the latest checkpoint before work. Investigate real failures before changes. Keep improvements scoped and reviewable rather than attempting all ten at once.

The earlier request-repetition fix is already committed in `1e12f9e`; generic fact actions/tab focus/package lookup are in `1359db9`. Their live behaviour remains unverified. Do not present these as fully proven or redo completed work without a reason.

## Status — 5 November 2026
Offline implementation covers all ten areas below. Account activation and human acceptance remain open; this is not a claim of perfect understanding, unrestricted autonomy or complete live validation.

| Area | Implemented | Remaining acceptance / limit |
| --- | --- | --- |
| Verified actions | Clipboard exact readback; actual tab/window-state readback; truthful partial/foreground failures | Real paste and user-app checks remain user-led; tests never use user clipboard/apps |
| Voice | Wake/question follow-ups armed before replies, overlap/echo handling, single-use listening window, moving pill/countdown, bounded speech/STT queues and overload notice | Live room/music/headset/device/hour-long trials unproved |
| Speed | One instant pass/running scan, exact-name shortcut after corrections, mtime shortcut cache, deduplicated background app refresh; phase/cold-warm/median/p95/RAM panel | Complex AI and blocked Windows calls still take time |
| Knowledge | Original stable IDs; label/value editing, derived type/source/update, explicit aliases/search/conflicts; generic copy/recall/open including URL queries/fragments | Types are derived; old free-form notes remain intact; exact heading wins before synonyms; ambiguous targets ask |
| Browser | All/this/site/position/title routes use native identities; original-position cumulative closure, deduplication, effect checks/reorder abort; existing unique/current page reuse | One intended window must be identifiable; extended real reuse/site-all/current checks blocked by Windows foreground policy; pure adapters pass |
| Apps | Process/package identity, fast polite visible-window close, unsaved prompt refusal; distinct minimize/maximize/restore; startup/manual background catalog refresh | Quick Share close remains unverified on real app; protected apps can refuse |
| Routines | Teach/create/edit/run/resume UI; prevalidate all calls/arguments; persistent cursor, stop on failure, deliberate resume without repeating successful steps | Safe allowlisted steps only; crash/in-flight state never blindly replays; legacy native steps can be replaced with plain commands |
| Organiser | Assignment deadlines, exam/event registration tracking, page deadline evidence, daily/weekly repeats, separate snoozed occurrence, optional daily briefing | Missing/conflicting dates ask; no hidden website monitoring or invented deadlines |
| Connections | Read-only Gmail subjects/senders + primary Calendar7days, OAuth+PKCE/state/loopback, secure credentials; chosen local document excerpts; existing confirmed app send/readback | Google Desktop client registration and user sign-in required: GOOGLE_SETUP.md. Mock/local callback only; no actual account accessed |
| Visible learning | Inspect/correct/delete words and reasons, pronunciation form, usage/habits/pause/forget, editable routines/fact cards; backup/confirmed restore/safety copy | Learns words/usage/routines, never edits source or creates unchecked abilities |

Quiet hours cover startup speech; command clips are optional and off by default. Cooler idle mode keeps the same models but can delay the next complex request. Backups contain facts/reminders/routines/learning, not preferences/accounts/models/recordings. Local documents are bounded excerpts, not a hidden file index.

### Evidence
- Silent core32/abilities47/memory35/skills29/ears27/organiser33/daily/feedback/clipboard shim/refinement/fact_actions/dialogue/window_actions/lifecycle and new expanded-features/voice-load/Google tests passed.
- Actual desktop runtime + production UI ALL OK: dark startup/both animated themes, isolated hover, fact headings/aliases, teaching, backup create/cancel/confirmed restore, performance, recurring snooze. Fake data/OS/no sound. Own screenshots: data/completed-improvements-ui.
- Earlier actual isolated Edge duplicate titles/third-tab focus/original5+2closure/missing-ninth refusal passed. Final extended test safely refused before keys on foreground denial; reuse/site-all/current real acceptance remains open.
- Full265 with same grader:224/265 vs committed eb68b0c221/265; clear209/246 vs206/246; held-out104/132 vs102/132; false5/wrong14 unchanged;0crashes; AI median325/p95815ms vs344/842ms, instant113 vs108. Full run predates final targeted fact-heading/argument fixes. Original understanding gate still unmet; do not claim all failures solved.
- Saved audio once/case: question overlap649–665ms, wake then name-free command650–868ms delivery. Not live human acoustics.
- Actual unchanged models/UI/silent fake mic: action2973MiB, answer3979MiB graphics; RAM2.14GB incl window, GPU55–59C. Sustained AI grading reached80C despite cooling intervals. No downloads/model changes.

## Additional recommendations (subsequently approved with “all improvements”)

Earlier six: personal pronunciation dictionary; undo and safe recovery; heard/understood/attempted/verified troubleshooting view; backup/restore; quiet hours; resource controls.

### Deeper speed, understanding and usability proposals
1. **A shared command interpreter.** Typed and spoken input should produce the same checked action plan; only speech cleanup differs. Preserve original words alongside cleaned words. Build regression cases from actual failures, including expected action and forbidden side effects.
2. **Explicit conversation state.** Track current target, unresolved question, pending confirmation and last completed action separately, with expiry. Bind yes/no to one specific question. Resolve “it”, “that” and “the other one” only when one target fits; otherwise ask a short targeted question. Never treat repetition as completion.
3. **Graduated understanding.** Exact known requests use a fast path; uncertain wording uses the existing language model. Separate uncertainty about hearing, intent and target. Ask about only the missing part, rather than requesting the whole sentence again. Preserve original app names, dates and numbers through conversion.
4. **Event-driven app/browser adapters.** Use structured window and tab identities where available instead of title matching and repeated key cycling. Track only the minimum state needed for explicit actions, invalidate it on changes, and recheck before acting. Any browser extension/permissions need a concrete proposal and user choice. No passive browsing-history collection.
5. **Remove slow discovery from the critical path.** Reuse a fresh app catalog, resolved shortcut targets and stable model prompt prefix. Refresh asynchronously or on changes. Give caches expiry/invalidation rules; do not reuse stale foreground windows, tabs or confirmations. Measure cold/warm latency separately.
6. **Independent command execution and feedback.** Keep microphone capture, interpretation, action execution and speech output separate, with bounded queues. Cancel obsolete transcription and queued speech; never cancel an action already committed without checking its result. Avoid speculative open/close/send actions on unfinished speech.
7. **End-to-end latency budgets.** Measure speech end -> transcript -> plan -> action -> verified result -> spoken feedback, with median and slow-tail figures. Instrument time spent waiting on models, Windows, audio and locks. Optimise the measured bottleneck and rerun accuracy checks; do not hide delays with premature success replies.
8. **Structured knowledge with evidence.** Store a stable fact ID, editable label, value, type, aliases, source and update time. Distinguish postal codes, secret PINs, URLs, emails and ordinary text. Resolve conflicts explicitly, show which fact an action used, and copy/open the selected value by ID. Provide a reversible migration of current notes.
9. **Transactional multi-step routines.** Preview actions where appropriate, check each outcome, stop on failure, and describe partial completion. Undo only reversible completed steps; never automatically resend a message on retry. Persist enough state for deliberate resume after restart.
10. **A real-use acceptance gate.** Small repeatable checks from the user's ordinary seat/device: wake+follow-up, interrupted questions, rapid commands, noisy playback and device changes. Track first-attempt success, wrong actions and slow responses separately. Silent replay remains the development check; user-led live trials establish actual reliability. Recording/retention should be optional and visible.

Suggested first architecture work: conversation state + typed/spoken parity + action verification, followed by measured scheduling/cache improvements. Then structured knowledge and browser adapters. Keep current models until measurements show a concrete need and the user approves a change.

## Latest usage instruction
The subsequent “begin with all the improvements” and “finishh all imprvementss” instructions resumed implementation. Check the five-hour allowance; stop at about5% remaining with a checkpoint and owned-process cleanup. The earlier “no dont stop” applied to the recommendations discussion. Latest check28% remaining; no resets/credits used. Work is not stopping for the allowance.

## Eight priorities from the latest discussion
Explicitly recorded at the user's request and subsequently approved. These elaborate the proposals above.

1. **Conversation memory:** current target, unanswered question and pending confirmation are separate states. Resolve “open it” only with one clear referent; bind “yes” to a specific pending question.
2. **Distinguish hearing from understanding failures:** identify whether words were unclear, intent was unclear, or the named target could not be found. Ask only for the missing detail.
3. **Move slow discovery off each command:** reuse installed-app catalogs and resolved shortcuts with appropriate refresh rules. Recheck the current target immediately before acting.
4. **Independent listening, execution and speech:** long replies cannot block new commands; interruption drops obsolete queued speech. Never execute speculative destructive/sending actions from unfinished speech.
5. **Reliable window/tab identities:** avoid relying solely on changeable or duplicate titles. Select the intended target and verify it where supported.
6. **Structured knowledge:** stable fact identity, editable label/value/type and aliases; distinguish postal codes from security PINs. Copy the resolved fact value directly.
7. **Measure slow everyday responses:** separate hearing, decision, execution and feedback times. Track slow-tail performance and first-attempt accuracy, not just average speed.
8. **Safe partial-failure recovery:** show completed/failed steps and resume deliberately without repeating completed actions or resending messages.

Implementation and remaining acceptance are recorded above; do not repeat old approval questions.

## Reported failure: cumulative tab closures
User reports that closing several specified tabs in one command fails: “close the second, third and fourth tabs” and “close the second and fifth tabs.” Implemented against original order with stable identities and per-target verification; acceptance detail above.

- Parse the complete list of requested positions, including nonconsecutive positions and spoken numbers. Support fourth/fifth and other positions within an explicitly defined supported range.
- Interpret positions against the tab order BEFORE the command. Resolve targets first, then close by stable tab identity where available; if using positions, close from highest to lowest so earlier closures do not shift later targets.
- Keep all closures in the intended browser window. Handle duplicate titles, missing positions, and a window disappearing when its last tab closes.
- Verify each closure and report actual completed/failed targets. Never report the whole request successful after doing only one part. Do not silently replace unavailable targets with other tabs.
- Test consecutive/nonconsecutive positions, changed tab order, duplicate positions, invalid positions, and partial failure with fake browsers or owned test windows. Live user-browser behaviour remains unverified.
- Treat this as a concrete example of general cumulative actions: retain every requested target/action in the checked plan rather than dropping all but one.

## Reported failure: minimize mistaken for close
User reports that “minimize the app” and “minimize all tabs” can close apps/windows instead. Distinct verified minimize/maximize/restore and forbidden-close checks implemented; disposable real-window checks passed.

- Minimize, maximize, restore, hide and close are distinct actions. Never substitute close/quit/terminate for a window-state request, including after model interpretation, retry or fallback.
- Support the current window, a named app/browser window, and multiple/all requested windows where supported. Resolve ambiguous targets with a short question.
- For “minimize all tabs,” interpret this as minimizing the containing browser window(s), preserving all tabs and running apps. If several browsers/windows make the scope unclear, ask which scope the user intends; never close tabs.
- Maximize enlarges the target window; restore returns it from minimized/maximized state. Keep full-screen browser/video mode distinct from maximizing a window.
- Verify the resulting window state and report failures honestly. Preserve unsaved work, open tabs and background processes.
- Regression checks must explicitly assert that minimize/maximize/restore requests invoke no close, tab-delete, quit or process-termination action. Test singular/plural targets and mixed requests such as “minimize Edge and maximize my notes” using fake apps or owned disposable windows.
