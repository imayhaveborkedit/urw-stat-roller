import memhook
from ui import Ui

h = memhook.Hook()

ui = Ui(h)
ui.run()
