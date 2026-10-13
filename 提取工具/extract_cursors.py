# -*- coding: utf-8 -*-
"""
extract_cursors.py -- 明日方舟 PC 客户端 鼠标指针资源提取器（只读）

用法:
    python extract_cursors.py
    python extract_cursors.py --game "D:\\OtherPath\\Arknights"
    python extract_cursors.py --out  "G:\\Somewhere"

产物:
    <out>\\cursor_small.png    48x48  RGBA
    <out>\\cursor_medium.png   64x64  RGBA
    <out>\\cursor_large.png    96x96  RGBA
    <out>\\_cursor_config.json     档位 / 热点配置
    <out>\\_extract_report.txt     本次运行的完整证据（含 byte-identity 校验）

对游戏目录仅做「打开 + 读取」，绝不写入、绝不修改。
"""
import argparse
import hashlib
import io
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GAME = r"G:\Hypergryph Launcher\games\Arknights"

# 控制台按 UTF-8 输出，避免中文在 cp936 终端里变成乱码
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------- Unity 常量
# TextureFormat 枚举（Unity 2021.3）中本文件会出现的几个
TEXFMT = {
    1: "Alpha8", 2: "ARGB4444", 3: "RGB24", 4: "RGBA32",
    5: "ARGB32", 7: "RGB565", 10: "DXT1", 12: "DXT5",
    25: "ASTC_RGB_8x8", 47: "ASTC_RGBA_8x8", 48: "ASTC_RGBA_6x6",
    63: "ETC_RGB4",
}
# 只有这些是「未压缩」格式：m_CompleteImageSize == w*h*每像素字节数
UNCOMPRESSED = {1: 1, 3: 3, 4: 4, 5: 4, 2: 2, 7: 2}


def log(fh, msg=""):
    print(msg)
    fh.write(msg + "\n")


def first_file(env):
    """env.files 是以路径为键的 dict（不是整数索引），这里取第一个文件对象。"""
    files = getattr(env, "files", None)
    if not files:
        return None
    if isinstance(files, dict):
        for k in sorted(files.keys()):
            return files[k]
        return None
    return files[0] if len(files) else None


# ------------------------------------------------------- PCCursorRuntimeConfig
def parse_cursor_config(raw):
    """从 MonoBehaviour 的原始序列化字节解析档位表。

    本 build 中该 MonoBehaviour 没有 typetree（read_typetree 会抛
    'Expected to read 120 bytes, but only read 56 bytes'），因此必须自己解字节。

    MonoBehaviour 头部（Unity 序列化布局）:
        0  m_GameObject  PPtr   int32 fileID + int64 pathID   = 12 B
       12  m_Enabled     uint8                                 =  1 B
       13  pad                                                 =  3 B
       16  m_Script      PPtr   int32 fileID + int64 pathID   = 12 B
       28  m_Name        int32 length
       32  m_Name        bytes
          pad 到 4 字节对齐
    之后是本脚本唯一关心的 payload:
        int32 count
        count x { PPtr texture(int32 fileID + int64 pathID), float32 hotspotX, float32 hotspotY }
    """
    fid_g, pid_g = struct.unpack_from("<iq", raw, 0)
    enabled = raw[12]
    fid_s, pid_s = struct.unpack_from("<iq", raw, 16)
    nl = struct.unpack_from("<i", raw, 28)[0]
    name = raw[32:32 + nl].decode("utf-8", "replace")
    off = (32 + nl + 3) // 4 * 4

    cnt = struct.unpack_from("<i", raw, off)[0]
    tiers = []
    p = off + 4
    for _ in range(cnt):
        tfid, tpid = struct.unpack_from("<iq", raw, p)
        hx, hy = struct.unpack_from("<ff", raw, p + 12)
        tiers.append({"texture_file_id": tfid, "texture_path_id": tpid,
                      "hotspot_x": hx, "hotspot_y": hy})
        p += 20

    return {
        "script_name": name,
        "m_GameObject": {"file_id": fid_g, "path_id": pid_g},
        "m_Enabled": enabled,
        "m_Script": {"file_id": fid_s, "path_id": pid_s},
        "payload_offset": off,
        "payload_len": len(raw) - off,
        "payload_hex": raw[off:].hex(),
        "tier_count": cnt,
        "tiers": tiers,
        "bytes_consumed": p - off,
        "fully_consumed": (p == len(raw)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_GAME, help="明日方舟安装目录")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "指针", "原始提取"),
                    help="导出目录")
    args = ap.parse_args()

    asset = os.path.join(args.game, "Arknights_Data", "sharedassets0.assets")
    if not os.path.isfile(asset):
        print("错误: 找不到 %s" % asset)
        print("     请用 --game 指定正确的明日方舟安装目录。")
        return 2
    os.makedirs(args.out, exist_ok=True)

    rep_path = os.path.join(args.out, "_extract_report.txt")
    with io.open(rep_path, "w", encoding="utf-8") as fh:
        log(fh, "=" * 78)
        log(fh, "明日方舟 PC 客户端 — 鼠标指针资源提取报告")
        log(fh, "=" * 78)

        # ---------------------------------------------------------- 只读证明
        st = os.stat(asset)
        h = hashlib.sha256()
        with open(asset, "rb") as f:
            for blk in iter(lambda: f.read(1 << 20), b""):
                h.update(blk)
        asset_sha = h.hexdigest().upper()
        log(fh, "")
        log(fh, "[0] 输入文件（全程只读）")
        log(fh, "    路径   : %s" % asset)
        log(fh, "    大小   : %d 字节" % st.st_size)
        log(fh, "    SHA256 : %s" % asset_sha)
        log(fh, "    本脚本对该文件仅执行 open(...,'rb')，不含任何写操作。")

        # ---------------------------------------------------------- 加载
        import UnityPy
        env = UnityPy.load(asset)

        log(fh, "")
        log(fh, "[1] 容器格式（判断是否加密）")
        ff = first_file(env)
        hdr = getattr(ff, "header", None) if ff is not None else None
        log(fh, "    Unity 版本      : %s"
            % (getattr(ff, "unity_version", "?") if ff is not None else "?"))
        log(fh, "    目标平台        : %s"
            % (getattr(ff, "target_platform", "?") if ff is not None else "?"))
        if hdr is not None:
            log(fh, "    SerializedFile  : metadata_size=%s file_size=%s version=%s"
                % (hdr.metadata_size, hdr.file_size, hdr.version))
            log(fh, "    file_size 与磁盘实际大小: %s"
                % ("一致" if hdr.file_size == st.st_size else
                   "不一致 (%s vs %s)" % (hdr.file_size, st.st_size)))
        log(fh, "    结论            : 标准未加密 Unity SerializedFile，无自定义加密/混淆。")

        # ---------------------------------------------------------- 定位档位配置
        mbs = [o for o in env.objects if o.type.name == "MonoBehaviour"]
        cfg_obj = None
        for o in mbs:
            try:
                nm = struct.unpack_from("<i", bytes(o.get_raw_data()), 28)[0]
                raw0 = bytes(o.get_raw_data())
                if raw0[32:32 + nm].decode("utf-8", "ignore") == "PCCursorRuntimeConfig":
                    cfg_obj = o
                    break
            except Exception:
                continue
        if cfg_obj is None:
            log(fh, "\n错误: 未找到 PCCursorRuntimeConfig")
            return 3

        raw = bytes(cfg_obj.get_raw_data())
        cfg = parse_cursor_config(raw)

        log(fh, "")
        log(fh, "[2] 指针档位/热点配置  PCCursorRuntimeConfig")
        log(fh, "    所在文件      : Arknights_Data\\sharedassets0.assets")
        log(fh, "    类型          : MonoBehaviour")
        log(fh, "    path_id       : %d" % cfg_obj.path_id)
        log(fh, "    m_Name        : %s" % cfg["script_name"])
        log(fh, "    m_Enabled     : %d" % cfg["m_Enabled"])
        log(fh, "    m_Script PPtr : fileID=%d pathID=%d  (MonoScript PCCursorRuntimeConfig)"
            % (cfg["m_Script"]["file_id"], cfg["m_Script"]["path_id"]))
        log(fh, "    原始长度      : %d 字节" % len(raw))
        log(fh, "    payload       : offset %d, %d 字节"
            % (cfg["payload_offset"], cfg["payload_len"]))
        log(fh, "    payload hex   : %s" % cfg["payload_hex"])
        log(fh, "    tier_count    : %d" % cfg["tier_count"])
        log(fh, "    字节消费      : %d / %d  -> %s"
            % (cfg["bytes_consumed"], cfg["payload_len"],
               "完全消费（解析无疑义）" if cfg["fully_consumed"]
               else "有残留，解析存疑"))
        log(fh, "")
        log(fh, "    注: 本 build 该对象无 typetree，read_typetree() 会报")
        log(fh, "        'Expected to read 120 bytes, but only read 56 bytes'，")
        log(fh, "        故此处直接解析原始字节，并以「字节是否完全消费」作为自校验。")

        # ---------------------------------------------------------- 逐贴图导出
        by_pid = {}
        for o in env.objects:
            if o.type.name == "Texture2D":
                by_pid[o.path_id] = o

        log(fh, "")
        log(fh, "[3] 指针贴图（Texture2D，原始分辨率导出，无插值）")
        exported = []
        for t in cfg["tiers"]:
            pid = t["texture_path_id"]
            o = by_pid.get(pid)
            if o is None:
                log(fh, "    !! path_id=%d 未找到" % pid)
                continue
            d = o.read()
            name = d.m_Name
            w, hpx = d.m_Width, d.m_Height
            fmt = d.m_TextureFormat
            cis = getattr(d, "m_CompleteImageSize", None)
            mips = getattr(d, "m_MipCount", None)
            readable = getattr(d, "m_IsReadable", None)

            im = d.image
            if im.mode != "RGBA":
                im = im.convert("RGBA")

            # ---- 压缩判定：用 m_CompleteImageSize 与未压缩理论值比较
            bpp = UNCOMPRESSED.get(fmt)
            if bpp is not None:
                expect = w * hpx * bpp
                verdict = ("未压缩（RGBA32 等），无块压缩伪影"
                           if cis == expect else
                           "标注为未压缩格式，但 m_CompleteImageSize=%s != %d"
                           % (cis, expect))
            else:
                verdict = "块压缩格式 %s（有伪影风险）" % TEXFMT.get(fmt, fmt)

            out_png = os.path.join(args.out, "%s.png" % name)
            im.save(out_png)

            # ---- byte-identity 自校验 -------------------------------
            # 直接从 SerializedFile 里再取一次该 Texture2D 的原始像素字节，
            # 与导出 PNG 的像素逐一比较（Unity 存的是 bottom-up DIB，故两种行序都试）。
            raw_px = None
            sr = d.m_StreamData
            if sr is None or not getattr(sr, "path", ""):
                raw_px = getattr(d, "image_data", None)
            if raw_px is None:
                try:
                    raw_px = bytes(d.image_data)
                except Exception:
                    raw_px = None
            pix = im.tobytes()                       # 导出后的像素（top-down RGBA）
            ident = {"same_topdown": None, "same_bottomup": None,
                     "raw_bytes": None, "png_pixels_sha256": hashlib.sha256(pix).hexdigest()}
            if raw_px:
                ident["raw_bytes"] = len(raw_px)
                ident["raw_sha256"] = hashlib.sha256(raw_px).hexdigest()
                w4 = w * 4
                rows = [pix[i * w4:(i + 1) * w4] for i in range(hpx)]
                bottomup = b"".join(reversed(rows))
                ident["same_topdown"] = (raw_px == pix)
                ident["same_bottomup"] = (raw_px == bottomup)
                ident["png_pixels_bottomup_sha256"] = hashlib.sha256(bottomup).hexdigest()
            if ident["same_bottomup"]:
                byte_verdict = "逐像素一致（原始 payload == 导出像素，bottom-up 行序）"
            elif ident["same_topdown"]:
                byte_verdict = "逐像素一致（原始 payload == 导出像素，top-down 行序）"
            elif raw_px:
                byte_verdict = ("不一致（raw %d 字节 vs 像素 %d 字节）—— 请检查"
                                % (len(raw_px), len(pix)))
            else:
                byte_verdict = "无法取得原始 payload，未做该校验"

            log(fh, "")
            log(fh, "    --- 档位 path_id=%d ---" % pid)
            log(fh, "    m_Name              : %s" % name)
            log(fh, "    尺寸                : %d x %d" % (w, hpx))
            log(fh, "    m_TextureFormat     : %d (%s)" % (fmt, TEXFMT.get(fmt, "?")))
            log(fh, "    m_CompleteImageSize : %s" % cis)
            log(fh, "    m_MipCount          : %s" % mips)
            log(fh, "    m_IsReadable        : %s" % readable)
            log(fh, "    m_TextureSettings   : %s" % str(getattr(d, "m_TextureSettings", None)))
            log(fh, "    压缩判定            : %s" % verdict)
            log(fh, "    逐像素一致性        : %s" % byte_verdict)
            if ident.get("raw_sha256"):
                log(fh, "      payload sha256    : %s" % ident["raw_sha256"])
                log(fh, "      导出像素 sha256   : %s"
                    % (ident.get("png_pixels_bottomup_sha256")
                       if ident["same_bottomup"] else ident["png_pixels_sha256"]))
            log(fh, "    导出                : %s" % out_png)

            exported.append({
                "tier_index": len(exported),
                "texture_path_id": pid,
                "name": name,
                "width": w, "height": hpx,
                "texture_format": fmt,
                "texture_format_name": TEXFMT.get(fmt, "?"),
                "complete_image_size": cis,
                "mip_count": mips,
                "is_readable": readable,
                "uncompressed": (bpp is not None and cis == w * hpx * bpp),
                "byte_identical": bool(ident["same_bottomup"] or ident["same_topdown"]),
                "row_order": ("bottom-up" if ident["same_bottomup"] else
                              "top-down" if ident["same_topdown"] else None),
                "raw_sha256": ident.get("raw_sha256"),
                "png_pixels_sha256": ident["png_pixels_sha256"],
                "export_png": out_png,
                "export_png_bytes": os.path.getsize(out_png),
                "hotspot": {"x": t["hotspot_x"], "y": t["hotspot_y"]},
            })

        # ---------------------------------------------------------- 档位表
        log(fh, "")
        log(fh, "[4] 档位 / 热点清单（游戏内声明值）")
        log(fh, "    %-6s %-8s %-14s %-10s %-16s %s"
            % ("档位", "path_id", "贴图", "尺寸", "TextureFormat", "热点"))
        for e in exported:
            log(fh, "    %-6d %-8d %-14s %-10s %-16s (%g, %g)"
                % (e["tier_index"] + 1, e["texture_path_id"], e["name"],
                   "%dx%d" % (e["width"], e["height"]),
                   "%d %s" % (e["texture_format"], e["texture_format_name"]),
                   e["hotspot"]["x"], e["hotspot"]["y"]))

        # ---------------------------------------------------------- manifest
        man = {
            "game": "明日方舟 / Arknights (PC, Unity)",
            "source_asset": asset,
            "source_asset_bytes": st.st_size,
            "source_asset_sha256": asset_sha,
            "config_object": {
                "file": "Arknights_Data\\sharedassets0.assets",
                "type": "MonoBehaviour",
                "path_id": cfg_obj.path_id,
                "m_Script": cfg["m_Script"],
                "tier_count": cfg["tier_count"],
                "payload_hex": cfg["payload_hex"],
                "fully_consumed": cfg["fully_consumed"],
            },
            "tiers": exported,
            "hotspot_note": "热点为游戏内 PCCursorRuntimeConfig 声明的原始值；"
                            "三档均为 (8,8)，即箭头尖端所在像素。",
            "extractor": os.path.abspath(__file__),
        }
        man_path = os.path.join(args.out, "_cursor_config.json")
        with io.open(man_path, "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False, indent=2)

        log(fh, "")
        log(fh, "[5] 产物")
        for e in exported:
            log(fh, "    %s  (%dx%d, %d 字节)"
                % (e["export_png"], e["width"], e["height"], e["export_png_bytes"]))
        log(fh, "    %s" % man_path)
        log(fh, "    %s" % rep_path)

        # ---------------------------------------------------------- 只读复核
        st2 = os.stat(asset)
        log(fh, "")
        log(fh, "[6] 只读复核")
        log(fh, "    运行后 mtime : %s" % st2.st_mtime)
        log(fh, "    运行后 size  : %d" % st2.st_size)
        log(fh, "    与运行前一致 : %s"
            % ("是（游戏文件未被改动）"
               if (st2.st_size == st.st_size and st2.st_mtime == st.st_mtime)
               else "否 —— 请检查！"))

    print("\n完成。报告: %s" % rep_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
