# -*- coding: utf-8 -*-
"""Decode every block of a [uc] bundle with the WORKING LZHAM filter set.

PROVEN container layout (do not re-derive):
  raw[0:8]    = b"UnityFS\\x00"           (7-byte signature + NUL)
  raw[8:12]   = format version, big-endian int32  (= 8)
  raw[12:]    = player version string, NUL-terminated ("5.x.x")
  next        = engine version string, NUL-terminated ("2021.3.39f1")
  next        = size  int64 BE
  next        = cbi u32 BE, ubi u32 BE, flags u32 BE
  header_end  = 50 for [uc]pc.ab ; blocks-info is LZ4 at align16(header_end) = 64
  dstart      = align16(64 + 119) = 192
  192 + sum(csize) = 353929 -> 354121 == file size EXACTLY
  sum(usize) = 692236 = 189068 (CAB node) + 503168 (.resS) EXACTLY

PROVEN block codec: LZHAM (block flag 4).  pylzham defaults
compute_adler32_during_decomp to ON, which returns status code 8
(LZHAM_DECOMP_STATUS_ADLER32_MISMATCH) on these streams.  Passing an explicit
filter dict with compute_adler32_during_decomp=0 decodes exactly.
"""
import os, struct, subprocess, sys, time

import lz4.block

PY310 = r"G:\ArknightsCursorExtract\_lzham\py310\python.exe"
WORK = r"G:\ArknightsCursorExtract\_blk\_full"
os.makedirs(WORK, exist_ok=True)

HELPER = r'''# -*- coding: utf-8 -*-
import sys, lzham
src, want, off, dsl, adler, outp = (sys.argv[1], int(sys.argv[2]), int(sys.argv[3]),
                                    int(sys.argv[4]), int(sys.argv[5]), sys.argv[6])
d = open(src, "rb").read()[off:]
flt = {"compute_adler32_during_decomp": adler}
if dsl:
    flt["dict_size_log2"] = dsl
try:
    out = lzham.decompress(d, want, flt)
except Exception as ex:
    print("ERR %s: %s" % (type(ex).__name__, ex))
    sys.exit(1)
if len(out) != want:
    print("LEN %d != %d" % (len(out), want))
    sys.exit(1)
open(outp, "wb").write(out)
print("OK %d" % len(out))
'''
HP = os.path.join(WORK, "_lz.py")
open(HP, "w", encoding="utf-8").write(HELPER)


def _cstr(raw, p):
    e = raw.index(b"\x00", p)
    return raw[p:e].decode("utf-8", "replace"), e + 1


def parse_bundle(path):
    raw = open(path, "rb").read()
    assert raw[:7] == b"UnityFS", raw[:16]
    p = 8
    fmt = struct.unpack_from(">i", raw, p)[0]
    p += 4
    player, p = _cstr(raw, p)
    engine, p = _cstr(raw, p)
    size = struct.unpack_from(">q", raw, p)[0]
    cbi, ubi, flags = struct.unpack_from(">III", raw, p + 8)
    header_end = p + 20
    qi = (header_end + 15) & ~15
    bi = lz4.block.decompress(raw[qi:qi + cbi], uncompressed_size=ubi)
    # blocks-info layout: 16-byte uncompressed-data hash, then block count.
    q = 16
    nb = struct.unpack_from(">i", bi, q)[0]
    q += 4
    blocks = []
    for _ in range(nb):
        u, c, f = struct.unpack_from(">IIH", bi, q)
        q += 10
        blocks.append((u, c, f))
    nn = struct.unpack_from(">i", bi, q)[0]
    q += 4
    nodes = []
    for _ in range(nn):
        off, sz, fl = struct.unpack_from(">qqI", bi, q)
        q += 20
        nm, q = _cstr(bi, q)
        nodes.append((off, sz, fl, nm))
    dstart = (qi + cbi + 15) & ~15
    hdr = dict(fmt=fmt, player=player, engine=engine, size=size,
               cbi=cbi, ubi=ubi, flags=flags, header_end=header_end,
               qi=qi, dstart=dstart)
    return raw, blocks, nodes, hdr


def decode_bundle(path, tag, timeout=45, order=(0, 23, 22, 21, 20, 24, 25, 26)):
    raw, blocks, nodes, h = parse_bundle(path)
    print("[%s] file=%d fmt=%d player=%s engine=%s size=%d"
          % (tag, len(raw), h["fmt"], h["player"], h["engine"], h["size"]))
    print("   cbi=%d ubi=%d flags=0x%X header_end=%d qinfo=%d dstart=%d"
          % (h["cbi"], h["ubi"], h["flags"], h["header_end"], h["qi"], h["dstart"]))
    print("   blocks=%d nodes=%d flags_seen=%s"
          % (len(blocks), len(nodes), sorted({f for _, _, f in blocks})))
    print("   sum(csize)=%d  dstart+sum(csize)=%d  file=%d  %s"
          % (sum(c for _, c, _ in blocks), h["dstart"] + sum(c for _, c, _ in blocks),
             len(raw),
             "EXACT" if h["dstart"] + sum(c for _, c, _ in blocks) == len(raw) else "MISMATCH"))
    print("   sum(usize)=%d  node sizes=%s"
          % (sum(u for u, _, _ in blocks), [n[1] for n in nodes]))

    parts, pos = [], h["dstart"]
    for i, (u, c, f) in enumerate(blocks):
        src = os.path.join(WORK, "%s_b%d.bin" % (tag, i))
        open(src, "wb").write(raw[pos:pos + c])
        pos += c
        outp = src + ".out"
        got = None
        for dsl in order:
            t0 = time.time()
            try:
                r = subprocess.run([PY310, HP, src, str(u), "0", str(dsl), "0", outp],
                                   capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                print("   blk%-2d usize=%-7d csize=%-6d dsl=%-2d TIMEOUT>%ds"
                      % (i, u, c, dsl, timeout), flush=True)
                continue
            dt = time.time() - t0
            so = (r.stdout or "").strip()
            if r.returncode == 0 and so.startswith("OK"):
                got = open(outp, "rb").read()
                print("   blk%-2d usize=%-7d csize=%-6d flag=%d dsl=%-2d OK in %.1fs"
                      % (i, u, c, f, dsl, dt), flush=True)
                break
            print("   blk%-2d usize=%-7d csize=%-6d dsl=%-2d rc=%d %s (%.1fs)"
                  % (i, u, c, dsl, r.returncode, so[:70], dt), flush=True)
        if got is None:
            print("   !! block %d FAILED (all dict sizes)" % i, flush=True)
            return None
        parts.append(got)
    blob = b"".join(parts)
    tot_u = sum(u for u, _, _ in blocks)
    print("   decoded %d bytes (expected %d) match=%s" % (len(blob), tot_u, len(blob) == tot_u))
    outs = []
    for (off, sz, fl, nm) in nodes:
        data = blob[off:off + sz]
        outs.append((nm, data))
        print("   node %-46s off=%-8d size=%-8d got=%-8d %s"
              % (nm, off, sz, len(data), "OK" if len(data) == sz else "SHORT"))
    return blob, blocks, nodes, outs


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else (
        r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
        r"\StreamingAssets\AB\Windows\ui\[uc]pc.ab")
    tag = sys.argv[2] if len(sys.argv) > 2 else "ucpc"
    res = decode_bundle(target, tag)
    if res:
        blob, blocks, nodes, outs = res
        op = os.path.join(WORK, tag + "_full.bin")
        open(op, "wb").write(blob)
        print("wrote %s (%d B)" % (op, len(blob)))
        cab = blob[:189068]
        print("CAB head:", cab[:64].hex())
        ms, fs, ver, doff = struct.unpack_from(">IIII", cab, 0)
        print("serialized: metadata=%d fileSize=%d version=%d dataOffset=%d"
              % (ms, fs, ver, doff))
        print("fileSize == node size 189068 ?", fs == 189068)
        for nm, data in outs:
            if not nm.endswith(".resS"):
                safe = nm.replace("/", "_").replace("\\", "_")
                op2 = os.path.join(WORK, safe + ".bin")
                open(op2, "wb").write(data)
                print("wrote %s" % op2)
