# -*- coding: utf-8 -*-
"""Can a genuine higher-resolution PRTS Replica source be obtained?

The registry lists a 'PRTS Replica v8 256x' scheme (Exists=false), and the
WebView2 cache shows the installer served from https://prts.local/ with
hosts sprts.cc in the profile.  Try to reach an update/asset endpoint.
"""
import os, re, json, socket, urllib.request, urllib.error, ssl, collections

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            b = r.read(400000)
            return r.status, dict(r.headers), b
    except urllib.error.HTTPError as e:
        return e.code, {}, b""
    except Exception as e:
        return None, {}, str(e).encode()


print("[1] resolve/download test for prts.local (installer origin)")
for url in ("https://prts.local/", "http://prts.local/", "https://prts.local/latest.json",
            "https://prts.local/manifest.json", "https://prts.local/version.json",
            "https://prts.local/index.html"):
    st, hdr, body = get(url)
    print("   %-42s -> %s  %s" % (url, st, (body[:120] if isinstance(body, bytes) else body)))

print("\n[sprts.cc and friends (found in WebView2 profile)]")
for url in ("https://sprts.cc/", "https://sprts.cc/Replica/latest.json",
            "https://sprts.cc/prts/latest.json"):
    st, hdr, body = get(url)
    print("   %-52s -> %s  %s" % (url, st, (body[:160] if isinstance(body, bytes) else body)))

print("\n[3] hosts file: is prts.local mapped somewhere?]")
hp = r"C:\Windows\System32\drivers\etc\hosts"
try:
    txt = open(hp, encoding="utf-8", errors="replace").read()
    for line in txt.splitlines():
        ls = line.strip()
        if ls and not ls.startswith("#"):
            print("   ", ls)
    if "prts" not in txt.lower():
        print("    (no prts entry in hosts)")
except Exception as ex:
    print("   ERR", ex)

print("\n[4] every unique http(s) origin present in the WebView2 profile]")
CACHE = r"C:\Users\22442\AppData\Local\PRTS\InstallerWebCache"
orig_re = re.compile(rb"https?://([a-zA-Z0-9\.\-]+)")
orig = collections.Counter()
for dp, dn, fns in os.walk(CACHE):
    for fn in fns:
        p = os.path.join(dp, fn)
        try:
            if os.path.getsize(p) > 30 * 1024 * 1024:
                continue
            b = open(p, "rb").read()
        except OSError:
            continue
        for m in orig_re.findall(b):
            orig[m.decode("ascii", "replace").lower()] += 1
for o, c in orig.most_common(60):
    print("   x%-5d %s" % (c, o))

print("\n[5] PRTS-Motion-96.exe strings hinting at an update/size endpoint]")
exe = r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\PRTS-Motion-96.exe"
try:
    b = open(exe, "rb").read()
    for pat in (rb"https?://[\x21-\x7e]{5,140}", rb"[\x20-\x7e]{6,120}\.(json|zip|7z|exe|bin)"):
        for m in re.findall(pat, b)[:40]:
            s = m.decode("ascii", "replace")
            if any(k in s.lower() for k in ("prts", "http", "replica", "size", "256", "update",
                                            "download", "variant", "96x")):
                print("   ", s[:150])
except Exception as ex:
    print("   ERR", ex)
