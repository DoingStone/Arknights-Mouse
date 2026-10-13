# -*- coding: utf-8 -*-
"""Hexdump [uc]pc.ab's blocks-info verbatim so the node table can be read by eye."""
import struct

BUNDLE = (r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data"
          r"\StreamingAssets\AB\Windows\ui\[uc]pc.ab")
import lz4.block

raw = open(BUNDLE, "rb").read()
p = 12


def cstr(buf, pp):
    e = buf.index(b"\x00", pp)
    return buf[pp:e].decode(), e + 1


player, p = cstr(raw, p)
engine, p = cstr(raw, p)
p += 8
cbi, ubi, flags = struct.unpack_from(">III", raw, p)
p += 12
qi = (p + 15) & ~15
bi = lz4.block.decompress(raw[qi:qi + cbi], uncompressed_size=ubi)
print("header_end=%d qi=%d cbi=%d ubi=%d len(bi)=%d" % (p, qi, cbi, ubi, len(bi)))
print("blocks-info hexdump:")
for off in range(0, len(bi), 16):
    chunk = bi[off:off + 16]
    hexs = " ".join("%02x" % c for c in chunk)
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
    print("  %04d  %-47s  %s" % (off, hexs, asc))

print("\nfield-by-field from offset 16:")
q = 16
nb = struct.unpack_from(">i", bi, q)[0]
print("  nb = %d" % nb)
q += 4
for i in range(nb):
    us, cs, fl = struct.unpack_from(">IIH", bi, q)
    print("  blk%d  usize=%-8d csize=%-8d flag=%d   (at %d)" % (i, us, cs, fl, q))
    q += 10
print("  q after blocks = %d" % q)
nn = struct.unpack_from(">i", bi, q)[0]
print("  nn = %d (at %d)" % (nn, q))
q += 4
for i in range(nn):
    print("  -- node %d begins at %d" % (i, q))
    off, sz, nfl = struct.unpack_from(">qqI", bi, q)
    q += 20
    print("     off=%-10d size=%-10d flags=%d  (cursor now %d)" % (off, sz, nfl, q))
    nl = struct.unpack_from(">i", bi, q)[0]
    q += 4
    print("     nameLen=%-4d raw bytes follow at %d" % (nl, q))
    nm = bi[q:q + nl]
    print("     name=%r" % nm)
    q += nl
    print("     q after name = %d   (remaining %d)" % (q, len(bi) - q))
    if q % 4:
        print("     [q not 4-aligned; next 4-aligned = %d]" % ((q + 3) & ~3))
print("\nfinal q=%d  len(bi)=%d  leftover=%d" % (q, len(bi), len(bi) - q))
print("trailing bytes: %r" % bi[q:])
