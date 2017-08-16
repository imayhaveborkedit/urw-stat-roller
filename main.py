import sys
import traceback

from threading import Lock

import memhook
from ui import Ui

l = Lock()
h = memhook.Hook()
ui = Ui(h)

def exhook(*args):
    with l:
        with open("error.txt", 'a') as f:
            f.writelines(traceback.format_exception(*args))
            f.write('\n')

        ui.on_error(*args)

sys.excepthook = exhook


ui.run()
