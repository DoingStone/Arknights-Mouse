# -*- coding: utf-8 -*-
"""Full UnityFS unpacker with the CORRECT flag decode.

flags = 0x243 -> compression 3 (LZ4HC), combined 0x40, NOT at end, enc 0x200.
Data layout (from UnityPy's writer):  [header][blocksInfo][data blocks][file data]
                                     with a 16-byte align when 0x200 is set.
Block flag 4 is claimed LZHAM; test LZ4 first, then shell out to the py310 lzham host.
"""
import os, sys, struct, subprocess, json

OUT = r"G:\ArknightsCursorExtract\_blk"
PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"
os.makedirs(OUT, exist_ok=True)

BUNDLES = sys.argv[1:] or [
    r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab",
]

import lz4.block


def parse_header(data):
    p = data.index(b"\0") + 1
    version, = struct.unpack_from(">I", data, p); p += 4
    e = data.index(b"\0", p); uv = data[p:e].decode(); p = e + 1
    e = data.index(b"\0", p); ur = data[p:e].decode(); p = e + 1
    size, = struct.unpack_from(">q", data, p); p += 8
    cbi, = struct.unpack_from(">I", data, p); p += 4
    ubi, = struct.unpack_from(">I", data, p); p += 4
    flags, = struct.unpack_from(">I", data, p); p += 4
    return dict(version=version, uv=uv, ur=ur, size=size, cbi=cbi, ubi=ubi,
                flags=flags, header_end=p)


def read_blocks_info(data, h):
    off = (h["header_end"] + 15) & ~15
    for o in range(h["header_end"], h["header_end"] + 128):
        try:
            r = lz4.block.decompress(data[o:o + h["cbi"]], uncompressed_size=h["ubi"])
            if len(r) == h["ubi"]:
                return o, r
        except Exception:
            pass
    return None, None


LZHAM_HELPER = r"""# -*- coding: utf-8 -*-
import sys, os, json, lzham
job = json.load(open(sys.argv[1]))
res = {}
for name, (path, usize) in job.items():
    d = open(path, "rb").read()
    out = b""
    err = ""
    try:
        out = lzham.decompress(d, usize)
    except Exception as e1:
        err = "%s: %s" % (type(e1).__name__, e1)
        try:
            dec = lzham.LZHAMDecompressor()
            out = dec.decompress(d, usize)
        except Exception as e2:
            err += " | %s: %s" % (type(e2).__name__, e2)
    open(path + ".out", "wb").write(out)
    res[name] = [len(out), err]
print(json.dumps(res))
"""


def lzham_batch(chunks):
    """One py310 call for every block. chunks: list of (payload, usize) -> list of bytes|None."""
    blkdir = os.path.join(OUT, "_lz")
    os.makedirs(blkdir, exist_ok=True)
    job = {}
    for i, (payload, usize) in enumerate(chunks):
        p = os.path.join(blkdir, "b%d" % i)
        open(p, "wb").write(payload)
        job["b%d" % i] = [p, usize]
    helpp = os.path.join(OUT, "_lzhelper.py")
    open(helpp, "w").write(LZHAM_HELPER)
    jobp = os.path.join(OUT, "_lzjob.json")
    json.dump(job, open(jobp, "w"))
    r = subprocess.run([PY310, helpp, jobp], capture_output=True, text=True)
    info = {}
    if r.stdout.strip():
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            info = {}
    if not info:
        print("    [py310 lzham] stdout:", r.stdout[:300])
        print("    [py310 lzham] stderr:", r.stderr[:300])
    outs = []
    for i in range(len(chunks)):
        key = "b%d" % i
        p = os.path.join(blkdir, key)
        op = p + ".out"
        got = open(op, "rb").read() if os.path.exists(op) else None
        usize = chunks[i][1]
        ok = got is not None and len(got) == usize
        outs.append(got if ok else None)
        rec = info.get(key)
        if rec is not None:
            print("      lzham %s: len=%s err=%s" % (key, rec[0], rec[1][:90] if rec[1] else "-"))
    return outs


for b in BUNDLES:
    print("=" * 78)
    print(os.path.basename(b))
    data = open(b, "rb").read()
    h = parse_header(data)
    print("  header_end=%d cbi=%d ubi=%d flags=0x%X" % (h["header_end"], h["cbi"], h["ubi"], h["flags"]))

    bi_off, bi = read_blocks_info(data, h)
    print("  blocksInfo at %d (%d B decoded)" % (bi_off, len(bi)))

    q = 16  # uncompressed data hash
    n, = struct.unpack_from(">I", bi, q); q += 4
    blocks = []
    for i in range(n):
        u, c, bf = struct.unpack_from(">IIH", bi, q); q += 10
        blocks.append((u, c, bf))
    nn, = struct.unpack_from(">I", bi, q); q += 4
    nodes = []
    for i in range(nn):
        o, s, fl = struct.unpack_from(">qqI", bi, q); q += 20
        e = bi.index(b"\0", q); path = bi[q:e].decode("utf-8", "replace"); q = e + 1
        nodes.append((o, s, fl, path))

    # data region
    dstart = bi_off + h["cbi"]
    if h["flags"] & 0x200:
        dstart_aligned = (dstart + 15) & ~15
    else:
        dstart_aligned = dstart
    print("  data region: raw=%d aligned=%d (delta %+d)" % (dstart, dstart_aligned, dstart_aligned - dstart))

    total_u = sum(b[0] for b in blocks)
    print("  blocks total usize=%d, nodes total size=%d" % (total_u, max(nd[1] for nd in nodes)))

    # collect the decompressed stream, trying LZ4 then LZHAM
    stream = b""
    pos = dstart_aligned
    results = []

    # First pass: everything LZ4 can handle (no subprocess needed).
    raw_chunks = []
    got_map = {}
    for i, (u, c, bf) in enumerate(blocks):
        chunk = data[pos:pos + c]
        pos += c
        raw_chunks.append(chunk)
        try:
            r = lz4.block.decompress(chunk, uncompressed_size=u)
            if len(r) == u:
                got_map[i] = (r, "lz4")
        except Exception:
            pass

    # Any block LZ4 refused: try LZ4 with small header skips, then real LZHAM in one batch.
    pending = [i for i in range(len(blocks)) if i not in got_map]
    if pending:
        for i in pending:
            u, c, bf = blocks[i]
            chunk = raw_chunks[i]
            for skip in (1, 2, 4, 8, 16):
                try:
                    r = lz4.block.decompress(chunk[skip:], uncompressed_size=u)
                    if len(r) == u:
                        got_map[i] = (r, "lz4-skip%d" % skip)
                        break
                except Exception:
                    pass
        still = [i for i in pending if i not in got_map]
        if still:
            print("    trying real LZHAM on %d block(s): %s" % (len(still), still))
            outs = lzham_batch([(raw_chunks[i], blocks[i][0]) for i in still])
            for i, got in zip(still, outs):
                if got is not None:
                    got_map[i] = (got, "lzham")

    for i, (u, c, bf) in enumerate(blocks):
        flag = bf & 0x3F
        rec = got_map.get(i)
        got, how = (rec[0], rec[1]) if rec else (None, "FAIL")
        results.append((i, u, c, flag, how))
        print("    blk%-2d usize=%-8d csize=%-8d flag=%-2d -> %s" % (i, u, c, flag, how))
        if got:
            stream += got
        else:
            stream += b"\x00" * u

    print("  reassembled stream: %d bytes" % len(stream))
    open(os.path.join(OUT, os.path.basename(b).replace("[", "").replace("]", "") + ".payload"), "wb").write(stream)

    # split by node offsets
    for idx, (o, s, fl, path) in enumerate(nodes):
        chunk = stream[o:o + s]
        safe = path.replace("\\", "_").replace("/", "_").replace(":", "_")
        fp = os.path.join(OUT, "node%d_%s" % (idx, safe))
        open(fp, "wb").write(chunk)
        print("    node%d off=%-9d size=%-9d wrote %s (%d B)" % (idx, o, s, fp, len(chunk)))
        print("      head: %s" % chunk[:32].hex())
        if chunk[:4] == b"\x00\x00\x00\x00" or len(chunk) < 100:
            pass

    json.dump({"bundle": b, "header": h, "blocks": blocks,
               "nodes": [{"offset": o, "size": s, "flags": f, "path": p} for o, s, f, p in nodes],
               "results": results},
              open(os.path.join(OUT, os.path.basename(b).replace("[", "").replace("]", "") + ".json"), "w"),
              ensure_ascii=False, indent=1)
    print("  wrote manifest json")
