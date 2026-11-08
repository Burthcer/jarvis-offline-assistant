import ctypes
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
k = ctypes.WinDLL("kernel32", use_last_error=True)
one = k.CreateMutexW(None, False, "JarvisOfflineAssistant")  # two copies would hear and talk over each other; Windows frees this when Jarvis exits
if ctypes.get_last_error() == 183:
    ctypes.windll.user32.MessageBoxW(None, "Jarvis is already running. Look for the green circle in the taskbar corner.", "Jarvis", 0x40)
    sys.exit()
from jarvis.ui import main

main()
