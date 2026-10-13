# -*- coding: utf-8 -*-
"""Acquire a real LZHAM decoder.

Runner 3.11 has no C compiler, so pylzham (cp310-only wheel) cannot be built.
Plan: download the Python 3.10 embeddable runtime (no install, no registry) and
the cp310 pylzham wheel, then use that standalone interpreter as a codec host.
Nothing is written inside the game directory.
"""
import os, sys, io, zipfile, urllib.request, subprocess, glob

ROOT = r"G:\ArknightsCursorExtract\_lzham"
os.makedirs(ROOT, exist_ok=True)

def fetch(url, dest, label):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"  [skip] {label}: already {os.path.getsize(dest)} B")
        return dest
    print(f"  [get ] {label}\n         {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r, open(dest, "wb") as f:
        n = 0
        while True:
            c = r.read(1 << 16)
            if not c:
                break
            f.write(c); n += len(c)
    print(f"         -> {n} B")
    return dest

print("=" * 78)
print("[1] Python 3.10 embeddable runtime")
pyz = os.path.join(ROOT, "python-3.10.11-embed-amd64.zip")
try:
    fetch("https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip", pyz, "cpython 3.10.11 embed")
except Exception as e:
    print("  FAIL", type(e).__name__, e)

print()
print("=" * 78)
print("[2] pylzham cp310 wheel")
whl = os.path.join(ROOT, "pylzham-0.1.3-cp310-cp310-win_amd64.whl")
try:
    fetch("https://files.pythonhosted.org/packages/source/p/pylzham/pylzham-0.1.3-cp310-cp310-win_amd64.whl", whl, "pylzham wheel (guess url)")
except Exception as e:
    print("  guess failed:", type(e).__name__, str(e)[:120])
    # resolve the real URL from the simple index
    try:
        h = urllib.request.urlopen("https://pypi.org/simple/pylzham/", timeout=30).read().decode()
        import re
        m = re.findall(r'href="([^"]*cp310[^"]*\.whl)[^"]*"', h)
        print("  index says:", m)
        if m:
            u = m[-1]
            if u.startswith("//"):
                u = "https:" + u
            elif u.startswith("/"):
                u = "https://pypi.org" + u
            fetch(u, whl, "pylzham wheel (index url)")
    except Exception as e2:
        print("  index failed:", type(e2).__name__, str(e2)[:120])

print()
print("=" * 78)
print("[3] unpack")
pydir = os.path.join(ROOT, "py310")
if os.path.exists(pyz) and not os.path.exists(os.path.join(pydir, "python.exe")):
    os.makedirs(pydir, exist_ok=True)
    with zipfile.ZipFile(pyz) as z:
        z.extractall(pydir)
    print("  extracted embeddable ->", pydir)
sp = os.path.join(pydir, "Lib", "site-packages")
os.makedirs(sp, exist_ok=True)
if os.path.exists(whl):
    with zipfile.ZipFile(whl) as z:
        names = z.namelist()
        print("  wheel contents:", names[:12])
        z.extractall(sp)
    print("  extracted wheel ->", sp)
    print("  pyd found:", glob.glob(os.path.join(sp, "**", "*.pyd"), recursive=True))

# make the embeddable import from site-packages: append to the ._pth file
pth = os.path.join(pydir, "python310._pth")
if os.path.exists(pth):
    txt = open(pth).read()
    if "Lib\\site-packages" not in txt and "Lib/site-packages" not in txt:
        open(pth, "w").write(txt + "\nLib\\site-packages\n")
        print("  patched python310._pth")
    print("  _pth now:", open(pth).read().split())

exe = os.path.join(pydir, "python.exe")
if os.path.exists(exe):
    print()
    print("=" * 78)
    print("[4] smoke test")
    r = subprocess.run([exe, "-c",
                        "import sys;print(sys.version);import pylzham;"
                        "print('pylzham OK', pylzham.__file__);"
                        "print([n for n in dir(pylzham) if not n.startswith('_')])"],
                       capture_output=True, text=True)
    print(r.stdout)
    print(r.stderr[:800])
