# ---------------------------------------------------------------------------
# Web service for MTDA
# ---------------------------------------------------------------------------
#
# This software is a part of MTDA.
# Copyright (C) 2023 Siemens Digital Industries Software
#
# ---------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# ---------------------------------------------------------------------------

from flask import Flask, render_template, request, session, send_from_directory
from flask_socketio import SocketIO
from urllib.parse import urlparse

import secrets
import threading
import uuid

import mtda.constants as CONSTS

app = Flask("mtda")
app.config["mtda"] = None
socket = SocketIO(app)


@app.route("/")
def index():
    return render_template("index.html")


@app.route('/assets/<path:path>')
def assets_dir(path):
    return send_from_directory('assets', path)


@app.route('/novnc/<path:path>')
def novnc_dir(path):
    return send_from_directory('/usr/share/novnc', path)


@socket.on("connect", namespace="/mtda")
def connect():
    session['id'] = uuid.uuid4().hex
    mtda = app.config['mtda']
    if mtda is not None:
        version = mtda.agent_version()
        socket.emit("mtda-version", {"version": version}, namespace="/mtda")

        data = mtda.console_dump()
        socket.emit("console-output", {"output": data}, namespace="/mtda")

        if mtda.video is not None:
            fmt = mtda.video.format
            url = urlparse(request.base_url)
            url = mtda.video.url(host=url.hostname)
            info = {"format": fmt, "url": url}
            socket.emit("video-info", info, namespace="/mtda")


@socket.on("console-input", namespace="/mtda")
def console_input(data):
    sid = session_id()
    mtda = app.config['mtda']
    if mtda is not None:
        mtda.console_send(data['input'], raw=False, session=sid)


@app.route('/keyboard-input')
def keyboard_input():
    mtda = app.config['mtda']
    map = {
      "Esc": mtda.keyboard.esc,
      "F1": mtda.keyboard.f1,
      "F2": mtda.keyboard.f2,
      "F3": mtda.keyboard.f3,
      "F4": mtda.keyboard.f4,
      "F5": mtda.keyboard.f5,
      "F6": mtda.keyboard.f6,
      "F7": mtda.keyboard.f7,
      "F8": mtda.keyboard.f8,
      "F9": mtda.keyboard.f9,
      "F10": mtda.keyboard.f10,
      "F11": mtda.keyboard.f11,
      "F12": mtda.keyboard.f12,
      "Backspace": mtda.keyboard.backspace,
      "Tab": mtda.keyboard.tab,
      "Caps Lock": mtda.keyboard.capsLock,
      "Enter": mtda.keyboard.enter,
      "Left": mtda.keyboard.left,
      "Right": mtda.keyboard.right,
      "Up": mtda.keyboard.up,
      "Down": mtda.keyboard.down
    }
    if mtda is not None and mtda.keyboard is not None:
        input = request.args.get('input', '', type=str)
        if len(input) > 1:
            if input in map:
                map[input]()
        else:
            mtda.keyboard.write(input)
    return ''


@app.route('/power-toggle')
def power_toggle():
    sid = session_id()
    mtda = app.config['mtda']
    if mtda is not None:
        return mtda.target_toggle(session=sid)
    return ''


def session_id():
    sid = None
    if 'id' in session:
        sid = session['id']
    return sid


class Service:
    def __init__(self, mtda):
        self.mtda = mtda
        self._host = CONSTS.DEFAULTS.WWW_HOST
        self._port = CONSTS.DEFAULTS.WWW_PORT
        app.config['SECRET_KEY'] = secrets.token_hex(16)
        app.config['mtda'] = mtda

    def configure(self, conf):
        if 'host' in conf:
            self._host = conf['host']
        if 'port' in conf:
            self._port = int(conf['port'])

    @property
    def host(self):
        return self._host

    def notify(self, what, event):
        if what == CONSTS.EVENTS.POWER:
            socket.emit("power-event", {"event": event}, namespace="/mtda")
        elif what == CONSTS.EVENTS.SESSION:
            socket.emit("session-event", {"event": event}, namespace="/mtda")
        elif what == CONSTS.EVENTS.STORAGE:
            socket.emit("storage-event", {"event": event}, namespace="/mtda")

    @property
    def port(self):
        return self._port

    def run(self):
        return socket.run(app, debug=False, use_reloader=False,
                          port=self._port, host=self._host)

    def start(self):
        self._thread = threading.Thread(target=self.run)
        return self._thread.start()

    def stop(self):
        socket.stop()

    def write(self, topic, data):
        if topic == CONSTS.CHANNEL.CONSOLE:
            socket.emit("console-output", {"output": data}, namespace="/mtda")
