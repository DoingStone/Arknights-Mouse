# -*- coding: utf-8 -*-
"""Decompress the CAB node from already-decoded blocks and list its objects."""
import os, struct, sys

sys.path.insert(0, r"G:\ArknightsCursorExtract\tools")
import _lzhamfull as L

WORK = L.WORK
tag = sys.argv[1] if len(sys.argv) > 1 else "ucpc2"
need = [0, 1]
parts = []
for i in need:
    p = os.path.join(WORK, "%s_b%d.bin.out" % (tag, i))
    if not os.path.exists(p):
        print("MISSING", p)
        sys.exit(1)
    d = open(p, "rb").read()
    print("blk%d -> %d B" % (i, len(d)))
    parts.append(d)
cab = b"".join(parts)[:189068]
op = os.path.join(WORK, "CAB_dec.bin")
open(op, "wb").write(cab)
print("wrote %s (%d B)" % (op, len(cab)))

# Unity serialized file header (version >= 22 style): metadata/fsize/ver/dataoff
ms, fs, ver, doff = struct.unpack_from(">IIII", cab, 0)
print("hdr: metadata=%d fileSize=%d version=%d dataOffset=%d endian=%s"
      % (ms, fs, ver, doff, cab[16:20]))
if ver >= 22:
    md_sz, md_off, mo_sz = struct.unpack_from(">III", cab, 20)
    print("v22+: metadataSize=%d metadataOffset=%d fileSize=%d" % (md_sz, md_off, mo_sz))
    md = cab[md_off:md_off + md_sz]
else:
    md = cab[doff:doff + ms]
print("metadata bytes: %d  (expect %s)" % (len(md), ms))

# UnityFS serialized files list types at the end of the metadata.
# Quick heuristic: scan metadata for type strings.
import re
strs = re.findall(rb"[ -~]{4,60}", md)
print("--- printable strings in metadata (%d) ---" % len(strs))
for s in strs[:120]:
    print("   ", s.decode("latin-1"))
