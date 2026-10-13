# -*- coding: utf-8 -*-
"""Hand-parse a UnityFS bundle: header -> blocks info -> block table -> node table.

UnityFS header fields are BIG-ENDIAN. Getting the node table out is the whole
point: the node paths are the file list inside the bundle, which tells us
whether `ui\\[uc]pc.ab` even contains cursor art (no decompression of the data
blocks is needed to read them).

Data blocks are dumped raw to _blk/ so the py310 lzham host can try them.
"""
import os, sys, json, struct, zlib

BUNDLE = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab"
OUT = r"G:\ArknightsCursorExtract\_blk"

if len(sys.argv) > 1:
    BUNDLE = sys.argv[1]

os.makedirs(OUT, exist_ok=True)
print("bundle:", BUNDLE)
data = open(BUNDLE, "rb").read()
print("size:", len(data), "bytes")
print("first 48 hex:", data[:48].hex())

p = 0

def cstr(buf, off):
    e = buf.index(b"\0", off)
    return buf[off:e].decode("utf-8", "replace"), e + 1

def align(o, a=16):
    return (o + a - 1) & ~(a - 1)

sig, p = cstr(data, p)
print("signature:", repr(sig))
version, = struct.unpack_from(">I", data, p); p += 4
unity_ver, p = cstr(data, p)
unity_rev, p = cstr(data, p)
size, = struct.unpack_from(">q", data, p); p += 8
cbi_size, = struct.unpack_from(">I", data, p); p += 4
ubi_size, = struct.unpack_from(">I", data, p); p += 4
flags, = struct.unpack_from(">I", data, p); p += 4
print("version:", version)
print("unityVersion:", unity_ver, "| unityRevision:", unity_rev)
print("declared size:", size)
print("compressedBlocksInfoSize:", cbi_size, "uncompressedBlocksInfoSize:", ubi_size)
print("flags: 0x%08X  -> blocksInfoAtEnd=%s  padAtStart=%s  infoCompression=%d"
      % (flags, bool(flags & 0x40), bool(flags & 0x200), flags & 0x3F))
print("pos after header:", p)

if version >= 7:
    p = align(p)
    print("aligned pos:", p)

# blocks info location
if flags & 0x40:
    bi_off = align(len(data) - cbi_size)
else:
    bi_off = p
print("blocksInfo at:", bi_off)
raw_bi = data[bi_off:bi_off + cbi_size]
print("raw blocksInfo head:", raw_bi[:64].hex())

# decompress the blocks info
bi = None
info_comp = flags & 0x3F
def try_lz4(d):
    import lz4.block
    out = []
    for label, payload in (("asis", d), ("skip4", d[4:]), ("skip1", d[1:])):
        for fn in ("block.decompress",):
            try:
                r = lz4.block.decompress(payload, uncompressed_size=ubi_size)
                out.append((label, r))
            except Exception as e:
                pass
    return out

cands = []
if info_comp in (2, 3):
    try:
        cands += try_lz4(raw_bi)
    except ImportError as e:
        print("no lz4 module:", e)
try:
    cands.append(("zlib", zlib.decompress(raw_bi)))
except Exception:
    pass
try:
    import lzma
    cands.append(("lzma", lzma.decompress(raw_bi)))
except Exception:
    pass

for label, r in cands:
    print("  blocksInfo decode [%s] -> %d B (want %d) %s" % (label, len(r), ubi_size, "OK" if len(r) == ubi_size else "mismatch"))
    if len(r) == ubi_size:
        bi = r
if bi is None and cands:
    bi = max(cands, key=lambda t: len(t[1]))[1]
    print("  using best effort blocksInfo of", len(bi), "B")

if bi is None:
    print("!! cannot decode blocks info")
    sys.exit(1)

q = 0
if flags & 0x80:
    print("info hash:", bi[:16].hex())
    q += 16
block_count, = struct.unpack_from(">I", bi, q); q += 4
print()
print("=" * 78)
print("BLOCK TABLE: %d blocks" % block_count)
blocks = []
for i in range(block_count):
    usize, csize, bflags = struct.unpack_from(">IIH", bi, q); q += 10
    blocks.append((usize, csize, bflags))
    print("  blk%-3d usize=%-10d csize=%-10d flags=%-6d (0x%04X) compression=%d %s"
          % (i, usize, csize, bflags, bflags, bflags & 0x3F,
             "(streamed)" if bflags & 0x80 else ""))
node_count, = struct.unpack_from(">I", bi, q); q += 4
print()
print("NODE TABLE: %d nodes" % node_count)
nodes = []
for i in range(node_count):
    off, nsize, nflags = struct.unpack_from(">qqI", bi, q); q += 20
    path, q = cstr(bi, q)
    nodes.append({"offset": off, "size": nsize, "flags": nflags, "path": path})
    print("  n%-3d off=%-10d size=%-9d flags=%-4d %s" % (i, off, nsize, nflags, path))
print("consumed %d / %d bytes of blocksInfo" % (q, len(bi)))

# dump raw data blocks
p2 = align(bi_off + cbi_size) if not (flags & 0x40) else p
print()
print("data region starts at:", p2)
for i, (usize, csize, bflags) in enumerate(blocks):
    if bflags & 0x80:
        continue
    chunk = data[p2:p2 + csize]
    p2 += csize
    fp = os.path.join(OUT, "blk%d.bin" % i)
    open(fp, "wb").write(chunk)
    print("  blk%d -> %s (%d B, declared usize=%d) head=%s" % (i, fp, len(chunk), usize, chunk[:24].hex()))

json.dump({"bundle": BUNDLE, "size": len(data), "version": version, "flags": flags,
           "blocks": blocks, "nodes": nodes},
          open(os.path.join(OUT, "meta.json"), "w"), ensure_ascii=False, indent=1)
print()
print("wrote", os.path.join(OUT, "meta.json"))
