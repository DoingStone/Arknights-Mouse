# -*- coding: utf-8 -*-
"""Dump a UnityFS bundle's blocks-info + per-block heads, then test decompressors
(including LZHAM, which UnityPy refuses to attempt)."""
import struct, sys, io, os, zlib, lzma
from pathlib import Path

try:
    import lz4.block
except Exception:
    lz4 = None

def align16(o):
    return (o + 15) & ~15

def parse(path):
    b = Path(path).read_bytes()
    assert b[:8] == b"UnityFS\0", b[:16]
    o = 8
    def cstr(o):
        e = b.index(b"\0", o)
        return b[o:e].decode("utf8", "replace"), e + 1
    unity_ver, o = cstr(o)
    unity_rev, o = cstr(o)
    total, cbis, ubis, flags = struct.unpack_from(">qIII", b, o)
    o += 20
    hdr_end = o
    o = align16(o)
    bi_off_raw = hdr_end
    bi_off = o
    bi_raw = b[o:o + cbis]
    o += cbis
    bi = lz4.block.decompress(bi_raw, uncompressed_size=ubis) if lz4 else None
    p = 0
    h = bi[:16]; p = 16
    nblk, = struct.unpack_from(">i", bi, p); p += 4
    blocks = []
    for i in range(nblk):
        us, cs, fl = struct.unpack_from(">IIH", bi, p); p += 10
        blocks.append((us, cs, fl))
    nnod, = struct.unpack_from(">i", bi, p); p += 4
    nodes = []
    for i in range(nnod):
        noff, nsize, nfl = struct.unpack_from(">qqI", bi, p); p += 20
        e = bi.index(b"\0", p)
        nm = bi[p:e].decode("utf8", "replace"); p = e + 1
        nodes.append((noff, nsize, nfl, nm))
    data_start = align16(o + len(bi_raw) * 0 + bi_off + cbis - cbis)  # placeholder
    data_start = align16(bi_off + cbis)
    return dict(path=path, size=len(b), unity_ver=unity_ver, unity_rev=unity_rev,
                total=total, cbis=cbis, ubis=ubis, flags=flags, hdr_end=hdr_end,
                bi_off=bi_off, bi=bi, blocks=blocks, nodes=nodes,
                data_start=data_start, raw=b)

def hexs(b, n=48):
    return " ".join(f"{x:02x}" for x in b[:n])

def try_all(data, usize, label):
    print(f"    {label}: csize={len(data)} usize={usize}  head={hexs(data,32)}")
    ok = []
    # 0) raw stored?
    if len(data) == usize:
        ok.append("RAW-STORED(len==usize)")
    # 1) LZHAM
    try:
        import pylzham
        for name, fn in [
            ("pylzham.decompress", lambda d, u: pylzham.decompress(d, u)),
        ]:
            try:
                out = fn(data, usize)
                tag = "OK" if len(out) == usize else f"LEN {len(out)}"
                print(f"      {name} -> {tag}")
                if len(out) == usize:
                    ok.append(name)
                    print(f"        head={hexs(out,32)}")
            except Exception as e:
                print(f"      {name} -> FAIL {type(e).__name__}: {str(e)[:90]}")
    except ImportError:
        print("      pylzham: NOT INSTALLED")
    # 2) LZ4 raw
    if lz4:
        for tag, kw in [("exact", dict(uncompressed_size=usize)),
                        ("auto ", dict())]:
            try:
                out = lz4.block.decompress(data, **kw)
                print(f"      lz4.block[{tag}] -> OK len={len(out)}")
                if len(out) == usize:
                    ok.append("lz4.block[" + tag + "]")
                    print(f"        head={hexs(out,32)}")
            except Exception as e:
                print(f"      lz4.block[{tag}] -> FAIL {type(e).__name__}: {str(e)[:70]}")
    # 3) skip-prefix + lz4
    if lz4:
        for sk in (1, 2, 4, 8, 16):
            try:
                out = lz4.block.decompress(data[sk:], uncompressed_size=usize)
                if len(out) == usize:
                    print(f"      lz4 skip{sk} -> OK")
                    ok.append(f"lz4 skip{sk}")
            except Exception:
                pass
    # 4) zlib / deflate / lzma / brotli
    for nm, fn in [("zlib", lambda d: zlib.decompress(d)),
                   ("raw-deflate", lambda d: zlib.decompress(d, -15)),
                   ("gzip", lambda d: zlib.decompress(d, 31)),
                   ("lzma-alone", lambda d: lzma.decompress(d)),
                   ("lzma-raw", lambda d: lzma.decompress(d, format=lzma.FORMAT_RAW,
                                                          filters=[{"id": lzma.FILTER_LZMA1,
                                                                    "dict_size": 1 << 23}])),
                   ("brotli", lambda d: __import__("brotli").decompress(d))]:
        try:
            out = fn(data)
            print(f"      {nm} -> OK len={len(out)}")
            if len(out) == usize:
                ok.append(nm)
        except Exception:
            pass
    return ok

def main():
    targets = sys.argv[1:] or [
        r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\[uc]pc.ab",
        r"G:\Hypergryph Launcher\games\Arknights\Arknights_Data\StreamingAssets\AB\Windows\ui\zonemap_misc.ab",
    ]
    try: import pylzham; print("pylzham:", pylzham.__file__)
    except ImportError: print("pylzham: NOT INSTALLED")
    for t in targets:
        print("=" * 78)
        print(t)
        d = parse(t)
        print(f"  size={d['size']} unityVer={d['unity_ver']}/{d['unity_rev']} total={d['total']}")
        print(f"  flags=0x{d['flags']:06x} cbis={d['cbis']} ubis={d['ubis']} hdr_end={d['hdr_end']}")
        print(f"  blocks-info at {d['bi_off']} (raw {d['hdr_end']}), {d['cbis']} -> {len(d['bi'])} bytes")
        print(f"  blocks-info hex: {hexs(d['bi'], 80)}")
        print(f"  data_start={d['data_start']}")
        print(f"  blocks={len(d['blocks'])}")
        tot_c = tot_u = 0
        off = d['data_start']
        o = off
        for i, (us, cs, fl) in enumerate(d['blocks']):
            blk = d['raw'][o:o + cs]
            print(f"  --- blk{i}: usize={us} csize={cs} flags=0x{fl:04x} at {o}")
            try_all(blk, us, f"blk{i}")
            o += cs
            tot_c += cs; tot_u += us
        print(f"  sum(csize)={tot_c} sum(usize)={tot_u} end={o} file={d['size']}")
        for (noff, nsize, nfl, nm) in d['nodes']:
            print(f"    node off={noff} size={nsize} flags=0x{nfl:08x} name={nm}")

main()
