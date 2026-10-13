# -*- coding: utf-8 -*-
"""Definitive test: what IS block flag 4 in this client's bundles?

Facts to re-verify here:
  * the actual UnityFS signature (UnityFS vs the UnityCN "#$unity3dchina!@")
  * which ArchiveFlags flavour applies (affects whether 0x200 means
    "encrypted" or merely "block info needs 16-byte padding")
  * whether pylzham can really decode a data block (with a hard timeout,
    so a hang cannot eat the turn)
"""
import struct, subprocess, sys, os, tempfile

BUNDLE = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab"
PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"

raw = open(BUNDLE, "rb").read()
print("file size      :", len(raw))
print("is UnityFS     :", raw.startswith(b"UnityFS"))
print("is UnityCN sig :", raw.startswith(b"#$unity3dchina!@"))
# read the signature as a null-terminated string
z = raw.index(b"\0")
print("signature      : %r" % raw[:z])
print("first 48 bytes : %s" % raw[:48].hex())

# engine version string
p = z + 1
ver, = struct.unpack_from(">I", raw, p); p += 4
e = raw.index(b"\0", p); player = raw[p:e].decode(); p = e + 1
e = raw.index(b"\0", p); engine = raw[p:e].decode(); p = e + 1
print("format=%d player=%r engine=%r" % (ver, player, engine))

# version tuple like UnityPy builds it
nums = []
for part in engine.split("."):
    d = "".join(ch for ch in part if ch.isdigit())
    if d == "":
        break
    nums.append(int(d))
ver_t = tuple(nums)
print("engine tuple   :", ver_t)

OLD = (ver_t < (2020,)
       or (ver_t[0] == 2020 and ver_t < (2020, 3, 34))
       or (ver_t[0] == 2021 and ver_t < (2021, 3, 2))
       or (ver_t[0] == 2022 and ver_t < (2022, 1, 1)))
print("ArchiveFlagsOld:", OLD, " -> 0x200 means:", "UsesAssetBundleEncryption"
      if OLD else "BlockInfoNeedPaddingAtStart")

# ---- block table -------------------------------------------------------
import lz4.block
size, = struct.unpack_from(">q", raw, p); p += 8
cbi, ubi, flags = struct.unpack_from(">III", raw, p); p += 12
print("declared size  : %d (file %d)" % (size, len(raw)))
print("cbi=%d ubi=%d flags=0x%x" % (cbi, ubi, flags))
print("  compression  : flags & 0x3F = %d" % (flags & 0x3F))
print("  combined     : bool(flags & 0x40) =", bool(flags & 0x40))
print("  atEnd        : bool(flags & 0x80) =", bool(flags & 0x80))
print("  other bits   : 0x%x" % (flags & ~0x3F))
header_end = p
print("header_end     : %d -> aligned16 %d" % (header_end, (header_end + 15) & ~15))
bi_off = (header_end + 15) & ~15
print("blocks-info at : %d (raw %d)  delta=%+d" % (bi_off, header_end, bi_off - header_end))
try:
    bi = lz4.block.decompress(raw[bi_off:bi_off + cbi], uncompressed_size=ubi)
except Exception as ex:
    print("!! blocks info decode failed at aligned offset:", ex)
    bi = None
    for cand in range(header_end, header_end + 64):
        try:
            t = lz4.block.decompress(raw[cand:cand + cbi], uncompressed_size=ubi)
            print("   blocks info decodes at offset %d (delta %+d)" % (cand, cand - header_end))
            bi = t; bi_off = cand
            break
        except Exception:
            pass
    if bi is None:
        print("   no offset in window decodes -> abort"); sys.exit(1)
print("data start (read-path) : %d" % (bi_off + cbi))
print("data start (write-path, aligned16): %d" % ((bi_off + cbi + 15) & ~15))
q = 16
n, = struct.unpack_from(">I", bi, q); q += 4
blocks = []
for _ in range(n):
    u, c, f = struct.unpack_from(">IIH", bi, q); q += 10
    blocks.append((u, c, f))
print("blocks:", blocks)
D = 192
chunks, pos = [], D
for (u, c, f) in blocks:
    chunks.append(raw[pos:pos + c]); pos += c
print("data consumed  : %d .. %d (file %d)" % (D, pos, len(raw)))

# ---- LZHAM, with a hard timeout ---------------------------------------
HELPER = r"""# -*- coding: utf-8 -*-
import sys, lzham, inspect
print("module:", lzham.__file__)
for nm in ("decompress", "LZHAMDecompressor", "compress", "LZHAMCompressor"):
    o = getattr(lzham, nm, None)
    print("  %-20s %s" % (nm, type(o)))
try:
    print("  decompress sig:", inspect.signature(lzham.decompress))
except Exception as ex:
    print("  decompress sig: ?", ex)
try:
    print("  decompress doc:", (lzham.decompress.__doc__ or "").strip()[:300])
except Exception:
    pass
print("  dir(decompress mod):", [x for x in dir(__import__('lzham.decompress', fromlist=['x'])) if not x.startswith('_')])
d = open(sys.argv[1], "rb").read()
u = int(sys.argv[2])
try:
    out = lzham.decompress(d, u)
    print("RESULT lzham.decompress -> %d bytes (want %d) ok=%s" % (len(out), u, len(out) == u))
    open(sys.argv[1] + ".out", "wb").write(out)
except Exception as ex:
    print("RESULT lzham.decompress FAILED: %s: %s" % (type(ex).__name__, ex))
    try:
        dec = lzham.LZHAMDecompressor()
        out = dec.decompress(d, u)
        print("RESULT LZHAMDecompressor -> %d bytes ok=%s" % (len(out), len(out) == u))
        open(sys.argv[1] + ".out", "wb").write(out)
    except Exception as ex2:
        print("RESULT LZHAMDecompressor FAILED: %s: %s" % (type(ex2).__name__, ex2))
"""
hp = r"G:\ArknightsCursorExtract\_blk\_lzprobe.py"
os.makedirs(os.path.dirname(hp), exist_ok=True)
open(hp, "w", encoding="utf-8").write(HELPER)

for i in (0, 5):
    bp = r"G:\ArknightsCursorExtract\_blk\_probe_b%d.bin" % i
    open(bp, "wb").write(chunks[i])
    print("-" * 70)
    print("block %d: usize=%d csize=%d flag=%d" % (i, blocks[i][0], blocks[i][1], blocks[i][2]))
    try:
        r = subprocess.run([PY310, hp, bp, str(blocks[i][0])],
                           capture_output=True, text=True, timeout=120)
        print(r.stdout)
        if r.stderr.strip():
            print("STDERR:", r.stderr[:800])
    except subprocess.TimeoutExpired:
        print("TIMEOUT after 120s -> this codec does not terminate on this data")
