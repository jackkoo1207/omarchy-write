import os
import signal
import sys

from PySide6.QtCore import QSocketNotifier, QTimer
from PySide6.QtWidgets import QApplication

app = QApplication([])
r, w = os.pipe()
os.set_blocking(r, False)
os.set_blocking(w, False)
signal.signal(signal.SIGUSR1, lambda *_: None)  # no-op: override default terminate
signal.set_wakeup_fd(w)
count = [0]

def on_read():
    try:
        os.read(r, 4096)
    except OSError:
        pass
    count[0] += 1
    print("NOTIFIER FIRED", count[0], flush=True)
    if count[0] >= 2:
        app.quit()

n = QSocketNotifier(r, QSocketNotifier.Type.Read)
n.activated.connect(on_read)

def fire():
    print("sending SIGUSR1 to", os.getpid(), flush=True)
    os.kill(os.getpid(), signal.SIGUSR1)

QTimer.singleShot(500, fire)
QTimer.singleShot(1500, fire)
QTimer.singleShot(4000, app.quit)
app.exec()
print("done, fired count:", count[0])
sys.exit(0 if count[0] >= 2 else 1)
