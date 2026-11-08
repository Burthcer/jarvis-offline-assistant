# Testing checklists

## M1 Reminders + memory (text only)
Run: double-click `Start Jarvis (text).bat` in the project folder. Type each line, press Enter.
1. `remind me to call mom in 1 minute` -> "Noted, sir..." and ~1 min later "[REMINDER] Sir, reminder: Call mom."
2. `remind me maths exam on 23 november` -> Noted, Mon 23 Nov 9:00 am.
3. `remind me about my exam on 25 november` -> "Updated" (NOT a second entry). Then `list` shows ONE exam, on 25 Nov.
4. `remind me to buy milk tomorrow at 5pm` -> Noted tomorrow 5:00 pm.
5. `what do we got to do today` -> lists today's items only.
6. `what did I miss yesterday` -> lists overdue items, or "Nothing missed".
7. `remember that my locker code is 4821` then `what do you remember about locker` -> shows it.
8. `delete buy milk` -> asks to confirm; `no` cancels; repeat and `yes` deletes.
9. `done exam` -> marked done, gone from `list`.
10. Close and reopen; `list` still shows saved items (stored on disk).
Report: pass/fail per number, any sentence it got wrong (copy it), speed feels instant? (Measured 0.03 ms per command.)

Automatic self-check (Claude runs it): `py -3.12 tests\test_store.py`

## Automatic stress tests (Claude runs these; ~1 minute total)
- `py -3.12 tests\test_store.py` quick check
- `py -3.12 tests\stress.py` ~75,600 checks: time parsing vs an independent oracle, edge dates, phrasing tables, 40,000 random-sentence fuzz, 30,000 random-date fuzz, concurrency, persistence, speed
- `py -3.12 tests\stress_spoken.py` 74 checks of speech-to-text style wording ("5 p.m.", "five thirty", "half past 4", "can you remind me")
Last result (2026-10-31): 75,628/75,628 + 74/74 pass.

## M2 + M3 manual checklist (PC actions and the pill)
Start: double-click `Start Jarvis.bat`. A dark pill appears at the bottom-centre of the screen and a green dot appears in the tray (the ^ arrow by the clock).
Type in the pill and press Enter. Expected results:
1. `open youtube` -> YouTube opens in Edge. `open linkedin` -> opens in Chrome. `open luma`, `open dev.to` -> Chrome.
2. `search lo-fi on youtube` -> YouTube results for lo-fi in Edge. `search weather in pune` -> Google in Edge.
3. `play lo-fi beats` -> YouTube Music search in Edge.
4. `volume up`, `volume down`, `set volume to 30`, `mute`, `unmute` -> the Windows volume follows.
5. `pause`, `next song` -> your music reacts (needs something playing).
6. `set a timer for 1 minute` -> after a minute the pill pops up "Sir, your 1-minute timer is up."
7. `remind me to stretch in 2 minutes` -> pill pops up the reminder by itself.
8. `make edge my default browser` -> the Windows Default apps page opens and Jarvis tells you what to click.
9. `open cmd` or `open evil.com` -> refused ("isn't on my list").
10. Click the gear -> settings window (browsers per site, start with Windows, wake replies, disabled voice/online placeholders). Click the cross -> pill hides; click the tray icon -> it comes back. Tray right-click -> Settings / Quit.
11. Drag the pill with the mouse -> it moves.
Report: anything that failed, and what the pill looked like (blurry text, wrong position, too big/small).

Automatic: `py -3.12 tests\stress_actions.py` (20,152 checks, fake backend), `py -3.12 tests\test_ui.py` (30 checks; pass a folder as argument to save screenshots).

## How YOU test it (main window)
1. Double-click `Start Jarvis.bat`. Two things appear: the big **Jarvis window** (conversation log on the left, "Reminders" and "Timers" on the right, a typing box at the bottom) and the small **pill** at the bottom of the screen.
2. Type each line from the M2 + M3 checklist above into the big window's box and press Enter (or click Send).
3. For every line, look at: (a) what Jarvis answered in the log, (b) whether the real thing happened (site opened, volume moved), (c) the right-hand lists.
4. Red text means Jarvis didn't understand or something broke. Amber text is a reminder/timer going off by itself.
5. When done, click **Copy log**, then paste (Ctrl+V) into the chat with Claude, plus a line on anything that looked wrong. A copy is also saved in `logs\conversation.log`.

## M4 VOICE: how YOU test it
1. Double-click `Start Jarvis.bat`. Wait about 10 seconds. In the big window the bottom line turns green: "Microphone listening for 'Hey Jarvis'." and the log says "Voice ready (GPU)".
2. Say **"Hey Jarvis"** in a normal voice, about an arm's length from the laptop. You should: see the dot/bar swell as you speak, hear "At your service, sir" / "Yes, sir" / "I'm listening, sir", and see the dot turn blue ("listening").
3. **Wait for the reply to finish**, then say your command, e.g. "set a timer for one minute", "open YouTube", "remind me to call mom tomorrow at five pm", "what do we have today", "volume up". The log shows `You (voice): ...` then Jarvis's answer, and Jarvis speaks the answer.
4. Say "speak slower", "speak faster", "increase your volume", "decrease your volume": Jarvis's own voice changes (this is NOT the PC volume).
5. Click **Mic: on** in the big window (or tray > Mute microphone): it turns OFF, "Hey Jarvis" is ignored. Click again to turn it on.
6. Plug in earphones while it runs, say "Hey Jarvis" again. Tell me if it still hears you (this part I could not test).
If it doesn't respond: look at the log. "almost heard (score 0.3)" = you were too quiet/far; nothing at all = tell me and press **Copy log**, paste it to me.
Things to report: how many tries before "Hey Jarvis" worked, any wrong words it heard, whether the voice sounds okay, and whether the laptop got hot or loud (fans).

Automatic: `py -3.12 tests\test_voice.py` (real models, generated speech through a fake mic, ~5 min), `py -3.12 tests\test_voice_live.py` (laptop speaks to itself through real speakers+mic, ~1 min, makes sound).

## Voice, round 2 (after the Opus fixes): how YOU test it
0. **Raise your microphone level once:** Settings > System > Sound > (scroll to Input) click **Microphone Array** > drag **Input volume** to **100**. It was at 51%.
1. Make sure only ONE Jarvis runs: if a Jarvis window is open, click the tray icon (^ by the clock) > right-click the green dot > **Quit**. Then double-click **Start Jarvis**.
2. Wait for the green line "Microphone listening for 'Hey Jarvis'." (about 10 s; the new voice loads too).
3. Try all three ways, a normal voice, arm's length:
   a. "Hey Jarvis" ... wait for the reply ... "open YouTube"
   b. "Hey Jarvis, set a timer for one minute" in one go (Jarvis should NOT say "Yes sir" in the middle)
   c. "Hey Jarvis" and start your command straight away while it is still answering ("what do we have today")
4. "Hey Jarvis, remind me to call mom" -> it asks when -> just say "tomorrow at five" (no "Hey Jarvis" needed).
5. Listen to the new voice. To try others: gear > Voice > pick George / Fable / Lewis / Daniel > Save. Samples are in the `voice_samples` folder.
6. Press **Copy log** and paste it to Claude, plus: how many tries "Hey Jarvis" took, anything it misheard, which voice you like.
