#!/usr/bin/python3
import gi
import time
import json
import requests
import traceback
import threading
import cryptocode
import tkinter

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

def idle_function(func):
    def wrapper(*args):
        GObject.idle_add(func, *args)
    return wrapper

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
    builder.get_object("main_win").show()

if __name__ == "__main__":
    builder = Gtk.Builder()
    builder.add_from_file("chat.ui")
    builder.get_object("login").connect("clicked", auth, builder, builder.get_object("password_entry"), builder.get_object("name_entry"))
    builder.get_object("auth_win").connect("delete-event", Gtk.main_quit)
    builder.get_object("auth_win").show()
    Gtk.main()
