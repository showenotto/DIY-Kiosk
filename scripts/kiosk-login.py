#!/usr/bin/env python3

import gi
import os
from pathlib import Path

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

class LoginWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)

        self.set_title("Library Login")
        self.set_default_size(400, 250)
        self.set_resizable(False)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10
        )

        box.set_margin_top(30)
        box.set_margin_bottom(30)
        box.set_margin_start(30)
        box.set_margin_end(30)

        self.username = Gtk.Entry()
        self.username.set_placeholder_text("Username")

        self.password = Gtk.Entry()
        self.password.set_placeholder_text("Password")
        self.password.set_visibility(False)

        button = Gtk.Button(label="Login")
        button.connect("clicked", self.on_login)

        box.append(self.username)
        box.append(self.password)
        box.append(button)

        self.set_child(box)

        # Put cursor in username field immediately
        self.username.grab_focus()

    def on_login(self, button):
        user = self.username.get_text().strip()
        pw = self.password.get_text()

        if not user or not pw:
            return

        uid = os.getuid()

        cred_file = Path(f"/run/user/{uid}/kiosk-creds")

        try:
            with open(cred_file, "w") as f:
                f.write(f"{user}:{pw}\n")

            os.chmod(cred_file, 0o600)

        except Exception as e:
            print(f"Failed to write credentials: {e}")
            return

        self.get_application().quit()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.library.kiosk"
        )

    def do_activate(self):
        win = LoginWindow(self)
        win.present()


app = App()
app.run(None)
