#!/usr/bin/python3
import os
import gi
import time
import json
import requests
import traceback
import threading
import cryptocode
import webbrowser

gi.require_version("Notify", "0.7")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, Gio, Notify
try:
    gi.require_version('XApp', '1.0')
    from gi.repository import XApp
except:
    pass

from urllib.parse import quote

# Used as a decorator to run things in the background
def _async(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper

# Used as a decorator to run things in the main loop, from another thread
def idle(func):
    def wrapper(*args):
        GLib.idle_add(func, *args)
    return wrapper

class Application(Gtk.Application):
    # Main initialization routine
    def __init__(self, application_id, flags):
        Gtk.Application.__init__(self, application_id=application_id, flags=flags)
        self.connect("activate", self.activate)

    def activate(self, application):
        windows = self.get_windows()
        if (len(windows) > 0):
            window = windows[len(windows)-1]
            window.present()
            window.show()
        else:
            window = MainWindow(self)
            self.add_window(window.window)
            window.window.show()

class MainWindow():
    def __init__(self, application):
        self.application = application
        self.settings = Gio.Settings(schema_id="com.akemsoft.messenger")

        Notify.init("Geheimchat")
        self.stop = False

        self.builder = Gtk.Builder()
        self.builder.add_from_file("/usr/share/geheimchat/geheimchat.ui")

        self.window = self.builder.get_object("auth_win")
        self.name_entry = self.builder.get_object("name_entry")
        self.password_entry = self.builder.get_object("password_entry")
        self.message_entry = self.builder.get_object("message_entry")
        #TODO self.stack = self.builder.get_object("stack")
        self.login_button = self.builder.get_object("login_button")
        self.send_button = self.builder.get_object("send_button")

        self.login_button.connect("clicked", self.login)
        self.send_button.connect("clicked", self.send)
        self.window.connect("delete-event", self.close_window)
        self.window.set_icon_name("hipchat")
        # TODO self.stack.set_visible_child_name("login_box")
        self.window.show()
        # Initialize statusicon menu
        self.menu = Gtk.Menu()

        self.menuItem1 = Gtk.MenuItem.new_with_label("Minimieren")
        self.menuItem1.connect('activate', self.minimize_or_open)
        self.menu.append(self.menuItem1)

        self.menuItem2 = Gtk.MenuItem.new_with_label("Benachrichtigungen aus")
        self.menuItem2.connect('activate', self.on_notifications_enable_toggled)
        self.menu.append(self.menuItem2)

        self.menuItem3 = Gtk.MenuItem.new_with_label("Beenden")
        self.menuItem3.connect('activate', self.quit) #TODO threads...
        self.menu.append(self.menuItem3)

        self.menu.show_all()
        # statusicon itself
        try:
            self.status_icon = XApp.StatusIcon()
            self.status_icon.set_name("geheimchat") # optional
            self.status_icon.connect("activate", self.on_statusicon_activated)
            self.status_icon.set_secondary_menu(self.menu)
            self.status_icon.set_icon_name("hipchat")
        except:
            self.status_icon = Gtk.StatusIcon()
            self.status_icon.connect("activate", self.on_gtk_statusicon_activated)
            self.status_icon.connect("popup-menu", self.on_gtk_statusicon_popup)
            self.status_icon.set_from_icon_name("hipchat")
        self.check_for_update()

    ### MAIN (AUTH, SEND, RECEIVE) ###
    def login(self, widget):
        self.name, self.password = self.name_entry.get_text(), self.password_entry.get_text()
        self.engine = AutoReceiverEngine(self)
        self.window.destroy()
        self.window = self.builder.get_object("chat_win")
        self.window.connect("delete-event", self.close_window)
        self.application.add_window(self.window)
        self.textbuffer = self.builder.get_object("history").get_buffer()
        self.textbuffer.set_text("")
        self.window.present()
        self.window.show()
        # TODO self.stack.set_visible_child_name("chat_box")

    def send(self, widget):
        try:
            request = requests.post("https://akemsoft.com/geheimchat/send.php", {"name": cryptocode.encrypt(self.name, self.password), "text": cryptocode.encrypt(self.message_entry.get_text(), self.password), "time": cryptocode.encrypt(time.ctime(), self.password)})
            if request.status_code != 200:
                raise Exception(f"Receive failed: wrong statuscode: {request.status_code}, error message (if any): {request.text}")
        except Exception as e:
            raise Exception(f"Send failed: {e}") from e
        self.message_entry.set_text("")

    ### UPDATER ###
    @_async
    def check_for_update(self):
        installed_version = "__DEB_VERSION__"
        error = False
        try:
            latest_version = requests.get("https://akemsoft.com/geheimchat/version").content.decode()
        except Exception as e:
            error = True
            errormsg = str(e)
        if error:
            self.show_update_info("exception", error=errormsg)
        elif installed_version == latest_version:
            self.show_update_info("uptodate", installed_version)
        elif "." in latest_version:
            self.show_update_info("outofdate", installed_version, latest_version)
        else:
            self.show_update_info("error", latest=latest_version)
    
    @idle
    def show_update_info(self, info, installed=None, latest=None, error=None):
        if info == "uptodate":
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.INFO)
            dialog.set_transient_for(self.window)
            dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
            dialog.set_title("Geheimchat-Updater")
            dialog.set_property("text", "Kein Update verfügbar")
            dialog.format_secondary_text("Sie benutzen die neueste Version vom Geheimchat (%s)" % installed)
            dialog.show()
            dialog.run()
            dialog.destroy()
        elif info == "outofdate":
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING)
            dialog.set_transient_for(self.window)
            dialog.add_buttons("Ignorieren", Gtk.ResponseType.CANCEL, "Aktualisieren", Gtk.ResponseType.YES)
            dialog.set_title("Geheimchat-Updater")
            dialog.set_property("text", "Update verfügbar")
            dialog.format_secondary_text("Sie benutzen NICHT die neueste Version vom Geheimchat. Geheimchat %s ist verfügbar. (Sie benutzen Geheimchat %s)" % (latest, installed))
            dialog.show()
            if dialog.run() == Gtk.ResponseType.YES:
                self.run_updater(installed)
            dialog.destroy()
        elif info == "exception":
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING)
            dialog.set_transient_for(self.window)
            dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
            dialog.set_title("Geheimchat-Updater")
            dialog.set_property("text", "Fehler")
            dialog.format_secondary_text("Die Suche nach einer neuen Version von Geheimchat ist fehlgeschlagen. Fehlermeldung: %s" % error)
            dialog.show()
            dialog.run()
            dialog.destroy()
        elif info == "error":
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING)
            dialog.set_transient_for(self.window)
            dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)
            dialog.set_title("Geheimchat-Updater")
            dialog.set_property("text", "Fehler")
            dialog.format_secondary_text("Die Suche nach einer neuen Version von Geheimchat ist fehlgeschlagen. Der Server gab eine ungültige Version zurück: %s" % latest)
            dialog.show()
            dialog.run()
            dialog.destroy()
    
    def run_updater(self, installed_version):
        webbrowser.open(f"https://akemsoft.com/geheimchat/update?v={quote(installed_version)}")
        self.application.quit()

    ### STATUSICON ###
    def on_statusicon_activated(self, icon, button, time):
        if button == Gdk.BUTTON_PRIMARY:
            self.tray_activate(time)

    def on_gtk_statusicon_activated(self, status_icon):
        self.on_statusicon_activated(status_icon, Gdk.BUTTON_PRIMARY, None)

    def on_gtk_statusicon_popup(self, status_icon, button, time):
        self.menu.popup(None, None, None, None, button, time)

    def tray_activate(self, time=0):
        if self.win_focused():
            self.save_window_size()
            self.window.hide()
            self.menuItem1.set_label("Geheimchat öffnen")
        else:
            self.show_window()

    def minimize_or_open(self, widget):
        if self.app_hidden():
            self.show_window()
        else:
            self.save_window_size()
            self.window.hide()
            self.menuItem1.set_label("Geheimchat öffnen")

    def show_window(self, notification=None, event=None):
        self.window.present()
        self.window.show()
        self.menuItem1.set_label("Minimieren")

    ### STATUSICON MENU ###
    def on_notifications_enable_toggled(self, widget):
        self.settings.set_boolean('notifications-enabled', not self.settings.get_boolean('notifications-enabled'))
        if self.settings.get_boolean('notifications-enabled'):
            self.menuItem2.set_label("Benachrichtigungen aus")
        else:
            self.menuItem2.set_label("Benachrichtigungen an")

    ### MORE ###

    def close_window(self, window, event):
        self.save_window_size()
        self.hide_main_window(window)
        return True

    def save_window_size(self):
        self.settings.set_int('window-width', self.window.get_size()[0])
        self.settings.set_int('window-height', self.window.get_size()[1])

    def hide_main_window(self, widget):
        self.window.hide()
        self.menuItem1.set_label("Geheimchat öffnen")

    def win_focused(self):
        try:
            return self.window.get_window().get_state() & Gdk.WindowState.FOCUSED
        except:
            return self.window.is_active() and self.window.get_visible()

    def app_hidden(self):
        return not self.window.get_visible()

    def quit(self, widget, data = None):
        self.stop = True
        self.application.quit()

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
    def __init__(self, appwin):
        threading.Thread.__init__(self)
        self.receiver = ReceiverEngine()
        self.appwin = appwin
        self.name = appwin.name
        self.password = appwin.password
        self.initial_run = True
        self.start()

    def run(self):
        while True:
            try:
                self.receiver.receive()
            except Exception as e:
                traceback.print_exc() # TODO
            for message in self.receiver.newmess[len(self.receiver.oldmess):]:
                if cryptocode.decrypt(message[0], self.password) and cryptocode.decrypt(message[1], self.password) and cryptocode.decrypt(message[2], self.password):
                    sender, text, date = cryptocode.decrypt(message[0], self.password), cryptocode.decrypt(message[1], self.password), cryptocode.decrypt(message[2], self.password)
                    self.textbuffer_insert(self.appwin.textbuffer.get_end_iter(), f"{date} -- {sender}: {text}\n")
                    if self.appwin.settings.get_boolean("notifications-enabled") and not (self.initial_run or self.appwin.win_focused()):
                        if self.name != sender:
                            Gdk.threads_init()
                            notification = Notify.Notification.new(f"Neue Nachricht von {sender}", f"{text}\n-- {date}", "hipchat")
                            notification.set_urgency(Notify.Urgency.CRITICAL)
                            notification.set_timeout(Notify.EXPIRES_NEVER)
                            notification.add_action("show-window", "Anzeigen", self.appwin.show_window)
                            notification.connect("closed", Gtk.main_quit)
                            notification.show()
                            Gtk.main()
                            Gdk.threads_leave()
                if self.appwin.stop:
                    return
            if self.appwin.stop:
                return
            self.receiver.oldmess = self.receiver.newmess
            self.initial_run = False
            time.sleep(2)

    @idle
    def textbuffer_insert(self, end, text):
        self.appwin.textbuffer.insert(end, text)

if __name__ == "__main__":
    application = Application("com.akemsoft.messenger", Gio.ApplicationFlags.FLAGS_NONE)
    application.run()
