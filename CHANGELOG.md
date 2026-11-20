# Changelog

## 1.2

**Changed**
- KDE: the screenshot now stays on top of everything on every monitor while it's open, like Lightshot. Windows that pop up meanwhile (for example Zoom when screen sharing ends) can't cover it or take focus from it, and it no longer shows up in the taskbar or Alt+Tab. Dialogs that belong to it, like the print dialog, still open on top of it.
- Printing now uses your desktop's own print dialog (KDE's on Plasma, GTK's on GNOME), with all your printer's settings, instead of snypshot's own print window. snypshot's window is still there as a backup on desktops without one. Like Lightshot, the dialog opens on top of the screenshot instead of the screenshot disappearing first (on desktops that can't do that, the screenshot steps aside as before). Pressing Print Screen or Esc while the print dialog is open closes it and brings the screenshot back (once you've clicked Print, the page is on its way and the screenshot closes when it's sent).
- KDE: Alt+Tab and other desktop shortcuts don't switch away from a screenshot while it's open.
- Right-click no longer throws the screenshot away (it was too easy to hit by accident). Esc still cancels.
- Like Lightshot, dragging the box past the edge of the screen now eats the part that goes past it, and dragging back doesn't bring it back. Between two monitors it still moves across.
- If the editor ever fails to open after a screenshot, you no longer lose the screenshot: the full screen is saved where Ctrl+S saves and copied to the clipboard, and a notification tells you where it went.

**Fixed**
- GNOME: the screenshot no longer shows up in the taskbar with a generic Wayland icon; it uses snypshot's icon.
- The editor could fail to open after taking a screenshot ("returned NULL without setting an exception" in the log), so no screenshot could be taken. The color picker's hue bar is now drawn without the Pillow call that failed.
- `snypshot --uninstall` now cleans up GNOME and KDE even when run over SSH, from a console or from your other desktop. Before, Print Screen could stop working on the desktop you weren't on, and the GNOME helper stayed installed.
- `sudo snypshot` now tells you to run it as yourself. Before, `sudo snypshot --uninstall` removed nothing but said snypshot was gone.
- `snypshot --once` also keeps the screenshot if the editor fails to open.
- `snypshot --tray` without an icon path shows an error instead of crashing.
- If copying fails (for example wl-copy or xclip can't reach the screen), snypshot now says so and keeps the screenshot open, instead of saying "Copied to clipboard" and closing with nothing copied.
- A typo in `config.json` no longer wipes all your settings the next time you save: the broken file is kept as `config.json.broken` and snypshot starts from the defaults.
- A "Names start with" prefix made of many emoji is now refused right away, instead of making every save fail with "File name too long".
- If the editor fails to open on monitors with different scaling, the rescued full-screen image no longer has big black bands with monitors in the wrong place.
- With monitors that don't line up, a selection reaching into the empty space above a monitor no longer comes out cut short, with your drawings squashed and in the wrong place.
- With monitors of different sizes, dragging the box past the edge of the smaller one now eats the part that goes past it too, instead of letting it slide into space no screen shows and saving that as black.
- On two monitors at the same fractional scaling (for example both at 150% on KDE), a screenshot across both no longer comes out slightly blurred on one of them.
- Clicking into a placed text and leaving it unchanged no longer makes Ctrl+Z remove that text before your newer drawings, and no longer throws away what Ctrl+Y could bring back. Undoing an edit puts the text back where it was.
- A shape drawn over a text label now covers it in the saved or copied image too, like it does on screen. Before, text always came out on top.
- Plugging in or removing a monitor while a screenshot is open now closes it, instead of leaving a window that shows and selects the wrong part of the screen. Your work is kept first: the selection with your drawings (or the whole screenshot if nothing is selected) is saved and copied the same way as when the editor can't open, and a notification says so. While the Save or Print window is open the screenshot is left alone, so the save or print still goes ahead; it only closes this way if you cancel and it would come back.
- Changing a monitor's scale, resolution, rotation or position while a screenshot is open now closes it the same way (your work is kept first), instead of leaving windows that no longer fit the screen and select the wrong part of it.
- No more GTK warning in the log when there's no keyboard or mouse seat (for example in a headless session) on KDE.
- Printing to label printers (for example a Dymo) no longer fails with "invalid matrix", and on small labels the screenshot is no longer squeezed into a sliver by page-sized margins. The page is now the real label size.
- Paper sizes with a decimal point in the name (like "3.5x5" on driverless photo printers) are now laid out on that paper instead of on A4 or Letter.
- Pressing Cancel or Esc while "Sending to the printer..." is showing no longer brings the screenshot back as if nothing was printed (the job still prints), so you don't print it twice by accident. If that print then fails, a notification says so.
- After a failed print, Print stays off until the newly chosen printer's settings have loaded, so it can't send the previous printer's paper size and settings to it.
- KDE: setting snypshot's shortcut to a key a Spectacle action shares with another key (like Meta+Shift+S for the region capture, which also has Meta+Shift+Print) now takes only that key. The other key keeps working, and when snypshot moves off the key, the action gets it back next to its others. Other apps' shortcuts you give a key away from also keep their other keys.
- KDE: if snypshot couldn't get a key after all (or you press Cancel when it asks), Spectacle's key is no longer left turned off, and snypshot keeps its old key.
- KDE: a shortcut you changed in System Settings is now kept when you quit snypshot from the tray, instead of the old key coming back (and being taken from Spectacle again) at the next start. This includes keys like the keypad ones, which stay set while snypshot is off.
- KDE: snypshot no longer gives Print Screen back to "Launch Spectacle" when you turned that off yourself.
- KDE: Alt+Print Screen can now be chosen as the shortcut (it was recorded as "Sys Req", which KDE refused).
- GNOME: if the computer crashed or lost power while you were picking a new shortcut in Preferences, Print Screen could stay dead for good (for snypshot and for GNOME's own tool), and picking a key later no longer worked properly. snypshot now gives the keys back at the next start.
- GNOME: picking a shortcut no longer wipes a GNOME screenshot key that was set up with an unusual spelling (like `<Ctrl><Alt>Print`). That key stays on while you pick; the others are still switched off so the key you press reaches Preferences.
- GNOME: moving snypshot off Shift+Print or Alt+Print now gives that key back to GNOME's screenshot tool. Before, only Print Screen came back. snypshot remembers which of GNOME's screenshot keys it took, so one you switched off yourself in Settings stays off.
- The log file (`~/.cache/snypshot/snypshot.log`) no longer grows forever: once it passes 1 MB it is moved to `snypshot.log.old` the next time snypshot starts in the background.
- KDE: messages the background copy prints itself, like the reason it was disconnected from the screen right before it stops, now go to `~/.cache/snypshot/snypshot.log` instead of only the system journal.
- KDE: if snypshot ever crashes, Print Screen works again after about a second instead of about three, and it keeps trying for as long as before when the desktop is slow to start at login.
- Unplugging a monitor after taking screenshots (docking or undocking, a KVM switch, or a monitor that drops off when it's turned off) could crash snypshot, so Print Screen did nothing for a few seconds until it restarted.
- If the desktop closed one of the screenshot's windows (Alt+F4 outside KDE, a window menu, the close button in the window overview), the rest of the screenshot stayed half open, and the next Print Screen brought back the old screenshot instead of taking a new one. Now the whole screenshot closes, like Esc.
- If the desktop's print service never confirmed a print after you clicked Print (for example because it crashed or the printing stalled), the screenshot stayed on top of everything with Esc, clicks and Print Screen doing nothing until snypshot was killed. Now Esc or Print Screen closes it, and if the print service crashed, snypshot says printing didn't work and brings the screenshot back.
- Pressing Print Screen right after clicking Save or Print, before its window showed up, threw the screenshot and your drawings away and started a new one. Now the Save or Print window opens as usual.
- KDE: when another app grabbed focus while a screenshot was open (for example Zoom or a chat pop-up), it got focus once the screenshot closed, instead of the app you were using.
- KDE: if the desktop's print dialog didn't attach itself to the screenshot, it opened behind the screenshot and every click on it was taken back, so you couldn't print. The keep-on-top script now recognizes KDE's real print dialog.

**Security**
- Saving over an existing file from the Save dialog keeps it as private as it was: a file only you could read no longer becomes readable by everyone.
- Portal screenshots: if the "Allow screenshot?" prompt is answered after snypshot gave up waiting, the copy the desktop saved in Pictures is now deleted instead of left behind.

## 1.1.2

**Changed**
- Enter in a text box now starts a new line instead of finishing the text. Finish with Ctrl+Enter or a click outside, like before. Home / End go to the start / end of the line, and Up / Down move between lines.

**Fixed**
- Chinese, Japanese, emoji and right-to-left text you type now comes out in the saved image exactly as on screen (it used to turn into empty boxes).
- On KDE scaling like 130% or 145%, screenshots touching the bottom of the screen were a pixel too tall and slightly blurred; they're pixel-exact now. Mixed-scale screenshots no longer get a thin dark line at a monitor edge.
- The watermark in the saved image now always matches the preview.
- "Actual size" printing is right on 200% screens, and the Save button no longer stays greyed out after switching back to Save as PDF.
- The editor: Esc while dragging a stroke drops it, Ctrl+Z while typing can be redone with Ctrl+Y, Shift at the start of a new line no longer jumps, the mouse wheel resizes big text properly, toolbars no longer blink on a plain click, and the Toolbar size setting no longer changes how thick your drawings are.
- The Save button's tip now shows Ctrl+Shift+S (the key that does the same). Ctrl+S is still the instant save.
- GNOME: the helper keeps working after a distro upgrade to a newer Python, supports GNOME 51, and doesn't close snypshot when the screen locks.
- `snypshot --help` shows the commands; unknown options no longer take a screenshot.
- Setup: the tray icon and notifications are optional extras (a missing one no longer stops setup), messages are accurate in more cases, and uninstall tells you if it couldn't remove something.

**Security**
- Setup can no longer be tricked by a file planted next to snypshot.py (for example in Downloads).
- snypshot doesn't load graphics add-ons or fonts from folders other programs can write to.

## 1.1.1
- On KDE, snypshot runs as a small user service and restarts itself within a few seconds if it ever crashes or loses the screen (for example when KWin restarts), so Print Screen never stays dead. Quitting it on purpose still stays quit.

## 1.1

**New**
- **KDE Plasma support** (tested on Plasma 5.27 in Ubuntu 24.04 and Plasma 6.6 in Ubuntu 26.04). Screenshots come straight from KWin, so they're fast (about 0.3 s) and pixel-perfect on mixed scaling. No logging out: Print Screen works as soon as setup finishes. Print Screen is taken over from Spectacle, the shortcut shows up in System Settings > Shortcuts (changes there are picked up), quitting snypshot hands Print Screen back to Spectacle until it starts again, and uninstalling gives Spectacle its keys back.
- A **Print button** (and Ctrl+P), like Lightshot's, with a simple print window like Chrome's: a preview, then pick a printer or Save as PDF, copies, paper, portrait or landscape, color or black and white, actual size or fit to page. "More settings" shows whatever else your printer offers (two-sided, quality, trays...).
- A small, see-through **"Screenshot taken with snypshot" watermark** in the bottom-right corner of copied, saved and printed screenshots. It's only added when the screenshot is big enough, you can see it in the selection before you save, and Preferences > Saving > Watermark turns it off.
- A simpler **color picker**: a compact palette where one click picks a color, **+** to save your own, and **Fine-tune** to open a color square and hex box beside it for editing them. The Windows/Lightshot-style dialog is still there: Preferences > Look > Classic color window.
- The "Select area" hint sits by the mouse, like Lightshot, and moves to the other side near screen edges.

**Better**
- Updates always take effect on the next Print Screen, no logging out, even when only the file changed and not the version number.
- Buttons act when you let go of the mouse, not when you press it (drag off to cancel).
- Clicking outside your selection no longer throws it away; only a real drag starts a new one.
- Saved and copied images are copied pixel for pixel in more cases: before, a selection started at a sub-pixel mouse position, or one on a 125%/150% screen, could come out very slightly resampled.
- Shortcuts like Ctrl+C work on non-Latin keyboard layouts (Russian, Greek...).
- The text tool supports dead keys, Compose and input methods, so é, ñ, emoji and Chinese/Japanese/Korean input work.
- While you record a new screenshot key, snypshot stops listening after 15 seconds or when you switch away, so your other shortcuts never stay switched off.

**Fixed**
- A memory leak: every screenshot stayed in memory after it closed, so snypshot grew by about 100 MB per screenshot. Memory now stays flat.
- Saving never leaves a half-written file (for example on a full disk), and the save dialog won't silently replace an existing file when you leave out the extension.
- Pressing Print Screen while the save dialog is open brings the dialog back instead of throwing your screenshot away.
- The screenshot shortcut can't be set to a plain key like Enter by accident, turning it off now sticks, and Reset restores GNOME's own screenshot keys.
- A damaged settings file or an unreadable shortcut list can no longer crash snypshot or wipe your other custom shortcuts.
- Only one background copy can run at a time, and it keeps listening even if a request fails.

**Security**
- Setup's root install step refuses any file that changed (or was swapped for a link) while sudo waited for your password; the checksum is fixed before sudo starts.
- snypshot only talks to a background copy running as you.
- Many smaller hardening fixes (leftover temp files, odd environment settings, symlink loops, unusual printers).

## 1.0
First public release.
- Lightshot-style capture: drag to select, move and resize the selection, size label.
- Tools: pen, line, arrow, box, marker, text (movable, resizable, editable after placing), 48-color picker with custom colors.
- Mouse wheel sets brush and text size (down = bigger, up = smaller); Shift straightens lines and squares boxes.
- Ctrl+C / Enter copies; Ctrl+S saves instantly as `Screenshot_N.png`; the Save button opens a save dialog.
- Esc puts the tool down first, then cancels. Undo / redo.
- Preferences (tray icon > Preferences, or the app menu): the screenshot shortcut, save folder, file names, PNG or JPG, your own keyboard shortcuts, how dark the background gets, the size label and the toolbar size.
- Multi-monitor, pixel-perfect on mixed scaling (for example 100% + 125%).
- Instant and silent on GNOME Wayland through a small helper extension; runs in the background with a tray icon.
- Two-step install (download, then `--setup`) and a full uninstall. `shot` works as a short alias.
