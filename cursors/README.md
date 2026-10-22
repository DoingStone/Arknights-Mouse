# Arknights · Crystal Cursor Pack

> A set of Windows mouse cursors: 17 characters, three tiers, **original animations preserved**.
> Install / switch / roll back all write only to `HKCU`, and **never touch any game file**.

---

## 1. What this pack is, and how it relates to the game

### 1.1 One fact that has to be stated up front

The "spiked crystal cursor" image you provided is **not an asset inside the Arknights client**.

I turned the client inside out, and the conclusion is exhaustive:

| Check | Method | Result |
|---|---|---|
| Texture2D/Sprite of all 16 `*.assets` | Regex-scanned names for `pointer\|cursor\|arrow\|mouse\|hand\|click\|aim\|select` | There are **only 3** genuine mouse cursor art assets |
| What those 3 are | Exported and inspected one by one | `cursor_small` 48×48, `cursor_medium` 64×64, `cursor_large` 96×96 —— **all white arrows** |
| Cursor tiers / hotspot configuration | `Torappu.UI.PCCursorRuntimeConfig` (path_id=28) in `sharedassets0.assets` | 3 tiers, all hotspots `(8,8)`, uncompressed RGBA32 |
| Outline shape matching | Normalized all 1022 game textures ≥20px into 48×48 outlines and computed IoU against the crystal cursor | **The highest in the entire game is only 0.574**, and it is an unrelated UI piece; the game's own three arrows score only 0.548 / 0.546 / 0.545 |
| Index file `.idx` (24,521,440 B) | Full-text search for `cursor` / `pointer` / `PCCursor` | `cursor` hits 18 entries, **all of them roguelike dungeon connector pieces** (`img_cursor*.png`) and `walkpreviewcursor.prefab`; `pointer` / `PCCursor` hit **0** |
| Filenames of 13,163 `.ab` asset bundles | Filtered for `pc` / `mouse` / `cursor` / `pointer` | Only 3, and 2 of them are sound effects and battle VFX; `ui\[uc]pc.ab` is the only suspicious item |
| `ui\[uc]pc.ab` | Manually parsed the UnityFS header (flag `0x243`, all 6 data blocks `flag=4` = LZHAM) | The blocks themselves can be located, but **the LZHAM decoder is physically infeasible on large blocks with 131,072 B of output** (out of 24 dictionary-parameter combinations, 21 hung until the 45 s timeout and 3 failed immediately in 0.00 s with `status code: 14`). This is a decoder capability problem, not a format problem |

**So where did that image come from?** It is a third-party cursor scheme you **already have fully installed** on your own computer:

```
HKCU\Control Panel\Cursors
  (default) = "PRTS Replica v8 96x"
  Arrow     = C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\
              cursors-34497b84e5b0d7cf\PRTS-Replica-v8-96x-normal.cur
```

This pack was deployed by a **WebView2 installer** outside of `G:\Hypergryph Launcher\...` (it left traces of the `prts.local` cache in `C:\Users\22442\AppData\Local\PRTS\InstallerWebCache\EBWebView\`), 1408 files in total (1010 `.cur` + 396 `.ani`).

So what this pack does is: **take this third-party artwork that is already in use on your machine and repackage it into a proper installer with controllable sizes, one-click switching, and one-click rollback** (each character gets all six rasters 32/48/64/96/128/256, so Windows picks according to the current cursor size and DPI itself, instead of letting the system stretch a small image).

> To be clear: the source image is **natively only 96×96**. The 128 and 256 tiers are **interpolated upscales** of 96px and will not conjure detail out of nothing —— their value is letting high-DPI screens use a "pre-interpolated version", which is more controllable than the system stretching in real time.

We have **not** modified, and **will not** modify, any file under the game directory.

### 1.2 About "lossless upscaling" —— an honest statement is required

In your original specification you asked that "the upscaling process must guarantee the image stays lossless". For **the game's own three white arrows**, this is **strictly achievable**: they are essentially a vector polygon plus a layer of Gaussian shadow, and I have fitted out the master geometry (a 26-vertex polygon, with 6 pixels of reconstruction error and MAE 0.00297 at 96px). Any size is **re-rasterized from the geometry**, always keeping a 1-pixel antialiasing ramp, with no interpolated blurry edges.

But this **crystal cursor cannot do that**, for reasons I measured myself:

- There are 995–1009 opaque pixels (α>200), with **156 distinct luminance levels**, and no single "facet" occupies a significant area;
- Tolerance segmentation: `tol=0` yields 868 connected components (the largest only 9 px); only at `tol=8` does it drop to 309 (the largest 114 px);
- Internal gradient: **zero-gradient pixels account for only 7.0%**, mean=14.77, p90=38.

In other words, this is a **continuously shaded 3D render** (smooth gradients), not a flat faceted model. It has **no extractable analytic geometry**, so any upscaling can only be interpolation. I will not deceive you with the word "lossless".

### 1.3 So what does this pack do about upscaling

It does three things that are the best achievable within an interpolation framework:

1. **The 96px tier stays pixel-for-pixel as-is** —— the 96 raster of the `large` tier is **pixel-for-pixel identical** to the source file (verified with a `True` assertion); not "very close", but **the same data**.
2. **Premultiplied-alpha resampling**. All fully transparent pixels in the source image happen to be pure black `(0,0,0,0)` (6569 pixels, distinct RGB = 1). Running LANCZOS directly on straight alpha would bleed black into the edges and create dark fringes. This pack goes "premultiply → scale → unpremultiply" throughout, and writes `(0,0,0,0)` directly when `a==0`. Measured A/B: at 128px the maximum difference between the two is 19/255, and **not a single pixel became darker because of premultiplication** (0 px degraded).
3. **Every character gets all 6 rasters** (32/48/64/96/128/256), letting Windows pick the most suitable one for the current cursor size and DPI, instead of letting the system stretch a small image. Among them **96 is the native resolution**, 32/48/64 are downscales (information is lost but the image looks sharper), and **128/256 are interpolated upscales** (they add no detail, they just take the interpolation work away from the system).

> **In one sentence**: the 96px tier = original data, zero loss; the other tiers = high-quality premultiplied LANCZOS interpolation, better than system stretching, but not lossless in the mathematical sense.

---

## 2. How the three tiers were determined

In-game `CURSOR_SIZE` is a **SLIDER** (a continuous slider, not discrete tiers), and it corresponds to only 3 actual art assets. I reverse-solved the geometric relationship among those three, and the conclusion is a **geometric sequence with a common ratio of 1/√2**:

| In-game tier | Texture | Size | Relative ratio | Fitted scale factor |
|---|---|---|---|---|
| 1 | `cursor_small` | 48×48 | `0.50` | **0.5050** (residual 39 px) |
| 2 | `cursor_medium` | 64×64 | `0.7071` | **0.709167** (residual 4 px) |
| 3 | `cursor_large` | 96×96 | `1.00` | **1.0000** (residual 6 px) |

Note that the middle tier is **1/√2 ≈ 0.7071**, not 2/3. Fitting with 2/3 produces an 86 px residual, while 1/√2 gives only 5 px —— a 17-fold difference, which cannot be a coincidence.

So the three tiers of this pack align directly with this sequence:

| Tier | Gain g | Visual size | Notes |
|---|---|---|---|
| `small` | `0.50` | Same as the in-game "small" tier | Closest to the feel of the Windows default cursor |
| `medium` | `0.7071` (1/√2) | **Exactly the same** as the in-game "medium" tier | The in-game geometric midpoint |
| `large` | `1.00` | 96px native resolution | Sharpest, recommended for 2K/4K screens |

**Hotspots do not scale with the tier.** In the game, the hotspot of all three tiers is fixed at `(8,8)` (the pixel where the arrow tip is), meaning that when you enlarge the tier, "the body grows, the tip stays put". This pack follows the same convention: on a canvas of N, the hotspot lands at `(round(hx*N/96), round(hy*N/96))`, and the on-screen position of the cursor tip is unchanged at any tier.

---

## 3. What is in the pack

```
CrystalCursorPack\
├─ README.md                  This file
├─ install.ps1                Install / switch / rollback script
├─ before-install-backup.json The system cursor scheme before installation (for rollback)
├─ _manifest.json             Full manifest: path, byte count, type, hotspot of every file
├─ preview_small.png          Small tier preview (17 characters, hotspots marked with a red cross)
├─ preview_medium.png         Medium tier preview
├─ preview_large.png          Large tier preview
├─ compare_tiers.png          Six characters × three tiers side by side (displayed by tier gain, for an intuitive sense of the size difference)
├─ edge_sharpness.png         Edge sharpness comparison: 96px as-is 1x / 2x / 4x vs 4x LANCZOS
├─ backup-applied.txt         Registry snapshot from the first install (for reference only)
├─ cursors\
│   ├─ small\   Arknights_Crystal_<character>_small.cur / .ani     (17)
│   ├─ medium\  Arknights_Crystal_<character>_medium.cur / .ani    (17)
│   └─ large\   Arknights_Crystal_<character>_large.cur / .ani     (17)
└─ extracted\
    ├─ Arknights_Crystal_<character>_native96.png   17 native-resolution 96×96 PNGs (taken directly from the source files, never scaled)
    ├─ small\   PNG preview of every character in each tier
    ├─ medium\
    └─ large\
```

### The 17 characters and hotspots

All hotspots are **native values read from the source files themselves** (each frame of an ANI is actually an embedded complete `.cur` file, so it carries its own hotspot too), not guesses:

| Character | Use | Source file | Hotspot (96px) |
|---|---|---|---|
| Arrow | Normal select | `normal.cur` | (28, 20) |
| Help | Help select | `helpsel.cur` | (28, 20) |
| AppStarting | Working in background | `work.ani` | (28, 20) |
| Wait | Busy | `busy.ani` | (48, 48) |
| Crosshair | Precise select | `cross.cur` | (48, 48) |
| IBeam | Text select | `beam.cur` | (48, 48) |
| NWPen | Handwriting | `pen.cur` | (8, 9) |
| No | Unavailable | `unavail1.ani` | (28, 20) |
| SizeNS | Vertical resize | `sel_1.ani` | (48, 48) |
| SizeWE | Horizontal resize | `sel_2.ani` | (48, 48) |
| SizeNWSE | Diagonal resize 1 | `sel_3.ani` | (48, 48) |
| SizeNESW | Diagonal resize 2 | `sel_4.ani` | (48, 48) |
| SizeAll | Move | `move.ani` | (48, 48) |
| UpArrow | Alternate select | `up.cur` | (48, 4) |
| Hand | Link select | `link.cur` | (28, 20) |
| Pin | Location select | `pin.cur` | (28, 20) |
| Person | Person select | `person.cur` | (28, 20) |

**8 of them are animated cursors** (`AppStarting`, `Wait`, `No`, `SizeNS`, `SizeWE`, `SizeNWSE`, `SizeNESW`, `SizeAll`), and this pack **fully preserves the animations**: `AppStarting`/`Wait` and the 5 resize ones have 72 frames each, `No` has 30 frames, with frame counts identical to the original files one by one; those that originally had a `rate` delay array (`AppStarting`, `Wait`) keep it as-is, and the rest keep the original format of "no rate chunk, using `anih`'s `dispRate`".

> ⚠️ **This is the key difference between this pack and many "cursor conversion tools"**: those tools flatten `.ani` into a static first frame, and after installing you find that the "busy" cursor no longer spins. This pack does not.

---

## 4. How to install

### 4.1 One-click install (recommended)

In PowerShell, go to the pack directory:

```powershell
cd G:\ArknightsCursorExtract\CrystalCursorPack

# Take a look at the current state and the available tiers first
.\install.ps1

# Install the "large" tier (96px native resolution)
.\install.ps1 -Tier large

# Or switch to the "medium" tier (exactly the same as the in-game "medium" tier)
.\install.ps1 -Tier medium

# Or the "small" tier
.\install.ps1 -Tier small
```

It takes effect **immediately** after installation (the script calls `SetSystemCursor` for the 16 characters that can be switched on the fly, no sign-out needed).
If some already-open windows have not refreshed, sign out once or restart `explorer.exe`.

### ⚠️ 4.1.1 Important: conflict with `PRTS-Motion-96.exe`

There is a resident program on your machine, **`PRTS-Motion-96.exe`** (the PID changes), and it has registered itself to start at boot:

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
  PRTS-v8-Motion = "C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\PRTS-Motion-96.exe"
                   "C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf"
```

It is the "motion cursor" backend of PRTS Replica: it periodically re-applies that 96x scheme (its own log `cursors-34497b84e5b0d7cf\motion.log` says `reapply 48x48 70 ms base=32`). **It may replace this pack.**
Every time `install.ps1` finishes an install it automatically detects and reports this conflict.

**Measured conclusion (40 seconds of continuous monitoring)**: during this installation it did **not** overwrite this pack —— but this pack cannot guarantee whether it re-applies at some trigger moment (such as changing the cursor size, locking the screen, or switching resolution).

**If the cursors get switched back, pick one of the two:**

```powershell
# Option A: just terminate it for now (it will still auto-start after a reboot)
Stop-Process -Name 'PRTS-Motion-96' -Force
.\install.ps1 -Tier large

# Option B: remove it together with its auto-start entry (choose this when you want to use this pack for good)
Remove-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'PRTS-v8-Motion'
Stop-Process -Name 'PRTS-Motion-96' -Force
.\install.ps1 -Tier large
```

> Note: Option B only deletes the **auto-start entry**; it does not delete any file of the PRTS pack, nor does it change its source code. To restore it, add that `Run` key back verbatim with the command above, or reinstall PRTS Replica once.
> This step is **optional** —— you only need it when you find the cursors have been switched back.

### 4.2 Viewing the current state

```powershell
.\install.ps1 -Status
```

It shows the current scheme name, the arrow cursor path, and whether this pack is currently in use.

### 4.3 One-click rollback

```powershell
.\install.ps1 -Restore
```

Restores the complete scheme from before installation from `before-install-backup.json` (that is, your original **PRTS Replica v8 96x**).
Rollback likewise takes effect **immediately** (the script feeds the 16 restored characters back to `SetSystemCursor`).

### 4.4 Manual installation (if you do not want to run the script)

1. Open "Settings" → "Personalization" → "Themes" → "Mouse cursor"
2. For each character click "Browse" and pick the corresponding `Arknights_Crystal_<character>_large.cur` / `.ani` from `cursors\large\`
3. Click "Save as" and name it something like "Arknights Crystal Cursor Large"

> **If the first install hits "PowerShell prohibits running scripts"**: run
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
> and retry (it only affects the current window, and it is safe).

---

## 5. How this pack was made (reproducible)

### 5.1 Tools and dependencies

- **Python 3.11.9** (already on this machine)
- **Pillow 12.3.0** (image decoding and LANCZOS resampling; the only third-party dependency)
- Build script: `G:\ArknightsCursorExtract\tools\build_crystal_pack.py` (pure standard library + Pillow, no numpy)

Extracting the game-side assets additionally used **UnityPy 1.25.4**; the LZHAM data blocks inside `.ani` additionally required **Python 3.10.11 + pylzham 0.1.3** (already placed under `G:\ArknightsCursorExtract\_lzham\py310\`, and **the import name is `lzham`, not `pylzham`**).

### 5.2 Rebuild commands

```powershell
cd G:\ArknightsCursorExtract\tools
$env:PYTHONIOENCODING="utf-8"
python build_crystal_pack.py
```

The script reads `CrystalCursorPack\before-install-backup.json` to get the source file paths of the 17 characters, rebuilds all three tiers × 17 characters, and refreshes `_manifest.json` and the three preview images.

### 5.3 Two easy-to-hit format pitfalls (both solved, recorded for reference)

**The `.cur` container**: `ICONDIR` has only **3 u16 fields** (reserved / type / count), not 4; each entry is 16 bytes `<BBBBHHII>`; the height field in the DIB header is **twice the actual height** (the combined height of the XOR + AND bitmaps stacked together); when the bitmap is 32bpp with straight alpha the AND mask may be all zeros, because Windows only looks at the alpha channel.

**The `.ani` container**: `RIFF` + `ACON`, with top-level `anih`(36 B) / `rate`(frame delay array) / `LIST`. The key point —— **the `LIST` type field is `fram`**, sub-blocks start **+12 bytes** from the start of the LIST data (8-byte chunk header + 4-byte type), each sub-block is an `icon`, and **its payload is an entire complete `.cur` file**.

At first I looked for `fram` as a **sub-chunk** of the LIST, and consequently could never find the frames; the real relationship is that `fram` belongs to the LIST's **type field**. In the same source file, `work.ani`'s `LIST@352`, the `icon`s starting at 364, each 38,078 B, with a spacing of 38,086 = 8 + 38078, all add up exactly.

---

## 6. Edge cases and known limitations

| Case | How this pack handles it |
|---|---|
| **"Lossless upscaling" cannot hold for the crystal artwork** | The reason is explained with measured data in §1.2 (a continuously shaded render, 156 luminance levels, zero-gradient only 7%). The 96px tier stays pixel-for-pixel as-is, and the other tiers are premultiplied LANCZOS interpolation. **No false claim of losslessness.** |
| **In-game `CURSOR_SIZE` is a continuous slider** | It was reverse-solved that the game actually has only 3 art tiers, with ratios 1 : 1/√2 : 1/2. The three tiers of this pack align directly with that sequence, so any slider position is covered by the three tiers. |
| **Assets being compressed/encrypted** | The game's own three cursor textures are **TextureFormat 4 = RGBA32 (uncompressed)**, and `m_CompleteImageSize` = `w*h*4` holds exactly (9216 / 16384 / 36864); the exported PNGs are **byte-for-byte sha256 identical** to the original payload. The LZHAM blocks of `ui\[uc]pc.ab` **could not be unpacked**, and the reason has been recorded truthfully (the decoder is infeasible on large blocks), without guessing at their contents. |
| **Multiple resources with the same name / from different sources** | All are listed: the genuine in-game cursors = the 3 white arrows in `sharedassets0.assets`; this pack's artwork = third-party PRTS Replica v8 96x (1408 files, `AppData\Local\PRTS\`). The provenance, byte counts, and sha256 of both are recorded. |
| **No higher-resolution source exists on this machine** | `C:\Users\22442`, `G:\`, `D:\`, and `C:\ProgramData` were all searched: no 256x version exists, and neither does the installer itself (only `PRTS-Motion-96.exe`, 87,552 B). So 96px is the highest true resolution this pack can obtain. |
| **Game file safety** | Read-only throughout. All tools and outputs are **outside** `G:\Hypergryph Launcher\games\Arknights\`. The install script writes only to `HKCU\Control Panel\Cursors` and needs no administrator rights. |

---

## 7. Uninstalling

```powershell
.\install.ps1 -Restore      # restore the pre-install PRTS Replica v8 96x scheme
```

After restoring, simply delete the `CrystalCursorPack` directory and nothing is left in the system (only your original scheme remains in `HKCU`).
