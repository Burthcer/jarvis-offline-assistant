"""Fast checks with no GPU: who is being spoken to, and which app is meant. py -3.12 tests\\test_names.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis import actions as A, voice as V

bad = []
for t in ["open YouTube", "Also open YouTube", "So open whisper flow and whisper no pro both", "Okay open chrome", "Now close Discord", "Please open YouTube", "I will open YouTube",
          "You should open Chrome", "my friend will open netflix", "Let's open YouTube", "Thank you", "God fucking chance, shut down"]:
    if V.rescue(t) is not None:
        bad.append(f"took {t!r} without the name -> {V.rescue(t)!r}")
for t, want in [("Harness, open YouTube.", "open YouTube"), ("Hey Jarvish, volume up", "volume up"), ("Harvest, set a timer for 5 minutes", "set a timer for 5 minutes")]:
    if V.rescue(t) != want:
        bad.append(f"lost {t!r} -> {V.rescue(t)!r}")
for t, want in [("open whisper flow", "open wispr flow"), ("Open Whisper, flow.", "open wispr flow"), ("Open wisper flo", "open wispr flow"), ("open Whisper Flow, Whisper Flow", "open wispr flow, wispr flow"),
                ("Close, Wisperno Pro", "close wisperno pro"), ("open armory crate", "open armoury crate"), ("open downloads", "open downloads"), ("go to my desktop", "go to my desktop"),
                ("close file explorer", "close file explorer"), ("open powershell", None), ("open command prompt", None), ("open registry editor", None), ("open whisper flow and whisper no pro both", "open wispr flow and whisper no pro")]:
    if A.direct(t) != want:
        bad.append(f"direct {t!r} -> {A.direct(t)!r}, wanted {want!r}")
for t, want in [("Close Claude and Whisper Flow", ["claude", "wispr flow"]), ("open up whisper no pro", ["wisperno pro"]), ("open youtube music", ["youtube music"])]:
    if A.mentioned(t) != want:
        bad.append(f"mentioned {t!r} -> {A.mentioned(t)}, wanted {want}")
from jarvis.brain import good_reply, misheard_close
for parts, want in [(["Closing Edge, sir.", "Closing File Explorer, sir.", "Closing WhatsApp, sir."], "Closing Edge, File Explorer and WhatsApp, sir."),
                    (["Timer set: 1 minute timer, sir.", "Timer set: 3 minute timer, sir."], "Timers set: 1 minute and 3 minute, sir."),
                    (["Opening Notepad, sir.", "Volume up, sir."], "Opening Notepad, sir. Volume up, sir.")]:
    if A.merge_replies(parts) != want:
        bad.append(f"merge {parts} -> {A.merge_replies(parts)}")
for t in ["search cats", "Search for the best laptops on Edge", "google news", "search lo-fi on youtube"]:
    if not A.direct(t):
        bad.append(f"a search must skip the AI: {t!r}")
for t in ["Lewis Chrome", "Clues File Explorer", "Clothes Discord", "Jarvis, closed Chrome"]:
    if not misheard_close(t):
        bad.append(f"should be close: {t!r}")
for t in ["open chrome", "Open up YouTube", "launch notepad", "I want to watch something", "can you open chrome", "play some music", "netflix please", "calculator"]:
    if misheard_close(t):
        bad.append(f"should NOT be close: {t!r}")
for line, fact, want in [("Both timers are set, sir: 1 minute and 3 minutes.", "Timer set: 1 minute timer, sir. Timer set: 3 minute timer, sir.", True),
                         ("Consider it done, sir. YouTube is opening in Edge.", "Opening YouTube in Edge, sir.", True),
                         ("Opening Netflix, sir.", "Opening YouTube in Edge, sir.", False),  # a different name
                         ("Timer set for 5 minutes, sir.", "Timer set: 7 minute timer, sir.", False),  # a different number
                         ("Chrome is open, sir.", "Closing Chrome, sir.", False),  # the opposite
                         ("I'm sorry, I can't do that, sir.", "Closing Chrome, sir.", False),
                         ("Closing Chrome.", "Closing Chrome, sir.", False),  # always sir
                         ("All done. What next, sir?", "Closing Chrome, sir.", False),
                         ("Noted, sir: call mom tomorrow at 5:00 pm.", "Noted, sir: 'Call mom' tomorrow 5:00 pm.", True),
                         ("Both timers are gone, sir.", "Both timers cancelled, sir.", True),
                         ("All three timers are off, sir.", "All 3 timers cancelled, sir.", True),
                         ("Edge, File Explorer and WhatsApp are closing, sir.", "Closing Edge, File Explorer and WhatsApp, sir.", True)]:
    if good_reply(line, fact) != want:
        bad.append(f"good_reply({line!r}, {fact!r}) should be {want}")
from jarvis.island import is_fullscreen
scr = (2560, 1600)
for cls, style, rect, want, what in [("Progman", 0x80000000, (0, 0, 2560, 1600), False, "the desktop"), ("WorkerW", 0, (0, 0, 2560, 1600), False, "the desktop (other kind)"),
                                     ("Chrome_WidgetWin_1", 0x16CF0000, (-12, -12, 2572, 1612), False, "a maximised window"), ("Chrome_WidgetWin_1", 0x96000000, (0, 0, 2560, 1600), True, "a full-screen video"),
                                     ("Notepad", 0x14CF0000, (100, 100, 900, 900), False, "a normal window")]:
    if is_fullscreen(cls, style, rect, scr) != want:
        bad.append(f"full-screen check wrong for {what}")
r = A.Real().running()
if "python.exe" not in [x.lower() for x in r]:
    bad.append(f"running() looks wrong: {r[:5]}")
print("NAMES:", "PASS" if not bad else "FAIL")
print("\n".join(bad))
sys.exit(1 if bad else 0)
