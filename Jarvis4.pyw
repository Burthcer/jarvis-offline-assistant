"""Jarvis V4. The V2 and V3 desktop launchers are unchanged."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from jarvis3.launcher import main
main()
