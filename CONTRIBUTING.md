# Contributing

Thanks for taking a look. This is a small Windows-only project; the notes below
are what you need to build and verify a change locally.

## Requirements

- Windows 10 or 11
- Python 3.9+ with **Pillow** (`pip install pillow`)
- PyInstaller, only if you want to rebuild the exe (`pip install pyinstaller`)
- Windows PowerShell 5.1 (`powershell.exe`) for the `.ps1` scripts

## Layout

| Path | What lives there |
|---|---|
| `src/arkmouse/` | The application. `main.pyw` is the Tk UI; `cursorwin.py` holds the Win32 layer; `guard.py` is the resident guard; `packbuild.py` regenerates cursor files from `art.bin` |
| `cursors/` | The prebuilt cursor pack (`cursors/<tier>/`, 17 roles each) plus `install.ps1` |
| `tools/` | Extraction and rebuild pipelines, plus the maintained acceptance scripts (`_*.py` probes are git-ignored by design) |
| `build/` | `build_exe.py` (PyInstaller) and `make_release.ps1` (portable zip) |
| `docs/` | Screenshots referenced by the README |

## Running from source

```powershell
cd src\arkmouse
python main.pyw
```

Run it from a real console, not `pythonw.exe` — the Win32 calls fail with
explanatory tracebacks only when there is a stdout.

## Building

```powershell
python build\build_exe.py
```

This builds the onefile exe **and** deploys it over `ArknightsMouse.exe` in the
repo root, verifying size and inode. Close the app and the guard first, or the
deploy step fails with a sharing violation.

```powershell
powershell -ExecutionPolicy Bypass -File build\make_release.ps1
```

That produces `release/ArknightsMouse_v<version>_portable.zip`.

## Before opening a PR

1. `python -c "import ast,sys; [ast.parse(open(p,encoding='utf-8').read()) for p in sys.argv[1:]]" src\arkmouse\*.py` — at minimum, make sure everything parses.
2. If you touched cursor generation, run `python tools\_verify_packbuild.py`. It
   regenerates a tier and compares it against the committed files; expect
   "语义一致 17 / 不一致 0".
3. If you touched `.ps1` files, re-check the UTF-8 BOM and that the file parses:
   ```powershell
   $e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\cursors\install.ps1),[ref]$null,[ref]$e); $e
   ```
4. Do not commit `settings.json`, `userdata/`, `runtime/`, `release/`,
   `build/dist/` or `build/_work/` — they are all ignored for a reason.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types used here: `feat`, `fix`, `docs`, `refactor`, `build`, `chore`.
Scopes are component names such as `cursor`, `guard`, `installer`, `release`.
A breaking change gets a `!` after the type and a `BREAKING CHANGE:` footer.

## Scope of contributions

The cursor art is third-party and not MIT-licensed — see `LICENSE`. Code
contributions are accepted under the MIT license; please do not add art assets
you do not have the rights to redistribute.
