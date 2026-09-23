# snypshot

**snypshot** (with a **y**) is a Lightshot-style screenshot tool for Linux. Press Print Screen, drag a box, scribble on it, then copy or save. That's it.

<!-- Add a GIF here: docs/demo.gif -->

## Install

Download it, then run its setup:

```sh
curl -fLO https://github.com/addition-official/snypshot/releases/latest/download/snypshot.py
python3 snypshot.py --setup
```

Nothing gets piped into a shell. It's one readable Python file, so you can look through it before you run it. Setup asks for your password once, to install the program for all users.

Then **log out and back in once**, and press **Print Screen**.

Works on **GNOME on Wayland** (tested on Ubuntu 24.04). Other desktops may work but aren't tested yet.

## Using it

| Do this | To |
| --- | --- |
| **Print Screen** | Take a screenshot |
| Drag | Select an area |
| Drag inside / on the edges | Move / resize the selection |
| Toolbar on the right | Pen, line, arrow, box, marker, text, color, undo |
| Mouse wheel | Down = bigger, up = smaller (brush or text size) |
| Hold **Shift** while drawing | Straight 45-degree lines, square boxes |
| **Ctrl+C** or **Enter** | Copy to clipboard and close |
| **Ctrl+S** | Save instantly as `Screenshot_N.png` in the last folder you used |
| **Ctrl+Shift+S** or the Save button | Save with a file dialog |
| **Ctrl+Z** / **Ctrl+Y** | Undo / redo |
| **Esc** | Put the tool down; press again to cancel |
| Right-click | Cancel |

You can draw outside the selection too, and it shows up if you make the selection bigger. Click placed text to edit it. The color picker has the 48 basic colors plus your own custom ones.

## Preferences

Right-click the tray icon and pick **Preferences**, or open snypshot from your app menu. Everything saves as soon as you change it.

- **General:** the screenshot shortcut (any key combo, not just Print Screen), the tray icon, notifications.
- **Saving:** where Ctrl+S saves (the last folder you used, or always the same one), numbered or date-and-time file names, what names start with, PNG or JPG, and JPG quality.
- **Keyboard:** your own shortcuts for copy, quick save, save as, undo and redo.
- **Look:** how dark the area outside the selection gets, the size label, and the toolbar size.

## Commands

```
snypshot              take a screenshot (Print Screen runs this; `shot` works too)
snypshot --preferences  open Preferences
snypshot --doctor     check the setup and do a test capture (nothing is saved)
snypshot --version    show the version
snypshot --quit       stop the background copy
snypshot --uninstall  remove snypshot completely
```

## Why log out once?

On Wayland, apps can't read the screen by themselves. snypshot ships a tiny GNOME Shell extension that takes the screenshot and hands it straight to snypshot. It's instant and silent, with no flash and no shutter sound. GNOME only loads new extensions when you log in.

## Privacy and security

- Screenshots never touch the disk unless you save them. They go from GNOME Shell to snypshot over a private pipe.
- The extension only hands screenshots to the copy of snypshot it started itself, and only if that copy is installed by root, so other programs can't swap themselves in. It refuses while snypshot is being debugged.
- The overlay is a native Wayland window that other apps can't read.
- snypshot doesn't use the network.

The full security notes are in the comments at the top of `snypshot.py`.

## Uninstall

```sh
snypshot --uninstall
```

This removes the program, the extension, the screenshot shortcut and the app-menu entry, and gives GNOME its own screenshot keys back. Your settings stay in `~/.config/snypshot` in case you come back.

## Requirements

`--setup` installs these for you (apt, dnf or pacman): Python 3, PyGObject with GTK 4, Pillow, pycairo, and optionally AyatanaAppIndicator (tray icon) and notify-send.

## License

MIT. See [LICENSE](LICENSE).

snypshot is an independent project and isn't affiliated with Lightshot.

## A note on how this was built

snypshot started because I wanted Lightshot on Linux and nothing else felt right, so I decided to make my own.

I built it with AI assistance: the code and this README were written with an AI. The idea, the name, the design calls (matching Lightshot's muscle memory, how Esc, saving, scrolling and text editing should behave, what goes in Preferences), and the push to harden it properly are mine. So is the testing on real hardware: running it daily on my own mixed-scaling dual-monitor setup is what caught the blurry captures, the save-dialog freeze and plenty more.