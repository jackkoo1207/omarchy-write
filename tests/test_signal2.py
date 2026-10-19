import os
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication([])
fired = []

signal.signal(signal.SIGUSR1, lambda *_: (fired.append(1), print("HANDLER RAN", flush=True)))

def fire():
    print("sending SIGUSR1", flush=True)
    os.kill(os.getpid(), signal.SIGUSR1)

QTimer.singleShot(500, fire)
QTimer.singleShot(2500, lambda: (print("fired count:", len(fired), flush=True), app.quit()))
QTimer.singleShot(5000, app.quit)
app.exec()
print("final fired count:", len(fired))
sys.exit(0 if len(fired) >= 1 else 1)
