# -*- coding: utf-8 -*-
"""Decode only the blocks needed for a node prefix, sweeping dict_size_log2."""
import os, struct, subprocess, sys, time

sys.path.insert(0, r"G:\ArknightsCursorExtract\tools")
import _lzhamfull as L

WORK = L.WORK
PY310 = L.PY310
HP = L.HP

target = r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab"
raw, blocks, nodes, h = L.parse_bundle(target)
print("header:", h)
print("blocks:", blocks)
print("nodes:", nodes)
cum = 0
for i, (u, c, f) in enumerate(blocks):
    print("  blk%d usize=%-7d csize=%-6d flag=%d cum[%d..%d)" % (i, u, c, f, cum, cum + u))
    cum += u
print("needed for CAB(0..189068): blocks whose cum range intersects -> above")

want_bytes = 189068
need = []
cum = 0
for i, (u, c, f) in enumerate(blocks):
    if cum < want_bytes:
        need.append(i)
    cum += u
print("blocks needed:", need)

dsls = [0, 26, 25, 24, 23, 22, 21, 20]
for i in need:
    u, c, f = blocks[i]
    src = os.path.join(WORK, "ucpc2_b%d.bin" % i)
    print("blk%-2d csize=%d writing %s" % (i, c, src), flush=True)
    pos = h["dstart"] + sum(blocks[j][1] for j in range(i))
    open(src, "wb").write(raw[pos:pos + c])
    outp = src + ".out"
    for dsl in dsls:
        t0 = time.time()
        try:
            r = subprocess.run([PY310, HP, src, str(u), "0", str(dsl), "0", outp],
                               capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            print("   blk%-2d dsl=%-2d TIMEOUT>300s" % (i, dsl), flush=True)
            continue
        dt = time.time() - t0
        so = (r.stdout or "").strip()
        ok = r.returncode == 0 and so.startswith("OK")
        print("   blk%-2d dsl=%-2d rc=%d %-60s %.1fs %s"
              % (i, dsl, r.returncode, so[:60], dt, "HIT" if ok else ""), flush=True)
        if ok:
            break
