---
title: DIY Kiosk for Raspberry Pi OS
updated: 2026-06-16 23:21:50Z
created: 2026-06-16 19:40:55Z
latitude: -22.56088070
longitude: 17.06575490
altitude: 0.0000
---

[TOC]

<div style="page-break-before: always;"></div>

# 1\. Introduction

We want to migrate from Clearcube small factor PCs to Raspberry PIs.

At the backend instead of using Inuvika's infrastructure server, we would like to replace that layer with WIndows RDS so that the PIs can use RDP to connect to a session/client/profile served/stored by RDS.

# 2\. Requirements

We already examined options like No Touch OS and WTware and they do not fit our needs as No Touch OS licensing is too expensive and the WTware is outdated especially in UI/UX, documentation and it's core community.

So we would like to go with a model like:

Raspberry Pi OS + FreeRDP + DIY Kiosk

Then each PIs would reach out to the RDS for a windows session via RDP.

We plan to use the raspberry PIs in the library for hundreds of students to access.

Since we are planning to deploy at the organization scale, we want to use tools/components within this DIY solution that:

- is actively maintained
    
- alot of documentation
    
- scales well with deployment and ease of management
    

# 3\. Architecture Overview

## 3.1 Component Selection

| Name | Purpose |
| --- | --- |
| **Raspberry Pi OS Lite** |     |
| **greetd** |     |
| **labwc** |     |
| **GTK** |     |
| **FreeRDP** |     |

## 3.2 Boot and Login flow

Power On  
↓  
Raspberry Pi OS Lite (or Debian)  
↓  
systemd (PID 1)  
↓  
greetd  
↓  
Automatic login as kiosk user  
↓  
dbus-run-session  
↓  
labwc (Wayland compositor)  
↓  
labwc autostart  
↓  
systemd --user services  
↓  
GTK Login Application  
↓  
FreeRDP  
↓  
Windows RDS Session

# 4\. Setup & Configuration

Flash Raspberry Pi OS Lite

**Initial Configuration**:

- Hostname
- SSH
- Locale
- Timezone

## 4.1 Package Installation
### 4.1.1 Base packages + greetd & labwc
`sudo apt update && sudo apt upgrade -y`

```bash
sudo apt install \
    greetd \
    labwc \
    seatd \
    dbus-user-session \
    policykit-1 \
    xdg-desktop-portal \
    xdg-desktop-portal-wlr
```


### 4.1.2 GTK Application
`sudo apt install -y python3 python3-gi gir1.2-gtk-4.0`

### 4.1.3 FreeRDP
`sudo apt install freerdp3-wayland`


<div style="page-break-before: always;"></div>

## 4.2 User Account
Keep your administrative account.

### 4.2.1 Purpose of the kiosk account.

### 4.2.2 Create Dedicated Kiosk User

Create: 
`sudo adduser kiosk`

Add required groups:
`sudo usermod -aG video,input,audio,render,seat kiosk`

Verify:
`id kiosk`


<div style="page-break-before: always;"></div>

## 4.3 Custom Application Components

### 4.3.1 Overview

/usr/local/bin/  
├── kiosk-session
├── kiosk-controller
├── kiosk-rdp
├── kiosk-login.py
└── kiosk-logout

| Script | Purpose |
| --- | --- |
| kiosk-session | Create labwc session |
| kiosk-controller | Orchestrates login and RDP workflow |
| kiosk-rdp | Launches FreeRDP using supplied credentials |
| kiosk-login.py | GTK login application |
| kiosk-logout | Session cleanup (future) |

### 4.3.2 kiosk-session
Create: `sudo vi /usr/local/bin/kiosk-session`
File:
```
#!/bin/sh

export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export XDG_SESSION_TYPE=wayland
export XDG_SESSION_DESKTOP=labwc
export XDG_CURRENT_DESKTOP=labwc

exec dbus-run-session labwc
```
Make it executable: `chmod +x /usr/local/bin/kiosk-session`

### 4.3.3 kiosk-controller
Create: `sudo vi /usr/local/bin/kiosk-controller`
File:
```bash
#!/bin/bash

CREDS="/run/user/$(id -u)/kiosk-creds"

while true
do
    rm -f "$CREDS"

    # 1. start login
    systemctl --user start kiosk-login.service

    # 2. wait until login exits
    while systemctl --user is-active kiosk-login.service >/dev/null
    do
        sleep 0.2
    done

    # 3. validate creds
    if [ ! -f "$CREDS" ]; then
        continue
    fi

    # 4. run RDP
    systemctl --user start kiosk-rdp.service

    # 5. wait until RDP exits
    while systemctl --user is-active kiosk-rdp.service >/dev/null
    do
        sleep 1
    done

done
```

Make it executable: `chmod +x /usr/local/bin/kiosk-session`

### 4.3.4 kiosk-login.py
Create: `sudo vi /usr/local/bin/kiosk-login.py`
File:
```python
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
```
Make it executable: `chmod +x usr/local/bin/kiosk-login.py`

### 4.3.5 kiosk-rdp
Create: `sudo vi /usr/local/bin/kiosk-rdp`
File:
```bash
#!/bin/bash

CREDS="/run/user/$(id -u)/kiosk-creds"

if [ ! -f "$CREDS" ]; then
    exit 1
fi

USER=$(cut -d: -f1 "$CREDS")
PASS=$(cut -d: -f2- "$CREDS")

exec /usr/bin/wlfreerdp3 \
    /v:10.13.14.142 \
    /u:"$USER" \
    /p:"$PASS" \
    /f \
    /dynamic-resolution \
    /cert:ignore \
    +clipboard \
    /sound:sys:pulse \
    /network:auto

```
Make it executable: `chmod +x usr/local/bin/kiosk-login.py`

### 4.3.6 kiosk-logout
TBD

<div style="page-break-before: always;"></div>

## 4.4 systemd User Services

### 4.4.1 Overview
### 4.4.2 kiosk-controller.service
Starts the controller

```
[Unit]
Description=Kiosk Session Controller
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/local/bin/kiosk-controller
Restart=always

[Install]
WantedBy=default.target
```


### 4.4.3 kiosk-login.service
Starts the GTK login.
```
[Unit]
Description=GTK Login

[Service]
Type=simple
Environment=GSK_RENDERER=cairo
Environment=LIBGL_ALWAYS_SOFTWARE=1
ExecStart=/usr/bin/python3 /usr/local/bin/kiosk-login.py
Restart=no

[Install]
WantedBy=default.target
```

### 4.4.4 kiosk-rdp.service
Connects to the RDS

```
[Unit]
Description=RDP Session

[Service]
Type=simple
ExecStart=/usr/local/bin/kiosk-rdp
Restart=on-failure

[Install]
WantedBy=default.target
```


<div style="page-break-before: always;"></div>

## 4.5 Display and Session Management

### 4.5.1 Enable seatd
Wayland compositors require seat management.

Enable:
`sudo systemctl enable seatd && sudo systemctl start seatd`

### 4.5.2 Configuring greetd
Edit: `sudo vi /etc/greetd/config.toml`

Contents:
```
[terminal]
vt = 1

[default_session]
command = "dbus-run-session labwc"
user = "kiosk"
```


### 4.5.3 Configuring labwc
Create:
`sudo -u kiosk mkdir -p /home/kiosk/.config/labwc`

<div style="page-break-before: always;"></div>

## 4.6 GTK Login Application
### 4.6.1 Application Overview
### 4.6.2 User Interface
### 4.6.3 Credential Handling

<div style="page-break-before: always;"></div>

## 4.7 RDP Integration
### 4.7.1 Connection Workflow
### 4.7.2 Connection Parameters

<div style="page-break-before: always;"></div>

## 4.8 Security Hardening

### 4.8.1 Remove Desktop Escape Route
### 4.8.2 Restrict Kiosk User
### 4.8.3 Protect Credentials
