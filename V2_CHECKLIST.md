# Jarvis V2 checklist

**Permission from the owner: if it's needed, rebuild Jarvis completely from scratch.** Keep whatever is solid and tested (the timers, reminders, tests, the window and the pill are examples), and replace whatever is in the way. the owner cares about how it feels and works, not about keeping V1's code. If you rebuild, say so plainly and keep the offline-first rules in CLAUDE.md.

**the owner's clarified goal (2026-11-02):** not GPT-level, and no coding help. It must understand what he means from loose, mis-heard speech and turn it into the right everyday action (search, open, close, timers, reminders, YouTube, notes), and ideally learn his habits and wording over time like an agent that tracks what he does and how. Offline first. The agreed plan for HOW is in `V2_REBUILD_PLAN.md`: read it first. This checklist is what must be true at the end.

Everything the owner asked for after testing V1 on 2026-11-01. "Likely cause" is a lead from the code, not proven: confirm it before fixing. Tick items only after testing them for real.
**Phase 2 (2026-11-03):** the core for items 44-45, 51-52, 57-58 and timers is built and passes with a fake PC (plan section 11). None is ticked: ticking needs a real test (Phase 5).
Status page for the owner: https://claude.ai/artifact/FeJYVu11ZCuK8y1XQLoUbb (update it as items finish).

## 0. Hearing and understanding the owner (do this first)
the owner: Wisperno Pro recognises what he says easily, and Jarvis is "very, very shit at it", even with simple wording. He asked whether a full rebuild is needed. My view, not proven: Jarvis uses the SAME speech model as Wisperno Pro (large-v3-turbo, int8_float16), so the engine isn't the difference. What differs is how audio reaches it, and what happens to the text afterwards:
- Wisperno is push-to-talk: it knows exactly when he starts and stops, and sends the whole sentence. Jarvis listens all the time and must guess where a sentence starts and ends, then transcribes pieces, sometimes very short ones (Whisper is worse on short clips), after silence trimming and a name hint.
- Far-field laptop mic, the speakers' own sound, music, and a mic level that was 51% for a long time.
- Wisperno has a personal vocabulary and a cleanup step. Jarvis has neither, and its name matching is crude.
- There are two layers: hearing (speech to text) and understanding (text to action). The understanding layer is a small 3B model. Both are weak today.
- Wispr Flow, as far as I know, processes speech online with a far bigger model; offline Jarvis won't match that, so set realistic goals.
- [x] (2026-11-03, numbers in plan section 13.1: whole clip clearly better, listening front end gets rewritten) FIRST, measure before rebuilding: record the owner saying 40+ real commands in his usual conditions (quiet, music on speakers, earphones). Run the same recordings through (a) a Wisperno-style whole-clip transcription and (b) Jarvis's current listening pipeline. Count misses and what causes them. If (a) is clearly better, rewrite the listening front-end (voice.py: _loop, _sentence, _capture and the patches piled on them). If both fail alike, the limit is the mic, room or accent, and a rewrite won't help. Report x/20 per condition.
- [ ] Hands-free "Jarvis" is the main way to talk to it and must work well first. Optional, later, only once that is solid: hold-a-key (push-to-talk) with a default key changeable in Settings. the owner did not ask for it; don't ask him for a key.
- [ ] Rework the understanding layer along with item 1 below: it must cope with mishearings and loose wording, ask when unsure, and keep names and numbers right.
- [x] (decided 2026-11-03, plan section 13) Keep what's solid: the actions allowlist, timers and reminders, the window and pill, and the tests. Rewriting the listening front-end and the decision layer is likely enough; a full rewrite of everything probably isn't. Decide from the measurements above, and say why.

## 1. Make it feel alive and smart (the main goal)
the owner: "it feels like hard-coded dumb-ass shit, not even AI, just a system." The goal is not real sentience, but it should FEEL aware and intelligent, and never pretend or lie about what it did.
- [ ] Let the AI choose actions instead of only rewriting into fixed sentences for regex rules. For example structured tool calls (name + arguments, checked against the allowlist). Today a request with no matching rule fails however well the AI understood it.
- [ ] Conversation that chains: follow-ups, "do that again", "undo that", "what did you just do", answering its own questions. Today it only keeps the last 2 exchanges. the owner: "quite bad at chain answering".
- [ ] Memory across sessions: what the owner tells it, preferences, habits, recent conversation summary. All local.
- [ ] Simple questions fail: "what is the time", "what is the date", "what day is it" and the like. Unproven lead: no rule answers them, and the AI is never told the date or time (App._situation only lists timers and reminders), so it can only guess. Give it the real clock, and answer these exactly from the system clock rather than from the model. Also cover time left until something, "what's tomorrow's date", and similar basics (simple sums, unit conversions).
- [ ] Awareness: date, time of day, what's running, what app or page is in front, what is on its lists. It should answer "how many reminders do I have" with "two", not read a list.
- [ ] Personality: a consistent calm British butler voice with dry wit. Varied wake replies and acknowledgements. Always "sir", never the owner's name. Reacts to frustration sensibly. No fixed lines unless accuracy needs them; every remaining fixed sentence in core.py / actions.py is a candidate.
- [ ] Knows its own abilities, and says honestly what it can't do and what it can do instead.
- [ ] Clarifies when unsure rather than doing the wrong thing. Vague complaints ("you still haven't done what I asked") must get a sensible answer: today they get a confused one.
- [ ] Better facts: it said (a+b)^2 = a^2 + b^2. Consider a stronger model.
- [x] (2026-11-03, plan section 13.1) Measure other local models within budget (Qwen2.5-1.5B is in Wisperno's folder; try 3-4B options, 4-bit). Report quality, speed and memory before switching. Tell the owner before any large download.
- [ ] Acceptance: write 30+ realistic multi-turn conversations as a test, with the real AI, through the whole app, checking actions AND reply quality. Existing scenario in tests/test_brain.py is short and partly unchecked.

## 2. Hearing
- [ ] (replay: 29/30 with cancelling; not live yet) Can't hear him while music or a video is playing, so it can't pause or skip. Likely cause: speaker sound in the mic drowns the name; voice._speech needs speech well above the noise floor, and Whisper garbles it. Ideas: subtract what Windows is playing (WASAPI loopback), or duck the volume when speech starts. Test with real music.
  the owner's finding: with earphones on it hears him and "next" works; through the laptop's own speakers and mic it fails. That fits the speaker sound being the problem. Fix the speaker case, and keep earphones working.
- [ ] Sometimes misses words when he speaks fast. Save clips and check: likely voice._loop's early end-of-sentence, or VAD trimming.
- [ ] Check the listening fix on his real voice: logs/wake_clips now keeps real clips. Name was heard 7/7 with the hint, but not rerun on the final code.
- [ ] Rerun tests/test_voice_realmic.py, test_voice.py, test_backtoback.py. Back-to-back was 21/24 (commands 0.3 s apart merge).

## 3. Music and YouTube
- [ ] (built Phase 2: previous/next through the media session; real player untested by me) (Windows media session did next and previous in a mix, confirmed by the owner; not built yet) "Previous" doesn't work reliably; "next" does. YouTube has no previous-video key outside playlists: use browser back or the media key.
- [ ] (built: play and pause are separate commands and the state is read back; real player untested) Play and pause don't work reliably. Likely causes: "pause" and "play" share one toggle key (actions._media), so it can do the opposite of what was asked; "pause the video" goes a different route (video_key). Make it check whether something is actually playing.
- [ ] (media session = one session per browser; tabs can't be told apart (stage 1); YouTube page keys use the first YouTube tab) Several YouTube tabs open: it can't tell which one play, pause, next and previous should act on. Real.video_key takes the first YouTube tab it finds. It should pick the tab that's playing sound, else the last one used, and ask if it really can't tell.
- [ ] Works in one session, fails after a restart: "next" and "previous" for YouTube worked, then after closing and reopening Jarvis it got confused and didn't know what to do. The empty chat on a fresh start is fine with the owner; commands must not depend on earlier conversation. Reproduce it with a fresh start: the AI's random wording and `recent` context, or the model's unsteady answers, are the first suspects. Test each command right after a restart.
- [ ] Wrong reply: sometimes it does go to the previous one but says "next". Find out which: the AI's wording (good_reply in brain.py doesn't check next against previous) or the command it chose. What it says must match what it did.
- [ ] Control the video while another app is in front, WITHOUT bringing the tab forward. Today actions.Real.video_key brings it forward. Try Windows media keys for pause/next/previous; for skip, restore the old front window afterwards or find a way that needs no focus.
- [ ] "Skip ahead" must work when the tab is in front.
- [x] (Phase 5, tests/v2/live_volume.py on the real PC: 30 / full / max / set 70 / zero / 50 after zero / up / down / mute twice / unmute / undo, all restored) System volume gets confused: "volume full" just turns it up, and "volume 100" doesn't set 100. Test every kind: full / max / half / zero / mute, "volume 30", "set volume to 70", "volume 100", up, down, "up by 20", "a bit louder". Check the real Windows level afterwards, and that what Jarvis says matches what it did. Unproven lead: actions._volume already handles a typed "volume full" and "volume 100", so suspect the AI rewriting it to "volume up", or the speech recogniser writing it differently. Reproduce through the whole app with the real AI first.
- [x] (Phase 5, live: Edge's own audio set to 40 and quieter while the system stayed at 50; an app with no sound says so) Volume of one app: "change the volume of YouTube" changes the whole system's volume (actions._volume only presses the system keys). It should change that app or video only, and plain "volume up" stays system-wide. Ideas: YouTube's own up/down keys for its player, Windows' per-app volume for other apps.
- [ ] "Play the current mix on screen": it opened YouTube Music and searched for those words. "Play" must prefer the YouTube page that's open. Read the links on the page through Windows accessibility (first_video already does this) and play the one named.
- [ ] Don't let the AI turn unclear "play ..." into a YouTube Music search.

## 4. Apps and focus
- [x] (Phase 5, conversations: open WhatsApp + close Discord + a timer in one sentence) Different actions in one sentence: "open WhatsApp and close Edge" gets confused and says it doesn't know what to do with "close Edge". Likely cause: actions.act and direct split on "and" and put the first verb on every part ("open close edge"). Each part must keep its own verb. Check other mixes too, such as "close Chrome and set a timer for 5 minutes".
- [ ] (built Phase 2; real apps untested by me) New command: "focus Edge", "focus WhatsApp", "switch to Chrome" bring any running app forward, without restarting it. Today this fails even when the app is already open, because no focus command exists (Real.focus is only used right after opening something). Must work for browsers, Store apps and ordinary apps; if the app isn't running, say so or offer to open it.
- [ ] Wrong window comes forward: opening an installed app works, but Chrome is brought to the front instead of the app, though nothing was opened in Chrome. Unproven lead: after opening, actions._front_app calls Real.focus with the app's name, and that matches ANY visible window whose title contains the name, including a Chrome or Edge window with a tab of that name (a "Claude" tab, for example), then brings the first match forward. Match by program, not title; never match browsers unless a browser was asked for; and bring forward the new window, not an old one. Test with Chrome open on tabs that share the name.
- [ ] "Open Obsidian" sometimes fails with "I can't do this". Check the log for how the speech model wrote it (add Obsidian's mishearings; it's already in voice.PROMPT, but the name check in _heard doesn't use that prompt), and whether the AI refused it.
- [ ] Opening Calculator doesn't bring it forward. Likely cause: Real.focus only tested on Edge; Store apps use a different window type (ApplicationFrameWindow). Test Calculator, Notepad, WhatsApp, Claude.

## 5. Tabs
- [x] (Phase 5, fake PC with the real AI: count=2 reaches the opener; real browsers untested) "Open two YouTube tabs" opens only one.
- [ ] (built Phase 5 (first/second/third/last by tab title); fake PC only, real browser untested) "Close the second YouTube tab" closes all of them. Support first / second / last.
- [ ] (decided in code: 'close YouTube' closes the one in front if it is YouTube, else the next one; 'close all YouTube tabs' closes all. Real browser untested) "Close YouTube" closes everything: decide with the owner. Suggested: the one in front, and "all YouTube tabs" for all. Check it isn't closing other sites too.

## 6. Bookmarks, sites and files
- [x] (Phase 5: 'open prome' opens Chrome, 'open jamin' opens Gemini (conversations, fake PC)) Same with Chrome: the owner says it is heard as "prome" and not understood. Checked with a fake PC on 2026-11-02: the rules accept "chrom" and "jemini" but refuse "prome", "crow", "krome" (Chrome) and "jamin" (Gemini). That matches the first-letter lead below: a mishearing is only forgiven if it starts with the right letter. Also found: "gem and i" was split at "and" into two commands (Gemini opened, then "i" refused), so splitting on "and" can break a misheard name. Needs real sound-alike matching against his actual apps, sites and bookmarks, not hand-written patterns.
- [x] (Phase 5: sound matching, one clear match acts, two close ones ask) A misheard name is refused: the owner said "Gemini", it was written as "jamin", and Jarvis replied "'jamin' isn't on my list". the owner says Wisperno Pro handles this and Jarvis doesn't, and he expected Jarvis to be a layer on top of Wisperno. In fact Jarvis only borrows Wisperno's speech and AI model files (read-only, a decision in CLAUDE.md) and none of Wisperno's own app features. Two unproven leads: (1) the fuzzy name matching in actions.act requires the same first letter, and "jamin" starts with J, not G; use sound-alike matching instead, and ask "did you mean Gemini?" when unsure. (2) Wisperno seems to keep a personal vocabulary (src/database.py mentions one used to bias recognition): check whether Jarvis can read it, read-only, and feed it into its own recogniser and name matching. Test with the words the owner actually says: Gemini, Hostinger, Wisperno, Obsidian, Armoury Crate, LinkedIn.
- [ ] (built: bookmarks of Edge and Chrome are in the catalog (15 found); opening one untested live) "Open Gmail", "open Hostinger", "open the dashboard" fail. Read Edge and Chrome bookmarks (local JSON in User Data\Default\Bookmarks) as another allowlist, plus well-known sites such as Gmail. Fuzzy-match names carefully.
- [ ] (built Phase 5: Desktop, Documents, Downloads (top level), safe types only, never deleted or run; real opening untested) Open files by name from Desktop, Documents and Downloads. Opening only; nothing that deletes or runs scripts.

## 7. Notes
- [x] (Phase 5, tests/v2/test_abilities.py and a conversation: 'jane dot doe at the rate acme dot com' is stored as jane.doe@acme.com) Spoken emails: "jane dot doe at the rate example dot edu" must be stored as a real address (at the rate = @, dot = .). Don't hard-code one address.
- [ ] (built: note_recall by the AI; conversation tested with another note) "Remind me my college email" should recall the note. Today it starts a reminder.
- [ ] (built: note_forget; 'gmail' vs 'email' wording still doesn't match a note saved as 'email') "Forget my college Gmail" should delete the note. Today it's refused.
- [x] (Phase 7: Knowledge tab lists and deletes your notes (tested through the real window); a notes-only tab is not separate) Show notes in the window, with delete.

## 8. Reminders
- [x] (Phase 5: the old reminder is renamed in place, undo restores it) Changing a reminder makes a copy. "Change the reminder for tomorrow, my maths test: instead it's a science test" left both. It must find and replace it (the AI sees the list; core has rename). Today store.add merging plus the AI's choice of "remind me" causes this.
- [ ] Keep his wording: "I have a mathematics test" became "Do my maths test". Brain.SYSTEM and examples push "do ...".

## 9. Alerts
- [x] (Phase 7: spoken and shown on the pill (alert with Stop/Snooze); the window stays where it is; the alert is raised and handed to the pill in the real-window test, how the pill draws it was not inspected) (Phase 5: they are SPOKEN (voice app, checked every 3 s; logic tested); the pill alert comes with the V2 window (Phase 7)) When a timer or reminder ends, open the PILL, not the whole window (App._fire calls open_main). Stop and Snooze on the pill. Window only if he asks.

## 10. Speed, memory, heat (budgets in CLAUDE.md)
- [ ] Faster replies: an AI-worded reply starts about 0.8 s after the action. Idea: speak a short instant acknowledgement, or synthesise while writing.
- [x] (Phase 7, real launch: idle RAM 1.62 GB (2.1 GB with the window), graphics 3.2 GB, CPU 4%, GPU 62 C; 1000-sentence soak flat: +8 MB RAM, +26 MiB graphics) RAM about 3.9 GB against a 2-3 GB target; graphics memory about 3.9 GB of a 4 GB limit. Any model change must stay inside it. Load on demand was the original plan.
- [ ] Closing takes about 3 s; the window was still visible 0.3 s after X. Cause not found.

## 11. Learns about the owner (stretch goal, after the rest works; see plan section 4.7)
- [x] (Phase 6: tests/v2/test_memory.py and two conversations with the real AI: 'no, I meant Chrome' teaches the word at once, takes the wrong action back, and the word works next time without the AI) Remembers a correction after one time ("no, I meant Chrome") and applies it from then on.
- [x] (Phase 6: every successful open/close counts per name and hour; the matcher adds it only among names that fit about equally well) Ranks ambiguous names by how he uses them.
- [x] (Phase 6: notes (facts) and routines tested: 'save that as study mode' keeps the last sentence's steps, the name runs them, each step goes through the risk check again) Remembers facts and preferences he tells it, and the routines he teaches it.
- [x] (Phase 6: three days at the same hour -> one spoken question; yes does it, no is remembered forever; never twice a day, never while learning is paused) Offers, never forces: notices habits and asks "shall I...?".
- [x] (Phase 7: built as the Knowledge tab of the V2 window, tested through the real window: words, usage, habits, routines, notes, delete one line, pause learning, forget everything with a confirmation) (Phase 6: by voice it works (what do you know about me / forget the word X / forget everything you learned, which asks first / pause learning); the page itself is mocked up at https://claude.ai/artifact/7Gq1KjUSvduqrCsAjTHm5Y and gets built into the window in Phase 7) A page "What Jarvis knows about me": read, edit, delete one item or everything, pause learning.
- [x] (decided 2026-11-03: stays off, not being built) Passive tracking of PC activity. Never keystrokes, screen contents or passwords.

## Ways of working (the owner insists)
- the owner keeps finding more problems of the same kind (volume, tabs, focus, play and pause). For every command family, test many phrasings through the whole app, including spoken-style ones, before calling it done. Don't stop at the exact sentence he reported. Fix the cause, not the one phrase.
- Plain short language. the owner tests and reports; Claude runs everything, gives no commands to run.
- Never leave test copies running, and close only processes verified as ours. Real-PC tests must not capture the screen beyond Jarvis's own window, or open or close the owner's real apps.
- Test the owner's exact sentences through the whole app with the real AI, and make the checks strict. V1 repeatedly "passed" tests while the app failed: the reply prompt silently overflowed, and errors were swallowed. Don't swallow errors silently; log them.
- Say plainly what's verified and what isn't. Don't call something done from a test alone when the owner's complaint is about real use.
- Visual changes: mock up first as an artifact.
- Report temperature and memory at each milestone.
