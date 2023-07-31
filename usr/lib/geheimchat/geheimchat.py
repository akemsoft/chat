#!/usr/bin/python3
import gi
import time
import json
import requests
import traceback
import threading
import cryptocode
import webbrowser

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from urllib.parse import quote

def _async(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper

def idle_function(func):
    def wrapper(*args):
        GLib.idle_add(func, *args)
    return wrapper

def check_for_update(window):
    installed_version = "__DEB_VERSION__"
    error = False
    try:
        # Wait a second
        time.sleep(1)
        latest_version = requests.get("https://akemsoft.com/geheimchat/version").content.decode()
    except Exception as e:
        error = True
        errormsg = str(e)

    if error:
        show_update_info(window, "exception", errormsg)
    elif installed_version == latest_version:
        show_update_info(window, "uptodate", installed_version)
    elif "." in latest_version:
        show_update_info(window, "outofdate", installed_version, latest_version)
    else:
        show_update_info(window, "error", latest_version)

@idle_function
def show_update_info(window, info, installed, latest=None):
    if info == "uptodate":
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.INFO)
        dialog.set_transient_for(window)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_title("Geheimchat-Updater")
        dialog.set_property("text", "Kein Update verfügbar")
        dialog.format_secondary_text("Sie benutzen die neueste Version vom Geheimchat (%s)" % installed)
        dialog.show()
        dialog.run()
        dialog.destroy()
    elif info == "outofdate":
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING)
        dialog.set_transient_for(window)
        dialog.add_buttons("Ignorieren", Gtk.ResponseType.CANCEL, "Aktualisieren", Gtk.ResponseType.YES)
        dialog.set_title("Geheimchat-Updater")
        dialog.set_property("text", "Update verfügbar")
        dialog.format_secondary_text("Sie benutzen NICHT die neueste Version vom Geheimchat. Geheimchat %s ist verfügbar. (Sie benutzen Geheimchat %s)" % (latest, installed))
        dialog.show()
        if dialog.run() == Gtk.ResponseType.YES:
            run_updater(installed)
        dialog.destroy()
    elif info == "exception":
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING)
        dialog.set_transient_for(window)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_title("Geheimchat-Updater")
        dialog.set_property("text", "Fehler")
        dialog.format_secondary_text("Die Suche nach einer neuen Version von Geheimchat ist fehlgeschlagen. Fehlermeldung: %s" % installed)
        dialog.show()
        dialog.run()
        dialog.destroy()
    elif info == "error":
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING)
        dialog.set_transient_for(window)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_title("Geheimchat-Updater")
        dialog.set_property("text", "Fehler")
        dialog.format_secondary_text("Die Suche nach einer neuen Version von Geheimchat ist fehlgeschlagen. Der Server gab eine ungültige Version zurück: %s" % installed)
        dialog.show()
        dialog.run()
        dialog.destroy()

def run_updater(installed_version):
    webbrowser.open(f"https://akemsoft.com/geheimchat/update?v={quote(installed_version)}")

def send(name, message, password):
    try:
        request = requests.post("https://akemsoft.com/geheimchat/send.php", {"name": cryptocode.encrypt(name, password), "text": cryptocode.encrypt(message, password), "time": cryptocode.encrypt(time.ctime(), password)})
        if request.status_code != 200:
            raise Exception(f"Receive failed: wrong statuscode: {request.status_code}, error message (if any): {request.text}")
    except Exception as e:
        raise Exception(f"Send failed: {e}") from e

def quit_everything(*args):
    global engine
    engine.my_stop()
    Gtk.main_quit()

def sendgtk(button, entry):
    global name, password
    send(name, entry.get_text(), password)
    entry.set_text("")

class ReceiverEngine:
    def __init__(self):
        self.oldmess = []

    def receive(self):
        try:
            request = requests.get("https://akemsoft.com/geheimchat/data.json")
            if request.status_code != 200:
                raise Exception(f"Receive failed: wrong statuscode: {request.status_code}, error message (if any): {request.text}")
            self.newmess = json.loads(request.text)["messages"]
        except Exception as e:
            raise Exception(f"Receive failed: {e}") from e

class AutoReceiverEngine(threading.Thread): # background
    def __init__(self, textbuffer, name, password):
        threading.Thread.__init__(self)
        self.receiver = ReceiverEngine()
        self.textbuffer = textbuffer
        self.name = name
        self.password = password
        self.stop = False
        self.start()

    def run(self):
        while self.stop == False:
            try:
                self.receiver.receive()
            except Exception as e:
                traceback.print_exc()
            for message in self.receiver.newmess[len(self.receiver.oldmess):]:
                if cryptocode.decrypt(message[0], self.password) and cryptocode.decrypt(message[1], self.password) and cryptocode.decrypt(message[2], self.password):
                    self.textbuffer_insert(self.textbuffer.get_end_iter(), f"{cryptocode.decrypt(message[2], self.password)} -- {cryptocode.decrypt(message[0], self.password)}: {cryptocode.decrypt(message[1], self.password)}\n")
            self.receiver.oldmess = self.receiver.newmess
            time.sleep(2)

    @idle_function
    def textbuffer_insert(self, end, text):
        self.textbuffer.insert(end, text)
    def my_stop(self):
        self.stop = True

def auth(widget, _builder, _password, _name):
    global builder, password, name, engine
    builder, password, name = _builder, _password.get_text(), _name.get_text()
    textbuffer = builder.get_object("history").get_buffer()
    textbuffer.set_text("")
    engine = AutoReceiverEngine(textbuffer, name, password)
    builder.get_object("send").connect("clicked", sendgtk, builder.get_object("message"))
    builder.get_object("auth_win").destroy()
    builder.get_object("main_win").connect("delete-event", quit_everything)
    builder.get_object("main_win").set_icon_name("hipchat")
    builder.get_object("main_win").show()

if __name__ == "__main__":
    builder = Gtk.Builder()
    builder.add_from_file("/usr/share/geheimchat/geheimchat.ui")
    builder.get_object("login").connect("clicked", auth, builder, builder.get_object("password_entry"), builder.get_object("name_entry"))
    builder.get_object("auth_win").connect("delete-event", Gtk.main_quit)
    builder.get_object("auth_win").set_icon_name("hipchat")
    builder.get_object("auth_win").show()
    check_for_update(builder.get_object("auth_win"))
    Gtk.main()
