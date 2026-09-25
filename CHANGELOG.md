# Changelog

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
