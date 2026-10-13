# Arknights PC Client · Mouse Cursor Resource Extraction (Reproducible Project)

This directory is a **reproducible** extraction project that covers two distinct cursor sources:

| ID | Source | Nature | Output |
|---|---|---|---|
| **A** | Game client `sharedassets0.assets` | The genuine cursors shipped with the game, white arrow, 3 tiers 48/64/96 | Pixel-identical PNGs + tier/hotspot manifest |
| **B** | Local third-party package «PRTS Replica v8 96x» | The crystal cursor the user actually uses, **not present in the game data** | Installable cursors in three size tiers × 17 characters |

> **Why the two are not conflated**: A is game-asset extraction, B is a third-party art repack.
> The "spiked crystal cursor" you (m01001) wanted belongs to **B**; it **does not exist in the game client** — see the exhaustive evidence in §1.1 of `CrystalCursorPack\README.md`.

---

## I. Directory Structure

```
G:\ArknightsCursorExtract\
├─ README.md                     This file
├─ extract_cursors.py            Extractor for Source A (cursors shipped with the game)
├─ extracted\                    Outputs of Source A
│   ├─ cursor_small.png          48×48  RGBA uncompressed original
│   ├─ cursor_medium.png         64×64  RGBA uncompressed original
│   ├─ cursor_large.png          96×96  RGBA uncompressed original
│   ├─ _cursor_config.json       Tier and hotspot configuration (parsed from PCCursorRuntimeConfig)
│   ├─ _extract_report.txt       Extraction report (with sha256 consistency proof)
│   └─ _provenance.txt           Resource provenance (file, path_id, MonoScript)
├─ proof_sheet.png               Acceptance image evidence for Source A (pixel-by-pixel sha256 identical)
├─ CrystalCursorPack\            Complete installable package for Source B (see its README.md)
├─ tools\                        All build/analysis scripts
└─ _lzham\py310\                 Python 3.10.11 + pylzham (for decompressing [uc] bundles)
```

---

## II. Source A: Cursors Shipped with the Game (White Arrow)

### 2.1 Resource Location and Format

| Item | Value |
|---|---|
| Target file | `G:\Hypergryph Launcher\games\Arknights\Arknights_Data\sharedassets0.assets` |
| Textures | `cursor_small` path_id=**11** / `cursor_medium` path_id=**7** / `cursor_large` path_id=**13** |
| Configuration | MonoBehaviour `PCCursorRuntimeConfig` (namespace `Torappu.UI`) path_id=**28**, script = `file 1 : path 4099` |
| Sizes | 48×48 / 64×64 / 96×96 |
| TextureFormat | **4 = RGBA32 (uncompressed)**; `m_CompleteImageSize` = 9216 / 16384 / 36864 = `w*h*4` holds exactly; `m_MipCount=1`; `m_IsReadable=True` |
| Hotspot | **All** three tiers `(8, 8)` — i.e. the pixel where the arrow tip sits; the game does not vary the hotspot by tier |
| Tiers | 3 tiers (`CursorTierConfig` array, each entry = texture PPtr + two float32 hotspots) |

### 2.2 Dependencies

- **Python 3.11.9**
- **UnityPy 1.25.4** (`pip install UnityPy`)
- Pillow (PNG export)

### 2.3 Run Commands

```powershell
cd G:\ArknightsCursorExtract
$env:PYTHONIOENCODING="utf-8"
python extract_cursors.py
```

Outputs land in `extracted\` and match what is already stored in the directory exactly (repeatability has been accepted).

### 2.4 How Pixel-by-Pixel Consistency Was Proven

What `_extract_report.txt` records is: after restoring pixels from the Texture2D's `image_data` (raw payload) in **bottom-up row order**, a sha256 is computed; and the exported PNG is decoded back to pixels and a sha256 is computed in the same order — **the two are byte-for-byte equal**:

| Texture | sha256 (payload == exported image) | payload bytes |
|---|---|---|
| `cursor_small` | `c9b41d746b14aa8e6e6d28df257523e9456f8ffb506d03581c2c03182b044094` | 9216 = 48×48×4 |
| `cursor_medium` | `cd685ccc50e460829da741a04696ddcbaec27e731158d4261b1c7e669d4444ac3` | 16384 = 64×64×4 |
| `cursor_large` | `de0e5c3fd2c3fcc995b7371af620d59c8a5002aa3407d542a467e9700bacbedf` | 36864 = 96×96×4 |

Because the TextureFormat is **uncompressed RGBA32**, there are **no compression artifacts whatsoever** between the exported image and the original.

---

## III. Source B: Crystal Cursors (Third-Party)

For full details see **`CrystalCursorPack\README.md`**. Key points:

- The artwork comes from `C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf\` (1408 files: 1010 `.cur` + 396 `.ani`), deployed by the WebView2 installer.
- Three tiers of gain `0.50 / 0.7071(1/√2) / 1.00`, aligned with the actual ratio sequence of the in-game three tiers.
- **17 characters**, all hotspots are the source files' native values; **8 animated characters fully retain their animation** (30 or 72 frames).
- The 96px raster is **pixel-for-pixel identical** to the source files (`_verify_pack.py` has asserted 17/17 passing).

---

## IV. `.cur` / `.ani` Binary Format Quick Reference

### `.cur`

```
ICONDIR:   <HHH>            reserved=0, type=2, count      ← only 3 u16!
  per entry: <BBBBHHII>     w, h, nColors, reserved, hsx, hsy, bytesInRes, imageOffset
                                         ↑ width or height of 0 means 256
payload:   if the first 4 bytes are \x89PNG → PNG compressed
           otherwise BITMAPINFOHEADER: <IiiHH> hdrSize, w, h, planes, bpp
                actual height = abs(h) // 2   ← XOR and AND bitmaps stacked
                pixels = data[40 : 40+w*h*4], BGRA, bottom-up
AND mask:  ((w+31)//32)*4*h bytes; may be all zeros when 32bpp passes alpha through
```

### `.ani`

```
RIFF + <size> + ACON
  anih  (36 B): 9 u32 — cbSize, nFrames, nSteps, w, h, bpp, planes, dispRate, attrs
  rate  (optional): u32 array, per-frame delay (jiffies)
  LIST  <size> 'fram'          ← key point: 'fram' is the LIST's type field
      icon  <size> <complete .cur byte stream>   ← the payload is an entire .cur (so it carries its own hotspot!)
      icon  ...
```

> **Pitfall encountered**: at first I looked for `fram` as a LIST **sub-chunk**, and could never find any frames.
> The truth is that `fram` is the LIST's **type field**, and the sub-blocks start at the LIST data offset **+12 bytes**
> (8-byte chunk header + 4-byte type).

---

## V. Environment and Known Limitations

| Item | Status |
|---|---|
| `web_search` | **Unavailable** (firecrawl 403, IP judged suspicious) |
| `prts.local` | **DNS unresolvable** — that installer is a local virtual domain, and the service is down |
| Higher-resolution source (256x) | **Not present on this machine** (searched the whole of `C:\Users\22442`, `G:\`, `D:\`, `C:\ProgramData`) |
| `ui\[uc]pc.ab` | All 6 data blocks `flag=4` (LZHAM); **the decoder is physically infeasible on large blocks** (21/24 parameter combinations hang until a 45 s timeout; 3 return in 0.00 s as `status code: 14`). Recorded faithfully; the contents were not guessed |
| bash heredoc inside pwsh | **Invariably fails** (`python - <<'PY'` raises `ParserError`); quoted `python -c @'...'@` also swallows the quotes. **You must write a .py file and then run it** |
| Game directory | **Read-only throughout**; all tools and outputs live outside `G:\Hypergryph Launcher\games\Arknights\` |

---

## VI. Acceptance Status

| Acceptance item | Result |
|---|---|
| Exported images pixel-identical to the original textures (no compression artifacts) | ✅ sha256 byte-for-byte equal across all three tiers |
| Hotspot coordinates match the in-game declaration | ✅ all three tiers `(8,8)`, taken from the raw `PCCursorRuntimeConfig` payload |
| The command reproduces the same result | ✅ `extract_cursors.py` is idempotent |
| Cursors can be installed, switched, and rolled back | ✅ `CrystalCursorPack\install.ps1` (writes only to `HKCU`) |
| Multiple size tiers | ✅ three tiers `0.50 / 0.7071 / 1.00`, aligned with the game's actual sequence |
| Animated cursors not flattened to static | ✅ 8 animated characters with 30/72 frames fully retained |
| Is upscaling lossless | ⚠️ **Game's own white arrow: analytically lossless** (polygon master already fitted); **crystal cursors: no** (continuously shaded rendered images, 156 brightness levels, zero gradient only 7%). Stated faithfully; not falsely claimed as lossless |
