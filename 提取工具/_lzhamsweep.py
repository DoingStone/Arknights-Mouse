# -*- coding: utf-8 -*-
"""LZHAM parameter sweep on real bundle blocks.

Why this matters: pylzham returned `ValueError: Decompression failed with
status code: 8` on block 5.  In LZHAM, 8 == LZHAM_DECOMP_STATUS_ADLER32_MISMATCH
(NOT "bad code"), i.e. the symbol decoder ran to completion and only the
trailing checksum disagreed -- which happens when the stream carries no
adler32 but we asked for verification, or vice versa.

Container facts already proven, do not re-derive:
  * UnityFS v8, engine 2021.3.39f1, blocks-info at 64 (LZ4, 119 -> 203 B)
  * 6 blocks, all flag 4, sizes (131072,42602) (131072,62388) (131072,85812)
    (131072,70942) (131072,71559) (36876,20626)
  * 192 + sum(csize) == file size EXACTLY; sum(usize) == CAB + .resS EXACTLY
"""
import os, struct, subprocess, sys, zlib

BUNDLE = (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
          r"\StreamingAssets\AB\Windows\ui\[uc]pc.ab")
PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"
WORK = r"G:\ArknightsCursorExtract\_blk\_lz"
os.makedirs(WORK, exist_ok=True)

raw = open(BUNDLE, "rb").read()
BLOCKS = [(131072, 42602), (131072, 62388), (131072, 85812),
          (131072, 70942), (131072, 71559), (36876, 20626)]
chunks, pos = [], 192
for (u, c) in BLOCKS:
    chunks.append(raw[pos:pos + c])
    pos += c
assert pos == len(raw), (pos, len(raw))
print("blocks sliced, consumed 192..%d == file size %d" % (pos, len(raw)))

HELPER = r'''# -*- coding: utf-8 -*-
"""Try LZHAM with explicit filter dict; report status codes."""
import sys, collections, lzham
sys.path.insert(0, r"G:\ArknightsCursorExtract\_blk\_lz")
import lzham as _lz

d     = open(sys.argv[1], "rb").read()
want  = int(sys.argv[2])
off   = int(sys.argv[3])
dsl   = int(sys.argv[4])
adler = int(sys.argv[5])
buf   = int(sys.argv[6])
flt = {}
if dsl:   flt["dict_size_log2"] = dsl
flt["compute_adler32_during_decomp"] = adler
if buf:   flt["unbuffered_decompression"] = 1

payload = d[off:]
for tag, mk in (
    ("func", lambda: lzham.decompress(payload, want, flt or None)),
    ("cls",  lambda: lzham.LZHAMDecompressor(flt or None).decompress(payload, want)),
):
    try:
        out = mk()
        print("OK %s off=%d dsl=%d adler=%d buf=%d len=%d match=%s"
              % (tag, off, dsl, adler, buf, len(out), len(out) == want))
        if len(out) == want:
            open(sys.argv[1] + ".out", "wb").write(out)
            print("PLAUSIBLE_HEAD " + out[:32].hex())
            h = collections.Counter(out)
            print("entropy_distinct %d top %s" % (len(h), h.most_common(5)))
            sys.exit(0)
    except Exception as ex:
        msg = str(ex)
        code = msg.rsplit(":", 1)[-1].strip() if "status code" in msg else "?"
        print("FAIL %s off=%d dsl=%d adler=%d buf=%d code=%s (%s)"
              % (tag, off, dsl, adler, buf, code, type(ex).__name__))
sys.exit(2)
'''
hp = os.path.join(WORK, "_sweep.py")
open(hp, "w", encoding="utf-8").write(HELPER)

# block 5 is the smallest -> fastest to probe
b5 = os.path.join(WORK, "b5.bin")
open(b5, "wb").write(chunks[5])
WANT5 = BLOCKS[5][0]

print("=" * 78)
print("block 5: usize=%d csize=%d  (head %s)"
      % (WANT5, BLOCKS[5][1], chunks[5][:16].hex()))

attempts = []
for off in (0, 1):
    for adler in (0, 1):
        for dsl in (0, 23, 24, 22, 21, 20, 25, 26):
            attempts.append((off, dsl, adler, 0))

hit = None
for i, (off, dsl, adler, buf) in enumerate(attempts):
    try:
        r = subprocess.run([PY310, hp, b5, str(WANT5), str(off), str(dsl),
                            str(adler), str(buf)],
                           capture_output=True, text=True, timeout=25)
        out = r.stdout.strip()
        print("[%02d] rc=%d  %s" % (i, r.returncode, out.replace("\n", " | ")[:200]))
        if r.returncode == 0 and "OK " in out:
            hit = (off, dsl, adler, buf)
            break
    except subprocess.TimeoutExpired:
        print("[%02d] off=%d dsl=%d adler=%d  TIMEOUT (never terminates -> wrong params)"
              % (i, off, dsl, adler))
    if i > 22:
        print("... stopping sweep after %d attempts to bound wall time" % (i + 1))
        break

print("=" * 78)
if hit:
    print("LZHAM decoded block 5 with off=%d dict_size_log2=%d adler=%d buf=%d"
          % hit)
    # decode every block with the winning parameters
    total = []
    for i, (u, c) in enumerate(BLOCKS):
        bp = os.path.join(WORK, "b%d.bin" % i)
        open(bp, "wb").write(chunks[i])
        try:
            r = subprocess.run([PY310, hp, bp, str(u), str(hit[0]), str(hit[1]),
                                str(hit[2]), str(hit[3])],
                               capture_output=True, text=True, timeout=120)
            ok = r.returncode == 0
            print("block %d -> rc=%d ok=%s" % (i, r.returncode, ok))
            if not ok:
                print("   ", r.stdout.strip()[:200])
                break
            total.append(open(bp + ".out", "rb").read())
        except subprocess.TimeoutExpired:
            print("block %d TIMEOUT" % i)
            break
    if len(total) == len(BLOCKS):
        blob = b"".join(total)
        print("all blocks decoded: %d bytes" % len(blob))
        cab = blob[:189068]
        res = blob[189068:]
        op = os.path.join(WORK, "CAB_611e071c.bin")
        open(op, "wb").write(blob)
        print("wrote", op)
        print("CAB head  :", cab[:48].hex())
        print("resS head :", res[:48].hex())
        ms, fs, ver, doff = struct.unpack_from(">IIII", cab, 0)
        print("serialized candidates: meta=%d file=%d ver=%d dataoff=%d (node 189068)"
              % (ms, fs, ver, doff))
else:
    print("no LZHAM parameter set decoded block 5")
    print("block 5 head:", chunks[5][:64].hex())
    print("block 5 tail:", chunks[5][-32:].hex())
