# Bugs and glitches, per version

Format: what went wrong, then the fix. "Unproven" means fixed in tests but not confirmed in live use.

## V1

**Typing and parsing (M1)**
- Crash on times like "at 99:99" or huge numbers: now refused politely.
- Emoji crashed the Windows console: output made safe.
- Two threads hit the database at once: added a lock and a busy timeout.
- "at 06:05" was read as 6 pm; "today" could pick a time in the past; "p.m." with dots, spoken numbers ("five thirty"), "can you remind me", "what's on Friday": all fixed.
- A confirmation question swallowed the next command: fixed.
- Seven more fixes from messy sentences ("the 1st of", "2 hours and 30 minutes", "mark X as done").
- Limits kept: English only, no repeating reminders at first, same-word reminders merge by design.

**Actions (M2)**
- Play, pause and stop share one key; mute state is a guess; volume 0 makes Windows mute; "play X" only opens search results.

**Voice (M4)**
- Wake word missed often (real scores 0.27 to 0.45): added a second check with Whisper.
- Commands lost after "Yes, sir": Jarvis now records through its own reply and strips it.
- Jarvis heard itself: echo filter on every command.
- **Old copy still running:** the owner was testing old code while a stale Jarvis also reacted to test audio, so many "flaky" results were not real. Rule since then: always check for stale copies first.
- Noise floor only went down, so raising the mic level to 100% broke detection: now learned both ways.
- Weak loopback from speaker to mic made live tests mostly measure the loopback: added a realistic recorded-room-noise test.
- GPU speech-to-text was slow when idle (0.5 s vs 0.2 s): the GPU is warmed when speech starts.
- Spoken replies took 0.65 s to make: cached, with common ones made at startup.
- the owner's accent spellings of the name ("Charles", "Travis", "Darviss") accepted.

**Understanding and apps**
- AI swapped one app for another: names it cannot know no longer go to it; guesses limited to built-in names.
- Replies were still fixed because the prompt overflowed the context size, with the error silently caught: context raised; the error is no longer swallowed.
- A word like "both" was rejected by the reply checker: fixed.
- Close slow (8 s): now asks Windows directly (about 10 ms).
- Closing a window left things open; closing Jarvis's window only hid it: now quits fully.
- "Open YouTube" tab closing walked through tabs with keys, which was risky: replaced later.
- A name hint made Whisper sometimes omit a clear "Jarvis": it listens again without the hint.
- Pill vanished: the desktop counted as a full-screen app.
- Wake clips got deleted by a filename bug.
- A foreign 7.7 GB Python process was killed by mistake once: new rule to stop only verified-own processes.

## V2

**First real use (4 Nov)**
- "Jarvis" then the command did not register (he talked over the "Yes, sir"): follow-up now accepted if it starts after the name's sentence.
- A video's speech became a command ("peace out"): the no-name window now opens only after the name alone or after a question.
- "Open yt" opened Narrator: a never-open list added (Narrator, Magnifier, Voice Access and others); "yt" means YouTube.

**"V2 felt worse than V1"**
- PC-sound cancelling clock ran behind the mic, a 30 s rule, no second listen, no logging: all fixed.
- Slow repeats: instant commands now answer in 0 to 30 ms; the voice is cached on disk.
- Startup alert could fire before the speaker existed: queued until ready.
- Theme startup showed a file-not-found page: a `?theme=` suffix broke the file URL. Fixed with `#theme=`. Earlier tests passed falsely because they built their own URL; tests now launch the real function.
- Update of an email created a second note instead of replacing it: facts now match by field name.
- Copy-to-clipboard was claimed but unproven: now read back under the same lock.
- A fact with an arbitrary heading fell through to AI chat, which could falsely say it was copied: generic routes added; the chat is blocked from claiming it.
- The AI repeated the request instead of acting (weather search): a guard rejects echoes, retries once, then asks honestly.
- "Close WhatsApp" rejected as starting before the question ended: windows now open before the question is spoken.
- "Minimize" closed things: a separate window-state ability; a guard stops the model swapping in close.
- "Close the second, third and fourth tabs" failed: positions are resolved against the original tab order, closed from the highest, each verified.
- Wi-Fi and Bluetooth requests opened generic Settings; "what is my volume" became a note lookup: fixed with a fixed page allowlist and a read-only volume ability.

## V3

- A speed request ("speak faster") got a blanket "unverified" warning, and "increase your speed" fell into a false chat refusal: direct patterns, read-back, honest limits.
- Vertical tabs in Edge could not be found: deeper bounded scan; exact per-tab close.
- Two shutdown phrases ignored, and shutdown was slow: an urgent exit that cancels capture, inference and actions.
- Two named commands in a row: the second was dropped: fixed with independent names and event keys.
- A stale copy hid behind a reused process ID: processes are compared by ID plus creation time.
- "Open YouTube" ignored because hands-free minutes were 0: default is now 3 minutes with follow-ups on.
- Uncancelled video audio kept the detector on, so sentences ended only at a 12 s cap: ears now end a sentence when the mic falls back to the background level; loopback follows the default speaker.
- A stale music tab hijacked next and pause: they now go to the focused tab.
- Our own "Which one?" was heard as an answer: echo stripped.
- Header wrapped badly on narrow windows; settings were unclear: compact layout and regrouped settings.
- Quiet speech: tests showed the name survived down to 5% volume, so misses were not loudness; whispered clips were requested.
- Hand gestures: built and tested but never proven live; removed at the owner's request.
- Some live items were unproven at release: noisy rooms, real accents, live Google clicks.

## V4

From the owner's first live test:
- "Click history/playlists" gave "2 matches" because YouTube lists each entry twice: same-name controls in one place are merged.
- "Click on Shorts" not found: Edge only describes a page fully after the first request (23 items, then 170): extra looks added.
- A misheard "click shots" clicked text in the AI chat's own tab: only visible controls are read; the browser tab strip is ignored.
- A click that did nothing was reported as done: web links are verified by the address bar.

From the second live test:
- **"Press close" clicked the browser's own Close:** browser controls and window buttons are never targets.
- "Click the third video in this playlist" failed: playlist entries are numbered, and refused if it does not look like a list.
- Page scrolling and collapsing playlists or pop-ups: new scroll and collapse abilities; a named list is scrolled by wheel with the pointer put back.
- Replies read long video titles aloud: now "Done, sir."

Smoothness:
- Floating pill looked laggy though drawing took 1 to 3 ms: the pacing was wrong (6-degree steps, 10 fps at rest). Now a steady 60 fps active, 30 fps at rest, measured at 33.3 ms gaps.

Known open items: live Google click unverified; picture model for unnamed icons parked; one test (`test_selection`) was stale at the V3 release and was updated.
