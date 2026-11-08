# the owner's tests for Jarvis V2 (do these at the end; each takes a minute)

## Latest quick check — 5 November

The silent desktop checks passed. These still need your real voice/devices; the Google connection also needs the one-time setup in GOOGLE_SETUP.md.

- [ ] Say “Jarvis”, then give one command while/after it says yes; try five times. Also answer a question once before its speech finishes. Report the exact words and whether the first attempt worked.
- [ ] Add university/PIN code/personal Gmail plus an alternate name in Knowledge. “Copy my university”, then paste somewhere safe yourself. Exact named facts should stay separate; aliases/search/edit should work.
- [ ] Using tabs you can discard: “focus the first tab”, then “close the second and fifth tabs.” Those original positions must close. Minimize/maximize/restore must preserve everything. Report any Windows foreground refusal rather than repeating blindly.
- [ ] Teach a short routine; edit it in Knowledge. If a step fails, only “resume routine NAME” retries the failed/remainder steps, without repeating successful steps.
- [ ] Plans: an assignment deadline, “remind me daily at 9 am to study”, and Daily briefing. Settings: quiet hours, backups, performance and optional recording controls.
- [ ] Google is optional and currently unconnected: follow GOOGLE_SETUP.md, sign in yourself, then try unread Gmail/calendar. No email sending or calendar changes are enabled.
- [ ] Headset changes, talking video and an hour of ordinary use remain live checks. The full understanding score is224/265, so do not assume every wording is solved.

Start: close V1 if it is running (tray icon, right-click, Quit). Double-click **Start Jarvis V2.bat**. The window says "Starting up", then Jarvis says "Ready, sir" (about 10 seconds).
Stop: click the X on the window, or say "Jarvis, shut down". Tell Claude what felt wrong, in your own words. Say the exact sentence and what Jarvis did.

## 1. Hearing (the most important)
- [ ] New first-batch controls: “minimize Edge”, “maximize Chrome”, “restore Edge”, “minimize all tabs”. These must never close any tab/app. “Open YouTube and minimize Edge and maximize Chrome” must retain all three actions.
- [ ] “Close second, third and fourth tabs” / “close fifth and second tabs”: positions refer to the ORIGINAL order. New adapter requires accessible unique tab identities; report any refusal and exact wording. Actual browser support still unverified.
- [ ] “Open YouTube”, then “close it”; after mentioning two apps, “close it” must ask which. An unanswered confirmation must expire after two minutes.
- [ ] Settings > Show last request: inspect heard text, attempted steps, result and timings after a failure.
Say each one 5 times, in your normal voice, from your normal seat.
- [ ] Quiet room: "Jarvis, open YouTube", "Jarvis, set a timer for 2 minutes", "Jarvis, what time is it"
- [ ] Music playing from the laptop speakers: "Jarvis, pause", "Jarvis, next", "Jarvis, volume down"
- [ ] Earphones plugged in (plug them in while Jarvis is running): the same sentences
- [ ] Unplug the earphones while it runs: does it keep listening on the laptop mic within about 10 seconds?
- [ ] Say only "Jarvis" and wait: it should answer "Yes, sir" (or another reply) and take your next sentence without the name
- [ ] Talk to someone else, or watch a video with people talking, for a few minutes: Jarvis should NOT react
- [ ] Mark any sentence it missed or got wrong

## 2. Doing things (real apps: these open and close your real windows)
- [ ] "Jarvis, open Notepad", "Jarvis, close Notepad", "Jarvis, focus Edge", "Jarvis, switch to Chrome"
- [ ] "Jarvis, open WhatsApp and close Edge" (two things in one sentence)
- [ ] "Jarvis, open two YouTube tabs", then "Jarvis, close the second YouTube tab", "Jarvis, close all YouTube tabs"
- [ ] With a YouTube video playing and another app in front: "Jarvis, pause", "play", "next", "previous"
- [ ] "Jarvis, search for lo-fi music on YouTube", "Jarvis, play the first video", "Jarvis, go fullscreen"
- [ ] "Jarvis, open Gmail" (a bookmark), and a file name from your Desktop or Downloads
- [ ] "Jarvis, take a screenshot" (it saves to Pictures/Screenshots)
- [ ] "Jarvis, volume 30", "volume up", "mute", "unmute"; "Jarvis, make Edge quieter" (only Edge)

## 3. Timers, reminders, notes
- [ ] "Jarvis, set a timer for 10 seconds": when it ends Jarvis speaks and the pill (top of the screen) shows it
- [ ] "Jarvis, remind me tomorrow at 5 pm to submit my lab record", then "what's on tomorrow", then "change that reminder to the doctor", then "cancel it"
- [ ] "Jarvis, remember my wifi password is purple tiger", then "what is my wifi password", then "forget my wifi password"
- [ ] "Jarvis, remember my work email is jane dot doe at the rate acme dot com" then ask for it

## 4. It learns
- [ ] Say a name wrongly on purpose ("Jarvis, open Prome"): it should open Chrome or ask. If it is wrong say "no, I meant Chrome"; next time it should just work
- [ ] "Jarvis, what do you know about me" (it reads out what it learned)
- [ ] Open the **Knowledge** tab in the window: delete one line, pause learning, switch it back on
- [ ] "Jarvis, open Notepad and set a timer for 5 minutes", then "save that as study mode", then "study mode"
- [ ] After a few days of opening the same app at the same time, it should ASK "Shall I open ...?" (it never does it by itself). Say no once: it must never ask again

## 5. Window, pill, settings, closing
- [ ] Home, Timers, Knowledge, Settings tabs all open; Settings changes stick after a restart
- [ ] "Jarvis, shut down" and the X both close everything: check Task Manager, nothing called Jarvis or Python from the project is left
- [ ] Minimise keeps it listening
- [ ] Leave it running for an hour: is the laptop hot or are the fans loud? How much memory does Task Manager show for Jarvis?

## 5b. Added after your first real use (say "Jarvis, ..." each time)
- [ ] With music playing from the laptop speakers: "Jarvis, next song", "Jarvis, pause", "Jarvis, volume down", 5 times each. Then look in `logs\jarvis2.log` for lines starting "canceller:": they say how many dB of the music it removed
- [ ] "Jarvis", wait for "Yes, sir", then say the command (no name): it must act. Do it 5 times
- [ ] "Jarvis, search Royal Rendering on Patreon", "Jarvis, search funny cats on Reddit"
- [ ] Ask it things: "Jarvis, what is the capital of Australia", "Jarvis, explain what a VPN is", "Jarvis, should I study in the morning or at night" (the first one takes about 2 s while the bigger brain loads)
- [ ] "Jarvis, do remember that my exam starts on 23 November" then "Jarvis, what do you remember about my exam"
- [ ] Open any page and say "Jarvis, read the screen" / "Jarvis, what does this page say about the price"
- [ ] With Claude open: "Jarvis, ask Claude to summarise my notes": it must type it and ask "Shall I send it?" before sending
- [ ] Is it faster now? Time "Jarvis, open YouTube" from the end of your sentence to the window appearing

## 5c. Skills, wishes, reading answers (added 2026-11-04 late)
- [ ] "Jarvis, when I say focus mode open notepad and set a timer for 10 seconds". Nothing should open yet. Then "Jarvis, focus mode": both must happen
- [ ] "Jarvis, learn a skill called morning that opens YouTube and then opens Gmail", then "morning"
- [ ] Try to teach it something unsafe: "when I say bad idea shut down" or "... ask Claude hello": it must refuse in plain words
- [ ] Open the Knowledge tab: your skills show their sentences
- [ ] "Jarvis, I wish you could order me a pizza", then "what is on your wish list"; check the file `dataequests.md`
- [ ] With Claude open: "Jarvis, ask Claude what is two plus two", say yes to "Shall I send it?": it should send, wait, and read the answer. If it says it cannot read anything, Claude's window does not share its text (a known risk): tell Claude
- [ ] Later: "Jarvis, what did Claude say"

## 6. Then decide
- [ ] Home now has a **Dark mode / Light mode** button beside the tabs. Switch both ways, restart: the choice must stay. Both modes have the website's moving dither and mouse trail; only neighbours within a local button row react. Hover Microphone: Send/Add in other cards must stay still. Hover theme: the navigation row must stay still. Motion pauses when minimised.
- [ ] Home or Knowledge > **Add fact**: heading "personal Gmail", value your email. Save. It must stay separate from college email. Edit can change both the heading and value. Close/reopen: both stay saved.
- [ ] When Jarvis asks you to repeat or clarify, answer once while its question is still finishing. The first answer should work without saying the name again. The silent replay now accepts this; live room sound still needs confirmation.
- [ ] "Jarvis, play the next song", "Jarvis, next song twice", "Jarvis, skip two songs", "Jarvis, previous twice". With an active listening window you may omit Jarvis. Multi-skip sends the requested number of player commands; actual player response remains a live check.
- [ ] Home and Knowledge saved facts have **Edit / Copy / Remove**. Edit the college email directly, save, then Copy. Paste it yourself somewhere safe: only the email value should be copied. Settings > Edit saved facts opens Knowledge.
- [ ] "Jarvis, edit my college email, it is ... at the rate ..." then "Jarvis, copy that to the clipboard". No AI refusal, no extra reminder. Your existing email is saved local data, not a default hard-coded into the UI.
- [ ] Say just "Jarvis": the pill and Home should show **Listening**, with moving bars and an eight-second window after the wake reply. Give a command without repeating the name. Repeat five times, including talking over the end of the reply.
- [ ] A reminder already due at startup must wait for the voice to become ready and then be spoken, rather than being marked fired silently.
- [ ] "Jarvis, close Edge": visible browser windows close without waiting for its background workers to exit. An app showing an unsaved-document prompt must remain open; Jarvis must not force it away.
- [ ] New desktop icon: a blue J with a lime spark. Open it: the cream window has a **Plans** tab.
- [ ] "Jarvis, I want to attend Techfest on 20 November". It should ask when registration closes and set a reminder to check. Answer "12 November at 5 pm". Plans should show the event and registration reminder. These are example dates: remove the test event afterwards.
- [ ] "Jarvis, my events", then "Jarvis, cancel event 1" (use the number it read out).
- [ ] "Jarvis, I have maths exams on 23 November". It should set exam/preparation reminders, without asking about registration.
- [ ] With the real event page in front: "Jarvis, check deadline for Techfest on this page". It should use a clearly labelled registration date, or say it cannot find one. It must not invent a date or browse other pages by itself.
- [ ] "Jarvis, plan open Notepad and set a timer for 10 minutes". It previews the steps; answer yes. Plans shows progress and completion. "Jarvis, stop plan" stops before the next step. Plans are limited to five checked steps; sensitive actions need a separate yes.
- [ ] Close and reopen Jarvis. Saved events/plans stay; unfinished plans never run just because it restarted. "Jarvis, run plan 1" resumes only when you ask.
- [ ] Real voice timing: "Jarvis, could you open YouTube?" and "Jarvis, close WhatsApp" five times each. Recorded replay was about 0.67 seconds to command delivery; this is NOT a live microphone result.
- [ ] Is V2 clearly better than V1? If yes, tell Claude "switch": it points the desktop icon at V2. V1 stays in the folder as the fallback.
