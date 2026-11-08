import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis.core import handle
from jarvis.store import Store
s = Store(":memory:"); t = time.perf_counter()
for _ in range(200): handle("remind me about exam on 25 november", s)
print("ms per command:", round((time.perf_counter() - t) * 5, 2))
