## What this changes

<!-- One or two sentences. -->

## Why

<!-- The bug it fixes or the need it serves. -->

## How it was verified

<!-- Commands you ran and what they printed. "It compiles" is not verification
     for anything that touches the cursor stack. -->

- [ ] `python tools\_verify_packbuild.py` still reports 语义一致 17 / 不一致 0
- [ ] `.ps1` files still parse and still have a UTF-8 BOM
- [ ] Cursor install still appears under Control Panel → Mouse → Pointers
- [ ] No files from `settings.json`, `userdata/`, `runtime/`, `release/`,
      `build/dist/` or `build/_work/` are staged
