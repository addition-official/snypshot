#!/usr/bin/python3 -I
"""
snypshot - a tiny Lightshot-style screenshot tool for Linux.

  snypshot              take a screenshot (Print Screen runs this; `shot` works too)
  snypshot --setup      install everything in one go (run as yourself; asks for sudo)
  snypshot --install    just the per-user part: app menu, Print Screen key, GNOME helper
  snypshot --uninstall  remove snypshot completely
  snypshot --preferences  change the shortcut, saving, keys and looks
  snypshot --doctor     check the setup and do a test capture (nothing is saved)
  snypshot --quit       stop the background copy
  snypshot --once       one screenshot without the background copy
  snypshot --allow-portal / --disallow-portal   GNOME fallback without the helper (opt-in)

Install (GNOME on Wayland, tested on Ubuntu 24.04):
  python3 snypshot.py --setup        then log out and back in once

  Drag                  select an area
  Drag inside / edges   move / resize the selection (like Lightshot)
  Right-side toolbar    pen, line, arrow, box, marker, text, color, undo
  Mouse wheel           down = bigger, up = smaller (brush / text size)
  Shift while drawing   straight 45-degree lines, square boxes
  Enter / Ctrl+C        copy to clipboard and close
  Ctrl+S                save to a file
  Ctrl+Z / Ctrl+Y       undo / redo
  Esc / right-click     cancel

Privacy: on GNOME Wayland the screen is read only by a small helper inside GNOME Shell,
which hands screenshots solely to the root-installed snypshot it started itself, over a
private pipe. The overlay is a native Wayland window other apps can't read. See the
"Security model" notes further down for details.
"""

import os
import sys

RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/snypshot-{os.getuid()}"
SOCK = os.path.join(RUNTIME_DIR, "snypshot", "snypshot.sock")
VERSION = "1.0"   # bump on every release: a newer `snypshot` replaces an older running copy


def send(cmd, timeout=1.0):  # noqa: E302
    """Talk to the background copy. Returns its reply, or None if it isn't running."""
    import socket
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(SOCK)
        s.sendall(cmd.encode() + b"\n")
        reply = s.recv(256).decode().strip()
        s.close()
        return reply or None
    except OSError:
        return None


def _root_only(path):
    """True if path (or, if it doesn't exist yet, its nearest existing parent) and every
    folder above it are owned by root and not writable by anyone else."""
    path = os.path.realpath(path)
    while not os.path.exists(path) and path != "/":
        path = os.path.dirname(path)
    while True:
        try:
            st = os.stat(path)
        except OSError:
            return False
        if st.st_uid != 0 or st.st_mode & 0o022:
            return False
        if path == "/":
            return True
        path = os.path.dirname(path)


if __name__ == "__main__" and (not sys.flags.isolated
                               or not _root_only(os.path.realpath(sys.executable))):
    # Isolated mode (-I) with the root-owned system Python: ignores PYTHON* variables,
    # your user site-packages and the current folder. Re-run ourselves that way before
    # importing anything else.
    os.execve("/usr/bin/python3", ["/usr/bin/python3", "-I", os.path.abspath(sys.argv[0])]
              + sys.argv[1:],
              {k: v for k, v in os.environ.items() if not k.startswith(("LD_", "PYTHON"))})

# Only import from folders nobody but root can change.
sys.path[:] = [p for p in sys.path if _root_only(p)]

OLD_NAME = "shot"                 # what snypshot was called before; `shot` stays as an alias
BIN = "/usr/local/bin/snypshot"
ALIAS = "/usr/local/bin/shot"
ALIAS_CODE = f"""#!/usr/bin/python3 -I
# `shot` is a short alias for snypshot (a Lightshot-style screenshot tool).
import os, sys
os.execv({BIN!r}, [{BIN!r}] + sys.argv[1:])
"""


def _ours(path):
    """True if path is missing, or is a copy of snypshot / its alias / the old `shot`."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return b"Lightshot-style" in head


def setup():
    """One command for everything: dependencies, the program itself, the `shot` alias,
    then the per-user part (--install). Uses only the standard library, so it works
    before the dependencies are there."""
    import subprocess, tempfile
    sys.stdout.reconfigure(line_buffering=True)  # keep our lines in order with sudo's
    me = os.path.realpath(__file__)
    if os.geteuid() == 0:
        sys.exit("Run this as yourself, without sudo. It asks for your password when needed.")
    desk = os.environ.get("XDG_CURRENT_DESKTOP", "")
    wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"
    print("Setting up snypshot.")
    if "gnome" not in desk.lower() or not wayland:
        print(f"  Heads up: snypshot is made for GNOME on Wayland (you're on "
              f"{desk or 'an unknown desktop'}, {'Wayland' if wayland else 'X11'}). Carrying on anyway.")

    def run(cmd):
        print("  $ " + " ".join(cmd))
        return subprocess.run(cmd).returncode == 0

    probe = ("import gi; gi.require_version('Gtk', '4.0'); gi.require_version('PangoCairo', '1.0');"
             "from gi.repository import Gtk, PangoCairo; import PIL, cairo")
    need = subprocess.run(["/usr/bin/python3", "-I", "-c", probe],
                          capture_output=True).returncode != 0
    tray = subprocess.run(["/usr/bin/python3", "-I", "-c",
                           "import gi; gi.require_version('AyatanaAppIndicator3', '0.1')"],
                          capture_output=True).returncode == 0
    notify = os.path.exists("/usr/bin/notify-send")
    if need or not tray or not notify:
        pkgs = None
        if os.path.exists("/usr/bin/apt-get"):
            pkgs = (["/usr/bin/apt-get", "install", "-y"],
                    ["python3-gi", "python3-gi-cairo", "gir1.2-gtk-4.0", "python3-pil",
                     "gir1.2-ayatanaappindicator3-0.1", "libnotify-bin"])
        elif os.path.exists("/usr/bin/dnf"):
            pkgs = (["/usr/bin/dnf", "install", "-y"],
                    ["python3-gobject", "gtk4", "python3-pillow",
                     "libayatana-appindicator-gtk3", "libnotify"])
        elif os.path.exists("/usr/bin/pacman"):
            pkgs = (["/usr/bin/pacman", "-S", "--needed", "--noconfirm"],
                    ["python-gobject", "python-cairo", "gtk4", "python-pillow",
                     "libayatana-appindicator", "libnotify"])
        print("1/3 Installing what snypshot needs (asks for your password):")
        if pkgs is None:
            if need:
                sys.exit("  Couldn't find apt, dnf or pacman. Install PyGObject with GTK 4, "
                         "Pillow and pycairo, then run this again.")
        elif not run(["/usr/bin/sudo", *pkgs[0], *pkgs[1]]) and need:
            sys.exit("  Installing the dependencies failed (see above).")
    else:
        print("1/3 Dependencies: already there.")

    print("2/3 Installing snypshot to /usr/local/bin:")
    if not (_ours(BIN) and run(["/usr/bin/sudo", "install", "-m", "755", me, BIN] if me != BIN
                                else ["true"])):
        sys.exit(f"  Couldn't install {BIN}.")
    if _ours(ALIAS):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(ALIAS_CODE)
        ok = run(["/usr/bin/sudo", "install", "-m", "755", f.name, ALIAS])
        os.unlink(f.name)
        if not ok:
            print(f"  (Couldn't add the `shot` alias; `snypshot` works.)")
    else:
        print(f"  {ALIAS} belongs to another program, so no `shot` alias; use `snypshot`.")

    print("3/3 Setting it up for you:")
    os.execv(BIN, [BIN, "--install", "--from-setup"])


if __name__ == "__main__" and sys.argv[1:2] == ["--setup"]:
    setup()

# Fast path for the Print Screen key: if snypshot is already running, just poke it
# and exit before loading anything heavy.
if __name__ == "__main__" and sys.argv[1:] in ([], ["--capture"]):
    if send("version") == VERSION and send("capture") == "ok":
        sys.exit(0)                               # (an older running copy: see main)



import colorsys
import datetime
import socket
import io
import json
import math
import re
import shutil
import signal
import subprocess
import time

from PIL import Image, ImageColor, ImageDraw, ImageFont

WAYLAND = (bool(os.environ.get("WAYLAND_DISPLAY"))
           or os.environ.get("XDG_SESSION_TYPE") == "wayland")
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                      "snypshot", "config.json")

# Same order as Lightshot's vertical toolbar.
TOOLS = ["pen", "line", "arrow", "rect", "marker", "text"]
DRAW_TOOLS = ("pen", "line", "arrow", "rect", "marker")
TIPS = {"pen": "Pen", "line": "Line", "arrow": "Arrow", "rect": "Rectangle",
        "marker": "Marker", "text": "Text", "color": "Color", "undo": "Undo (Ctrl+Z)",
        "copy": "Copy (Ctrl+C)", "save": "Save (Ctrl+S)", "close": "Close (Esc)"}

# The 48 "Basic colors" from the classic Windows color dialog Lightshot uses.
BASIC_COLORS = [
    "#ff8080", "#ffff80", "#80ff80", "#00ff80", "#80ffff", "#0080ff", "#ff80c0", "#ff80ff",
    "#ff0000", "#ffff00", "#80ff00", "#00ff40", "#00ffff", "#0080c0", "#8080c0", "#ff00ff",
    "#804040", "#ff8040", "#00ff00", "#008080", "#004080", "#8080ff", "#800040", "#ff0080",
    "#800000", "#ff8000", "#008000", "#008040", "#0000ff", "#0000a0", "#800080", "#8000ff",
    "#400000", "#804000", "#004000", "#004040", "#000080", "#000040", "#400040", "#400080",
    "#000000", "#808000", "#808040", "#808080", "#408080", "#c0c0c0", "#400040", "#ffffff",
]

BAR_BG = "#f4f4f4"
BAR_EDGE = "#9a9a9a"
HOVER_BG = "#e2e2e2"
HOVER_EDGE = "#c2c2c2"
ACTIVE_BG = "#d4e5fb"
ACTIVE_EDGE = "#7ba7e1"
ICON_RGB = (55, 55, 55)
FONT_FAMILY = "DejaVu Sans"

# Sizes at 100% scale; everything is multiplied by the UI scale.
BTN = 30        # toolbar button
ICON = 20       # icon inside a button
FONT = 13       # UI text, px


# ---------------------------------------------------------------- helpers

# ---- security helpers -------------------------------------------------------------
#
# snypshot handles screenshots, so it never trusts anything a non-root program could
# have planted: helper programs come only from root-owned system folders (never from
# ~/.local/bin via $PATH), scratch files live in a private folder, and child
# processes get an environment scrubbed of code-loading variables.

TRUSTED_DIRS = ("/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin")

# Environment variables that make a program load code from somewhere else.
# Child processes get ONLY these variables (an allowlist: anything else - LD_PRELOAD,
# PYTHONPATH, GTK/GIO/Tcl module paths, fontconfig overrides... - is dropped).
SAFE_ENV = ("HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "DISPLAY", "WAYLAND_DISPLAY",
            "XAUTHORITY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP",
            "XDG_SESSION_DESKTOP", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
            "XDG_STATE_HOME", "XDG_CONFIG_DIRS", "XDG_DATA_DIRS", "DBUS_SESSION_BUS_ADDRESS",
            "GDK_SCALE", "GDK_DPI_SCALE", "SNYPSHOT_SCALE")
SAFE_PATH = "/usr/local/bin:/usr/bin:/bin"


def root_owned(path):
    """True if path and every folder above it belong to root and only root can change
    them - i.e. nothing running as you could have swapped it."""
    import stat
    path = os.path.abspath(path)
    while True:
        try:
            st = os.lstat(path)
        except OSError:
            return False
        if stat.S_ISLNK(st.st_mode):
            try:
                target = os.path.join(os.path.dirname(path), os.readlink(path))
            except OSError:
                return False
            if not root_owned(target) or st.st_uid != 0:
                return False
        elif st.st_uid != 0 or st.st_mode & 0o022:
            return False
        parent = os.path.dirname(path)
        if parent == path:
            return True
        path = parent


_tool_cache = {}


def tool(name):
    """Absolute path of a system program, only if it's root-owned and in a system folder."""
    if name not in _tool_cache:
        _tool_cache[name] = next((os.path.join(d, name) for d in TRUSTED_DIRS
                                  if os.path.isfile(os.path.join(d, name))
                                  and root_owned(os.path.join(d, name))), None)
    return _tool_cache[name]


def T(name):
    p = tool(name)
    if not p:
        raise FileNotFoundError(f"{name} (not installed in a system folder)")
    return p


def have(cmd):
    return tool(cmd) is not None


def clean_env():
    """The minimal environment our child processes get (see SAFE_ENV)."""
    env = {k: v for k, v in os.environ.items() if k in SAFE_ENV or k.startswith("LC_")}
    env["PATH"] = SAFE_PATH
    if WAYLAND:                       # never let a child fall back to X11 on Wayland
        env.pop("DISPLAY", None)
        env.pop("XAUTHORITY", None)
    return env


def no_dumps():
    """Mark this process non-dumpable: no core dump or crash report can contain a
    screenshot, and no other program running as you can attach a debugger to it."""
    try:
        import ctypes
        ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)   # PR_SET_DUMPABLE = 4
    except Exception as e:
        log(f"couldn't disable core dumps: {e}")


def private_dir():
    """$XDG_RUNTIME_DIR/snypshot: owned by us, mode 0700, not a symlink. Screenshots only
    ever touch disk in here."""
    import stat
    base = RUNTIME_DIR
    for d in (base, os.path.join(base, "snypshot")):
        try:
            os.mkdir(d, 0o700)
        except FileExistsError:
            pass
        st = os.lstat(d)
        if stat.S_ISLNK(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise PermissionError(f"{d} isn't private to you (owner/permissions/symlink); "
                                  "refusing to use it")
    return os.path.join(base, "snypshot")


APP_ID = "io.github.snypshot"

# ---- optional GNOME Shell helper: instant, silent screenshots (no portal sound/flash)

EXT_UUID = "snypshot@io.github.snypshot"
EXT_METADATA = """{
  "uuid": "snypshot@io.github.snypshot",
  "name": "snypshot helper",
  "description": "Hands screenshots to the snypshot screenshot tool instantly, without the portal's sound and flash. It never gives screenshots to anything except a verified, root-installed copy of snypshot.",
  "shell-version": ["45", "46", "47", "48", "49", "50"]
}
"""

# Security model of the helper extension
# -------------------------------------
# GNOME only lets GNOME Shell itself read the screen silently. The helper extension
# runs inside GNOME Shell, and it:
#   * STARTS the snypshot background process itself: the root-owned /usr/local/bin/snypshot,
#     run by the root-owned system Python in isolated mode (-I), with an environment
#     scrubbed of every variable that could inject code;
#   * hands screenshots ONLY over that process's private stdin pipe, which no other
#     program can read or write. There is no method that returns pixels to a caller;
#   * refuses to send anything while snypshot is being traced/debugged. Because GNOME
#     Shell is snypshot's parent, no other program is its ancestor, so under the kernel's
#     Yama ptrace rules (Ubuntu's default) nothing else can attach to it either.
# The only D-Bus methods are Start() (make sure snypshot is running) and Check() (status
# text); neither takes or shows a screenshot. Captures are requested by snypshot itself,
# which only takes orders from you over its private per-user socket.
EXT_JS_TEMPLATE = r"""// snypshot helper - see the security notes in the snypshot script itself.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const SCRIPT = @SCRIPT@;
const PYTHON = @PYTHON@;
// snypshot gets ONLY these environment variables (allowlist), plus a fixed PATH.
const SAFE_ENV = ['HOME', 'USER', 'LOGNAME', 'LANG', 'LANGUAGE', 'DISPLAY', 'WAYLAND_DISPLAY',
    'XAUTHORITY', 'XDG_RUNTIME_DIR', 'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP',
    'XDG_SESSION_DESKTOP', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME',
    'XDG_STATE_HOME', 'XDG_CONFIG_DIRS', 'XDG_DATA_DIRS', 'DBUS_SESSION_BUS_ADDRESS',
    'GDK_SCALE', 'GDK_DPI_SCALE', 'SNYPSHOT_SCALE'];
const MAX_LINE = 64;
const WAYLAND_SESSION = GLib.getenv('WAYLAND_DISPLAY') !== null;

const IFACE = `<node>
  <interface name="io.github.snypshot.Helper">
    <method name="Start"/>
    <method name="Check">
      <arg type="b" direction="out" name="ok"/><arg type="s" direction="out" name="why"/>
    </method>
  </interface>
</node>`;

// Path and every folder above it owned by root and writable only by root.
function rootOwned(path) {
    try {
        for (let p = path; ; p = GLib.path_get_dirname(p)) {
            const info = Gio.File.new_for_path(p).query_info(
                'unix::uid,unix::mode,standard::is-symlink',
                Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, null);
            if (info.get_is_symlink() || info.get_attribute_uint32('unix::uid') !== 0 ||
                (info.get_attribute_uint32('unix::mode') & 0o022))
                return false;
            if (p === '/')
                return true;
        }
    } catch (e) {
        return false;
    }
}

function tracerOf(pid) {
    try {
        const [, bytes] = GLib.file_get_contents(`/proc/${pid}/status`);
        const m = new TextDecoder().decode(bytes).match(/^TracerPid:\s*(\d+)/m);
        return m ? m[1] : '?';
    } catch (e) {
        return '?';
    }
}

export default class ShotHelper extends Extension {
    enable() {
        this._enabled = true;
        this._proc = null;
        this._why = 'starting';
        this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
        this._dbus.export(Gio.DBus.session, '/io/github/snypshot/Helper');
        this._name = Gio.bus_own_name_on_connection(Gio.DBus.session,
            'io.github.snypshot.Helper', Gio.BusNameOwnerFlags.NONE, null, null);
        // Wayland doesn't let a background app focus its own new window, so when snypshot
        // opens its overlay, GNOME Shell gives it the keyboard (for Esc, Ctrl+C...).
        this._winSig = global.display.connect('window-created', (display, win) => {
            if (!this._proc || win.get_pid() !== this._pid ||
                win.get_client_type() !== Meta.WindowClientType.WAYLAND)
                return;
            if (Main.overview.visible)              // snypshot must be on top, not
                Main.overview.hide();               // hidden behind Activities
            // Once the overlay is on its final monitor, give it the keyboard if that's
            // the monitor your mouse is on (so Esc, Ctrl+C and typing go there).
            const id = win.connect('shown', () => {
                win.disconnect(id);
                this._focusSoon();
            });
        });
        this._start();
    }

    // After snypshot's overlays have appeared (one per monitor), give the keyboard to the
    // one on the monitor your mouse is on. Waits a moment so it runs after GNOME's own
    // focus-on-map for the last window.
    _focusSoon() {
        if (this._focusId)
            GLib.source_remove(this._focusId);
        this._focusId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 80, () => {
            this._focusId = 0;
            const mon = global.display.get_current_monitor();
            const ours = global.get_window_actors().map(a => a.meta_window).filter(w =>
                this._proc && w.get_pid() === this._pid &&
                w.get_client_type() === Meta.WindowClientType.WAYLAND);
            // the screenshot overlay (fullscreen) first, so an open Preferences
            // window doesn't keep the keyboard; then anything else of ours (dialogs)
            const full = ours.filter(w => w.is_fullscreen());
            const target = full.find(w => w.get_monitor() === mon) ?? full[0] ??
                ours.find(w => w.get_monitor() === mon) ?? ours[0];
            if (target)
                Main.activateWindow(target);
            return GLib.SOURCE_REMOVE;
        });
    }

    disable() {
        this._enabled = false;
        if (this._focusId)
            GLib.source_remove(this._focusId);
        this._focusId = 0;
        if (this._winSig)
            global.display.disconnect(this._winSig);
        this._winSig = 0;
        if (this._restartId)
            GLib.source_remove(this._restartId);
        this._restartId = 0;
        this._dbus?.unexport();
        this._dbus = null;
        if (this._name)
            Gio.bus_unown_name(this._name);
        this._name = 0;
        const proc = this._proc;
        this._proc = null;
        proc?.force_exit();
    }

    _start() {
        if (this._proc || !this._enabled)
            return;
        if (!rootOwned(SCRIPT) || !rootOwned(PYTHON)) {
            this._why = `refusing: ${SCRIPT} or ${PYTHON} is not a root-owned install`;
            console.warn(`snypshot helper: ${this._why}`);
            return;
        }
        const env = GLib.get_environ().filter(kv => {
            const key = kv.split('=')[0];
            if ((key === 'DISPLAY' || key === 'XAUTHORITY') && WAYLAND_SESSION)
                return false;                   // on Wayland snypshot must never use X11
            return SAFE_ENV.includes(key) || key.startsWith('LC_');
        });
        env.push('PATH=/usr/local/bin:/usr/bin:/bin');
        const launcher = new Gio.SubprocessLauncher({
            flags: Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE,
        });
        launcher.set_environ(env);
        launcher.set_cwd('/');
        let proc;
        try {
            proc = launcher.spawnv([PYTHON, '-I', SCRIPT, '--daemon', '--foreground', '--helper']);
        } catch (e) {
            this._why = `could not start snypshot: ${e.message}`;
            return;
        }
        this._proc = proc;
        this._pid = Number(proc.get_identifier());
        this._stdin = proc.get_stdin_pipe();
        this._stdout = proc.get_stdout_pipe();
        this._buf = '';
        this._ready = false;
        this._busy = false;
        this._waiting = [];
        this._why = 'starting';
        this._started = GLib.get_monotonic_time();
        this._read(proc);
        proc.wait_async(null, () => {
            if (this._proc !== proc)
                return;
            this._proc = null;
            // came down (crash, `snypshot --quit`): bring it back, backing off if it
            // keeps dying quickly
            const ranLong = GLib.get_monotonic_time() - this._started > 30 * 1000000;
            this._fails = ranLong ? 0 : (this._fails ?? 0) + 1;
            const delay = Math.min(60, 3 * 2 ** Math.min(this._fails, 5));
            this._why = `snypshot stopped; restarting in ${delay}s`;
            if (this._enabled)
                this._restartId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, delay, () => {
                    this._restartId = 0;
                    this._start();
                    return GLib.SOURCE_REMOVE;
                });
        });
    }

    // Read snypshot's requests: short ASCII lines only. Anything else = protocol error,
    // and we stop that snypshot process (it'll be restarted).
    _read(proc) {
        this._stdout.read_bytes_async(256, GLib.PRIORITY_DEFAULT, null, (stream, res) => {
            if (this._proc !== proc)
                return;
            let bytes;
            try {
                bytes = stream.read_bytes_finish(res).toArray();
            } catch (e) {
                return;
            }
            if (bytes.length === 0)
                return;                                   // snypshot closed the pipe
            for (const b of bytes) {
                if (b === 10) {
                    this._line(this._buf);
                    this._buf = '';
                } else if (b >= 32 && b < 127 && this._buf.length < MAX_LINE) {
                    this._buf += String.fromCharCode(b);
                } else {
                    console.warn('snypshot helper: protocol error, restarting snypshot');
                    proc.force_exit();
                    return;
                }
            }
            this._read(proc);
        });
    }

    _line(line) {
        let m;
        if (line === 'ready') {
            this._ready = true;
            this._why = 'ready';
        } else if ((m = line.match(/^capture ([0-9]{1,9})$/))) {
            this._shoot(m[1]);
        }
    }

    // Take a screenshot and give it to OUR snypshot process only, over its private pipe.
    _shoot(id) {
        if (!this._proc || !this._ready)
            return;
        if (this._busy) {                                  // answer it with the same snypshot
            if (this._waiting.length < 8)
                this._waiting.push(id);
            return;
        }
        const proc = this._proc;
        if (tracerOf(this._pid) !== '0') {
            console.warn('snypshot helper: snypshot is being debugged/traced; not sending it the screen');
            this._send(proc, id, null);
            return;
        }
        this._busy = true;
        // One capture per monitor: GNOME renders each at that monitor's own scale, so
        // a 100% monitor next to a 125% one isn't blown up (and blurred) to 125%.
        const mons = Main.layoutManager.monitors.map(m => [m.x, m.y, m.width, m.height]);
        const parts = [];
        const finish = ok => {
            this._busy = false;
            if (this._proc !== proc)
                return;
            let payload = null;
            if (ok && tracerOf(this._pid) === '0') {   // check again before handing it over
                const chunks = [];
                for (const [[x, y, w, h], png] of parts) {
                    chunks.push(new TextEncoder().encode(`MON ${x} ${y} ${w} ${h} ${png.length}\n`));
                    chunks.push(png);
                }
                payload = new Uint8Array(chunks.reduce((n, c) => n + c.length, 0));
                let o = 0;
                for (const c of chunks) {
                    payload.set(c, o);
                    o += c.length;
                }
            }
            for (const i of [id, ...this._waiting.splice(0)])
                this._send(proc, i, payload);
        };
        const next = () => {
            if (parts.length === mons.length) {
                finish(true);
                return;
            }
            const [x, y, w, h] = mons[parts.length];
            const mem = Gio.MemoryOutputStream.new_resizable();
            try {
                new Shell.Screenshot().screenshot_area(x, y, w, h, mem, (obj, res) => {
                    try {
                        obj.screenshot_area_finish(res);
                        mem.close(null);
                        parts.push([[x, y, w, h], mem.steal_as_bytes().toArray()]);
                    } catch (e) {
                        console.warn(`snypshot helper: screenshot failed: ${e.message}`);
                        finish(false);
                        return;
                    }
                    next();
                });
            } catch (e) {
                console.warn(`snypshot helper: screenshot failed: ${e.message}`);
                finish(false);
            }
        };
        next();
    }

    _send(proc, id, payload) {
        const data = payload ?? new Uint8Array(0);
        const header = new TextEncoder().encode(`${payload ? 'IMG' : 'FAIL'} ${id} ${data.length}\n`);
        const frame = new Uint8Array(header.length + data.length);
        frame.set(header, 0);
        frame.set(data, header.length);
        this._stdin.write_all_async(frame, GLib.PRIORITY_DEFAULT, null, (s, res) => {
            try {
                s.write_all_finish(res);
            } catch (e) {
                console.warn(`snypshot helper: could not hand over screenshot: ${e.message}`);
            }
        });
    }

    // Make sure snypshot is running (e.g. Print Screen right after it crashed). This can't
    // take or show a screenshot - captures are only requested by snypshot itself, which
    // only listens to you (its socket is private to your user).
    Start() {
        const now = GLib.get_monotonic_time();
        if (now - (this._lastAsk ?? 0) < 1000000)          // at most once a second
            return;
        this._lastAsk = now;
        if (!this._proc) {
            if (this._restartId)
                GLib.source_remove(this._restartId);
            this._restartId = 0;
            this._start();
        }
    }

    Check() {
        return [Boolean(this._proc && this._ready), this._why];
    }
}
"""


def ext_dir():
    data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(data, "gnome-shell", "extensions", EXT_UUID)


class HelperChannel:
    """Private pipe to the GNOME helper that started us (only in --helper mode).

    Our stdin is where the helper writes screenshots; our stdout is where we ask for
    them. Both are moved to private file descriptors first, so nothing else in snypshot
    (a stray print, a library warning) can ever write into the protocol."""

    def __init__(self):
        import threading
        self.inp = os.fdopen(os.dup(0), "rb")
        self.out = os.fdopen(os.dup(1), "wb", buffering=0)
        devnull = os.open(os.devnull, os.O_RDWR)
        logfd = log_fd()
        os.dup2(devnull, 0)
        os.dup2(logfd, 1)
        os.dup2(logfd, 2)
        self.lock = threading.Lock()
        self.event = threading.Event()
        self.want = None
        self.data = None
        self.eof = False
        self.seq = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        f = self.inp
        while True:
            line = f.readline(80)
            parts = line.split()
            if (not line or len(parts) != 3 or parts[0] not in (b"IMG", b"FAIL")
                    or not re.fullmatch(rb"[0-9]{1,9}", parts[1])
                    or not re.fullmatch(rb"[0-9]{1,10}", parts[2])):
                self.eof = True                      # helper gone (or garbage): stop
                self.event.set()
                return
            n = int(parts[2])
            if n > 1 << 30:
                self.eof = True
                self.event.set()
                return
            data = f.read(n) if n else b""
            if len(data) != n:
                self.eof = True
                self.event.set()
                return
            with self.lock:
                if parts[1].decode() == self.want:      # anything unrequested is dropped
                    self.data = data if parts[0] == b"IMG" else None
                    self.event.set()

    def say(self, line):
        self.out.write(line.encode() + b"\n")

    def request(self, timeout=4):
        with self.lock:
            self.seq += 1
            self.want = str(self.seq)
            self.data = None
            self.event.clear()
        try:
            self.say(f"capture {self.want}")
        except OSError:
            self.eof = True
            return None
        self.event.wait(timeout)
        with self.lock:
            data, self.want = self.data, None
        return data


HELPER = None


def parse_parts(data):
    """The helper's payload: per monitor, 'MON x y w h len' + PNG. (A bare PNG, from an
    older helper, is one image of the whole desktop.)"""
    global _old_helper
    _old_helper = data.startswith(b"\x89PNG")
    if _old_helper:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img.convert("RGB")
    parts, pos = [], 0
    while pos < len(data):
        end = data.index(b"\n", pos, pos + 80)
        m = re.fullmatch(rb"MON (-?\d{1,6}) (-?\d{1,6}) (\d{1,6}) (\d{1,6}) (\d{1,10})",
                         data[pos:end])
        if not m:
            raise ValueError("bad helper payload")
        x, y, w, h, n = (int(v) for v in m.groups())
        img = Image.open(io.BytesIO(data[end + 1:end + 1 + n]))
        img.load()
        parts.append(((x, y, w, h), img.convert("RGB")))
        pos = end + 1 + n
    if not parts:
        raise ValueError("empty helper payload")
    return parts


def grab_helper():
    if HELPER is None or HELPER.eof:
        return None
    data = HELPER.request()
    if not data:
        log("GNOME helper didn't send a screenshot")
        return None
    try:
        return parse_parts(data)
    except Exception as e:
        log(f"GNOME helper sent something unreadable: {e}")
        return None


def helper_call(method, reply_type, timeout):
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    return bus.call_sync("io.github.snypshot.Helper", "/io/github/snypshot/Helper",
                         "io.github.snypshot.Helper", method, None,
                         GLib.VariantType(reply_type) if reply_type else None,
                         Gio.DBusCallFlags.NO_AUTO_START, timeout, None)


def helper_active():
    try:
        helper_call("Check", "(bs)", 1500)
        return True
    except Exception:
        return False


def helper_expected():
    """Our helper extension is installed and switched on (it may not be loaded yet,
    e.g. right at login)."""
    if "gnome" not in os.environ.get("XDG_CURRENT_DESKTOP", "").lower() or not WAYLAND:
        return False
    if not os.path.isfile(os.path.join(ext_dir(), "extension.js")) or not have("gsettings"):
        return False
    return (EXT_UUID in gset("get", "org.gnome.shell", "enabled-extensions")
            and gset("get", "org.gnome.shell", "disable-user-extensions") != "true")


def helper_status():
    try:
        ok, why = helper_call("Check", "(bs)", 3000).unpack()
        return "ready (instant, silent)" if ok else why
    except Exception as e:
        if "ServiceUnknown" not in str(e) and "NameHasNoOwner" not in str(e):
            return f"error: {e}"
        if helper_expected():
            return "installed; GNOME loads it when you log out and back in"
        return "not installed (run: snypshot --install, then log out and back in)"


def install_extension():
    """Put the helper extension in place and switch it on (active after next login)."""
    if "gnome" not in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
        print("The helper extension is only for GNOME; skipping it.")
        return
    if not root_owned(os.path.realpath(sys.executable)):
        print(f"Not installing the helper: {sys.executable} isn't a root-owned system Python.")
        return
    if not root_owned(SCRIPT):
        print(f"Not installing the helper: {SCRIPT} can be changed without root, so the\n"
              "helper couldn't trust it. Install snypshot system-wide first:\n"
              f"  sudo install -m 755 {SCRIPT} /usr/local/bin/snypshot\n"
              "  /usr/local/bin/snypshot --install")
        return
    if '"' in SCRIPT or "\\" in SCRIPT or "\n" in SCRIPT:
        print("Refusing: odd characters in the install path.")
        return
    d = ext_dir()
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "metadata.json"), "w") as f:
        f.write(EXT_METADATA)
    with open(os.path.join(d, "extension.js"), "w") as f:
        f.write(EXT_JS_TEMPLATE.replace("@SCRIPT@", json.dumps(SCRIPT))
                .replace("@PYTHON@", json.dumps(os.path.realpath(sys.executable))))
    enabled = False
    if have("gnome-extensions"):
        enabled = subprocess.run([T("gnome-extensions"), "enable", EXT_UUID],
                                 capture_output=True, env=clean_env()).returncode == 0
    if not enabled and have("gsettings"):              # shell hasn't seen it yet: pre-enable
        import ast
        raw = gset("get", "org.gnome.shell", "enabled-extensions").replace("@as ", "")
        try:
            exts = list(ast.literal_eval(raw))
        except Exception:
            exts = []
        if EXT_UUID not in exts:
            exts.append(EXT_UUID)
            gset("set", "org.gnome.shell", "enabled-extensions", str(exts))
    if gset("get", "org.gnome.shell", "disable-user-extensions") == "true":
        print("Note: user extensions are switched off in GNOME. Turn them on in the "
              "Extensions app, or snypshot will fall back to the slower portal.")
    print("GNOME helper installed (GNOME loads new versions of it when you log in).")
    return gset("get", "org.gnome.shell", "disable-user-extensions") != "true"


def uninstall_extension():
    if have("gnome-extensions"):
        subprocess.run([T("gnome-extensions"), "disable", EXT_UUID], capture_output=True, env=clean_env())
    shutil.rmtree(ext_dir(), ignore_errors=True)


def my_cgroup_unit():
    """The systemd unit we're running in - it decides which app the portal thinks we are."""
    try:
        with open("/proc/self/cgroup") as f:
            return f.read().strip().rsplit("/", 1)[-1]
    except OSError:
        return ""


def set_portal_permission(allow):
    """Whether GNOME's screenshot portal may serve io.github.snypshot without asking.

    Off unless you opt in with `snypshot --allow-portal`: the portal recognises apps by a
    launch label that any program can copy, so a stored "yes" would let other programs
    take (noisy, flashing) screenshots by pretending to be snypshot. The GNOME helper
    extension doesn't have that weakness and is the recommended fast path."""
    try:
        import gi  # noqa: F401
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        args = (GLib.Variant("(sbssas)", ("screenshot", True, "screenshot", APP_ID, ["yes"]))
                if allow else GLib.Variant("(sss)", ("screenshot", "screenshot", APP_ID)))
        bus.call_sync("org.freedesktop.impl.portal.PermissionStore",
                      "/org/freedesktop/impl/portal/PermissionStore",
                      "org.freedesktop.impl.portal.PermissionStore",
                      "SetPermission" if allow else "DeletePermission",
                      args, None, Gio.DBusCallFlags.NONE, 3000, None)
    except Exception as e:
        if allow or ("No entry" not in str(e) and "NotFound" not in str(e)):
            log(f"portal permission change: {e}")


def grab_portal():
    """Screenshot through the desktop portal (works on GNOME and KDE Wayland).
    The first time, your desktop may ask whether to allow it."""
    try:
        import gi
        from gi.repository import Gio, GLib
    except Exception:
        return None
    from urllib.parse import unquote, urlparse
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sender = bus.get_unique_name()[1:].replace(".", "_")
        import secrets
        token = "snypshot" + secrets.token_hex(8)
        req = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        loop, result = GLib.MainLoop(), {}

        def on_response(conn, name, path, iface, signal, params):
            code, res = params.unpack()
            result["code"], result["uri"] = code, res.get("uri")
            loop.quit()

        sub = bus.signal_subscribe("org.freedesktop.portal.Desktop",
                                   "org.freedesktop.portal.Request", "Response", req,
                                   None, Gio.DBusSignalFlags.NONE, on_response)
        opts = {"handle_token": GLib.Variant("s", token),
                "interactive": GLib.Variant("b", False)}
        bus.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                      "org.freedesktop.portal.Screenshot", "Screenshot",
                      GLib.Variant("(sa{sv})", ("", opts)), None,
                      Gio.DBusCallFlags.NONE, -1, None)
        GLib.timeout_add_seconds(60, loop.quit)
        loop.run()
        bus.signal_unsubscribe(sub)
        if result.get("code") != 0 or not result.get("uri"):
            log(f"portal said no (code {result.get('code')}). Use the GNOME helper "
                "(snypshot --install-extension) or opt in with snypshot --allow-portal")
            return None
        path = unquote(urlparse(result["uri"]).path)
        try:
            img = Image.open(path)
            img.load()
            return img.convert("RGB")
        finally:
            try:
                os.remove(path)  # GNOME's portal leaves a copy in ~/Pictures: remove it
            except OSError:
                pass
    except Exception as e:
        log(f"portal failed: {e}")
        return None


def grab_with(cmd_for, timeout=4):
    import secrets
    tmp = os.path.join(private_dir(), f"grab-{secrets.token_hex(8)}.png")
    cmd = cmd_for(tmp)
    try:
        r = subprocess.run(cmd, capture_output=True, env=clean_env(), text=True, timeout=timeout)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            img = Image.open(tmp).convert("RGB")
            os.remove(tmp)
            return img
        log(f"{cmd[0]} made no image (exit {r.returncode}): {r.stderr.strip()[:300]}")
    except subprocess.TimeoutExpired:
        name = os.path.basename(cmd[0])
        log(f"{name} hung for {timeout}s, giving up on it")
        subprocess.run([T("pkill"), "-f", f"^(/usr/bin/)?{name}( |$)"],   # don't leave it stuck
                       capture_output=True, env=clean_env())
    except Exception as e:
        log(f"{cmd[0]} failed: {e}")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return None


_working_method = None      # remembered while running in the background
_old_helper = False         # the GNOME part still loaded is an old one (log out to update)


def _set_method(m, secs=None):
    global _working_method
    if _working_method != m:
        log(f"capturing with {m}" + (f" ({secs:.2f}s)" if secs is not None else ""))
    _working_method = m


def grab_screen():
    """Capture every monitor as one image, using whatever this system supports."""
    if HELPER is not None:
        # Started by the GNOME helper: the private pipe is the ONLY way we capture.
        # (No silent fallback to other methods.)
        img = grab_helper()
        if img is not None:
            _set_method("ext")
            return img
        sys.exit("snypshot: the GNOME helper didn't hand over a screenshot (it refuses while "
                 "snypshot is being debugged). Details: ~/.cache/snypshot/snypshot.log")
    if not WAYLAND:  # X11
        try:
            from PIL import ImageGrab
            return ImageGrab.grab(all_screens=True).convert("RGB")
        except Exception:
            pass

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "gnome" in desktop or "unity" in desktop or "cinnamon" in desktop:
        # On GNOME the helper extension is the real path (see HELPER above). Without it:
        # gnome-screenshot (blocked on newer GNOME), and the portal only if opted in.
        methods = ["gnome"]           # (spectacle may go through the portal: opt-in only)
        if load_config().get("allow_portal"):
            methods.append("spectacle")
    elif "kde" in desktop:
        methods = ["spectacle", "gnome", "grim"]
    else:
        methods = ["grim", "gnome", "spectacle"]
    # GNOME's screenshot portal is only used if you opted in (snypshot --allow-portal).
    if load_config().get("allow_portal"):
        methods.insert(1, "portal")

    if _working_method in methods:          # try whatever worked last time first
        methods.remove(_working_method)
        methods.insert(0, _working_method)

    for m in methods:
        img = None
        t0 = time.time()
        if m == "grim" and have("grim"):
            try:
                out = subprocess.run([T("grim"), "-"], capture_output=True, env=clean_env(), timeout=10).stdout
                img = Image.open(io.BytesIO(out)).convert("RGB") if out else None
            except Exception:
                img = None
        elif m == "gnome" and have("gnome-screenshot"):
            img = grab_with(lambda t: [T("gnome-screenshot"), "-f", t])
        elif m == "spectacle" and have("spectacle"):
            img = grab_with(lambda t: [T("spectacle"), "-b", "-n", "-f", "-o", t])
        elif m == "portal":
            img = grab_portal()
        else:
            continue
        if img:
            _set_method(m, time.time() - t0)
            return img
        log(f"{m} didn't work ({time.time() - t0:.2f}s)")

    if "gnome" in desktop and not load_config().get("allow_portal"):
        if helper_expected():
            sys.exit("snypshot: log out and back in once to finish setting up snypshot "
                     "(GNOME only loads its helper at login)")
        sys.exit("snypshot: on GNOME, install snypshot system-wide and run snypshot --install "
                 "(see snypshot --doctor), or opt in to the slower portal: snypshot --allow-portal")
    hint = ("gnome-screenshot is installed but isn't working - details in ~/.cache/snypshot/snypshot.log"
            if ("gnome" in desktop or "unity" in desktop) and have("gnome-screenshot")
            else "sudo apt install gnome-screenshot" if "gnome" in desktop or "unity" in desktop
            else "sudo apt install kde-spectacle" if "kde" in desktop
            else "install grim (sway/Hyprland), gnome-screenshot (GNOME) or spectacle (KDE)")
    sys.exit(f"snypshot: couldn't capture the screen on this Wayland desktop "
             f"({desktop or 'unknown'}).\nFix: {hint}")


def copy_png(img):
    """Put a PNG on the clipboard. Returns False if no clipboard tool is installed."""
    buf = io.BytesIO()
    img.save(buf, "PNG")
    if WAYLAND:                       # X11 clipboard tools would expose it to X11 apps
        if not have("wl-copy"):
            return False
        cmd = [T("wl-copy"), "--type", "image/png"]
    elif have("xclip"):
        cmd = [T("xclip"), "-selection", "clipboard", "-t", "image/png", "-i"]
    else:
        return False
    subprocess.run(cmd, input=buf.getvalue(), stdout=subprocess.DEVNULL, env=clean_env(),
                   stderr=subprocess.DEVNULL, timeout=10)
    return True


def notify(msg):
    if have("notify-send"):
        subprocess.Popen([T("notify-send"), "-a", "snypshot", "Screenshot", msg], env=clean_env(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


DEFAULT_KEYS = {"copy": "<Control>c", "save": "<Control>s", "save_as": "<Control><Shift>s",
                "undo": "<Control>z", "redo": "<Control>y"}
DEFAULTS = {
    "color": "#ff0000", "width": 3, "custom": [None] * 16, "slot": 0, "ui_scale": None,
    "allow_portal": False, "last_dir": None,
    "hotkey": "Print",              # the key that takes a screenshot (GNOME shortcut)
    "save_mode": "last",            # Ctrl+S saves to: "last" folder used, or "fixed" save_dir
    "save_dir": None,
    "name_style": "number",         # Screenshot_7.png, or "date": Screenshot_2026-09-23_13-44-02
    "name_prefix": "Screenshot_",
    "format": "png",                # or "jpg"
    "jpg_quality": 95,
    "notify": True,                 # a notification after saving / copying
    "dim": 0.45,                    # how dark the area outside the selection is
    "show_size": True,              # the 800x600 label above the selection
    "tray": True,                   # tray icon
    "keys": dict(DEFAULT_KEYS),     # shortcuts inside the screenshot
}
ACCEL_RE = re.compile(r"(<(Control|Primary|Shift|Alt|Super|Meta|Hyper)>){0,4}[A-Za-z0-9_]{1,32}")


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(CONFIG) as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except Exception:
        pass
    # Validate everything: a broken or tampered config must never crash snypshot or put
    # odd values into the UI.
    hex_ok = lambda v: isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) is not None
    accel_ok = lambda v: isinstance(v, str) and ACCEL_RE.fullmatch(v) is not None
    pick = lambda k, ok: cfg.__setitem__(k, cfg[k] if ok(cfg.get(k)) else DEFAULTS[k])
    if not hex_ok(cfg.get("color")):
        cfg["color"] = "#ff0000"
    try:
        cfg["width"] = max(1, min(20, int(cfg.get("width", 3))))
    except (TypeError, ValueError):
        cfg["width"] = 3
    custom = cfg.get("custom") if isinstance(cfg.get("custom"), list) else []
    cfg["custom"] = [c if hex_ok(c) else None for c in (custom + [None] * 16)[:16]]
    cfg["slot"] = cfg["slot"] % 16 if isinstance(cfg.get("slot"), int) else 0
    u = cfg.get("ui_scale")
    cfg["ui_scale"] = float(u) if isinstance(u, (int, float)) and 0.5 <= u <= 3 else None
    cfg["allow_portal"] = cfg.get("allow_portal") is True
    for k in ("last_dir", "save_dir"):
        if not (isinstance(cfg.get(k), str) and os.path.isabs(cfg[k]) and os.path.isdir(cfg[k])):
            cfg[k] = None
    pick("hotkey", accel_ok)
    pick("save_mode", lambda v: v in ("last", "fixed"))
    pick("name_style", lambda v: v in ("number", "date"))
    pick("name_prefix", lambda v: isinstance(v, str) and len(v) <= 64 and not v.startswith(".")
         and re.fullmatch(r"[^/\\\x00-\x1f\x7f]*", v) is not None)
    pick("format", lambda v: v in ("png", "jpg"))
    pick("jpg_quality", lambda v: isinstance(v, int) and not isinstance(v, bool) and 50 <= v <= 100)
    pick("dim", lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 0.9)
    for k in ("notify", "show_size", "tray"):
        pick(k, lambda v: isinstance(v, bool))
    keys = cfg.get("keys") if isinstance(cfg.get("keys"), dict) else {}
    cfg["keys"] = {a: keys[a] if accel_ok(keys.get(a)) or keys.get(a) == "" else d
                   for a, d in DEFAULT_KEYS.items()}
    return {k: cfg[k] for k in DEFAULTS}


def save_config(cfg):
    """Write the whole config atomically (a crash can't leave half a file), private."""
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        tmp = CONFIG + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(cfg, f, indent=1)
        os.replace(tmp, CONFIG)
    except Exception:
        pass


def next_file_name(folder, cfg):
    """The next file name for Ctrl+S. Numbered: prefix + one past the highest number
    already in the folder (skipping ahead if that one exists too). Date: prefix + date
    and time, with _2, _3... if that name is taken."""
    prefix = cfg.get("name_prefix", "Screenshot_")
    ext = "jpg" if cfg.get("format") == "jpg" else "png"
    taken = lambda stem: any(os.path.exists(os.path.join(folder, f"{stem}.{e}"))
                             for e in ("png", "jpg", "jpeg"))
    if cfg.get("name_style") == "date":
        stem = prefix + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        n, out = 1, stem
        while taken(out):
            n += 1
            out = f"{stem}_{n}"
        return f"{out}.{ext}"
    nums = []
    try:
        for f in os.listdir(folder):
            m = re.fullmatch(re.escape(prefix) + r"(\d{1,9})\.(png|jpe?g)", f, re.IGNORECASE)
            if m:
                nums.append(int(m.group(1)))
    except OSError:
        pass
    n = max(nums, default=0) + 1
    while taken(f"{prefix}{n}"):
        n += 1
    return f"{prefix}{n}.{ext}"


def update_config(**changes):
    """Change just these settings, keeping whatever else is saved (the preferences
    window and a screenshot can both be open at once)."""
    cfg = load_config()
    cfg.update(changes)
    save_config(cfg)
    return load_config()


def load_font(px):
    for name in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "FreeSansBold.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


def stroke(draw, pts, col, w):
    if len(pts) > 1:
        draw.line(pts, fill=col, width=w, joint="curve")
    r = w / 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=col)


def hex_rgb(h):
    return ImageColor.getrgb(h)[:3]


def rgb_hex(r, g, b):
    return "#%02x%02x%02x" % (round(r), round(g), round(b))


# ---------------------------------------------------------------- icons

def make_icon(name, size, bg=BAR_BG):
    """Draw a toolbar icon on an 18-unit grid, supersampled for smooth edges."""
    S = size * 4 / 18
    im = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = ICON_RGB + (255,)
    back = hex_rgb(bg) + (255,)

    def p(*pts):
        return [(x * S, y * S) for x, y in pts]

    def w(v):
        return max(1, round(v * S))

    if name == "pen":
        d.polygon(p((5, 13), (13, 5), (15, 7), (7, 15)), fill=c)
        d.polygon(p((5, 13), (7, 15), (2.5, 16.5), (3.5, 15.5)), fill=c)
        d.polygon(p((13.7, 4.3), (14.6, 3.4), (16.6, 5.4), (15.7, 6.3)), fill=c)
    elif name == "line":
        d.line(p((3, 15), (15, 3)), fill=c, width=w(1.7))
    elif name == "arrow":
        d.line(p((3, 15), (12, 6)), fill=c, width=w(1.7))
        d.polygon(p((15.5, 2.5), (8, 4.5), (13.5, 10)), fill=c)
    elif name == "rect":
        d.rectangle(p((2.5, 4.5), (15.5, 13.5)), outline=c, width=w(1.6))
    elif name == "marker":
        d.polygon(p((6, 10), (11, 5), (15, 9), (10, 14)), fill=c)
        d.polygon(p((6, 10), (10, 14), (7, 15), (5, 13)), fill=c)
        d.line(p((2, 16.5), (16, 16.5)), fill=(235, 190, 0, 255), width=w(1.8))
    elif name == "text":
        d.rectangle(p((3, 3), (15, 5.4)), fill=c)
        d.rectangle(p((7.8, 3), (10.2, 16)), fill=c)
    elif name == "undo":
        d.arc(p((4.5, 4.5), (15.5, 15.5)), start=270, end=120, fill=c, width=w(1.7))
        d.polygon(p((3, 5), (9.5, 1.3), (9.5, 8.7)), fill=c)
    elif name == "copy":
        d.rectangle(p((6.5, 2.5), (15.5, 12.5)), outline=c, width=w(1.4))
        d.rectangle(p((2.5, 6), (11.5, 16)), fill=back, outline=c, width=w(1.4))
    elif name == "save":
        d.rounded_rectangle(p((2.5, 2.5), (15.5, 15.5)), radius=S, outline=c, width=w(1.4))
        d.rectangle(p((5.5, 2.5), (12, 6.8)), fill=c)
        d.rectangle(p((5, 10), (13, 15.5)), outline=c, width=w(1.3))
    elif name == "close":
        d.line(p((4, 4), (14, 14)), fill=c, width=w(1.9))
        d.line(p((14, 4), (4, 14)), fill=c, width=w(1.9))
    return im.resize((size, size), Image.LANCZOS)


def sv_square(h, size):
    """Saturation (left->right) / brightness (top->bottom) square for hue h."""
    grad = Image.linear_gradient("L").resize((size, size))   # top 0 -> bottom 255
    sat = grad.rotate(90)                                     # left 0 -> right 255
    val = grad.transpose(Image.FLIP_TOP_BOTTOM)               # top 255 -> bottom 0
    pure = Image.new("RGB", (size, size),
                     tuple(int(v * 255) for v in colorsys.hsv_to_rgb(h, 1, 1)))
    base = Image.composite(pure, Image.new("RGB", (size, size), "white"), sat)
    return Image.composite(base, Image.new("RGB", (size, size), "black"), val)


def hue_strip(w, size):
    im = Image.new("RGB", (1, size))
    for y in range(size):
        im.putpixel((0, y), tuple(int(v * 255) for v in colorsys.hsv_to_rgb(y / size, 1, 1)))
    return im.resize((w, size), Image.NEAREST)


# ---------------------------------------------------------------- GTK4 overlay
#
# The overlay is drawn with GTK4 so that on Wayland it is a native Wayland window:
# other programs can't read its pixels (an X11/Xwayland window could be read by any
# X11 program). Everything is painted with cairo from one shared "scene" in desktop
# coordinates; each monitor gets its own fullscreen window showing its slice.

Gtk = Gdk = Pango = PangoCairo = cairo = GLib = Gio = Gsk = Graphene = None
Canvas = None


def init_gtk():
    """Load GTK4 (lazily: the tray process uses GTK3). On a Wayland desktop, insist on
    the Wayland backend - never fall back to X11, where other apps could read us."""
    global Gtk, Gdk, Pango, PangoCairo, cairo, GLib, Gio, Gsk, Graphene, Canvas
    if Gtk is not None:
        return
    if WAYLAND:
        if not os.environ.get("WAYLAND_DISPLAY"):
            sys.exit("snypshot: Wayland session but no WAYLAND_DISPLAY; refusing to use X11")
        os.environ["GDK_BACKEND"] = "wayland"
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Gdk as _Gdk, Gtk as _Gtk, Pango as _Pango
    gi.require_version("Gsk", "4.0")
    gi.require_version("Graphene", "1.0")
    from gi.repository import PangoCairo as _PangoCairo, GLib as _GLib, Gio as _Gio
    from gi.repository import Gsk as _Gsk, Graphene as _Graphene
    import cairo as _cairo
    Gtk, Gdk, Pango, PangoCairo, cairo = _Gtk, _Gdk, _Pango, _PangoCairo, _cairo
    GLib, Gio, Gsk, Graphene = _GLib, _Gio, _Gsk, _Graphene

    class _Canvas(Gtk.Widget):
        """One monitor's view of the overlay (see Overlay.snapshot)."""
        __gtype_name__ = "ShotCanvas"

        def __init__(self, overlay, region):
            super().__init__()
            self.overlay, self.region = overlay, region
            self.set_hexpand(True)
            self.set_vexpand(True)

        def do_snapshot(self, snap):
            self.overlay.snapshot(self, snap)

    Canvas = _Canvas
    if not Gtk.init_check():
        sys.exit("snypshot: can't open the display")
    disp = Gdk.Display.get_default()
    if WAYLAND and "Wayland" not in type(disp).__name__:
        sys.exit("snypshot: refusing to show screenshots in an X11 window on a Wayland "
                 "desktop (other apps could read it). Is gir1.2-gtk-4.0 installed?")


CURSORS = {"left_ptr": "default", "hand2": "pointer", "crosshair": "crosshair",
           "sb_v_double_arrow": "ns-resize", "fleur": "move", "xterm": "text",
           "none": "none", "top_left_corner": "nw-resize",
           "bottom_right_corner": "se-resize", "top_right_corner": "ne-resize",
           "bottom_left_corner": "sw-resize", "top_side": "n-resize",
           "bottom_side": "s-resize", "left_side": "w-resize", "right_side": "e-resize"}


def rgbf(h):
    r, g, b = hex_rgb(h)
    return r / 255, g / 255, b / 255


def pil_surface(img):
    """PIL image -> cairo ImageSurface (premultiplied BGRA)."""
    img = img.convert("RGBA")
    if img.getextrema()[3][0] < 255:                 # has transparency: premultiply
        r, g, b, a = img.split()
        from PIL import ImageChops
        img = Image.merge("RGBA", [ImageChops.multiply(ch, a) for ch in (r, g, b)] + [a])
    data = bytearray(img.tobytes("raw", "BGRA"))
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, img.width)
    if stride != img.width * 4:                      # pad rows if cairo wants wider ones
        rows = [data[i * img.width * 4:(i + 1) * img.width * 4] for i in range(img.height)]
        data = bytearray(b"".join(bytes(r) + b"\0" * (stride - img.width * 4) for r in rows))
    return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32,
                                              img.width, img.height, stride)


class Fonts:
    """Pango text measuring (same fonts the painting uses)."""

    def __init__(self):
        self.ctx = PangoCairo.FontMap.get_default().create_context()
        self.cache = {}

    def desc(self, px, bold=False):
        key = (px, bold)
        if key not in self.cache:
            d = Pango.FontDescription.from_string(FONT_FAMILY + (" Bold" if bold else ""))
            d.set_absolute_size(max(1, px) * Pango.SCALE)
            self.cache[key] = d
        return self.cache[key]

    def size(self, text, desc):
        lay = Pango.Layout.new(self.ctx)
        lay.set_font_description(desc)
        lay.set_text(text or " ", -1)
        w, h = lay.get_pixel_size()
        return (w if text else 0), h


class Overlay:
    """One screenshot session: fullscreen window(s) on every monitor, sharing one scene."""

    def __init__(self, capture, on_close=None, persistent=True):
        self.on_close = on_close
        self.persistent = persistent          # daemon: keep clipboard alive after close
        self.cfg = load_config()
        self.closed = False
        try:
            self.k = float(os.environ.get("SNYPSHOT_SCALE") or self.cfg.get("ui_scale") or 1.0)
        except ValueError:
            self.k = 1.0
        self.k = max(0.5, min(4.0, self.k)) if self.k == self.k else 1.0   # also NaN

        # Monitors in GDK's logical coordinates (GTK already handles 125% etc.).
        disp = Gdk.Display.get_default()
        mons = disp.get_monitors()
        self.gmons = [mons.get_item(i) for i in range(mons.get_n_items())]
        rects = []
        for m in self.gmons:
            g = m.get_geometry()
            rects.append((g.x, g.y, g.width, g.height))
        ox = min(r[0] for r in rects)
        oy = min(r[1] for r in rects)
        self.monitors = [(x - ox, y - oy, w, h) for x, y, w, h in rects]
        self.sw = max(x + w for x, y, w, h in self.monitors)
        self.sh = max(y + h for x, y, w, h in self.monitors)
        self.dev = max(1, max(m.get_scale_factor() for m in self.gmons))
        self.parts = self.place_parts(capture, (ox, oy))

        self.fonts = Fonts()
        self.f_ui = self.fonts.desc(self.S(FONT))
        self.f_bold = self.fonts.desc(self.S(FONT), bold=True)
        self.f_head = self.fonts.desc(self.S(FONT + 2))
        self.btn = self.S(BTN)

        # Each monitor's capture becomes a GPU texture, drawn pixel-for-pixel.
        for p in self.parts:
            im = p["img"]
            p["tex"] = Gdk.MemoryTexture.new(im.width, im.height, Gdk.MemoryFormat.R8G8B8,
                                             GLib.Bytes.new(im.tobytes()), im.width * 3)
        isz = self.S(ICON)
        self.icons = {k: pil_surface(make_icon(k, isz * self.dev))
                      for k in TOOLS + ["undo", "copy", "save", "close"]}
        self.sv_size = self.S(150)
        self.hue_w = self.S(16)
        self.hue_surf = pil_surface(hue_strip(self.hue_w * self.dev, self.sv_size * self.dev))
        self.sv_surf = None
        self.sv_hue = None

        # State (same as before).
        self.sel = None
        self.tool = None
        self.color = self.cfg["color"]
        self.width = int(self.cfg["width"])
        self.annots = []
        self.undone = []
        self.cur = None
        self.drag = None
        self.hot = []
        self.ui_ops = []
        self.hover = None
        self.tip = None
        self.tip_job = None
        self.picker = None
        self.last_click = (None, 0)
        self.entry = None
        self.cursor = None
        self.ring = None                        # (x, y) while the brush circle shows
        self.flash = None                       # "Aa" preview for the text tool
        self.flash_job = None
        self.mouse = (0, 0)
        self.shift = False
        self.dialog_open = False
        self.dialog_win = None
        self.want_save = False
        self.hidden = False

        # One fullscreen window per monitor, fully drawn before it appears.
        self.wins, self.areas = [], []
        for gm, (mx, my, mw, mh) in zip(self.gmons, self.monitors):
            win = Gtk.Window()
            win.set_title("snypshot")
            win.set_decorated(False)
            area = Canvas(self, (mx, my, mx + mw, my + mh))
            win.set_child(area)

            drag = Gtk.GestureDrag()
            drag.set_button(1)
            drag.connect("drag-begin", self._drag_begin, area)
            drag.connect("drag-update", self._drag_update, area)
            drag.connect("drag-end", self._drag_end, area)
            area.add_controller(drag)
            rclick = Gtk.GestureClick()
            rclick.set_button(3)
            rclick.connect("pressed", lambda *a: self.close())
            area.add_controller(rclick)
            motion = Gtk.EventControllerMotion()
            motion.connect("motion", self._motion, area)
            area.add_controller(motion)
            scroll = Gtk.EventControllerScroll.new(
                Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.DISCRETE)
            scroll.connect("scroll", self._scroll)
            area.add_controller(scroll)
            keys = Gtk.EventControllerKey()
            keys.connect("key-pressed", self._key_pressed)
            keys.connect("key-released", self._key_released)
            win.add_controller(keys)

            win.fullscreen_on_monitor(gm)
            self.wins.append(win)
            self.areas.append(area)
        self.root = self.wins[0]
        self.render_ui()
        for win in self.wins:
            win.present()
        self.set_cursor("crosshair")

    def S(self, v):
        return max(1, round(v * self.k))

    # --- GLib timer helpers (stand-ins for Tk's after / after_cancel)

    def after(self, ms, fn):
        def run():
            if not self.closed:
                fn()
            return False
        return GLib.timeout_add(ms, run)

    @staticmethod
    def after_cancel(job):
        try:
            GLib.source_remove(job)
        except Exception:
            pass

    # --- events -> desktop coordinates

    def _drag_begin(self, g, x, y, area):
        if self.dialog_open:                      # the screenshot should be hidden now;
            self.drag_origin = None               # if you can click it anyway, the dialog
            self.cancel_dialog()                  # gives way (never a dead screen)
            return
        self.drag_origin = (area.region[0] + x, area.region[1] + y)
        self.shift = bool(g.get_current_event_state() & Gdk.ModifierType.SHIFT_MASK)
        self.press(*self.drag_origin)

    def _drag_update(self, g, dx, dy, area):
        if not self.drag_origin:
            return
        self.shift = bool(g.get_current_event_state() & Gdk.ModifierType.SHIFT_MASK)
        x0, y0 = self.drag_origin
        self.motion(round(x0 + dx), round(y0 + dy))

    def _drag_end(self, g, dx, dy, area):
        if self.want_save:                        # Save button: open the dialog only
            self.want_save = False                # once the click is over
            GLib.timeout_add(60, lambda: self.save_dialog() or False)
        if not self.drag_origin:
            return
        x0, y0 = self.drag_origin
        self.release(round(x0 + dx), round(y0 + dy))

    def _motion(self, ctl, x, y, area):
        gx, gy = round(area.region[0] + x), round(area.region[1] + y)
        self.mouse = (gx, gy)
        if not self.drag:
            self.hover_move(gx, gy)

    def _scroll(self, ctl, dx, dy):
        if dy:
            self.brush(-1 if dy < 0 else 1, *self.mouse)   # wheel up: thinner, down: thicker
        return True

    def _key_pressed(self, ctl, keyval, keycode, state):
        if self.dialog_open:
            if (Gdk.keyval_name(keyval) or "") == "Escape":
                self.cancel_dialog()
            return True
        name = Gdk.keyval_name(keyval) or ""
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if name in ("Shift_L", "Shift_R"):
            self.shift_changed(True)
            return False
        action = self.shortcut_for(keyval, state)
        if name == "Escape":
            self.escape()
        elif name in ("Return", "KP_Enter"):
            self.enter()
        elif action:
            {"copy": self.copy, "save": self.quick_save, "save_as": self.save_dialog,
             "undo": self.undo, "redo": self.redo}[action]()
        elif self.entry and not ctrl:
            ch = chr(Gdk.keyval_to_unicode(keyval)) if Gdk.keyval_to_unicode(keyval) else ""
            return self.on_key(name, ch)
        else:
            return False
        return True

    def tip_text(self, key):
        """Tooltip, with your current shortcut: "Save (Ctrl+S)"."""
        action = {"copy": "copy", "save": "save", "undo": "undo"}.get(key)
        base = TIPS[key].split(" (")[0]
        accel = self.cfg.get("keys", DEFAULT_KEYS).get(action) if action else None
        if key == "close":
            return "Close (Esc)"
        if accel:
            ok, k, m = Gtk.accelerator_parse(accel)
            if ok:
                return f"{base} ({Gtk.accelerator_get_label(k, m)})"
        return base

    def shortcut_for(self, keyval, state):
        """Which of your shortcuts (Preferences > Keyboard) this key press is, if any."""
        if not hasattr(self, "_accels"):
            self._accels = []
            keys = self.cfg.get("keys", DEFAULT_KEYS)
            for action, accel in keys.items():
                ok, k, m = Gtk.accelerator_parse(accel) if accel else (False, 0, 0)
                if ok and k:
                    self._accels.append((Gdk.keyval_to_lower(k), m & mods_mask(), action))
            ctrl = Gdk.ModifierType.CONTROL_MASK
            used = {(k, m) for k, m, _ in self._accels}
            if keys.get("redo") == DEFAULT_KEYS["redo"] and \
                    (Gdk.KEY_z, ctrl | Gdk.ModifierType.SHIFT_MASK) not in used:
                self._accels.append((Gdk.KEY_z, ctrl | Gdk.ModifierType.SHIFT_MASK, "redo"))
        kv, mods = Gdk.keyval_to_lower(keyval), state & mods_mask()
        typing_safe = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | \
            Gdk.ModifierType.SUPER_MASK
        for k, m, action in self._accels:
            if k == kv and m == mods and (not self.entry or m & typing_safe):
                return action
        return None

    def _key_released(self, ctl, keyval, keycode, state):
        if (Gdk.keyval_name(keyval) or "") in ("Shift_L", "Shift_R"):
            self.shift_changed(False)

    # --- window

    def redraw(self):
        for a in self.areas:
            a.queue_draw()

    def set_cursor(self, name):
        if name != self.cursor:
            self.cursor = name
            for a in self.areas:
                a.set_cursor_from_name(CURSORS.get(name, "default"))

    def take_focus(self):
        if self.closed:
            return
        self.hidden = False
        for win in self.wins:
            win.set_visible(True)
            win.present()

    def let_go(self):
        self.hidden = True
        for win in self.wins:
            win.set_visible(False)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.cancel_dialog()
        for job in (self.tip_job, self.flash_job, self.entry and self.entry.get("blink")):
            if job:
                self.after_cancel(job)
        self.cfg.update(color=self.color, width=self.width)
        update_config(color=self.color, width=self.width)
        for win in self.wins:
            win.destroy()
        if self.on_close:
            self.on_close()

    def escape(self):
        """Esc backs out one step at a time (like Lightshot): stop typing, close the color
        dialog, put the tool down - and only then throw the screenshot away."""
        if self.dialog_open:
            self.cancel_dialog()
            return
        if self.entry:
            self.cancel_text()
        elif self.picker:
            self.close_picker()
        elif self.tool:
            self.tool = None
            self.ring = self.flash = None
            self.set_cursor("fleur" if self.sel and self.inside(*self.mouse) else "crosshair")
            self.render_ui()
        else:
            self.close()

    def enter(self):
        if self.entry:
            self.commit_text()
        elif self.picker:
            self.picker_ok()
        else:
            self.copy()

    # --- selection

    def inside(self, x, y):
        x0, y0, x1, y1 = self.sel
        return x0 <= x <= x1 and y0 <= y <= y1

    def set_sel(self, ax, ay, bx, by):
        x0, x1 = sorted((max(0, min(ax, self.sw)), max(0, min(bx, self.sw))))
        y0, y1 = sorted((max(0, min(ay, self.sh)), max(0, min(by, self.sh))))
        self.sel = (x0, y0, x1, y1)

    def handles(self):
        x0, y0, x1, y1 = self.sel
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return {"nw": (x0, y0), "n": (mx, y0), "ne": (x1, y0), "e": (x1, my),
                "se": (x1, y1), "s": (mx, y1), "sw": (x0, y1), "w": (x0, my)}

    def handle_at(self, x, y):
        if not self.sel:
            return None
        r = self.S(7)
        for k, (hx, hy) in self.handles().items():
            if abs(x - hx) <= r and abs(y - hy) <= r:
                return k
        if self.tool:
            return None
        x0, y0, x1, y1 = self.sel
        t = self.S(5)
        onx, ony = x0 - t <= x <= x1 + t, y0 - t <= y <= y1 + t
        k = ("n" if abs(y - y0) <= t and onx else "s" if abs(y - y1) <= t and onx else "")
        k += ("w" if abs(x - x0) <= t and ony else "e" if abs(x - x1) <= t and ony else "")
        return k or None

    # --- mouse

    def hit(self, x, y):
        for x0, y0, x1, y1, key in reversed(self.hot):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return key
        return None

    def press(self, x, y):
        if self.entry:
            part = self.typing_part(x, y)
            if part == "handle":                  # drag the corner: bigger / smaller text
                self.drag = ("tsize", y, self.entry["px"])
                return
            if part == "box":                     # click: place cursor / drag: move text
                self.drag = ("tmove", x - self.entry["x"], y - self.entry["y"], x, y)
                self.tmoved = False
                return
            self.commit_text()                    # clicked elsewhere: done typing
        key = self.hit(x, y)
        if key is not None:
            self.ui_press(key, x, y)
            return
        if self.picker:                           # click outside the color dialog closes it
            self.close_picker()
            return
        if self.sel:
            h = self.handle_at(x, y)
            if h:
                self.drag = ("resize", h, self.sel)
                self.render_ui()
                return
            # Like Lightshot, a tool draws anywhere on screen. Marks outside the box
            # are just decoration until you grow the box over them.
            if self.tool == "text":
                i = self.text_at(x, y)
                if i is not None:                 # click placed text: edit it again
                    self.edit_text(i)
                    self.place_caret(x)
                    self.drag = ("tmove", x - self.entry["x"], y - self.entry["y"], x, y)
                    self.tmoved = False
                else:
                    self.start_text(x, y)
                return
            if self.tool:
                self.cur = {"type": self.tool, "color": self.color, "width": self.width,
                            "pts": [(x, y)]}
                self.drag = ("draw",)
                self.redraw()
                return
            if self.inside(x, y):
                self.drag = ("move", (x, y), self.sel)
                self.render_ui()
                return
            if self.annots:                       # don't let a stray click throw away drawings
                return
        self.drag = ("new", (x, y))
        self.set_sel(x, y, x, y)
        self.render_ui()

    def motion(self, x, y):
        d = self.drag
        self.mouse = (x, y)
        if not d:
            return
        if d[0] == "new":
            self.set_sel(*d[1], x, y)
        elif d[0] == "move":
            (sx, sy), (x0, y0, x1, y1) = d[1], d[2]
            dx = max(-x0, min(x - sx, self.sw - x1))
            dy = max(-y0, min(y - sy, self.sh - y1))
            self.set_sel(x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        elif d[0] == "resize":
            h, (x0, y0, x1, y1) = d[1], d[2]
            if "n" in h: y0 = y
            if "s" in h: y1 = y
            if "w" in h: x0 = x
            if "e" in h: x1 = x
            self.set_sel(x0, y0, x1, y1)
        elif d[0] == "draw" and self.cur:
            self.draw_to(x, y, self.shift)
            return
        elif d[0] in ("sv", "hue"):
            self.picker_drag(d[0], x, y)
            return
        elif d[0] == "tmove" and self.entry:
            if not self.tmoved and abs(x - d[3]) + abs(y - d[4]) < self.S(5):
                return                            # still just a click, not a drag
            self.tmoved = True
            self.entry["x"], self.entry["y"] = x - d[1], y - d[2]
            self.redraw()
            return
        elif d[0] == "tsize" and self.entry:
            px = int(max(self.S(8), min(self.S(300), d[2] + (y - d[1]))))
            self.entry["px"] = px
            # keep the scroll-wheel size in step, so scrolling continues from here
            self.width = max(1, min(20, round((px / self.k - 10) / 3)))
            self.redraw()
            return
        self.render_ui()

    def draw_to(self, x, y, shift):
        """Extend the stroke being drawn. Shift = straight 45° lines / square boxes."""
        x, y = min(max(x, 0), self.sw), min(max(y, 0), self.sh)
        self.last_pt = (x, y)
        t = self.cur["type"]
        if t in ("pen", "marker"):
            self.cur["pts"].append((x, y))
        else:
            x0, y0 = self.cur["pts"][0]
            dx, dy = x - x0, y - y0
            if shift and t in ("line", "arrow"):
                step = math.pi / 4
                ang = round(math.atan2(dy, dx) / step) * step
                length = math.hypot(dx, dy)
                x, y = round(x0 + length * math.cos(ang)), round(y0 + length * math.sin(ang))
            elif shift and t == "rect":
                side = max(abs(dx), abs(dy))
                x, y = x0 + side * (1 if dx >= 0 else -1), y0 + side * (1 if dy >= 0 else -1)
            self.cur["pts"] = [(x0, y0), (x, y)]
        self.ring = (x, y)
        self.redraw()

    def shift_changed(self, down):
        """Pressing / letting go of Shift mid-drag re-snaps right away."""
        self.shift = down
        if self.drag and self.drag[0] == "draw" and self.cur and \
                self.cur["type"] in ("line", "arrow", "rect") and getattr(self, "last_pt", None):
            self.draw_to(*self.last_pt, down)

    def release(self, x, y):
        d, self.drag = self.drag, None
        if not d:
            return
        if d[0] == "tmove" and self.entry and not self.tmoved:
            self.place_caret(x)                   # a click in the text: move the cursor
            return
        if d[0] == "new":
            x0, y0, x1, y1 = self.sel
            if x1 - x0 < 4 or y1 - y0 < 4:
                self.sel = None
        elif d[0] == "draw" and self.cur:
            a, self.cur = self.cur, None
            if not (a["type"] in ("line", "arrow", "rect") and len(a["pts"]) < 2):
                self.annots.append(a)
                self.undone.clear()
            self.redraw()
            return
        self.render_ui()

    def hover_move(self, x, y):
        key = self.hit(x, y)
        if key is not None:
            cur = {"panel": "left_ptr", "sv": "crosshair", "hue": "sb_v_double_arrow"}.get(
                key, "hand2") if not isinstance(key, tuple) else "hand2"
        elif self.picker:
            cur = "left_ptr"
        elif self.entry and self.typing_part(x, y):
            cur = "bottom_right_corner" if self.typing_part(x, y) == "handle" else "fleur"
        elif self.sel and self.handle_at(x, y):
            cur = {"nw": "top_left_corner", "se": "bottom_right_corner",
                   "ne": "top_right_corner", "sw": "bottom_left_corner",
                   "n": "top_side", "s": "bottom_side",
                   "w": "left_side", "e": "right_side"}[self.handle_at(x, y)]
        elif self.sel and self.tool in DRAW_TOOLS:
            cur = "none"                          # the brush circle is the cursor
        elif self.sel and self.tool:
            cur = "xterm"
        elif self.sel and self.inside(x, y):
            cur = "fleur"
        else:
            cur = "crosshair"
        old_ring = self.ring
        if cur == "none":
            self.ring = (x, y)
        elif not self.flash_job:
            self.ring = None
        self.set_cursor(cur)

        if key != self.hover:
            self.hover = key
            self.tip = None
            if self.tip_job:
                self.after_cancel(self.tip_job)
                self.tip_job = None
            if key in TIPS:
                self.tip_job = self.after(450, lambda k=key, tx=x, ty=y: self.show_tip(k, tx, ty))
            self.render_ui()
        elif self.ring != old_ring:
            self.redraw()

    def show_tip(self, key, x, y):
        self.tip_job = None
        if self.hover == key:
            self.tip = (self.tip_text(key), x, y)
            self.render_ui()

    def ring_diameter(self):
        return self.line_px(self.width) * (4 if self.tool == "marker" else 1)

    def brush(self, d, x, y):
        """Mouse wheel: thicker / thinner, shown as the circle (or 'Aa' for text)."""
        self.width = max(1, min(20, self.width + d))
        if self.flash_job:
            self.after_cancel(self.flash_job)
            self.flash_job = None
        if self.entry:                            # typing: resize the text itself, live
            self.entry["px"] = self.text_px(self.width)
            self.redraw()
            return
        if self.tool == "text":
            self.flash = (x + self.S(14), y)
        else:
            self.ring = (x, y)
        if self.cursor != "none":                 # not a drawing tool: only show it briefly
            def fade():
                self.flash_job = None
                self.flash = None
                if self.cursor != "none":
                    self.ring = None
                self.redraw()
            self.flash_job = self.after(700, fade)
        self.redraw()

    # --- toolbars (Lightshot layout), built as a list of shapes to paint

    def mon_at(self, x, y):
        """(x0, y0, x1, y1) of the monitor at a point, or the nearest one."""
        def dist(m):
            mx, my, mw, mh = m
            dx = max(mx - x, 0, x - (mx + mw))
            dy = max(my - y, 0, y - (my + mh))
            return dx * dx + dy * dy
        mx, my, mw, mh = min(self.monitors, key=dist)
        return mx, my, mx + mw, my + mh

    def op(self, *o):
        self.ui_ops.append(o)

    def line_h(self, desc):
        return self.fonts.size("Ag", desc)[1]

    def label_box(self, x, y, text, desc, fg="#ffffff", bg="#2b2b2b", anchor="nw", pad=None):
        """A text label whose box is sized to the text, kept on its monitor."""
        pad = self.S(7) if pad is None else pad
        tw, th = self.fonts.size(text, desc)
        w, h = tw + 2 * pad, th + self.S(6)
        if anchor == "n":
            x -= w / 2
        mx0, my0, mx1, my1 = self.mon_at(x + w / 2, y)
        x = max(mx0, min(x, mx1 - w))
        y = max(my0, min(y, my1 - h))
        self.op("rect", x, y, x + w, y + h, bg, None, 1, None)
        self.op("text", x + pad, y + h / 2, text, desc, fg, "w")
        return w, h

    def render_ui(self):
        if self.closed:
            return
        self.ui_ops = []
        self.hot = []
        self._build_ui()
        self.redraw()

    def _build_ui(self):
        if not self.sel:
            for mx, my, mw, mh in self.monitors:
                self.label_box(mx + mw / 2, my + self.S(24),
                               "Drag to select an area   ·   Esc to cancel",
                               self.f_head, anchor="n", pad=self.S(14))
            return
        x0, y0, x1, y1 = self.sel
        k = self.S

        # selection border + handles
        self.op("rect", x0, y0, x1, y1, None, "#1a1a1a", 1, None)
        self.op("rect", x0, y0, x1, y1, None, "#ffffff", 1, (3, 3))
        hs = k(3)
        for hx, hy in self.handles().values():
            self.op("rect", hx - hs, hy - hs, hx + hs, hy + hs, "#1a1a1a", "#ffffff", 1, None)

        # size label, top-left
        s = self.out_scale(self.sel)
        label = f"{round((x1 - x0) * s)}x{round((y1 - y0) * s)}"
        lh = self.line_h(self.f_bold) + k(6)
        if not self.cfg.get("show_size", True):
            pass
        elif y0 >= lh + k(4):
            self.label_box(x0, y0 - lh - k(2), label, self.f_bold)
        else:
            self.label_box(x0 + k(4), y0 + k(4), label, self.f_bold)

        if self.drag and self.drag[0] in ("new", "move", "resize"):
            return                                # Lightshot hides toolbars while dragging

        b, pad, gap = self.btn, k(3), k(6)
        # Toolbars live on the monitor where the selection's bottom-right corner is.
        mx0, my0, mx1, my1 = self.mon_at(x1 - 1, y1 - 1)

        # vertical toolbar: right of the selection, bottom-aligned
        vkeys = TOOLS + ["color", "undo"]
        vw, vh = b + 2 * pad, b * len(vkeys) + 2 * pad
        if x1 + gap + vw <= mx1:
            vx = x1 + gap
        elif x0 - gap - vw >= mx0:
            vx = x0 - gap - vw
        else:
            vx = min(x1, mx1) - vw - gap
        vy = max(my0, min(y1 - vh, my1 - vh))
        self.vbar = (vx, vy, vw, vh)
        self.bar(vx, vy, vw, vh)
        for i, key in enumerate(vkeys):
            self.button(vx + pad, vy + pad + i * b, key)

        # horizontal toolbar: under the selection, right-aligned
        sep = k(9)
        hw, hh = b * 3 + sep + 2 * pad, b + 2 * pad
        hx = max(mx0, min(x1, mx1) - hw)
        hy = y1 + gap if y1 + gap + hh <= my1 else max(my0, min(y1, my1) - hh - gap)
        if hx < vx + vw and hx + hw > vx and hy < vy + vh and hy + hh > vy:
            hx = max(mx0, vx - hw - gap)
        self.bar(hx, hy, hw, hh)
        bx = hx + pad
        for key in ["copy", "save", None, "close"]:
            if key is None:
                self.op("line", [(bx + sep / 2, hy + k(7)), (bx + sep / 2, hy + hh - k(7))],
                        "#c8c8c8", 1, "butt", 1.0)
                bx += sep
                continue
            self.button(bx, hy + pad, key)
            bx += b

        if self.picker:
            self.draw_picker()

        if self.tip and not self.picker:
            text, tx, ty = self.tip
            below = ty + k(22)
            h = self.line_h(self.f_ui) + k(6)
            self.label_box(tx + k(12), below if below + h < self.mon_at(tx, ty)[3]
                           else ty - h - k(8), text, self.f_ui, fg="#222222", bg="#ffffe1")

    def bar(self, x, y, w, h):
        s = self.S(2)
        self.op("shadow", x + s, y + s, x + w + s, y + h + s)
        self.op("rect", x, y, x + w, y + h, BAR_BG, BAR_EDGE, 1, None)

    def button(self, x, y, key):
        b = self.btn
        if key == self.tool or (key == "color" and self.picker):
            self.op("rect", x, y, x + b - 1, y + b - 1, ACTIVE_BG, ACTIVE_EDGE, 1, None)
        elif key == self.hover:
            self.op("rect", x, y, x + b - 1, y + b - 1, HOVER_BG, HOVER_EDGE, 1, None)
        if key == "color":
            m = self.S(7)
            self.op("rect", x + m, y + m, x + b - m, y + b - m, self.color, "#333333", 1, None)
        else:
            isz = self.S(ICON)
            self.op("image", self.icons[key], x + (b - isz) / 2, y + (b - isz) / 2, isz, isz)
        self.hot.append((x, y, x + b - 1, y + b - 1, key))

    def ui_press(self, key, x, y):
        now = time.time()
        double = self.last_click[0] == key and now - self.last_click[1] < 0.4
        self.last_click = (key, now)

        if key in TOOLS:
            self.tool = None if self.tool == key else key
        elif key == "color":
            self.close_picker() if self.picker else self.open_picker()
        elif key == "undo":
            self.undo()
        elif key == "copy":
            self.copy()
            return
        elif key == "save":
            self.want_save = True                 # opens on release (see _drag_end)
            return
        elif key == "close":
            self.close()
            return
        elif isinstance(key, tuple):                    # a color cell
            kind, i = key
            col = BASIC_COLORS[i] if kind == "basic" else self.cfg["custom"][i]
            if col:
                self.picker_set(col)
                if double:
                    self.picker_ok()
                    return
        elif key == "define":
            self.picker["expanded"] = True
        elif key == "add":
            slot = self.cfg.get("slot", 0) % 16
            self.cfg["custom"][slot] = self.picker["color"]
            self.cfg["slot"] = (slot + 1) % 16
            update_config(custom=self.cfg["custom"], slot=self.cfg["slot"])
        elif key == "ok":
            self.picker_ok()
            return
        elif key in ("cancel", "pclose"):
            self.close_picker()
            return
        elif key in ("sv", "hue"):
            self.drag = (key,)
            self.picker_drag(key, x, y)
            return
        self.render_ui()

    # --- Windows-style color dialog

    def open_picker(self):
        h, s, v = colorsys.rgb_to_hsv(*[ch / 255 for ch in hex_rgb(self.color)])
        self.picker = {"color": self.color, "expanded": False, "h": h, "s": s, "v": v}
        self.render_ui()

    def close_picker(self):
        self.picker = None
        self.render_ui()

    def picker_set(self, col):
        p = self.picker
        p["color"] = col
        h, s, v = colorsys.rgb_to_hsv(*[ch / 255 for ch in hex_rgb(col)])
        if s > 0 and v > 0:
            p["h"] = h
        p["s"], p["v"] = s, v

    def picker_ok(self):
        self.color = self.picker["color"]
        self.cfg["color"] = self.color
        update_config(color=self.color)
        self.close_picker()

    def picker_drag(self, kind, x, y):
        p, n = self.picker, self.sv_size
        sx0, sy0 = p["sv_at"]
        if kind == "sv":
            p["s"] = min(max((x - sx0) / n, 0), 1)
            p["v"] = 1 - min(max((y - sy0) / n, 0), 1)
        else:
            p["h"] = min(max((y - sy0) / n, 0), 0.999)
        p["color"] = rgb_hex(*[ch * 255 for ch in colorsys.hsv_to_rgb(p["h"], p["s"], p["v"])])
        self.render_ui()

    def dlg_button(self, x, y, w, h, text, key, enabled=True):
        bg = HOVER_BG if key == self.hover and enabled else "#fdfdfd"
        self.op("rect", x, y, x + w, y + h, bg, "#adadad", 1, None)
        self.op("text", x + w / 2, y + h / 2, text, self.f_ui,
                "#222222" if enabled else "#a0a0a0", "center")
        if enabled:
            self.hot.append((x, y, x + w, y + h, key))

    def draw_picker(self):
        p, k = self.picker, self.S
        PAD, CELL, SW = k(10), k(24), k(18)
        TB = k(30)                                      # title bar
        LBL = self.line_h(self.f_ui) + k(6)             # "Basic colors:" row
        BH = self.line_h(self.f_ui) + k(12)             # dialog button height
        n, hw = self.sv_size, self.hue_w

        LW = 2 * PAD + 8 * CELL - (CELL - SW)
        LW = max(LW, self.fonts.size("Define Custom Colors >>", self.f_ui)[0] + k(24) + 2 * PAD)
        RW = n + k(8) + hw + k(8) + PAD
        RW = max(RW, self.fonts.size("Add to Custom Colors", self.f_ui)[0] + k(24) + PAD)
        W = LW + (RW if p["expanded"] else 0)
        left_h = TB + k(8) + LBL + 6 * CELL + k(4) + LBL + 2 * CELL + k(8) + BH + k(12) + BH + PAD
        right_h = TB + k(8) + LBL + n + k(12) + k(34) + k(12) + BH + PAD
        H = max(left_h, right_h if p["expanded"] else 0)

        vx, vy, vw, vh = self.vbar
        mx0, my0, mx1, my1 = self.mon_at(vx + vw / 2, vy + vh / 2)
        ox = vx - W - k(8) if vx - W - k(8) >= mx0 else vx + vw + k(8)
        ox = max(mx0, min(ox, mx1 - W))
        oy = max(my0, min(vy + vh - H, my1 - H))

        s = k(3)
        self.op("shadow", ox + s, oy + s, ox + W + s, oy + H + s)
        self.op("rect", ox, oy, ox + W, oy + H, "#f0f0f0", "#8a8a8a", 1, None)
        self.hot.append((ox, oy, ox + W, oy + H, "panel"))
        self.op("rect", ox + 1, oy + 1, ox + W - 1, oy + TB, "#ffffff", None, 1, None)
        self.op("text", ox + PAD, oy + TB / 2, "Color", self.f_ui, "#222222", "w")
        cw = k(40)
        cx = ox + W - cw
        if self.hover == "pclose":
            self.op("rect", cx, oy + 1, ox + W - 1, oy + TB, "#e81123", None, 1, None)
        self.op("text", cx + cw / 2, oy + TB / 2, "✕", self.f_ui,
                "#ffffff" if self.hover == "pclose" else "#222222", "center")
        self.hot.append((cx, oy + 1, ox + W - 1, oy + TB, "pclose"))

        def cell(x, y, col, key):
            self.op("rect", x, y, x + SW, y + SW, col or "#ffffff", "#a0a0a0", 1, None)
            if col and col.lower() == p["color"].lower():
                m = k(3)
                self.op("rect", x - m, y - m, x + SW + m, y + SW + m, None, "#000000", k(2), None)
            self.hot.append((x - k(2), y - k(2), x + SW + k(2), y + SW + k(2), key))

        y = oy + TB + k(8)
        self.op("text", ox + PAD, y + LBL / 2, "Basic colors:", self.f_ui, "#222222", "w")
        y += LBL
        for i, col in enumerate(BASIC_COLORS):
            cell(ox + PAD + (i % 8) * CELL, y + (i // 8) * CELL, col, ("basic", i))
        y += 6 * CELL + k(4)
        self.op("text", ox + PAD, y + LBL / 2, "Custom colors:", self.f_ui, "#222222", "w")
        y += LBL
        for i, col in enumerate(self.cfg["custom"]):
            cell(ox + PAD + (i % 8) * CELL, y + (i // 8) * CELL, col, ("custom", i))
        y += 2 * CELL + k(8)
        self.dlg_button(ox + PAD, y, LW - 2 * PAD, BH, "Define Custom Colors >>", "define",
                        enabled=not p["expanded"])
        y += BH + k(12)
        bw = (LW - 2 * PAD - k(8)) // 2
        self.dlg_button(ox + PAD, y, bw, BH, "OK", "ok")
        self.dlg_button(ox + PAD + bw + k(8), y, bw, BH, "Cancel", "cancel")

        if p["expanded"]:
            sx, sy = ox + LW, oy + TB + k(8) + LBL
            hx = sx + n + k(8)
            p["sv_at"] = (sx, sy)
            hue_key = round(p["h"], 3)
            if self.sv_hue != hue_key:
                self.sv_surf = pil_surface(sv_square(p["h"], n * self.dev))
                self.sv_hue = hue_key
            self.op("image", self.sv_surf, sx, sy, n, n)
            self.op("rect", sx - 1, sy - 1, sx + n, sy + n, None, "#8a8a8a", 1, None)
            self.hot.append((sx, sy, sx + n, sy + n, "sv"))
            mx, my = sx + p["s"] * n, sy + (1 - p["v"]) * n
            r = k(5)
            self.op("oval", mx, my, r, "#000000", k(2))
            self.op("oval", mx, my, r - 1, "#ffffff", 1)
            self.op("image", self.hue_surf, hx, sy, hw, n)
            self.op("rect", hx - 1, sy - 1, hx + hw, sy + n, None, "#8a8a8a", 1, None)
            self.hot.append((hx - k(3), sy, hx + hw + k(6), sy + n, "hue"))
            ty = sy + p["h"] * n
            self.op("poly", [(hx + hw + 1, ty), (hx + hw + k(7), ty - k(4)),
                             (hx + hw + k(7), ty + k(4))], "#222222")
            y2 = sy + n + k(12)
            self.op("rect", sx, y2, sx + k(64), y2 + k(34), p["color"], "#8a8a8a", 1, None)
            self.op("text", sx + k(74), y2 + k(17), p["color"].upper(), self.f_ui, "#222222", "w")
            self.dlg_button(sx, y2 + k(34) + k(12), RW - PAD, BH, "Add to Custom Colors", "add")

    # --- drawings

    def line_px(self, width):
        return max(1, round(width * self.k))

    def text_px(self, width):
        return round((10 + width * 3) * self.k)

    def item_ops(self, a):
        """Shapes for one drawing - the same geometry the saved image uses."""
        t, col, pts = a["type"], a["color"], a["pts"]
        w = self.line_px(a["width"])
        if t in ("pen", "marker"):
            return [("line", pts if len(pts) > 1 else pts * 2, col,
                     w * 4 if t == "marker" else w, "round", 1.0)]
        if t == "text":
            return [("text", pts[0][0], pts[0][1], a["text"], self.fonts.desc(a["px"], True),
                     col, "nw")]
        if len(pts) < 2:
            return []
        (ax, ay), (bx, by) = pts
        if t == "line":
            return [("line", pts, col, w, "round", 1.0)]
        if t == "rect":                          # outline drawn inside the box, like PIL
            x0, y0, x1, y1 = min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)
            return [("rect", x0 + w / 2, y0 + w / 2, x1 - w / 2, y1 - w / 2, None, col, w, None)]
        if t == "arrow":
            length = math.hypot(bx - ax, by - ay)
            if length < 1:
                return []
            ux, uy = (bx - ax) / length, (by - ay) / length
            nx, ny = -uy, ux
            head = min(4 * w + 6, length)
            half = w / 2 + 2 * w + 3
            hx, hy = bx - ux * head, by - uy * head
            return [("line", [(ax, ay), (hx, hy)], col, w, "round", 1.0),
                    ("poly", [(bx, by), (hx + nx * half, hy + ny * half),
                              (hx - nx * half, hy - ny * half)], col)]
        return []

    # --- text tool: typed straight onto the screenshot, with a caret and dashed box

    def start_text(self, x, y, text="", px=None, color=None, replaces=None):
        self.entry = {"x": x, "y": y, "text": text, "caret": len(text),
                      "px": px or self.text_px(self.width), "color": color or self.color,
                      "caret_on": True, "replaces": replaces}
        self.blink()

    def text_size(self, text, px):
        desc = self.fonts.desc(px, True)
        w, h = self.fonts.size(text, desc)
        return desc, max(w, px // 2), h

    def typing_geometry(self):
        t = self.entry
        x, y, text = t["x"], t["y"], t["text"]
        desc, w, h = self.text_size(text, t["px"])
        cx = x + self.fonts.size(text[:t["caret"]], desc)[0]
        pad, hs = self.S(5), self.S(4)
        box = (x - pad, y - pad, x + w + pad, y + h + pad)
        t["bbox"] = box
        t["hbox"] = (box[2] - hs - self.S(3), box[3] - hs - self.S(3),
                     box[2] + hs + self.S(3), box[3] + hs + self.S(3))
        return desc, box, hs, cx, h

    def typing_ops(self):
        t = self.entry
        desc, box, hs, cx, h = self.typing_geometry()
        ops = [("rect", *box, None, "#000000", 1, None),
               ("rect", *box, None, "#ffffff", 1, (3, 3)),
               ("text", t["x"], t["y"], t["text"], desc, t["color"], "nw"),
               ("rect", box[2] - hs, box[3] - hs, box[2] + hs, box[3] + hs,
                "#ffffff", "#1a1a1a", 1, None)]
        if t["caret_on"]:
            ops.append(("line", [(cx, t["y"]), (cx, t["y"] + h)], t["color"],
                        max(1, t["px"] // 12), "butt", 1.0))
        return ops

    def typing_part(self, x, y):
        """Is (x, y) on the text box's resize handle, on the box, or neither?"""
        t = self.entry
        if not t:
            return None
        self.typing_geometry()
        hx0, hy0, hx1, hy1 = t["hbox"]
        if hx0 <= x <= hx1 and hy0 <= y <= hy1:
            return "handle"
        bx0, by0, bx1, by1 = t["bbox"]
        if bx0 <= x <= bx1 and by0 <= y <= by1:
            return "box"
        return None

    def place_caret(self, x):
        """Put the text cursor at the character boundary nearest to x."""
        t = self.entry
        desc = self.fonts.desc(t["px"], True)
        edges = [t["x"] + self.fonts.size(t["text"][:i], desc)[0]
                 for i in range(len(t["text"]) + 1)]
        t["caret"] = min(range(len(edges)), key=lambda i: abs(edges[i] - x))
        t["caret_on"] = True
        self.redraw()

    def text_at(self, x, y):
        """Index of the placed text under (x, y), topmost first."""
        for i in range(len(self.annots) - 1, -1, -1):
            a = self.annots[i]
            if a["type"] != "text":
                continue
            ax, ay = a["pts"][0]
            _, w, h = self.text_size(a["text"], a["px"])
            if ax - 4 <= x <= ax + w + 4 and ay - 4 <= y <= ay + h + 4:
                return i
        return None

    def edit_text(self, i):
        """Reopen placed text for typing / moving / resizing."""
        a = self.annots.pop(i)
        (x, y), = a["pts"]
        self.start_text(x, y, text=a["text"], px=a["px"], color=a["color"], replaces=a)

    def blink(self):
        if not self.entry or self.closed:
            return
        self.entry["caret_on"] = not self.entry["caret_on"]
        self.redraw()
        self.entry["blink"] = self.after(530, self.blink)

    def on_key(self, name, ch):
        """Typing into the text box (Enter, Esc and Ctrl+ shortcuts are handled elsewhere)."""
        t = self.entry
        text, i = t["text"], t["caret"]
        if name == "BackSpace":
            if i > 0:
                text, i = text[:i - 1] + text[i:], i - 1
        elif name == "Delete":
            text = text[:i] + text[i + 1:]
        elif name == "Left":
            i = max(0, i - 1)
        elif name == "Right":
            i = min(len(text), i + 1)
        elif name == "Home":
            i = 0
        elif name == "End":
            i = len(text)
        elif ch and ch.isprintable():
            text, i = text[:i] + ch + text[i:], i + 1
        else:
            return False
        t["text"], t["caret"], t["caret_on"] = text, i, True
        self.redraw()
        return True

    def end_typing(self):
        t = self.entry
        if t and t.get("blink"):
            self.after_cancel(t["blink"])
        self.entry = None
        self.redraw()
        return t

    def commit_text(self):
        t = self.end_typing()
        if t["text"].strip():
            a = {"type": "text", "color": t["color"], "width": self.width,
                 "pts": [(t["x"], t["y"])], "text": t["text"], "px": t["px"]}
        elif t["replaces"]:                       # emptied an existing text = delete it
            a = {"type": "deleted", "color": t["color"], "width": self.width, "pts": []}
        else:
            return
        a["replaces"] = t["replaces"]             # so undo can bring the old version back
        self.annots.append(a)
        self.undone.clear()
        self.redraw()

    def cancel_text(self):
        """Esc while typing: throw away the edit (an edited text goes back as it was)."""
        t = self.end_typing()
        old = t and t["replaces"]
        if old:
            self.annots.append(old)
            self.redraw()

    def _remove(self, a):
        for i, b in enumerate(self.annots):
            if b is a:
                del self.annots[i]
                return

    def undo(self):
        if self.entry:
            self.cancel_text()
        elif self.annots:
            a = self.annots.pop()
            self.undone.append(a)
            old = a.get("replaces")
            if old:                               # an edit: put the previous version back
                self.annots.append(old)
        self.redraw()

    def redo(self):
        if self.entry or not self.undone:
            return
        a = self.undone.pop()
        if a.get("replaces"):
            self._remove(a["replaces"])
        self.annots.append(a)
        self.redraw()

    # --- painting

    def place_parts(self, capture, origin):
        """Where each monitor capture goes, in our desktop coordinates, and its scale."""
        ox, oy = origin
        if isinstance(capture, Image.Image):          # one image of the whole desktop
            capture = [((ox, oy, self.sw, self.sh), capture)]
        rects = [r for r, _ in capture]
        gd = [(x + ox, y + oy, w, h) for x, y, w, h in self.monitors]
        parts = []
        for i, ((x, y, w, h), img) in enumerate(capture):
            if (x, y, w, h) not in gd and len(capture) == len(gd):
                # GNOME and GTK disagree on coordinates (e.g. integer-scaling mode):
                # pair them up by position instead
                order_c = sorted(range(len(rects)), key=lambda j: (rects[j][1], rects[j][0]))
                order_g = sorted(range(len(gd)), key=lambda j: (gd[j][1], gd[j][0]))
                x, y, w, h = gd[order_g[order_c.index(i)]]
            parts.append({"rect": (x - ox, y - oy, w, h), "img": img,
                          "scale": img.width / max(1, w)})
        return parts

    def out_scale(self, sel):
        """Pixels per desktop unit for the output: the sharpest monitor the selection
        touches (a selection on one monitor keeps that monitor's exact pixels)."""
        x0, y0, x1, y1 = sel
        hits = [p["scale"] for p in self.parts
                if p["rect"][0] < x1 and p["rect"][0] + p["rect"][2] > x0
                and p["rect"][1] < y1 and p["rect"][1] + p["rect"][3] > y0]
        return max(hits or [p["scale"] for p in self.parts])

    def snapshot(self, area, snap):
        mx0, my0, mx1, my1 = area.region
        R = lambda x, y, w, h: Graphene.Rect().init(x, y, w, h)
        snap.save()
        snap.translate(Graphene.Point().init(-mx0, -my0))   # draw in desktop coordinates
        view = R(mx0, my0, mx1 - mx0, my1 - my0)
        try:
            dev = area.get_native().get_surface().get_scale()     # e.g. 1.25
        except Exception:
            dev = area.get_scale_factor()
        for p in self.parts:                                      # the screenshot itself
            x, y, w, h = p["rect"]
            if abs(p["scale"] - dev) < 0.01:
                # 1:1 with the screen. Plain append_texture is pixel-exact even at
                # fractional scales (GTK 4.14's scaled-texture path resamples there).
                snap.append_texture(p["tex"], R(x, y, w, h))
            else:
                snap.append_scaled_texture(p["tex"], Gsk.ScalingFilter.LINEAR, R(x, y, w, h))
        dim = Gdk.RGBA()
        dim.parse(f"rgba(0,0,0,{self.cfg.get('dim', 0.45):.2f})")
        if self.sel and self.sel[2] > self.sel[0] and self.sel[3] > self.sel[1]:
            x0, y0, x1, y1 = self.sel                             # dim all but the selection
            W, H = self.sw, self.sh
            for r in (R(0, 0, W, y0), R(0, y1, W, H - y1), R(0, y0, x0, y1 - y0),
                      R(x1, y0, W - x1, y1 - y0)):
                if r.get_width() > 0 and r.get_height() > 0:
                    snap.append_color(dim, r)
        else:
            snap.append_color(dim, R(0, 0, self.sw, self.sh))
        cr = snap.append_cairo(view)                              # drawings + toolbars
        self.paint(cr)
        snap.restore()

    def paint(self, cr):
        # drawings: markers first as one see-through layer, then everything else
        items = self.annots + ([self.cur] if self.cur else [])
        markers = [a for a in items if a["type"] == "marker"]
        if markers:
            cr.push_group()
            for a in markers:
                self.paint_ops(cr, self.item_ops(a))
            cr.pop_group_to_source()
            cr.paint_with_alpha(0.45)
        for a in items:
            if a["type"] != "marker":
                self.paint_ops(cr, self.item_ops(a))
        if self.entry:
            self.paint_ops(cr, self.typing_ops())
        self.paint_ops(cr, self.ui_ops)

        # brush circle / "Aa" preview always on top
        if self.ring:
            x, y = self.ring
            r = max(self.ring_diameter() / 2, self.S(2))
            self.paint_ops(cr, [("oval", x, y, r + 1, "#000000", 1),
                                ("oval", x, y, r, self.color, max(1, self.S(1.5)))])
        if self.flash:
            fx, fy = self.flash
            self.paint_ops(cr, [("text", fx, fy, "Aa",
                                 self.fonts.desc(self.text_px(self.width), True),
                                 self.color, "w")])

    def paint_ops(self, cr, ops):
        for o in ops:
            kind = o[0]
            if kind == "rect":
                _, x0, y0, x1, y1, fill, outline, lw, dash = o
                cr.rectangle(x0, y0, x1 - x0, y1 - y0)
                if fill:
                    cr.set_source_rgb(*rgbf(fill))
                    if outline:
                        cr.fill_preserve()
                    else:
                        cr.fill()
                if outline:
                    if lw == 1:                      # crisp 1px lines
                        cr.new_path()
                        cr.rectangle(x0 + .5, y0 + .5, x1 - x0 - 1, y1 - y0 - 1)
                    cr.set_source_rgb(*rgbf(outline))
                    cr.set_line_width(lw)
                    cr.set_dash(list(dash) if dash else [])
                    cr.stroke()
                    cr.set_dash([])
            elif kind == "shadow":
                _, x0, y0, x1, y1 = o
                cr.rectangle(x0, y0, x1 - x0, y1 - y0)
                cr.set_source_rgba(0, 0, 0, 0.25)
                cr.fill()
            elif kind == "line":
                _, pts, col, lw, cap, alpha = o
                cr.move_to(*pts[0])
                for p in pts[1:]:
                    cr.line_to(*p)
                cr.set_source_rgba(*rgbf(col), alpha)
                cr.set_line_width(lw)
                cr.set_line_cap(cairo.LINE_CAP_ROUND if cap == "round" else cairo.LINE_CAP_BUTT)
                cr.set_line_join(cairo.LINE_JOIN_ROUND)
                cr.stroke()
            elif kind == "poly":
                _, pts, col = o
                cr.move_to(*pts[0])
                for p in pts[1:]:
                    cr.line_to(*p)
                cr.close_path()
                cr.set_source_rgb(*rgbf(col))
                cr.fill()
            elif kind == "oval":
                _, x, y, r, col, lw = o
                cr.new_sub_path()
                cr.arc(x, y, max(r, 0.5), 0, 2 * math.pi)
                cr.set_source_rgb(*rgbf(col))
                cr.set_line_width(lw)
                cr.stroke()
            elif kind == "text":
                _, x, y, text, desc, col, anchor = o
                lay = PangoCairo.create_layout(cr)
                lay.set_font_description(desc)
                lay.set_text(text, -1)
                w, h = lay.get_pixel_size()
                if anchor == "w":
                    y -= h / 2
                elif anchor == "center":
                    x, y = x - w / 2, y - h / 2
                cr.move_to(x, y)
                cr.set_source_rgb(*rgbf(col))
                PangoCairo.show_layout(cr, lay)
                cr.new_path()
            elif kind == "image":
                _, surf, x, y, w, h = o
                cr.save()
                cr.translate(x, y)
                cr.scale(w / surf.get_width(), h / surf.get_height())
                cr.set_source_surface(surf, 0, 0)
                cr.paint()
                cr.restore()

    # --- output

    def compose(self, sel, s):
        """The selected area at s pixels per desktop unit, from each monitor's own
        pixels (only resampled if the selection spans monitors of different scales)."""
        x0, y0, x1, y1 = sel
        out = Image.new("RGB", (max(1, round((x1 - x0) * s)), max(1, round((y1 - y0) * s))))
        for p in self.parts:
            px, py, pw, ph = p["rect"]
            ix0, iy0 = max(x0, px), max(y0, py)
            ix1, iy1 = min(x1, px + pw), min(y1, py + ph)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            ps = p["scale"]
            piece = p["img"].crop((round((ix0 - px) * ps), round((iy0 - py) * ps),
                                   round((ix1 - px) * ps), round((iy1 - py) * ps)))
            size = (round((ix1 - ix0) * s), round((iy1 - iy0) * s))
            if piece.size != size:
                piece = piece.resize(size, Image.LANCZOS)
            out.paste(piece, (round((ix0 - x0) * s), round((iy0 - y0) * s)))
        return out

    def render(self):
        x0, y0, x1, y1 = self.sel
        s = self.out_scale(self.sel)
        sx = sy = s
        base = self.compose(self.sel, s).convert("RGBA")
        marks = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ink = Image.new("RGBA", base.size, (0, 0, 0, 0))
        dm, di = ImageDraw.Draw(marks), ImageDraw.Draw(ink)

        for a in self.annots:
            col = hex_rgb(a["color"]) + (255,)
            lw = self.line_px(a["width"])
            w = max(1, round(lw * s))
            pts = [((px - x0) * sx, (py - y0) * sy) for px, py in a["pts"]]
            t = a["type"]
            if t == "marker":
                stroke(dm, pts, col, w * 4)
            elif t in ("pen", "line"):
                stroke(di, pts, col, w)
            elif t == "rect":
                (ax, ay), (bx2, by2) = pts
                di.rectangle([min(ax, bx2), min(ay, by2), max(ax, bx2), max(ay, by2)],
                             outline=col, width=w)
            elif t == "arrow":
                (ax, ay), (bx2, by2) = pts
                length = math.hypot(bx2 - ax, by2 - ay)
                if length < 1:
                    continue
                ux, uy = (bx2 - ax) / length, (by2 - ay) / length
                nx, ny = -uy, ux
                head = min((4 * lw + 6) * s, length)
                half = (lw / 2 + 2 * lw + 3) * s
                hx, hy = bx2 - ux * head, by2 - uy * head
                stroke(di, [(ax, ay), (hx, hy)], col, w)
                di.polygon([(bx2, by2), (hx + nx * half, hy + ny * half),
                            (hx - nx * half, hy - ny * half)], fill=col)
            elif t == "text":
                di.text(pts[0], a["text"], fill=col, font=load_font(round(a["px"] * s)))

        marks.putalpha(marks.getchannel("A").point(lambda v: v * 45 // 100))
        out = Image.alpha_composite(Image.alpha_composite(base, marks), ink)
        return out.convert("RGB")

    def copy(self):
        if not self.sel or self.drag:
            return
        if self.entry:
            self.commit_text()
        img = self.render()
        ok = False
        if self.persistent:
            # GTK's own Wayland/X11 clipboard: no helper program ever sees the image.
            try:
                buf = io.BytesIO()
                img.save(buf, "PNG")
                self.root.get_clipboard().set_content(Gdk.ContentProvider.new_for_bytes(
                    "image/png", GLib.Bytes.new(buf.getvalue())))
                ok = True
            except Exception as e:
                log(f"clipboard: {e}")
        if not ok:
            ok = copy_png(img)
        if ok:
            if self.cfg.get("notify", True):
                notify("Copied to clipboard")
            GLib.timeout_add(150, lambda: self.close() or False)   # let the offer go out
            self.let_go()
        else:
            self.tip = ("Can't copy: install wl-clipboard (Wayland) or xclip (X11)",
                        self.sel[0], self.sel[1])
            self.render_ui()

    # --- saving

    def save_folder(self):
        """Where Ctrl+S saves: your chosen folder, or the one you last saved in (else
        Pictures, else home)."""
        first = self.cfg.get("save_dir") if self.cfg.get("save_mode") == "fixed" else None
        for d in (first, self.cfg.get("last_dir"), os.path.expanduser("~/Pictures")):
            if d and os.path.isdir(d):
                return d
        return os.path.expanduser("~")

    def next_name(self, folder):
        return next_file_name(folder, self.cfg)

    def write_image(self, img, path, exclusive=False):
        if not os.path.splitext(path)[1]:
            path += ".jpg" if self.cfg.get("format") == "jpg" else ".png"
        fmt = "JPEG" if path.lower().endswith((".jpg", ".jpeg")) else "PNG"
        with open(path, "xb" if exclusive else "wb") as f:
            if fmt == "JPEG":
                img.convert("RGB").save(f, fmt, quality=self.cfg.get("jpg_quality", 95))
            else:
                img.save(f, fmt)
        self.cfg["last_dir"] = os.path.dirname(os.path.abspath(path))
        update_config(last_dir=self.cfg["last_dir"])
        return path

    def quick_save(self, img=None):
        """Ctrl+S: save straight away as the next Screenshot_N.png - no dialog."""
        if not self.sel or self.drag:
            return
        if self.entry:
            self.commit_text()
        img = img or self.render()
        folder = self.save_folder()
        for _ in range(20):                       # another program grabbed the name? next
            try:
                path = self.write_image(img, os.path.join(folder, self.next_name(folder)),
                                        exclusive=True)
                break
            except FileExistsError:
                continue
            except OSError as e:
                notify(f"Couldn't save: {e}")
                return
        else:
            return
        if self.cfg.get("notify", True):
            notify(f"Saved as {os.path.basename(path)} in {folder}")
        self.close()

    def save_dialog(self):
        """The Save button: a save dialog in its own window, drawn by snypshot itself (no
        desktop portal in between, so it shows up the same way the screenshot does).
        The screenshot steps aside meanwhile; Cancel brings it back exactly as it was."""
        if self.closed or not self.sel or self.drag or self.dialog_open:
            return
        if self.entry:
            self.commit_text()
        img = self.render()
        folder = self.save_folder()
        name = self.next_name(folder)
        self.dialog_open = True
        self.dialog_win = None
        self.ring = None
        self.let_go()                              # hide the overlay while saving

        def finish(dlg, response):
            if self.dialog_win is not dlg:
                return
            path = None
            if response == Gtk.ResponseType.ACCEPT:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    f = dlg.get_file()
                path = f.get_path() if f else None
            self.dialog_win = None
            self.dialog_open = False
            dlg.destroy()
            if self.closed:
                return
            if not path:
                self.back_from_dialog()            # cancelled: back to the screenshot
                return
            try:
                path = self.write_image(img, path)
            except (OSError, ValueError) as e:
                notify(f"Couldn't save: {e}")
                self.back_from_dialog()
                return
            if self.cfg.get("notify", True):
                notify(f"Saved to {path}")
            self.close()

        def show():                                # once the screenshot is off screen
            if self.closed or not self.dialog_open:
                return False
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")      # FileChooserDialog is "deprecated"
                    dlg = Gtk.FileChooserDialog(title="Save screenshot",
                                                action=Gtk.FileChooserAction.SAVE)
                    dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
                    dlg.add_button("Save", Gtk.ResponseType.ACCEPT)
                    dlg.set_default_response(Gtk.ResponseType.ACCEPT)
                    dlg.set_current_folder(Gio.File.new_for_path(folder))
                    dlg.set_current_name(name)
                dlg.set_size_request(860, 560)
                dlg.connect("response", finish)
                self.dialog_win = dlg
                dlg.present()
            except Exception as e:
                import traceback
                log("save dialog failed:\n" + traceback.format_exc())
                self.dialog_open = False
                self.dialog_win = None
                self.back_from_dialog()            # never leave you with nothing
                notify(f"Couldn't open the save dialog ({e}). Ctrl+S still works.")
                return False

            def watchdog():                        # it must actually be on screen
                if self.dialog_win is dlg and not dlg.get_mapped():
                    log("save dialog never appeared; bringing the screenshot back")
                    finish(dlg, Gtk.ResponseType.CANCEL)
                    notify("The save dialog didn't open. Ctrl+S still works.")
                return False
            GLib.timeout_add(2500, watchdog)
            return False
        GLib.timeout_add(120, show)

    def back_from_dialog(self):
        self.take_focus()
        self.set_cursor("crosshair")
        self.render_ui()

    def cancel_dialog(self):
        dlg = getattr(self, "dialog_win", None)
        if dlg is not None:
            dlg.response(Gtk.ResponseType.CANCEL)
        elif self.dialog_open:                     # not shown yet
            self.dialog_open = False
            if not self.closed:
                self.back_from_dialog()


# ---------------------------------------------------------------- preferences

PREFS_CSS = b"""
.snyp-page { padding: 24px 32px; }
.snyp-title { font-size: 1.35em; font-weight: bold; margin-bottom: 2px; }
.snyp-note { opacity: 0.7; }
.snyp-group { border-radius: 10px; border: 1px solid alpha(currentColor, 0.15); }
.snyp-group > row { padding: 10px 14px; }
.snyp-group > row:not(:last-child) { border-bottom: 1px solid alpha(currentColor, 0.1); }
.snyp-sub { opacity: 0.65; font-size: 0.9em; }
.snyp-key { font-family: monospace; min-width: 150px; }
.snyp-recording { background: alpha(@accent_bg_color, 0.25); }
.snyp-bad { color: #c01c28; }
entry.snyp-bad { outline: 2px solid #c01c28; }
"""

KEY_ACTIONS = [("copy", "Copy to clipboard"), ("save", "Quick save"),
               ("save_as", "Save as (opens the save dialog)"), ("undo", "Undo"), ("redo", "Redo")]


def mods_mask():
    """The modifier keys shortcuts care about (Gdk is loaded lazily, hence a function)."""
    return (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
            | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK)


def accel_label(accel):
    if not accel:
        return "Off"
    ok, k, m = Gtk.accelerator_parse(accel)
    label = Gtk.accelerator_get_label(k, m) if ok else accel
    return re.sub(r"\bPrint$", "Print Screen", label)


class Preferences:
    """Preferences window: everything you can change, saved as soon as you change it."""

    def __init__(self, daemon):
        self.daemon = daemon
        self.cfg = load_config()
        self.recording = None                    # (button, on_done, global?) while waiting
        self.win = win = Gtk.Window(title="snypshot Preferences")
        win.set_default_size(760, 560)
        css = Gtk.CssProvider()
        css.load_from_data(PREFS_CSS, len(PREFS_CSS))
        Gtk.StyleContext.add_provider_for_display(win.get_display(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._key)
        win.add_controller(keys)
        win.connect("close-request", self._closing)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True)
        side = Gtk.StackSidebar(stack=self.stack)
        side.set_size_request(180, -1)
        body = Gtk.Box()
        body.append(side)
        body.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        body.append(self.stack)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(body)
        body.set_vexpand(True)
        self.status = Gtk.Label(xalign=0, wrap=True, margin_start=16, margin_end=16,
                                margin_top=6, margin_bottom=8)
        self.status.add_css_class("snyp-note")
        outer.append(self.status)
        win.set_child(outer)
        self._build()
        win.present()

    # --- building blocks

    def page(self, name, title, note=None):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.add_css_class("snyp-page")
        t = Gtk.Label(label=title, xalign=0)
        t.add_css_class("snyp-title")
        box.append(t)
        if note:
            n = Gtk.Label(label=note, xalign=0, wrap=True)
            n.add_css_class("snyp-note")
            box.append(n)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroll.set_child(box)
        self.stack.add_titled(scroll, name, title)
        return box

    def group(self, page):
        lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        lb.add_css_class("snyp-group")
        page.append(lb)
        return lb

    def row(self, group, title, widget, sub=None):
        box = Gtk.Box(spacing=12)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        text.append(Gtk.Label(label=title, xalign=0, wrap=True))
        subl = None
        if sub is not None:
            subl = Gtk.Label(label=sub, xalign=0, wrap=True)
            subl.add_css_class("snyp-sub")
            text.append(subl)
        box.append(text)
        widget.set_valign(Gtk.Align.CENTER)
        box.append(widget)
        r = Gtk.ListBoxRow(activatable=False)
        r.set_child(box)
        group.append(r)
        return subl

    def switch(self, key, on_change=None):
        sw = Gtk.Switch(active=self.cfg[key])

        def changed(w, _):
            self.set(**{key: w.get_active()})
            if on_change:
                on_change(w.get_active())
        sw.connect("notify::active", changed)
        return sw

    def dropdown(self, key, options, on_change=None):
        values = [v for v, _ in options]
        dd = Gtk.DropDown.new_from_strings([t for _, t in options])
        dd.set_selected(values.index(self.cfg[key]) if self.cfg[key] in values else 0)

        def changed(w, _):
            self.set(**{key: values[w.get_selected()]})
            if on_change:
                on_change()
        dd.connect("notify::selected", changed)
        return dd

    def set(self, **kv):
        self.cfg = update_config(**kv)
        self.refresh()

    def say(self, text, bad=False):
        self.status.set_text(text)
        (self.status.add_css_class if bad else self.status.remove_css_class)("snyp-bad")

    # --- pages

    def _build(self):
        cfg = self.cfg
        # General
        pg = self.page("general", "General")
        g = self.group(pg)
        self.hotkey_btn = self.key_button(cfg["hotkey"], self.set_hotkey, is_global=True)
        self.row(g, "Screenshot shortcut", self.hotkey_btn,
                 "Click, then press the keys you want. Backspace turns it off, Esc cancels.")
        self.row(g, "Tray icon", self.switch("tray", self.daemon.set_tray),
                 "Right-click it for these preferences. Without it, open snypshot from "
                 "the app menu.")
        self.row(g, "Notifications", self.switch("notify"), "After copying or saving")
        reset = Gtk.Button(label="Reset all preferences", halign=Gtk.Align.START)
        reset.connect("clicked", self.reset)
        pg.append(reset)

        # Saving
        pg = self.page("saving", "Saving",
                       "Ctrl+S saves straight away. The Save button asks where.")
        g = self.group(pg)
        self.row(g, "Ctrl+S saves to", self.dropdown(
            "save_mode", [("last", "The folder you last saved in"),
                          ("fixed", "Always the same folder")]))
        self.folder_btn = Gtk.Button(label=self.folder_text())
        self.folder_btn.connect("clicked", self.pick_folder)
        self.row(g, "Folder", self.folder_btn)
        g = self.group(pg)
        self.row(g, "File names", self.dropdown(
            "name_style", [("number", "Numbered (Screenshot_1)"),
                           ("date", "Date and time (Screenshot_2026-09-23_13-44-02)")]))
        self.prefix = Gtk.Entry(text=cfg["name_prefix"], width_chars=18)
        self.prefix.connect("changed", self.prefix_changed)
        self.row(g, "Names start with", self.prefix)
        self.row(g, "Format", self.dropdown("format", [("png", "PNG (sharp, bigger)"),
                                                       ("jpg", "JPG (smaller)")]))
        self.quality = Gtk.SpinButton.new_with_range(50, 100, 1)
        self.quality.set_value(cfg["jpg_quality"])
        self.quality.connect("value-changed",
                             lambda w: self.set(jpg_quality=int(w.get_value())))
        self.row(g, "JPG quality", self.quality)
        self.preview = Gtk.Label(xalign=0)
        self.preview.add_css_class("snyp-note")
        pg.append(self.preview)

        # Keyboard
        pg = self.page("keys", "Keyboard",
                       "Shortcuts while a screenshot is open. Click one, then press the new "
                       "keys. Backspace turns it off, Esc cancels. Enter always copies and "
                       "Esc always backs out.")
        g = self.group(pg)
        self.key_btns = {}
        for action, title in KEY_ACTIONS:
            b = self.key_button(cfg["keys"][action],
                                lambda accel, a=action: self.set_key(a, accel))
            self.key_btns[action] = b
            self.row(g, title, b)
        rk = Gtk.Button(label="Reset shortcuts", halign=Gtk.Align.START)
        rk.connect("clicked", lambda *_: self.set(keys=dict(DEFAULT_KEYS)) or self.sync_keys())
        pg.append(rk)

        # Look
        pg = self.page("look", "Look")
        g = self.group(pg)
        dim = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 90, 5)
        dim.set_value(round(cfg["dim"] * 100))
        dim.set_size_request(220, -1)
        dim.set_draw_value(True)
        dim.set_format_value_func(lambda sc, v: f"{int(v)}%")
        dim.connect("value-changed", lambda w: self.set(dim=round(w.get_value()) / 100))
        self.row(g, "Darken outside the selection", dim)
        self.row(g, "Size label", self.switch("show_size"), "The 800x600 above the selection")
        ui = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 75, 200, 5)
        ui.set_value(round((cfg["ui_scale"] or 1.0) * 100))
        ui.set_size_request(220, -1)
        ui.set_draw_value(True)
        ui.set_format_value_func(lambda sc, v: f"{int(v)}%")
        ui.connect("value-changed", lambda w: self.set(ui_scale=round(w.get_value()) / 100))
        self.row(g, "Toolbar size", ui)
        self.refresh()

    def refresh(self):
        cfg = self.cfg
        if not hasattr(self, "preview"):
            return
        fixed = cfg["save_mode"] == "fixed"
        self.folder_btn.set_sensitive(fixed)
        self.folder_btn.set_label(self.folder_text())
        self.quality.set_sensitive(cfg["format"] == "jpg")
        folder = (cfg["save_dir"] if fixed else None) or cfg["last_dir"] or \
            os.path.expanduser("~/Pictures")
        if os.path.isdir(folder):
            self.preview.set_text(f"Next Ctrl+S: {os.path.join(folder, next_file_name(folder, cfg))}")

    def folder_text(self):
        d = self.cfg["save_dir"]
        return d.replace(os.path.expanduser("~"), "~", 1) if d else "Choose..."

    def pick_folder(self, *_):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dlg = Gtk.FileChooserDialog(title="Save screenshots in", transient_for=self.win,
                                        modal=True, action=Gtk.FileChooserAction.SELECT_FOLDER)
            dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dlg.add_button("Select", Gtk.ResponseType.ACCEPT)
            start = self.cfg["save_dir"] or os.path.expanduser("~/Pictures")
            if os.path.isdir(start):
                dlg.set_current_folder(Gio.File.new_for_path(start))

        def done(d, resp):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                f = d.get_file() if resp == Gtk.ResponseType.ACCEPT else None
            path = f.get_path() if f else None
            d.destroy()
            if path and os.path.isdir(path):
                self.set(save_dir=path, save_mode="fixed")
        dlg.connect("response", done)
        dlg.present()

    def prefix_changed(self, e):
        text = e.get_text()
        before = self.cfg["name_prefix"]
        self.cfg = update_config(name_prefix=text)
        if self.cfg["name_prefix"] != text:           # rejected by the validator
            update_config(name_prefix=before)
            self.cfg = load_config()
            e.add_css_class("snyp-bad")
            self.say("File names can't contain / or \\ or start with a dot.", bad=True)
        else:
            e.remove_css_class("snyp-bad")
            self.say("")
        self.refresh()

    # --- shortcuts

    def key_button(self, accel, on_done, is_global=False):
        b = Gtk.Button(label=accel_label(accel))
        b.add_css_class("snyp-key")
        b.connect("clicked", lambda *_: self.record(b, on_done, is_global))
        return b

    def record(self, btn, on_done, is_global):
        self.stop_recording(cancel=True)
        if is_global:
            suspend_hotkeys()                      # so the key reaches us
        self.recording = (btn, on_done, is_global, btn.get_label())
        btn.set_label("Press keys...")
        btn.add_css_class("snyp-recording")
        self.say("Press the new shortcut. Backspace turns it off, Esc cancels.")

    def stop_recording(self, cancel=False):
        if not self.recording:
            return
        btn, _, is_global, old = self.recording
        self.recording = None
        btn.remove_css_class("snyp-recording")
        if cancel:
            btn.set_label(old)
        if is_global:
            resume_hotkeys()

    def _key(self, ctl, keyval, keycode, state):
        if not self.recording:
            return False
        btn, on_done, is_global, old = self.recording
        name = Gdk.keyval_name(keyval) or ""
        mods = state & mods_mask()
        if name in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
                    "Super_L", "Super_R", "Meta_L", "Meta_R", "ISO_Level3_Shift"):
            return True                            # wait for the real key
        if name == "Escape" and not mods:
            self.stop_recording(cancel=True)
            self.say("")
            return True
        if name == "BackSpace" and not mods:
            accel = ""
        else:
            accel = Gtk.accelerator_name(Gdk.keyval_to_lower(keyval), mods)
            plain = not mods & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK
                                | Gdk.ModifierType.SUPER_MASK)
            ch = Gdk.keyval_to_unicode(keyval)
            if is_global and plain and ch and chr(ch).isprintable():
                self.say("Add Ctrl, Alt or Super to that key, or it would fire while you type.",
                         bad=True)
                return True
        self.stop_recording()
        btn.set_label(accel_label(accel))
        on_done(accel)
        return True

    def set_hotkey(self, accel, take=False):
        other = apply_hotkey(accel, take=take)
        if other:
            self.hotkey_btn.set_label(accel_label(self.cfg["hotkey"]))
            dlg = Gtk.AlertDialog(message=f"“{other}” already uses {accel_label(accel)}",
                                  detail=f"Give {accel_label(accel)} to snypshot? "
                                         f"“{other}” stays, just without a key.",
                                  buttons=["Cancel", "Use it for snypshot"],
                                  cancel_button=0, default_button=1)

            def chosen(d, res):
                try:
                    if d.choose_finish(res) == 1:
                        self.set_hotkey(accel, take=True)
                except GLib.Error:
                    pass
            dlg.choose(self.win, None, chosen)
            return
        self.cfg = load_config()
        self.hotkey_btn.set_label(accel_label(accel))
        self.say(f"{accel_label(accel)} now takes a screenshot." if accel else
                 "The screenshot shortcut is off. Use the tray icon to take one.")

    def set_key(self, action, accel):
        keys = dict(self.cfg["keys"])
        clash = [a for a, v in keys.items() if a != action and v and accel
                 and norm_accel(v) == norm_accel(accel)]
        for a in clash:
            keys[a] = ""
        keys[action] = accel
        self.set(keys=keys)
        self.sync_keys()
        names = dict(KEY_ACTIONS)
        self.say(f"{accel_label(accel)} moved here from “{names[clash[0]]}”, which is "
                 "now off." if clash else "")

    def sync_keys(self):
        for a, b in self.key_btns.items():
            b.set_label(accel_label(self.cfg["keys"][a]))

    def reset(self, *_):
        keep = {k: self.cfg[k] for k in ("color", "width", "custom", "slot", "last_dir",
                                          "allow_portal")}
        save_config({**json.loads(json.dumps(DEFAULTS)), **keep})
        apply_hotkey(DEFAULTS["hotkey"], take=True)
        self.daemon.set_tray(True)
        self.win.destroy()
        self.daemon.prefs = None
        self.daemon.open_prefs()

    def _closing(self, *_):
        self.stop_recording(cancel=True)
        self.daemon.prefs = None
        return False

    def present(self):
        self.win.present()


# ---------------------------------------------------------------- background mode

CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
                         "snypshot")
LOG = os.path.join(CACHE_DIR, "snypshot.log")
SCRIPT = os.path.realpath(__file__)   # the real file, even when run as the `shot` alias


def cache_dir():
    """~/.cache/snypshot, private (0700) even if it already existed."""
    os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
    os.chmod(CACHE_DIR, 0o700)
    return CACHE_DIR


def log_fd():
    """The log file, private (0600), opened for appending."""
    cache_dir()
    fd = os.open(LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    return fd


def log(msg):
    try:
        with os.fdopen(log_fd(), "a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def tray_icon_path():
    """A simple white crop-marks icon for the top bar / tray."""
    path = os.path.join(CACHE_DIR, "snypshot-tray.png")
    cache_dir()
    S = 4
    im = Image.new("RGBA", (64 * S, 64 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    white, w = (255, 255, 255, 255), 6 * S
    a, b, L = 10 * S, 54 * S, 16 * S
    for (x, y, dx, dy) in ((a, a, 1, 1), (b, a, -1, 1), (a, b, 1, -1), (b, b, -1, -1)):
        d.line([(x, y), (x + dx * L, y)], fill=white, width=w)
        d.line([(x, y), (x, y + dy * L)], fill=white, width=w)
        r = w / 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=white)
    c, r = 32 * S, 5 * S
    d.ellipse([c - r, c - r, c + r, c + r], fill=white)
    im.resize((64, 64), Image.LANCZOS).save(path)
    return path


def run_tray(icon):
    """Separate little process that shows the tray icon (keeps GTK away from Tk)."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AI
        except (ValueError, ImportError):
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3 as AI
        from gi.repository import GLib, Gtk
    except Exception as e:
        print(f"snypshot: no tray icon ({e}). To get one: "
              "sudo apt install gir1.2-ayatanaappindicator3-0.1", file=sys.stderr)
        return

    ind = AI.Indicator.new("snypshot", icon, AI.IndicatorCategory.APPLICATION_STATUS)
    ind.set_status(AI.IndicatorStatus.ACTIVE)
    ind.set_title("snypshot")
    menu = Gtk.Menu()

    def item(label, cmd):
        mi = Gtk.MenuItem(label=label)
        mi.connect("activate", lambda *_: send(cmd))
        menu.append(mi)
        return mi

    first = item("Take screenshot", "capture-menu")
    item("Preferences", "prefs")
    menu.append(Gtk.SeparatorMenuItem())
    item("Quit snypshot", "quit")
    menu.show_all()
    ind.set_menu(menu)
    ind.set_secondary_activate_target(first)     # middle-click = screenshot

    parent = os.getppid()

    def watch():                                  # exit if the main process goes away
        if os.getppid() != parent:
            Gtk.main_quit()
            return False
        return True

    GLib.timeout_add_seconds(2, watch)
    signal.signal(signal.SIGTERM, lambda *a: GLib.idle_add(Gtk.main_quit))
    Gtk.main()


class Daemon:
    """Stays loaded in the background so Print Screen opens the overlay instantly."""

    def __init__(self, capture_now, helper=False):
        global HELPER
        if helper:                                # started by the GNOME helper extension
            parent = ""
            try:
                parent = os.readlink(f"/proc/{os.getppid()}/exe")
            except OSError:
                pass
            if parent.endswith(" (deleted)"):   # gnome-shell was upgraded while running
                parent = parent[:-len(" (deleted)")]
            if parent != "/usr/bin/gnome-shell" or not root_owned(parent):
                sys.exit("snypshot: --helper is only for the GNOME helper extension")
            HELPER = HelperChannel()
        no_dumps()
        init_gtk()
        self.loop = GLib.MainLoop()
        self.shot = None
        self.busy = False

        private_dir()                             # our own 0700 folder, verified
        if helper and send("ping") == "ok":       # an older, non-helper copy is running:
            send("quit")                          # take over from it
            for _ in range(40):
                if send("ping") != "ok":
                    break
                time.sleep(0.05)
        try:
            os.remove(SOCK)                       # stale socket from a crash
        except OSError:
            pass
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old_umask = os.umask(0o177)               # socket is born 0600, no race
        try:
            self.srv.bind(SOCK)
        finally:
            os.umask(old_umask)
        self.srv.listen(8)
        self.srv.setblocking(False)
        GLib.io_add_watch(self.srv.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN,
                          self.on_request)

        self.tray = None
        self.prefs = None
        resume_hotkeys()                          # in case we died while you picked a key
        if load_config()["tray"]:
            self.set_tray(True)

        for sig in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self.quit)
        GLib.timeout_add(500, self.tick)
        log(f"started ({my_cgroup_unit() or 'no systemd scope'})")
        set_portal_permission(bool(load_config().get("allow_portal")) and not HELPER)
        if HELPER:
            HELPER.say("ready")
        if capture_now:
            self.launcher = os.getppid()
            self.waited = 0
            GLib.timeout_add(10, self.capture_when_detached)

    def run(self):
        self.loop.run()

    def set_tray(self, on):
        if on and not (self.tray and self.tray.poll() is None):
            try:
                err = os.fdopen(log_fd(), "a")
                self.tray = subprocess.Popen(
                    [sys.executable, "-I", SCRIPT, "--tray", tray_icon_path()],
                    stdin=subprocess.DEVNULL, stdout=err, stderr=err, env=clean_env())
            except Exception as e:
                log(f"tray failed: {e}")
        elif not on and self.tray and self.tray.poll() is None:
            self.tray.terminate()
            self.tray = None

    def open_prefs(self):
        if self.prefs is not None:
            self.prefs.present()
            return
        try:
            self.prefs = Preferences(self)
        except Exception:
            import traceback
            log("preferences failed:\n" + traceback.format_exc())
            self.prefs = None

    def open_overlay(self, img):
        self.shot = Overlay(img, on_close=self.closed)

    def capture_when_detached(self):
        """First capture right after starting: wait until our launcher has exited, so
        the shortcut that started us is done and we're fully in the background."""
        if os.getppid() == self.launcher and self.waited < 1500:
            self.waited += 25
            return True                           # check again in 25ms
        self.capture()
        return False

    def tick(self):
        if HELPER and HELPER.eof:                 # the GNOME helper went away: so do we
            self.quit()
            return False
        return True

    def on_request(self, *_):
        try:
            conn, _ = self.srv.accept()
        except OSError:
            return True
        cmd = ""
        try:
            # Only processes running as you may talk to snypshot (belt and braces: the
            # socket is already 0600 inside a 0700 folder).
            import struct
            creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                    struct.calcsize("3i"))
            _pid, uid, _gid = struct.unpack("3i", creds)
            if uid != os.getuid():
                return True
            conn.settimeout(0.5)
            cmd = conn.recv(64).decode(errors="replace").strip()
            if cmd == "test":                     # diagnostics: report, never save
                conn.settimeout(70)
                conn.sendall(self.test_capture().encode())
            elif cmd == "version":
                conn.sendall(VERSION.encode())
            else:
                conn.sendall(b"ok")
        except OSError:
            cmd = ""
        finally:
            conn.close()
        if cmd == "capture":
            GLib.idle_add(lambda: self.capture() or False)
        elif cmd == "capture-menu":               # let the tray menu close first
            GLib.timeout_add(400, lambda: self.capture() or False)
        elif cmd == "prefs":
            GLib.idle_add(lambda: self.open_prefs() or False)
        elif cmd == "quit":
            GLib.idle_add(lambda: self.quit() or False)
        return True

    def capture(self):
        if self.shot is not None and getattr(self.shot, "hidden", False):
            self.shot.close()                     # a leftover hidden overlay: start fresh
        if self.shot is not None:                 # already open: just bring it forward
            self.shot.take_focus()
            return
        if self.busy:
            return
        self.busy = True
        try:
            self.open_overlay(grab_screen())
        except SystemExit as e:                   # couldn't capture / refused
            log(str(e))
            notify(str(e).splitlines()[-1])
            self.shot = None
        except Exception:
            import traceback
            log(traceback.format_exc())
            notify("Something went wrong, see ~/.cache/snypshot/snypshot.log")
            self.shot = None
        finally:
            self.busy = False

    def closed(self):
        self.shot = None

    def test_capture(self):
        """Grab the screen, report how, throw the pixels away."""
        t0 = time.time()
        try:
            img = grab_screen()
        except SystemExit as e:
            return f"FAILED: {str(e).splitlines()[-1]}"
        shots = img if isinstance(img, list) else [(None, img)]
        size = " + ".join(f"{im.width}x{im.height}" for _, im in shots)
        return (f"OK: {size} via '{_working_method}' in "
                f"{time.time() - t0:.2f}s" + ("" if _working_method == "ext" else
                                              f" | helper: {helper_status()}")
                + (" | the GNOME part loaded right now is the OLD one (blurry on mixed "
                   "scaling): log out and back in to finish updating" if _old_helper else ""))

    def quit(self, *_):
        log("quit")
        if self.prefs is not None:
            self.prefs.stop_recording(cancel=True)   # give the screenshot keys back
        if self.tray and self.tray.poll() is None:
            self.tray.terminate()
        try:
            self.srv.close()
            os.remove(SOCK)
        except OSError:
            pass
        self.loop.quit()
        return False


DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=snypshot
Comment=Lightshot-style screenshots
Exec="{exe}" {arg}
Icon={icon}
Terminal=false
Categories=Utility;Graphics;
X-GNOME-Autostart-enabled=true
"""


def install(gnome_helper=False):
    if any(ch in SCRIPT for ch in '"\\\n$`%'):
        print("Refusing: odd characters in the install path.")
        return
    home_cfg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    home_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    folders = {os.path.join(home_data, "applications"): "--preferences"}  # app menu: settings
    autostart = os.path.join(home_cfg, "autostart", "snypshot.desktop")
    if gnome_helper:                  # the GNOME helper starts snypshot itself at login
        try:
            os.remove(autostart)
        except OSError:
            pass
    else:
        folders[os.path.dirname(autostart)] = "--daemon"
    for folder, arg in folders.items():
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "snypshot.desktop"), "w") as f:
            f.write(DESKTOP_ENTRY.format(exe=SCRIPT, icon=tray_icon_path(), arg=arg))
    print("snypshot is in your app menu" + ("." if gnome_helper else
                                        " and will start in the background at login."))


def uninstall():
    home_cfg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    home_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    for folder in (os.path.join(home_cfg, "autostart"), os.path.join(home_data, "applications")):
        try:
            os.remove(os.path.join(folder, "snypshot.desktop"))
        except OSError:
            pass
    set_portal_permission(False)
    cfg = load_config()
    if cfg.get("allow_portal"):
        cfg["allow_portal"] = False
        save_config(cfg)
    print("Removed snypshot from startup and the app menu.")


def migrate_from_shot():
    """Move an existing `shot` install over to snypshot: settings, Print Screen key,
    app-menu entry and the old helper. Only touches things that are recognisably ours
    (another app could also be called "shot"). Returns True if there was one."""
    home_cfg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    home_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    found = False

    def remove_if_ours(path, marker):
        try:
            with open(path, "rb") as f:
                if marker not in f.read(65536):
                    return False
            os.remove(path)
            return True
        except OSError:
            return False

    old_ext = os.path.join(home_data, "gnome-shell", "extensions", f"{OLD_NAME}@io.github.{OLD_NAME}")
    if os.path.isdir(old_ext) and not os.path.islink(old_ext):
        # Still loaded until you log out; it keeps running snypshot through the `shot`
        # alias until then, so Print Screen keeps working. Only its files go.
        found = True
        shutil.rmtree(old_ext, ignore_errors=True)
    for f in (os.path.join(home_data, "applications", f"{OLD_NAME}.desktop"),
              os.path.join(home_cfg, "autostart", f"{OLD_NAME}.desktop")):
        found |= remove_if_ours(f, b"Lightshot-style")
    if have("gsettings"):
        old_key = KEY_PATH.replace("/snypshot/", f"/{OLD_NAME}/")
        paths = custom_key_paths()
        cmd = gset("get", f"{MEDIA_KEYS}.custom-keybinding:{old_key}", "command")
        if old_key in paths and cmd.strip("'") == ALIAS:
            found = True
            gset("set", MEDIA_KEYS, "custom-keybindings", str([p for p in paths if p != old_key]))
            gset("reset-recursively", f"{MEDIA_KEYS}.custom-keybinding:{old_key}")
    old_dir = os.path.join(home_cfg, OLD_NAME)
    old_cfg = os.path.join(old_dir, "config.json")
    if found and os.path.isfile(old_cfg) and not os.path.islink(old_cfg):
        if not os.path.exists(CONFIG):            # colors, brush size, last folder
            os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
            shutil.copyfile(old_cfg, CONFIG)
            os.chmod(CONFIG, 0o600)
        os.remove(old_cfg)
        try:
            os.rmdir(old_dir)
        except OSError:
            pass
    old_sock = os.path.join(RUNTIME_DIR, OLD_NAME, f"{OLD_NAME}.sock")
    try:                                          # stop the old background copy
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(old_sock)
        s.sendall(b"quit\n")
        s.recv(16)
        s.close()
        found = True
    except OSError:
        pass
    if found:
        print("Moved your old `shot` setup over to snypshot.")
    return found


def clean_old_cache():
    """The old ~/.cache/shot (log + tray icon), once the old copy has stopped."""
    old_cache = os.path.join(os.path.dirname(CACHE_DIR), OLD_NAME)
    for f in ("shot.log", "shot-tray.png"):
        try:
            os.remove(os.path.join(old_cache, f))
        except OSError:
            pass
    try:
        os.rmdir(old_cache)
    except OSError:
        pass


MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
KEY_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/snypshot/"


def gset(*args):
    return subprocess.run([T("gsettings"), *args], capture_output=True, env=clean_env(), text=True).stdout.strip()


def custom_key_paths():
    import ast
    raw = gset("get", MEDIA_KEYS, "custom-keybindings").replace("@as ", "")
    try:
        return list(ast.literal_eval(raw))
    except Exception:
        return []


SHELL_KEYS = "org.gnome.shell.keybindings"
SHELL_SHOT_KEYS = ("show-screenshot-ui", "screenshot", "screenshot-window")


def norm_accel(a):
    """'<Primary><shift>print' and '<Shift><Control>Print' -> one comparable form."""
    a = (a or "").strip("'")
    mods = sorted(m.lower().replace("primary", "control") for m in re.findall(r"<(\w+)>", a))
    return "".join(f"<{m}>" for m in mods) + re.sub(r"<\w+>", "", a).lower()


def gsettings_list(schema, key):
    import ast
    raw = gset("get", schema, key).replace("@as ", "")
    try:
        v = ast.literal_eval(raw)
        return [x for x in v if isinstance(x, str)]
    except Exception:
        return []


def hotkey_owner(accel):
    """Name of another custom shortcut already using accel, or None."""
    for p in custom_key_paths():
        if p == KEY_PATH:
            continue
        b = gset("get", f"{MEDIA_KEYS}.custom-keybinding:{p}", "binding")
        if accel and norm_accel(b) == norm_accel(accel):
            return gset("get", f"{MEDIA_KEYS}.custom-keybinding:{p}", "name").strip("'") or "another shortcut"
    return None


def apply_hotkey(accel, take=False):
    """Make accel ("Print", "<Shift>Print", "<Super><Shift>s"...) take a screenshot.
    "" turns the shortcut off. If another custom shortcut has it, returns that one's
    name and changes nothing, unless take=True (then it loses the key, keeps the rest).
    GNOME's own screenshot keys always give it up."""
    if accel and not ACCEL_RE.fullmatch(accel):
        return "that key"
    other = hotkey_owner(accel)
    if other and not take:
        return other
    for p in custom_key_paths():
        if p != KEY_PATH and accel and norm_accel(
                gset("get", f"{MEDIA_KEYS}.custom-keybinding:{p}", "binding")) == norm_accel(accel):
            gset("set", f"{MEDIA_KEYS}.custom-keybinding:{p}", "binding", "''")
    paths = custom_key_paths()
    if KEY_PATH not in paths:
        paths.append(KEY_PATH)
        gset("set", MEDIA_KEYS, "custom-keybindings", str(paths))
    k = f"{MEDIA_KEYS}.custom-keybinding:{KEY_PATH}"
    gset("set", k, "name", "'snypshot'")
    gset("set", k, "command", f"'{SCRIPT}'")
    gset("set", k, "binding", f"'{accel}'")
    for key in SHELL_SHOT_KEYS:                    # GNOME's own screenshot keys step aside
        cur = gsettings_list(SHELL_KEYS, key)
        keep = [x for x in cur if norm_accel(x) != norm_accel(accel)]
        if keep != cur:
            gset("set", SHELL_KEYS, key, str(keep))
    if norm_accel(accel) != "print" and not gsettings_list(SHELL_KEYS, "show-screenshot-ui"):
        gset("reset", SHELL_KEYS, "show-screenshot-ui")   # Print back to GNOME's tool
        if norm_accel(accel) in map(norm_accel, gsettings_list(SHELL_KEYS, "show-screenshot-ui")):
            gset("set", SHELL_KEYS, "show-screenshot-ui", "[]")
    update_config(hotkey=accel or "")
    return None


SUSPENDED = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
                         "snypshot", "suspended-keys.json")


def suspend_hotkeys():
    """While you pick a new shortcut, switch off the screenshot keys (ours and GNOME's)
    so pressing one reaches the Preferences window instead of taking a screenshot.
    Remembered on disk, so they come back even if snypshot is killed meanwhile."""
    if not have("gsettings") or os.path.exists(SUSPENDED):
        return
    saved = {"ours": gset("get", f"{MEDIA_KEYS}.custom-keybinding:{KEY_PATH}", "binding").strip("'"),
             "shell": {k: gsettings_list(SHELL_KEYS, k) for k in SHELL_SHOT_KEYS}}
    cache_dir()
    fd = os.open(SUSPENDED, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(saved, f)
    gset("set", f"{MEDIA_KEYS}.custom-keybinding:{KEY_PATH}", "binding", "''")
    for k in SHELL_SHOT_KEYS:
        gset("set", SHELL_KEYS, k, "[]")


def resume_hotkeys():
    try:
        with open(SUSPENDED) as f:
            saved = json.load(f)
        os.remove(SUSPENDED)
    except (OSError, ValueError):
        return
    ok = lambda v: isinstance(v, str) and (v == "" or ACCEL_RE.fullmatch(v))
    if isinstance(saved, dict):
        if ok(saved.get("ours")):
            gset("set", f"{MEDIA_KEYS}.custom-keybinding:{KEY_PATH}", "binding", f"'{saved['ours']}'")
        shell = saved.get("shell") if isinstance(saved.get("shell"), dict) else {}
        for k in SHELL_SHOT_KEYS:
            v = shell.get(k)
            if isinstance(v, list) and all(ok(x) for x in v):
                gset("set", SHELL_KEYS, k, str(v))


def bind_key(key=None):
    """Point the screenshot key (Print Screen unless you changed it) at snypshot in
    GNOME, keeping your other custom shortcuts."""
    key = load_config()["hotkey"] if key is None else key
    if not have("gsettings") or "gnome" not in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
        print("Automatic key setup only works on GNOME. Add a custom shortcut in your "
              f"keyboard settings that runs:  {SCRIPT}")
        return
    other = apply_hotkey(key)
    if other:
        answer = ""
        if sys.stdin.isatty():
            answer = input(f"Your '{other}' shortcut is using {key}. Give {key} to snypshot "
                           f"instead? ('{other}' is kept, just without a key) [Y/n] ")
        if sys.stdin.isatty() and answer.strip().lower() in ("", "y", "yes"):
            apply_hotkey(key, take=True)
            print(f"Took {key} off '{other}'.")
        else:
            print(f"Your custom shortcut '{other}' already uses {key}. Change it in "
                  "Settings > Keyboard > Custom Shortcuts, or pick another key in snypshot's "
                  "Preferences.")
            return
    print(f"{key} now opens snypshot. (Your other custom shortcuts are untouched.)")


def unbind_key():
    paths = [p for p in custom_key_paths() if p != KEY_PATH]
    gset("set", MEDIA_KEYS, "custom-keybindings", str(paths))
    gset("reset-recursively", f"{MEDIA_KEYS}.custom-keybinding:{KEY_PATH}")
    resume_hotkeys()
    for k in SHELL_SHOT_KEYS:                     # GNOME's own screenshot keys, as they were
        gset("reset", SHELL_KEYS, k)
    print("Print Screen is back to GNOME's screenshot tool.")


def replace_old_daemon():
    """After an update, the background copy is still running the OLD code (Python loaded
    it at login). If it isn't this version, stop it; the GNOME helper (or the code
    below in main) starts the new one straight away."""
    if send("ping") != "ok" or send("version") == VERSION:
        return
    log(f"replacing an older running copy with {VERSION}")
    send("quit")
    for _ in range(60):
        if send("ping") != "ok":
            break
        time.sleep(0.05)
    if helper_active() or helper_expected():
        for _ in range(50):                       # helper allows one Start() a second
            try:
                helper_call("Start", None, 2000)
            except Exception:
                pass
            if send("ping") == "ok":
                return
            time.sleep(0.1)


def main():
    args = sys.argv[1:]
    if "--bind-key" in args:
        bind_key()
        return
    if "--unbind-key" in args:
        unbind_key()
        return
    if "--test-capture" in args or "--doctor" in args:
        # Diagnostics. The background copy does the capture and only REPORTS how it
        # went; no screenshot is ever written to disk (or it could be abused).
        print(f"installed at:   {SCRIPT} ({'root-owned, good' if root_owned(SCRIPT) else 'NOT root-owned: the GNOME helper will refuse it'})")
        print(f"version:        {VERSION}")
        replace_old_daemon()
        running = send("version") if send("ping") == "ok" else None
        print(f"background:     {('running ' + running) if running else 'not running (start: snypshot --daemon)'}")
        if "gnome" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
            print(f"GNOME helper:   {helper_status()}")
            print(f"portal opt-in:  {'yes (less private)' if load_config().get('allow_portal') else 'no'}")
        print("clipboard:      built in (GTK)")
        if send("ping") == "ok":
            print(f"test capture:   {send('test', timeout=75) or 'no answer'}")
        return
    if "--version" in args:
        print(f"snypshot {VERSION}")
        return
    if "--allow-portal" in args or "--disallow-portal" in args:
        cfg = load_config()
        cfg["allow_portal"] = "--allow-portal" in args
        save_config(cfg)
        set_portal_permission(cfg["allow_portal"])
        print("Portal fallback " + ("allowed. Note: other programs could pretend to be snypshot "
                                    "to use it (with GNOME's sound and flash)."
                                    if cfg["allow_portal"] else "disabled."))
        return
    if "--tray" in args:
        run_tray(args[args.index("--tray") + 1])
        return
    if "--quit" in args:
        print("stopped snypshot" if send("quit") == "ok" else "snypshot wasn't running")
        return
    if "--install-extension" in args:
        install_extension()
        return
    if "--install" in args:
        moved = migrate_from_shot()
        bind_key()
        helper = install_extension()
        install(gnome_helper=helper)
        replace_old_daemon()
        if moved:                                 # the old helper restarts us through the
            for _ in range(80):                   # `shot` alias; wait for that
                if send("ping") == "ok":
                    break
                time.sleep(0.1)
            clean_old_cache()
        if send("ping") != "ok":
            subprocess.Popen([sys.executable, "-I", SCRIPT, "--daemon"], env=clean_env(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if "--from-setup" in args:
            print()
            if helper_active():
                print("Done! Press Print Screen.")
            elif moved and send("ping") == "ok":
                print("Done! Print Screen works now (your settings came along from shot).\n"
                      "Log out and back in once whenever you like to finish the switch.")
            else:
                print("Done! Log out and back in once, then press Print Screen.")
        return
    if "--uninstall" in args:
        send("quit")
        uninstall()
        if "gnome" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
            unbind_key()
            uninstall_extension()
        files = [f for f in (BIN, ALIAS) if os.path.exists(f) and _ours(f)]
        if files and os.geteuid() != 0:
            print("Removing the program itself (asks for your password):")
            subprocess.run([T("sudo"), "rm", "-f", *files], env=clean_env())
        print("snypshot is gone. Your settings are in ~/.config/snypshot if you want them.")
        return
    if "--once" in args:
        no_dumps()
        img = grab_screen()
        init_gtk()
        loop = GLib.MainLoop()
        Overlay(img, on_close=loop.quit, persistent=False)
        loop.run()
        return

    if "--preferences" in args:
        if send("ping") != "ok":                  # start the background copy first
            subprocess.run([sys.executable, "-I", SCRIPT, "--daemon"], env=clean_env(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                if send("ping") == "ok":
                    break
                time.sleep(0.1)
        if send("prefs") != "ok":
            sys.exit("snypshot isn't running (see snypshot --doctor)")
        return
    capture_now = "--daemon" not in args or "--capture" in args
    if "--helper" in args:                        # launched by the GNOME helper extension
        Daemon(False, helper=True).run()
        return
    replace_old_daemon()                          # just updated? swap in the new code now
    if send("ping") == "ok":                      # already running in the background
        if capture_now:
            send("capture")
        else:
            print("snypshot is already running in the background.")
        return
    if helper_active() or helper_expected():     # on GNOME the helper runs snypshot itself
        for _ in range(60):                       # (it may still be starting at login)
            try:
                helper_call("Start", None, 2000)
            except Exception:
                pass
            if send("ping") == "ok":
                break
            time.sleep(0.1)
        if send("ping") == "ok":
            if capture_now:
                send("capture")
            else:
                print("The GNOME helper extension runs snypshot for you.")
            return
        log("the GNOME helper didn't start snypshot; running it directly")

    if "--foreground" not in args:                # detach, so the terminal/shortcut returns
        out = os.fdopen(log_fd(), "a")
        cmd = [sys.executable, "-I", SCRIPT, "--daemon", "--foreground"]
        if capture_now:
            cmd.append("--capture")
        started = False
        if have("systemd-run"):
            # Run inside a systemd scope named after our app ID, so GNOME's screenshot
            # portal always sees the same app ("io.github.snypshot") no matter how snypshot was
            # launched - that's what the screenshot permission gets attached to.
            scoped = [T("systemd-run"), "--user", "--scope", "--quiet", "--collect",
                      f"--unit=app-{APP_ID}-{os.getpid()}"] + cmd
            p = subprocess.Popen(scoped, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                 start_new_session=True, env=clean_env())
            try:
                started = p.wait(timeout=0.4) == 0      # exited already = it failed
            except subprocess.TimeoutExpired:
                started = True                           # still running = good
        if not started:
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                             start_new_session=True, env=clean_env())
        if not capture_now:
            print("snypshot is running in the background. Press your screenshot key to use it.")
        return

    Daemon(capture_now, helper="--helper" in args).run()


if __name__ == "__main__":
    main()
