"""The 'smart' layer (M5): a local AI model (Llama 3.2 3B, from Wisperno's folder, READ-ONLY) rewrites whatever the user said,
however messy or misheard, into ONE clean command the tested rules engine understands, or a short chat reply.
It never runs anything itself: actions still only happen through handle() and its allowlist. Offline, on the GPU (~0.2 s)."""
import difflib
import os
import random
import re
import threading
import time

W = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Wisperno\_internal")  # Wisperno's GPU engine files, read-only
MODELS = [r"C:\Users\USER\Desktop\Wisperno-pro\models\Llama-3.2-3B-Instruct-Q4_K_M.gguf",
          os.path.expandvars(r"%LOCALAPPDATA%\Programs\Wisperno\models\Llama-3.2-3B-Instruct-Q4_K_M.gguf")]

SYSTEM = """You are the command interpreter of Jarvis, an offline voice assistant running on the user's Windows laptop, able to do everything listed below (never call yourself a text-based AI, never comment on the user's language). The user sometimes mixes in Hindi: band karo = close, kholo / open karna = open, chalao = play. The user's words come from \
speech recognition, so they can be messy, rambling or slightly misheard. Work out what the user MEANS, not just the words they used, and rewrite it as ONE line in one of these forms (two requests in one sentence: one line each, at most three), \
keeping the user's meaning and their exact time words. Fix obvious mishearings: you tube -> youtube, loom/lumo -> luma, linked in -> linkedin, crow/chrom/crome -> chrome, note to her/note here/note 10 -> notepad, next salt/next so/next son -> next song, calculater -> calculator.

remind me to <task> <time>        task is the plain action ("do my maths homework", never "to do..." or "I have to..."); time like "tomorrow at 5pm", "in 10 minutes", "on friday at 3pm", "on 23 november"
remind me to <task>               if no time was given ("remind me" always means a reminder, never "remember")
alarms and "wake me up at <time>" are reminders too: remind me to wake up <time>
set a timer for <duration>
how much time is left on my timer
cancel the timer | pause the timer | resume the timer      with one timer
cancel the <length> timer | pause the <length> timer | resume the <length> timer      one of several, named by its length ("the 3 minute timer")
cancel all timers | pause all timers | resume all timers
cancel my reminders for <day>     every reminder on that day ("today", "tomorrow", "friday")
open <site or app> [in chrome|in edge]   sites: youtube, youtube music, gemini, netflix, amazon, claude console, google, linkedin, dev.to, luma. Apps: any installed app by the name the user said (claude, chatgpt, task manager, armoury crate, wispr flow, wisperno pro, file explorer, notepad, calculator, settings, paint...). Keep the app the user named; never swap it for a similar one.
open <downloads|desktop|documents|pictures|music|videos|screenshots|this pc>   folders in File Explorer ("go to my downloads", "show me the desktop")
take a screenshot                 a picture of the whole screen
play the first video | pause the video | play the video | next video | fullscreen | skip ahead | rewind | captions      controls on the YouTube page
close <app or website>            close an app completely, or a website's browser tab (same names as open)
close this tab                    the browser tab in front
shut down                         Jarvis closes ITSELF ("quit", "exit", "turn yourself off", "go to sleep", "shut down jarvis"). Never for the laptop/computer.
search <query>                    a plain search: Google. Only name a site or browser the user named.
search <query> on <youtube|youtube music|amazon|linkedin|dev.to|netflix>      only if the user named that site
search <query> in <edge|chrome>   only if the user named that browser
play <song, artist or genre> [on youtube]
volume up | volume down | set volume to <number> | mute | unmute      the COMPUTER's sound (music, videos). This is the default meaning of "volume", "louder", "turn it up".
pause | play | next song | previous song      music/media controls ("skip", "go back a song", "stop the music")
what do i have today | what do i have tomorrow | what do i have this week | what do i have on <day or date> | what did i miss
remember <fact>                   ONLY when the user gives NEW information (the fact itself, e.g. "my locker code is 4512")
what is <something the user asked me to remember>      for QUESTIONS about saved things ("what's my...", "what was my...", "do you know my...")
move <item> to <time>
rename <item> to <new wording>    change what a reminder says ("edit", "change the wording", "reword")
what are my reminders             every reminder coming up ("current reminders", "list my reminders")
i'm done with <item>
delete <item>
snooze for <duration>
speak slower | speak faster | increase your volume | decrease your volume      ONLY when the user means Jarvis's own voice ("speak up", "your voice", "talk louder").
make <edge|chrome> my default browser
what can you do
chat: <reply>                     for greetings, small talk, a simple question you can answer in one short sentence, or anything not in this list. \
The reply is Jarvis speaking: calm, polite, a little dry wit, at most two short sentences, addresses the user as "sir", never by name. \
If it's an action you can't do, say so politely. Answer simple arithmetic and well-known facts yourself in the chat reply.

"it", "that", "the first one" mean whatever the recent conversation was about, if one is given below.
If a line "Timers now / Reminders now" is given, it is what is really there: use it to work out what the user means, and to answer questions about it.
Output only the line(s), nothing else."""

EXAMPLES = [
    ("Remind me, for tomorrow, 5 pm, I have to do my Web Technology Lab assignment", "remind me to do my web technology lab assignment tomorrow at 5pm"),
    ("remind me tomorrow at 5pm that I have to do my Web Technology Lab assignment", "remind me to do my web technology lab assignment tomorrow at 5pm"),
    ("could you set a timer about the next 5 minutes", "set a timer for 5 minutes"),
    ("yo turn it up a bit", "volume up"),
    ("it's way too loud", "volume down"),
    ("open up you tube for me", "open youtube"),
    ("put on some lo-fi", "play lo-fi"),
    ("what's the plan for tomorrow", "what do i have tomorrow"),
    ("did I forget anything", "what did i miss"),
    ("how long till the timer's done", "how much time is left on my timer"),
    ("I finally finished the maths exam", "i'm done with maths exam"),
    ("push the dentist thing to friday 4pm", "move dentist to friday at 4pm"),
    ("note that my locker code is 4512", "remember my locker code is 4512"),
    ("what was my locker code again", "what is my locker code"),
    ("look up python tutorials on youtube", "search python tutorials on youtube"),
    ("I want to know the best laptops under 50000", "search the best laptops under 50000"),
    ("find out who won the match in edge", "search who won the match in edge"),
    ("You have not cancelled them, I asked you to cancel them", "cancel my reminders for tomorrow"),
    ("how many reminders do I have", "what are my reminders"),
    ("can you talk a bit slower", "speak slower"),
    ("how are you doing today", "chat: Very well, sir, thank you for asking. Ready when you are."),
    ("what's the capital of France", "chat: Paris, sir."),
    ("order me a pizza", "chat: I'm afraid I can't order things yet, sir."),
    ("thanks mate", "chat: My pleasure, sir."),
    ("what the fuck man", "chat: Is something the matter, sir?"),
    ("make the sound louder please", "volume up"),
    ("could you speak up, I can't hear you", "increase your volume"),
    ("go back one song", "previous song"),
    ("stop the music for a sec", "pause"),
    ("remind me to water the plants", "remind me to water the plants"),
    ("set an alarm for 7 tomorrow", "remind me to wake up tomorrow at 7am"),
    ("do you know my wifi password", "what is my wifi password"),
    ("open crow", "open chrome"),
    ("launch spotify", "open spotify"),
    ("turn off the wifi", "chat: I can't change the Wi-Fi yet, sir."),
    ("you still haven't done what I asked", "chat: I'm sorry, sir. Tell me once more and I'll get it right."),
    ("open my bank account", "chat: I'm afraid I can't open that, sir."),
    ("I want to listen to something", "open youtube music"),
    ("what's 9 times 7", "chat: 63, sir."),
    ("not sure why you can't hear me", "chat: I can hear you now, sir. What can I do for you?"),
    ("open whisper no pro", "open wisperno pro"),
    ("fire up chat gpt for me", "open chatgpt"),
    ("Clues File Explorer", "close file explorer"),
    ("Lewis Chrome", "close chrome"),
    ("cancel all the reminders for tomorrow", "cancel my reminders for tomorrow"),
    ("get rid of the 3 minute timer", "cancel the 3 minute timer"),
    ("hold the one minute timer", "pause the 1 minute timer"),
    ("clear all my timers", "cancel all timers"),
    ("pause both of them", "pause all timers"),
    ("make two timers, one for 5 minutes and one for 10", "set a timer for 5 minutes\nset a timer for 10 minutes"),
    ("click a screenshot of the current screen", "take a screenshot"),
    ("show me what's in my downloads", "open downloads"),
    ("play the first one", "play the first video"),
    ("make the video bigger", "fullscreen"),
    ("YouTube open karna", "open youtube"),
    ("Edge band kar do", "close edge"),
    ("can you see my screen", "chat: I can take a screenshot of it, sir, but I can't read it yet."),
    ("Essentially, remind me, today, 5 PM, I have to submit my assignment", "remind me to submit my assignment today at 5pm"),
    ("Edit the reminder of check LinkedIn to check LinkedIn tasks", "rename check linkedin to check linkedin tasks"),
    ("What are the current reminders?", "what are my reminders"),
    ("get rid of the youtube tab", "close youtube"),
    ("I'm done with this tab", "close this tab"),
    ("open notepad and set a timer for 5 minutes", "open notepad\nset a timer for 5 minutes"),
    ("I need something to take notes in", "open notepad"),
    ("I'm bored, I want to watch a movie", "open netflix"),
    ("close i hate pdf completely", "close ihatepdf"),
    ("alright you can turn yourself off now", "shut down"),
    ("shut down my laptop", "chat: I'm afraid I can't shut down the computer, sir."),
]


def _dlls():
    for d in (W + r"\torch\lib", W, W + r"\llama_cpp\lib"):
        if os.path.isdir(d):
            os.add_dll_directory(d)
    os.environ["PATH"] = W + r"\torch\lib;" + W + ";" + os.environ["PATH"]
    os.environ["LLAMA_CPP_LIB_PATH"] = W + r"\llama_cpp\lib"


UNSURE = "I'm afraid I'm not sure how to do that yet, sir."
PROMISE = re.compile(r"\b(?:i've|i have|i will|i'll|i am going to|i'm going to|now shutting|done)\b", re.I)  # a chat reply does nothing, so it must not say it did or will
FORMS = (r"(?:chat:|remind me|set a timer|how much time|cancel the timer|open |search |google |play|volume |set volume|mute|unmute|pause|"
         r"next song|previous song|what do i have|what did i miss|remember |what is |move |i'm done|delete |snooze|speak |increase your|"
         r"pause |resume |cancel |decrease your|make (?:edge|chrome)|what can you do|close |shut down|rename |what are my reminders|take a screenshot|fullscreen|skip ahead|rewind|captions|next video)")


WORDING = [("open netflix", "Opening Netflix in Edge, sir.", "Netflix is on its way in Edge, sir."),
           ("make two timers", "Timers set: 5 minute and 10 minute, sir.", "Both timers are running, sir: 5 minutes and 10 minutes."),
           ("close discord and notepad", "Closing Discord and Notepad, sir.", "Discord and Notepad are closing now, sir."),
           ("kill all the timers", "Both timers cancelled, sir.", "Both timers are gone, sir."),
           ("cancel tomorrow's stuff", "Cancelled 2 reminders for tomorrow, sir: Buy milk and Call dad.", "Consider them gone, sir: buy milk and call dad are off tomorrow's list."),
           ("close paint", "Paint isn't running, sir.", "Paint isn't open at the moment, sir."),
           ("remind me to buy milk", "Noted, sir: 'Buy milk' tomorrow 9:00 am.", "I'll remind you to buy milk tomorrow at 9:00 am, sir."),
           ("search for cats", "Searching Google for cats, sir.", "Looking up cats on Google, sir.")]
OPENERS = {"open", "launch", "start", "run", "show", "bring", "pull", "go", "take", "fire", "visit", "play", "watch", "get", "kholo"}
FILLER = {"jarvis", "hey", "ok", "okay", "please", "so", "and", "now", "then", "can", "could", "would", "will", "you", "the", "just", "um", "uh"}


def misheard_close(text):
    """Speech recognition writes "close" as Lewis, Clues, Focus... and the model then guesses "open". The first real word decides."""
    words = [w for w in re.findall(r"[a-z]+", text.lower()) if w not in FILLER]
    if not words or words[0] in OPENERS or "open" in words:
        return False
    if len(words[0]) > 7:
        return False
    close = difflib.SequenceMatcher(None, words[0], "close").ratio()
    return close >= 0.4 and close > difflib.SequenceMatcher(None, words[0], "open").ratio()


def good_reply(line, fact):
    """May the model's wording replace the plain fact? It must not change a number or a name, flip the meaning, refuse, or ramble."""
    if not line or len(line) > 160 or "\n" in line or "?" in line:
        return False
    low, flow = line.lower(), fact.lower()
    words = re.sub(r"\b(two|both)\b", " 2 ", re.sub(r"\bone\b", " 1 ", re.sub(r"\bthree\b", " 3 ", re.sub(r"\bfour\b", " 4 ", re.sub(r"\bfive\b", " 5 ", low)))))  # "two" counts as 2
    told, kept = set(re.findall(r"\d+", flow)), set(re.findall(r"\d+", words))
    if kept - told - {"1", "2"} or told - kept:
        return False
    if re.search(r"\b(?:can't|cannot|unable|sorry|afraid|as an ai|i don't)\b", low) and not re.search(r"\b(?:can't|cannot|afraid|couldn't|no )\b", flow):
        return False
    for a, b in (("clos", "open"), ("open", "clos"), ("up", "down"), ("down", "up"), ("paus", "resum"), ("cancel", "set"), ("unmute", "mute ")):
        if re.search(r"\b" + a, flow) and re.search(r"\b" + b, low) and not re.search(r"\b" + b, flow):
            return False
    names = re.findall(r"(?<![.!?:] )(?<!^)\b[A-Z][\w.]+", fact) + [w for q in re.findall(r"'([^']+)'", fact) for w in q.split()]
    if any(n.lower().strip(".,") not in low for n in names if n.lower().strip(".,") not in ("sir", "timer", "the", "a")):
        return False
    return "sir" in low


class Brain:
    def __init__(self):
        self.llm, self.ready, self.error, self.lock = None, False, None, threading.Lock()
        self.system = SYSTEM
        self.last = 0.0
        self.rest = []  # further commands from the same sentence ("open notepad and set a timer")

    def warm(self):
        """Someone just started talking: run a tiny job so the GPU is awake by the time they finish (idle GPU = slow first answer).
        Same prompt as a real request, so the AI's memory of the long instructions is kept, not thrown away."""
        if self.ready and time.time() - self.last > 2 and not self.lock.locked():
            self.last = time.time()
            threading.Thread(target=self._ask, args=([{"role": "user", "content": "hello"}], 1), daemon=True).start()

    def _msgs(self):
        msgs = [{"role": "system", "content": self.system}]
        for u, a in EXAMPLES:
            msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        return msgs

    def _ask(self, extra, max_tokens, temperature=0):
        with self.lock:
            out = self.llm.create_chat_completion(self._msgs() + extra, max_tokens=max_tokens, temperature=temperature, seed=random.randrange(1 << 30))
        return out["choices"][0]["message"]["content"]

    def load(self):
        """Call on a background thread (takes ~2 s). Leaves ready=False and error set if it can't load; Jarvis then uses the rules only."""
        try:
            path = next(p for p in MODELS if os.path.isfile(p))
            _dlls()
            from llama_cpp import Llama
            self.llm = Llama(model_path=path, n_gpu_layers=-1, n_ctx=4096, verbose=False)
            self.rewrite("hello")  # first answer is slow: do it now
            self.ready = True
        except Exception as e:
            self.error = str(e)[:120]

    def phrase(self, said, result):
        """The rules did it and know what happened (`result`); the AI says it in its own words. Falls back to `result` if the wording can't be trusted."""
        extra = [{"role": "system", "content": "New job: each message now says what the user said, then DONE: and what really happened. Reply to them as Jarvis, a calm, polished British butler, with chat: and one short sentence in fresh words. Keep every name and number. Say it once even if it happened twice. No advice, no instructions, no questions, no commands."}]
        for heard, done, reply in WORDING:
            extra += [{"role": "user", "content": f"User said: {heard}\nDONE: {done}"}, {"role": "assistant", "content": "chat: " + reply}]
        extra.append({"role": "user", "content": f"User said: {said[:200]}\nDONE: {result[:300]}"})
        out = self._ask(extra, 40, 0.6)
        line = out.strip().splitlines()[0].strip().strip('"') if out.strip() else ""
        line = re.sub(r"^chat\s*:\s*", "", line, flags=re.I).strip().strip('"')
        return line if good_reply(line, result) else result

    def converse(self, text, recent=(), now=None):
        """No command fits what was said, so answer like a person would. It may explain or ask; it must never claim it did something."""
        extra = [{"role": "system", "content": "Recent conversation:\n" + "\n".join(f"User: {u[:120]}\nJarvis: {a[:120]}" for u, a in recent)}] if recent else []
        if now:
            extra.append({"role": "system", "content": now[:600]})
        extra.append({"role": "system", "content": "No command fits this message, so nothing is being done. Answer the user directly as Jarvis, with chat: and at most two short sentences, calling them sir. Use the conversation and what is there now. If they want something you can't do, say so plainly and say what you can do instead. Never say you did or will do something."})
        out = self._ask(extra + [{"role": "user", "content": text[:400]}], 60, 0.6)
        line = re.sub(r"^chat\s*:\s*", "", out.strip().splitlines()[0].strip().strip('"') if out.strip() else "", flags=re.I).strip()
        if not line or re.match(FORMS, line, re.I) and not line.lower().startswith(("what", "how")) or PROMISE.search(line) or re.search(r"\b(?:cancelled|opened|closed)\b", line, re.I):
            return "I'm sorry, sir. Tell me once more what you'd like, and if I can do it, I will."
        return line if re.search(r"\bsir\b", line, re.I) else line.rstrip(".!") + ", sir."

    def rewrite(self, text, asked=None, recent=(), now=None):
        """Messy words -> one clean command line, or 'chat: ...'. `asked` = the question Jarvis just asked, if any;
        `recent` = the last (user, Jarvis) exchanges, so "move it to 6" makes sense. Extra commands land in self.rest."""
        msgs = [{"role": "system", "content": "Recent conversation:\n" + "\n".join(f"User: {u[:120]}\nJarvis: {a[:120]}" for u, a in recent)}] if recent else []
        if now:
            msgs.append({"role": "system", "content": now[:600]})
        if asked:
            msgs.append({"role": "system", "content": f"Jarvis just asked the user: \"{asked}\". Their words answer it: give the complete command."})
        self.last = time.time()
        out = self._ask(msgs + [{"role": "user", "content": text[:400]}], 90)
        lines = [x.strip().strip('"').strip() for x in out.strip().splitlines() if x.strip()]
        # a second command only if the user actually asked for two things: the model sometimes adds one of its own
        self.rest = [x for x in lines[1:3] if re.match(FORMS, x, re.I) and not x.lower().startswith("chat:")] if re.search(r"\b(?:and|then|also|both)\b|,", text, re.I) else []
        line = lines[0] if lines else ""
        if re.search(r"\bgoogle\b", text, re.I) and re.match(r"search (?!.* on )", line, re.I):
            line = "google " + line[7:]  # said Google: not the site opened last
        if re.fullmatch(r"(?:increase|decrease) your volume", line, re.I) and not re.search(r"\b(?:your|voice|speak|talk|talking)\b", text, re.I):
            line = ("volume up" if line.lower().startswith("inc") else "volume down") if re.search(r"\b(?:volume|sound|loud|louder|quiet)\b", text, re.I) else "chat: I'm listening, sir. What can I do for you?"
        if re.match(r"resume\b", line, re.I) and re.search(r"\b(?:hold|pause|freeze|stop)\b", text, re.I):
            line = "pause" + line[6:]
        if re.fullmatch(r"(?:play )?next (?:song|track)", line, re.I) and not re.search(r"\b(?:next|skip|another|change)\b", text, re.I):
            line = "open youtube music"
        if re.match(r"(?:cancel|delete)\b", line, re.I) and not re.search(r"\b(?:cancel|cancell?ed|delete|remove|clear|kill|stop|end|rid|scrap|forget|drop|off|band)\b", text, re.I):
            # removing something needs the user to have said so; the model has mixed up "put a timer on" with "cancel"
            n = re.search(r"\b\d+ (?:second|minute|hour)s?\b", line)
            line = f"set a timer for {n[0]}" if n and "timer" in line.lower() else "chat: I'm afraid I didn't quite catch that, sir."
        if re.search(r"\b(?:all|both|every)\b", text, re.I) and re.fullmatch(r"(cancel|pause|resume) the timer", line, re.I):
            line = line.split()[0].lower() + " all timers"
        if re.match(r"search\s.+\son\s(\S.*)$", line, re.I) and not re.search(re.escape(re.match(r"search\s.+\son\s(\S.*)$", line, re.I)[1]), text, re.I):
            line = re.sub(r"\son\s\S.*$", "", line)  # a site the user didn't name: plain search
        if re.match(r"open\s", line, re.I) and misheard_close(text):
            line = "close" + line[4:]  # "Lewis Chrome", "Clues File Explorer": that was "close"
        m = re.match(r"(open|close)\s+(?:the |my )?(.+?)(?:\s+in (?:chrome|edge))?$", line, re.I)
        if m:  # the model must not swap the app the user named for a similar one
            from .actions import APPS, FOLDERS, SITES, _canon, _squash, mentioned
            named = mentioned(text)
            if named and _squash(m[2]) not in map(_squash, named):
                line, self.rest = f"{m[1].lower()} {named[0]}", [f"{m[1].lower()} {n}" for n in named[1:]]
            elif not named and m[2].lower() not in (*SITES, *APPS, *FOLDERS):
                # a guess may only land on the well-known list: "open my bank account" must not become "open samsung browser"
                sq, tg = _squash(_canon(text)), _squash(m[2])
                if difflib.SequenceMatcher(None, sq, tg).find_longest_match(0, len(sq), 0, len(tg)).size < 0.6 * len(tg):
                    line = "chat: I'm afraid I can't do that yet, sir."
        line = re.sub(r"^(?:command|output)\s*:\s*", "", line, flags=re.I)
        if re.search(r"\bremind me\b|\bdon'?t let me forget\b", text, re.I) and re.match(r"remember\b", line, re.I):
            line = re.sub(r"^remember\s+(?:to\s+)?", "remind me to ", line, flags=re.I)  # "remind me" always means a reminder, never a note
        if re.match(r"speak (?:slower|faster)", line, re.I) and not re.search(r"slow|fast|quick|pace|speed|rush", text, re.I):
            line = "chat: I'm listening, sir. What can I do for you?"  # a complaint is not a request to change my pace
        if re.match(r"shut down", line, re.I) and not re.search(r"\b(?:shut|shutdown|quit|exit|off|sleep|close|bye|goodbye|offline|power|leave|stop)\b", text, re.I):
            line = "chat: " + UNSURE  # quitting needs the user to have asked; a complaint is not a goodbye
        if re.match(r"shut down", line, re.I) and re.search(r"\b(?:laptop|computer|pc|windows|system|machine)\b", text, re.I):
            line = "chat: I'm afraid I can't shut down the computer, sir."
        if not re.match(FORMS, line, re.I):  # not one of the command forms: it can only be talk, never an action
            line = re.sub(r"^chat\s*:\s*", "", line, flags=re.I)
            line = "chat: " + (line if re.search(r"\bsir\b", line, re.I) else UNSURE)  # a half-made command is not a reply
        return line
