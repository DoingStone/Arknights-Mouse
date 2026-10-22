# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0] — 2026-10-22

First public release.

### Added

- The complete Arknights crystal cursor pack: 17 Windows cursor roles
  (Arrow, Help, AppStarting, Wait, Crosshair, IBeam, NWPen, No, SizeNS, SizeWE,
  SizeNWSE, SizeNESW, SizeAll, UpArrow, Hand, Pin, Person) at four gain tiers
  (`small` 0.50×, `medium` 1/√2, `p72` 0.75×, `large` 1.00×), 68 files in total.
- `ArknightsMouse.exe` — a portable tool that installs the cursors at any pixel
  size by building the HCURSOR in memory (`CreateDIBSection` +
  `CreateIconIndirect` + `SetSystemCursor`) and manages mouse parameters.
- A resident cursor guard that restores the pointer whenever Windows resets it,
  and re-registers the cursor scheme if it is cleared.
- The three PRTS motion effects, ported frame-for-frame: click squeeze, drag
  claw and idle animation.
- `cursors/install.ps1` — a file-based installer that writes only `HKCU`, so no
  elevation is required.
- `src/arkmouse/packbuild.py` — regenerates any tier's `.cur`/`.ani` straight
  from the embedded `art.bin` (~3 s for 17 files), so the tool still works when
  `cursors/` is missing next to the exe.
- A registered Windows mouse scheme, so the pack also shows up under
  Control Panel → Mouse → Pointers → Scheme like any other cursor theme.

### Notes

- Windows renders cursors loaded *from a scheme* at 32×32 regardless of the
  raster sizes in the file or of `CursorBaseSize`. Real larger pointers only
  come from `SetSystemCursor`, which is what the tool's "Apply" button does.
- The crystal cursor art is **not** from the Arknights game client; it ships with
  the third-party "PRTS Replica v8 96x" cursor pack. See `LICENSE`.

[Unreleased]: https://github.com/DoingStone/Arknights-Mouse/compare/v1.0...HEAD
[1.0]: https://github.com/DoingStone/Arknights-Mouse/releases/tag/v1.0
