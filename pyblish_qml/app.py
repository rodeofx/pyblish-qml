"""Application entry-point"""

# Standard library
import os
import sys
import time
import logging
import threading

# Dependencies
from PyQt5 import QtCore, QtGui, QtQuick, QtTest

import pyblish_rpc.client

# Local libraries
import util
import compat
import control

MODULE_DIR = os.path.dirname(__file__)
QML_IMPORT_DIR = os.path.join(MODULE_DIR, "qml")
APP_PATH = os.path.join(MODULE_DIR, "qml", "main.qml")
ICON_PATH = os.path.join(MODULE_DIR, "icon.ico")


class Window(QtQuick.QQuickView):
    """Main application window"""

    def __init__(self, parent=None):
        super(Window, self).__init__(None)
        self.parent = parent

        self.setTitle("Pyblish")
        self.setResizeMode(self.SizeRootObjectToView)

        self.setWidth(430)
        self.setHeight(600)
        self.setMinimumSize(QtCore.QSize(430, 300))

    def event(self, event):
        """Allow GUI to be closed upon holding Shift"""
        if event.type() == QtCore.QEvent.Close:
            modifiers = self.parent.queryKeyboardModifiers()
            shift_pressed = QtCore.Qt.ShiftModifier & modifiers

            if shift_pressed:
                event.accept()

            elif "publishing" in self.parent.controller.states:
                event.ignore()

            elif not self.parent.keep_alive:
                event.accept()

            else:
                event.ignore()
                self.parent.hide()

        return super(Window, self).event(event)


class Application(QtGui.QGuiApplication):
    """Pyblish QML wrapper around QGuiApplication

    Provides production and debug launchers along with controller
    initialisation and orchestration.

    """

    server_unresponsive = QtCore.pyqtSignal()
    show_signal = QtCore.pyqtSignal()
    quit_signal = QtCore.pyqtSignal()
    keep_alive = False

    def __init__(self, source, port):
        super(Application, self).__init__(sys.argv)

        self.setWindowIcon(QtGui.QIcon(ICON_PATH))

        window = Window(self)
        window.statusChanged.connect(self.on_status_changed)

        engine = window.engine()
        engine.addImportPath(QML_IMPORT_DIR)

        controller = control.Controller(port)

        context = engine.rootContext()
        context.setContextProperty("app", controller)

        self.window = window
        self.engine = engine
        self.controller = controller
        self.port = port
        self.host = pyblish_rpc.client.Proxy(port)

        self.server_unresponsive.connect(self.on_server_unresponsive)
        self.show_signal.connect(self.show)

        window.setSource(QtCore.QUrl.fromLocalFile(source))

    def on_status_changed(self, status):
        if status == QtQuick.QQuickView.Error:
            self.quit()

    def show(self):
        """Display GUI

        Once the QML interface has been loaded, use this
        to display it.

        """

        window = self.window

        previously_hidden = False
        if not window.isVisible():
            previously_hidden = True

        window.requestActivate()
        window.showNormal()

        if os.name == "nt":
            # Work-around for window appearing behind
            # other windows upon being shown once hidden.
            previous_flags = window.flags()
            window.setFlags(previous_flags | QtCore.Qt.WindowStaysOnTopHint)
            window.setFlags(previous_flags)

        if previously_hidden:
            # Give statemachine enough time to boot up
            if not any(state in self.controller.states
                       for state in ["ready", "finished"]):
                util.timer("ready")

                ready = QtTest.QSignalSpy(self.controller.ready)

                count = len(ready)
                ready.wait(1000)
                if len(ready) != count + 1:
                    util.echo("Warning: Could not enter ready state")

                util.timer_end("ready", "Awaited statemachine for %.2f ms")

            self.controller.show.emit()
            self.controller.reset()

    def hide(self):
        """Hide GUI

        Process remains active and may be shown
        via a call to `show()`

        """

        # self.controller.hide.emit()
        self.window.hide()

    def on_server_unresponsive(self):
        """Handle server unresponsive events"""

        util.echo("Server unresponsive; shutting down")

        self.quit()

    def listen(self):
        """Listen on incoming messages from host

        Two types of messages are handled here;
            1. Heartbeat
            2. Not heartbeat

        In the event of a heartbeat not being received on-time,
        the application is notified that the server might be
        unresponsive.

        Any other event is handled separately.

        Usage:
            >> from pyblish_endpoint import client
            >> client.request("show")  # Show a hidden GUI
            >> client.request("close")  # Close GUI permanently
            >> client.request("kill")  # Close GUI forcefully (careful)

        """

        timer = {"time": 0,
                 "count": 0,
                 "interval": 1,
                 "intervals_before_death": 2}

        def message_monitor():
            while True:
                try:
                    message = self.host.push()
                except Exception as e:
                    util.echo(getattr(e, "msg", str(e)))
                    self.server_unresponsive.emit()
                    break

                if message == "heartbeat":
                    timer["value"] = time.time()
                    timer["count"] += 1

                elif message == "show":
                    self.show_signal.emit()

                elif message == "close":
                    self.quit_signal.emit()

                elif message == "kill":
                    util.echo(
                        "Kill message received from "
                        "server, shutting down NOW!")
                    os._exit(1)

                else:
                    self.controller.info.emit(
                        "Unhandled incoming message: \"%s\""
                        % message)

                # NOTE(marcus): If we don't sleep, signals get trapped
                # TODO(marcus): Find a way around that.
                time.sleep(0.1)

        def heartbeat_monitor():
            while True:
                time.sleep(timer["interval"])
                if timer["time"] > (timer["interval"] *
                                    timer["intervals_before_death"]):
                    util.echo("Timer interval elapsed")
                    self.server_unresponsive.emit()

        for thread in (message_monitor, heartbeat_monitor):
            thread = threading.Thread(target=thread, name=thread.__name__)
            thread.daemon = True
            thread.start()


def main(port, source=None, pid=None,
         preload=False, debug=False, validate=True):
    """Start the Qt-runtime and show the window

    Arguments:
        port (int): Port through which to communicate
        source (str): QML entry-point
        pid (int, optional): Process id of parent process. Deprecated
        preload (bool, optional): Load in backgrund. Defaults to False
        debug (bool, optional): Run in debug-mode. Defaults to False
        validate (bool, optional): Whether the environment should be validated
            prior to launching. Defaults to True

    """

    if validate and compat.validate() is False:
        util.echo("""
Could not start application due to a misconfigured environment.

Pass validate=False to pyblish_qml.app:main
in order to bypass validation.
""")

        return 255

    # Initialise OS compatiblity
    compat.main()

    # Initialise logger for Endpoint
    formatter = logging.Formatter(
        '%(levelname)s - '
        '%(name)s: '
        '%(message)s',
        '%H:%M:%S')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    for logger in ("endpoint", "werkzeug"):
        log = logging.getLogger(logger)
        log.handlers[:] = []
        log.addHandler(stream_handler)
        log.setLevel(logging.DEBUG)
        # log.setLevel(logging.INFO)

    if debug:
        util.echo("Starting in debug-mode")
        util.echo("Looking for server..")
        import pyblish_rpc.client
        proxy = pyblish_rpc.client.Proxy(port)

        if not proxy.ping():
            util.echo("No existing server found, creating..")
            import pyblish_rpc.server
            os.environ["PYBLISH_CLIENT_PORT"] = str(port)

            thread = threading.Thread(
                target=pyblish_rpc.server.start_debug_server,
                kwargs={"port": port})
            thread.daemon = True
            thread.start()

            util.echo("Debug server created successfully.")
            util.echo("Listening on port: %s" % port)

    util.echo("Starting Pyblish..")
    util.timer("application")

    app = Application(source or APP_PATH, port)

    app.keep_alive = not debug
    app.listen()

    if not preload:
        app.show_signal.emit()

    util.timer_end("application",
                   "Spent %.2f ms creating the application")

    return app.exec_()


if __name__ == "__main__":
    proxy = pyblish_rpc.client.Proxy(6000)
    main(port=6000,
         pid=os.getpid(),
         preload=False,
         debug=True,
         validate=False)
