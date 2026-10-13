# -*- coding: utf-8 -*-
"""Hexdump the ANI container layout so the frame walker can be fixed."""
import os, struct

SRC = (r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows"
       r"\cursors-34497b84e5b0d7cf\PRTS-Replica-v8-96x-work.ani")
raw = open(SRC, "rb").read()
print("file = %s" % os.path.basename(SRC))
print("size = %d" % len(raw))
print("head = %r" % raw[:64])


def walk(buf, start, end, depth, label):
    p = start
    pad = "   " * depth
    n = 0
    while p + 8 <= end and n < 12:
        cid = buf[p:p + 4]
        sz = struct.unpack_from("<I", buf, p + 4)[0]
        print("%s%s@%-8d size=%-9d" % (pad, cid.decode("latin1"), p, sz))
        if cid == b"LIST":
            typ = buf[p + 8:p + 12]
            print("%s   LIST-type=%r" % (pad, typ))
            walk(buf, p + 12, min(p + 8 + sz, end), depth + 1, label)
        elif cid in (b"icon", b"cur "):
            d = buf[p + 8:p + 8 + sz]
            if d[:4] == b"\x89PNG":
                print("%s   -> PNG %d B" % (pad, len(d)))
            else:
                hs, bw, bh = struct.unpack_from("<Iii", d, 0)
                print("%s   -> DIB %dx%d (hdr=%d) bs=%d" % (pad, bw, abs(bh) // 2, hs, len(d)))
        p += 8 + sz + (sz & 1)
        n += 1
    if p < end:
        print("%s... (%d bytes remain)" % (pad, end - p))


walk(raw, 12, len(raw), 0, "top")
