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
from gi.repository import Gtk

def send(name, message, password):
    try:
        request = requests.post("https://akemsoft.com/geheimchat/send.php", {"name": cryptocode.encrypt(name, password), "text": cryptocode.encrypt(message, password), "time": cryptocode.encrypt(time.ctime(), password)})
        if request.status_code != 200:
            raise Exception(f"Receive failed: wrong statuscode: {request.status_code}, error message (if any): {request.text}")
    except Exception as e:
        raise Exception(f"Send failed: {e}") from e

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
    def __init__(self, name, password):
        threading.Thread.__init__(self)
        self.receiver = ReceiverEngine()
        self.name = name
        self.password = password
        self.start()

    def run(self):
        while True:
            try:
                self.receiver.receive()
            except Exception as e:
                traceback.print_exc()
            for message in self.receiver.newmess[len(self.receiver.oldmess):]:
                if cryptocode.decrypt(message[0], self.password) and cryptocode.decrypt(message[1], self.password) and cryptocode.decrypt(message[2], self.password):
                    print(f"{cryptocode.decrypt(message[2], self.password)} -- {cryptocode.decrypt(message[0], self.password)}: {cryptocode.decrypt(message[1], self.password)}")
            self.receiver.oldmess = self.receiver.newmess
            time.sleep(2)

if __name__ == "__main__":
    passwort = input("Passwort? ")
    name = input("Dein Name? ")
    # send
    def sendgtk(button, entry):
        send(name, entry.get_text(), passwort)
        entry.set_text("")
    builder = Gtk.Builder()
    builder.add_from_file("send.ui")
    builder.get_object("send").connect("clicked", sendgtk, builder.get_object("message"))
    builder.get_object("win").show()
    # receive (this runs in the background)
    AutoReceiverEngine(name, passwort)
    Gtk.main()
