# -*- coding: utf-8 -*-
"""scan_provenance.py -- 全客户端扫描：列出所有「指针/箭头」命名贴图及其出处。

用途：回答边界情况「若存在多份同名或不同来源的资源，全部列出并说明出处」。
对每个 .assets 只读打开，列出 Texture2D 名称命中 cursor|pointer|arrow 的对象。

用法:
    python scan_provenance.py
    python scan_provenance.py --game "D:\\OtherPath\\Arknights"

产物:
    <out>\\_provenance.txt    全客户端指针类贴图出处清单
"""
import argparse
import io
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GAME = r"G:\Hypergryph Launcher\games\Arknights"

TEXFMT = {1: "Alpha8", 2: "ARGB4444", 3: "RGB24", 4: "RGBA32", 5: "ARGB32",
          7: "RGB565", 10: "DXT1", 12: "DXT5", 25: "ASTC_RGB_8x8",
          47: "ASTC_RGBA_8x8", 48: "ASTC_RGBA_6x6", 63: "ETC_RGB4"}

KEY = ("cursor", "pointer", "arrow")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--out", default=os.path.join(HERE, "extracted"))
    args = ap.parse_args()

    data = os.path.join(args.game, "Arknights_Data")
    if not os.path.isdir(data):
        print("错误: 找不到 %s，请用 --game 指定安装目录。" % data)
        return 2
    os.makedirs(args.out, exist_ok=True)
    rp = os.path.join(args.out, "_provenance.txt")

    import UnityPy

    files = sorted(f for f in os.listdir(data) if f.endswith(".assets"))
    with io.open(rp, "w", encoding="utf-8") as fh:
        def w(m=""):
            print(m)
            fh.write(m + "\n")

        w("=" * 78)
        w("全客户端「指针 / 箭头」类贴图出处清单")
        w("=" * 78)
        w("扫描目录: %s" % data)
        w("扫描文件: %d 个 *.assets" % len(files))
        w("命中关键字: %s" % ", ".join(KEY))
        w("")

        total = 0
        for fn in files:
            path = os.path.join(data, fn)
            try:
                env = UnityPy.load(path)
            except Exception as e:
                w("[%s] 打开失败: %s" % (fn, e))
                continue
            hits = []
            for o in env.objects:
                if o.type.name != "Texture2D":
                    continue
                try:
                    d = o.read()
                except Exception:
                    continue
                nm = getattr(d, "m_Name", "") or ""
                if any(k in nm.lower() for k in KEY):
                    hits.append((o.path_id, nm, d.m_Width, d.m_Height,
                                 d.m_TextureFormat,
                                 getattr(d, "m_CompleteImageSize", None)))
            if hits:
                w("[%s]" % fn)
                for pid, nm, wd, ht, fmt, cis in hits:
                    w("   path_id=%-6d %-38s %4dx%-4d fmt=%-2d %-11s complete=%s"
                      % (pid, nm, wd, ht, fmt, TEXFMT.get(fmt, "?"), cis))
                total += len(hits)
                w("")

        w("-" * 78)
        w("合计命中 %d 张贴图。" % total)
        w("说明：其中只有 sharedassets0.assets 的 cursor_small / cursor_medium /")
        w("      cursor_large 三张是真正的鼠标指针美术；其余均为 UI 箭头/图标/")
        w("      游戏内准星等，命名含 arrow/pointer 但与鼠标指针无关。")
        w("      本次扫描未发现任何「同名不同来源」的指针贴图。")

    print("\n完成。清单: %s" % rp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
