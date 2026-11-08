import ctypes
import logging
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename=os.path.join("logs", "jarvis2.log"), level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
k = ctypes.WinDLL("kernel32", use_last_error=True)
one = k.CreateMutexW(None, False, "JarvisOfflineAssistant")  # same name as V1: two copies would hear and talk over each other; Windows frees this when Jarvis exits
if ctypes.get_last_error() == 183:
    ctypes.windll.user32.MessageBoxW(None, "Jarvis (V1 or V2) is already running. Look for the green circle in the taskbar corner.", "Jarvis V2", 0x40)
    sys.exit()
from jarvis2.ui import main

main()
