# snypshot

**snypshot** (with a **y**) is a Lightshot-style screenshot tool for Linux. Press Print Screen, drag a box, scribble on it, then copy or save. That's it.

<img width="800" height="450" alt="demo" src="https://github.com/user-attachments/assets/f543a1a5-ba26-4743-b4de-e79e7bb62a4c" />

## Install

Download it, then run its setup:

```sh
curl -fLO https://github.com/addition-official/snypshot/releases/latest/download/snypshot.py
python3 snypshot.py --setup
```

Nothing gets piped into a shell. It's one readable Python file, so you can look through it before you run it. Setup asks for your password once, to install the program for all users.

On **KDE Plasma**, that's it: press **Print Screen**. On **GNOME**, **log out and back in once** first.

Works on **GNOME** and **KDE Plasma** on Wayland (tested on Ubuntu 24.04 and 26.04, with GNOME and with KDE Plasma 5.27 and 6.6). Other desktops may work but aren't tested yet.

## Updating

Download the new `snypshot.py` and run `python3 snypshot.py --setup` again. Your settings stay. On GNOME, log out and back in once afterwards so GNOME loads the updated helper (snypshot keeps working until you do).

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
| **Ctrl+P** or the Print button | Print it (or print to a PDF file) |
| **Ctrl+Z** / **Ctrl+Y** | Undo / redo |
| **Esc** | Put the tool down; press again to cancel |
| Right-click | Cancel |

You can draw outside the selection too, and it shows up if you make the selection bigger. Click placed text to edit it. The color picker is a compact palette: click a color and you're drawing with it. **+** saves a new color of your own, and **Fine-tune** opens a color square and hex box next to the palette, where clicking one of your colors lets you edit it in place. Prefer the Windows/Lightshot-style dialog? Turn on **Classic color window** in Preferences.

## Preferences

Right-click the tray icon and pick **Preferences**, or open snypshot from your app menu. Everything saves as soon as you change it.

- **General:** the screenshot shortcut (any key combo, not just Print Screen), the tray icon, notifications. On KDE you can also change the shortcut in System Settings > Shortcuts, where it's listed as snypshot.
- **Saving:** where Ctrl+S saves (the last folder you used, or always the same one), numbered or date-and-time file names, what names start with, PNG or JPG, JPG quality, and the small "Screenshot taken with snypshot" watermark (on by default, only added when the screenshot is big enough for it).
- **Keyboard:** your own shortcuts for copy, quick save, save as, print, undo and redo.
- **Look:** how dark the area outside the selection gets, the size label, the toolbar size, and the classic color window.

## Commands

```
snypshot              take a screenshot (Print Screen runs this; `shot` works too)
snypshot --preferences  open Preferences
snypshot --doctor     check the setup and do a test capture (nothing is saved)
snypshot --version    show the version
snypshot --quit       stop the background copy
snypshot --uninstall  remove snypshot completely
```

## Why log out once on GNOME?

On Wayland, apps can't read the screen by themselves. On GNOME, snypshot ships a tiny GNOME Shell extension that takes the screenshot and hands it straight to snypshot. It's instant and silent, with no flash and no shutter sound. GNOME only loads new extensions when you log in.

KDE Plasma doesn't need that: KWin hands screenshots to apps it's told to trust, the same way it does for Spectacle, and setup takes care of it. Print Screen works straight away.

## KDE Plasma notes

- snypshot restarts itself if it ever crashes or KWin restarts, so Print Screen keeps working.
- Print Screen goes to snypshot instead of Spectacle. If you quit snypshot (tray icon > Quit), Print Screen goes back to Spectacle until snypshot starts again. Uninstalling gives Spectacle its keys back.
- On a screen with fractional scaling (like 125%), the frozen screen you draw on can look a little soft. The saved or copied image is still pixel-perfect.

## Privacy and security

- Screenshots never touch the disk unless you save or print them (printing writes a temporary PDF in a private folder and deletes it right after). They go from GNOME Shell or KWin to snypshot over a private pipe.
- On GNOME, the extension only hands screenshots to the copy of snypshot it started itself, and only if that copy is installed by root, so other programs can't swap themselves in. It refuses while snypshot is being debugged.
- On KDE, KWin trusts snypshot's own copy of Python (installed by root) to take screenshots. Like Spectacle's permission, that means programs you run could use it to take a screenshot without asking, which KDE already allows through Spectacle anyway.
- The overlay is a native Wayland window that other apps can't read.
- snypshot doesn't use the network.

The full security notes are in the comments at the top of `snypshot.py`.

## Uninstall

```sh
snypshot --uninstall
```

This removes the program, the extension, the screenshot shortcut and the app-menu entry, and gives GNOME or Spectacle its own screenshot keys back. Your settings stay in `~/.config/snypshot` in case you come back.

## Requirements

`--setup` installs these for you (apt, dnf or pacman): Python 3, PyGObject with GTK 4, Pillow, pycairo, and optionally AyatanaAppIndicator (tray icon) and notify-send. Printing to a printer uses CUPS, which desktop Linux already has; Save as PDF works without it.

## A note on how this was built

The hard part of this project wasn't the code, it was getting it to feel exactly like Lightshot and to hold up on a real, messy setup. That came from using it every day on my own dual-monitor, mixed-scaling machine, first on GNOME and then on KDE Plasma, and pushing back on everything that felt wrong. That's what caught the blurry captures, the save dialog that froze the whole desktop, the memory leak, the Print Screen and permission problems on KDE, and plenty more.

I used AI assistance to write the code and this README. The idea, the name, the design calls (matching Lightshot's muscle memory, how Esc, saving, scrolling and text editing behave, what goes in Preferences, how printing should look), the push to harden it properly, and the testing on real hardware are mine.

snypshot is an independent project and isn't affiliated with Lightshot.
