# How we got to V4: the key decisions, and why

## Product rules from day one
- **Offline only.** Nothing leaves the laptop. Privacy, and it works without internet. An online "brain" switch was parked; it would need the owner's own key stored in Windows Credential Manager.
- **Rules first, AI second.** Common commands run through plain rules with no AI at all (instant, predictable). The AI is only for messy speech.
- **Allowlist plus confirm.** Jarvis can only do things on a list. Risky things (delete, send, change settings) need a "yes".
- **Never lie about doing something.** A reply must match what really happened. This one rule caused many later fixes.
- **Always "sir".** It never uses the owner's name.
- **Resource budget.** Small models, little graphics memory (the laptop runs hot), no models pushed out to RAM, models unloaded when idle.

## V1 decisions
- **Order: reminders, actions, interface, voice, AI.** The interface moved up so the owner could judge it early.
- **Tk, then a web window.** Tk was light, but the owner wanted a real app look; a WebView2 window with a separate see-through pill gave that.
- **Reuse an existing speech tool's model, read-only.** Saved a download and kept the other tool untouched.
- **Whisper large-v3-turbo for hearing.** Best accuracy on the owner's recordings among the options tried.
- **Kokoro for the voice.** A calm British male voice, open source, no actor cloning.

## Why V2 was a rebuild
The owner said V1 felt hard-coded and heard badly. We did not guess: we **recorded 40+ real commands in three situations and measured**. Whole-sentence transcription beat V1's listening. So: rewrite the ears and the decision layer, keep the solid parts (timers, reminders, tests, window, pill).

Other V2 decisions:
- **Hands-free first.** Hold-a-key was optional and never asked of the owner.
- **A registry of abilities.** The AI picks a named ability with arguments, checked against a list, instead of rewriting into sentences for regex rules.
- **Two models.** A 1.5B model decides actions fast; a 4B model answers questions. Tested a 4B for actions too: slower for the same score, so the 1.5B stayed.
- **Cancel the PC's own sound.** So music and videos stop being heard as commands.
- **Learn, but never rewrite itself.** It learns names, habits, routines and facts. It does not invent new abilities or edit its own code. Wishes go to a list for the owner.
- **Gold sentences as a gate.** 265 labelled sentences give a number for understanding, so changes can be judged, not argued about.

## Why V3 was separate
V2 was the owner's daily tool. Rebuilding the voice pipeline in place could break it. So V3 got its own folder, data and shortcut, with V2 file hashes checked after every change. If V3 failed, V2 still worked.

V3 decisions:
- **Read state back before saying "done".** Timers, reminders, tabs, windows and volume are checked after the action.
- **Opt-in for anything intrusive.** Voice-only mode, hands-free minutes, camera arrival, clipboard context: all off by default.
- **Try, measure, drop.** The speech-separation model and hand gestures were built and tested; neither earned a place. Hand gestures were removed at the owner's request.
- **Native Windows tab and window control** instead of key presses, because keys closed the wrong thing.

## Why V4 sees the screen
The owner wanted to say "click that" and have it happen. Decisions:
- **Use the accessibility tree, not screenshots.** Fast (tens of milliseconds), private, no model needed. A picture model for unnamed icons is parked until a download is approved.
- **Standard-library matching** instead of extra fuzzy-matching libraries. Less to install, fewer surprises.
- **Press with Windows' own invoke before a real mouse click.** Safer and faster.
- **Ask when unsure.** Two close matches get numbered badges and "which one?".
- **Check before every remembered click.** Site memory stores where a control was; if the spot no longer matches, it abandons the shortcut and rescans.
- **Draft, confirm, send.** A message is typed (not pasted, so the clipboard is untouched), read back, and held until "send".
- **Browser controls and window buttons are never targets.** A live test showed "press close" had hit the browser's own Close.
- **Fewer words in replies.** Successful actions now just say "Done, sir."

## Working rules that helped
- Test without sound and without touching real apps; use fake PCs and owned throwaway windows.
- Close every test process before ending a turn.
- Report real numbers (milliseconds, memory, temperature), and say plainly what is unproven.
- Write a checkpoint when the AI allowance runs low, so work can continue elsewhere.
