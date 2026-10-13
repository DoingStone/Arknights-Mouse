# -*- coding: utf-8 -*-
"""Enumerate animated roles: frame count, rate array, and the anih fields needed
to rebuild byte-faithful .ani files."""
import os, struct

D = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
     r"\cursors-34497b84e5b0d7cf")

ROLES = {
    "Arrow": "normal.cur", "Help": "helpsel.cur", "AppStarting": "work.ani",
    "Wait": "busy.ani", "Crosshair": "cross.cur", "IBeam": "beam.cur",
    "NWPen": "pen.cur", "No": "unavail1.ani", "SizeNS": "sel_1.ani",
    "SizeWE": "sel_2.ani", "SizeNWSE": "sel_3.ani", "SizeNESW": "sel_4.ani",
    "SizeAll": "move.ani", "UpArrow": "up.cur", "Hand": "link.cur",
    "Pin": "pin.cur", "Person": "person.cur",
}

for role, fn in ROLES.items():
    p = os.path.join(D, "PRTS-Replica-v8-96x-" + fn)
    if not fn.endswith(".ani"):
        continue
    raw = open(p, "rb").read()
    # top-level chunk walk
    chunks = []
    q = 12
    while q + 8 <= len(raw):
        cid = raw[q:q + 4]
        sz = struct.unpack_from("<I", raw, q + 4)[0]
        chunks.append((cid, q, sz))
        if cid == b"LIST":
            break
        q += 8 + sz + (sz & 1)
    frames, rate = 0, []
    for cid, o, sz in chunks:
        if cid == b"anih":
            f = struct.unpack_from("<9I", raw, o + 8 + 8)
            # data starts at o+8; first u32 is cbSize
            allv = struct.unpack_from("<9I", raw, o + 8)
            print("%-12s %-11s anih cbSize=%d nFrames=%d nSteps=%d w=%d h=%d bpp=%d planes=%d "
                  "dispRate=%d attrs=0x%x" % (role, fn, *allv))
        elif cid == b"rate":
            n = sz // 4
            rate = list(struct.unpack_from("<%dI" % n, raw, o + 8))
        elif cid == b"LIST":
            typ = raw[o + 8:o + 12]
            p2, end = o + 12, o + 8 + sz
            while p2 + 8 <= end:
                iid = raw[p2:p2 + 4]
                isz = struct.unpack_from("<I", raw, p2 + 4)[0]
                if iid in (b"icon", b"cur "):
                    frames += 1
                p2 += 8 + isz + (isz & 1)
            print("%-12s   LIST type=%r frames=%d  rate[0:6]=%s  distinct rates=%d"
                  % (role, typ, frames, rate[:6], len(set(rate))))
    print()
