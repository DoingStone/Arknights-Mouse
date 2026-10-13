# 明日方舟 · 水晶指针安装包

> 一套 17 个角色、三档尺寸、**保留原动画**的 Windows 鼠标指针。
> 安装 / 切换 / 回滚全程只写 `HKCU`，**不碰任何游戏文件**。

---

## 一、这个包是什么，以及它和游戏的关系

### 1.1 一个必须先讲清楚的事实

你给的那张「尖刺水晶指针」图，**不是明日方舟客户端内的资源**。

我把客户端翻了个底朝天，结论是穷举性的：

| 检查项 | 方法 | 结果 |
|---|---|---|
| 全部 16 个 `*.assets` 的 Texture2D/Sprite | 按 `pointer\|cursor\|arrow\|mouse\|hand\|click\|aim\|select` 正则扫名字 | 真正的鼠标指针美术**只有 3 张** |
| 那 3 张是什么 | 逐一导出查看 | `cursor_small` 48×48、`cursor_medium` 64×64、`cursor_large` 96×96 —— **全是白色箭头** |
| 指针档位/热点配置 | `sharedassets0.assets` 里 `Torappu.UI.PCCursorRuntimeConfig`（path_id=28） | 3 档，热点全部 `(8,8)`，未压缩 RGBA32 |
| 轮廓形状匹配 | 把全游戏 1022 张 ≥20px 的贴图归一化成 48×48 轮廓，与水晶指针算 IoU | **全游戏最高只有 0.574**，且是无关 UI 件；游戏自带三张箭头只有 0.548 / 0.546 / 0.545 |
| 索引文件 `.idx`（24,521,440 B） | 全文搜 `cursor` / `pointer` / `PCCursor` | `cursor` 命中 18 条，**全是肉鸽地牢的连线件**（`img_cursor*.png`）与 `walkpreviewcursor.prefab`；`pointer` / `PCCursor` **命中 0** |
| 13,163 个 `.ab` 资源包的文件名 | 筛 `pc` / `mouse` / `cursor` / `pointer` | 只有 3 个，其中 2 个是音效与战斗特效；`ui\[uc]pc.ab` 是唯一可疑项 |
| `ui\[uc]pc.ab` | 手工解析 UnityFS 头（flag `0x243`，6 个数据块全 `flag=4` = LZHAM） | 块本身能定位，但 **LZHAM 解码器在 131,072 B 输出的大块上物理不可行**（24 个字典参数组合里，21 个 45 s 超时挂起、3 个 0.00 s 立即 `status code: 14` 失败）。这是解码器能力问题，不是格式问题 |

**那么那张图是哪来的？** 是你自己电脑上已经**整套装着**的第三方指针方案：

```
HKCU\Control Panel\Cursors
  (default) = "PRTS Replica v8 96x"
  Arrow     = C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\
              cursors-34497b84e5b0d7cf\PRTS-Replica-v8-96x-normal.cur
```

这个包由 `G:\Hypergryph Launcher\...` 之外的 **WebView2 安装器**部署（`C:\Users\22442\AppData\Local\PRTS\InstallerWebCache\EBWebView\` 里留下了 `prts.local` 的缓存痕迹），共 1408 个文件（1010 个 `.cur` + 396 个 `.ani`）。

所以本包做的事情是：**把你机器上这套已经在用的第三方美术，重新打包成一套尺寸可控、可一键切换、可一键回滚的规范安装包**（每个角色补齐 32/48/64/96/128/256 六档光栅，让 Windows 按当前光标尺寸与 DPI 自己挑，而不是让系统去拉伸一张小图）。

> 需要说清楚：源图**原生就只有 96×96**。128 与 256 两档是 96px 的**插值放大**，不会凭空长出细节——它们的价值在于让高 DPI 屏走「预先插值好的版本」，比系统实时拉伸更可控。

我们**没有**、也**不会**修改游戏目录下的任何文件。

### 1.2 关于「放大无损」——必须诚实说明

你在最初的设定里要求「放大过程需保证画面无损」。对**游戏自带的那三张白色箭头**，这一点是**可以严格做到**的：它们本质是一个矢量多边形 + 一层高斯阴影，我已经把母版几何拟合出来了（26 顶点多边形，96px 下还原误差 6 像素、MAE 0.00297），任意尺寸都是**从几何重新光栅化**，永远保持 1 像素抗锯齿斜坡，不存在插值糊边。

但这套**水晶指针不行**，原因是我实测出来的：

- 不透明像素（α>200）有 995–1009 个，**亮度值有 156 个不同档**，没有任何一个「面片」占据显著面积；
- 容差分割：`tol=0` 得 868 个连通块（最大仅 9 px）；`tol=8` 才降到 309 个（最大 114 px）；
- 内部梯度**零梯度只占 7.0%**，mean=14.77、p90=38。

也就是说，这是一张**连续着色的 3D 渲染图**（平滑渐变），不是平面刻面模型。它**没有可提取的解析几何**，任何放大都只能是插值。我不会拿「无损」这个词骗你。

### 1.3 那这个包在放大上做了什么

做了三件在插值框架内能做到最好的事：

1. **96px 档保持像素级原样**——`large` 档的 96 光栅与源文件**逐像素完全一致**（已用 `True` 断言验证），不是「很接近」，是**同一份数据**。
2. **预乘 alpha 重采样**。源图所有完全透明像素恰好是纯黑 `(0,0,0,0)`（6569 个像素，distinct RGB = 1）。直接对 straight alpha 做 LANCZOS 会把黑色渗进边缘形成黑边。本包全程走「预乘 → 缩放 → 反预乘」，`a==0` 直接写 `(0,0,0,0)`。实测 A/B：128px 下两者最大差 19/255，且**没有任何一个像素因为预乘而变暗**（0 px 退化）。
3. **每个角色都给满 6 档光栅**（32/48/64/96/128/256），让 Windows 按当前光标尺寸和 DPI 自己挑最合适的那一档，而不是让系统去拉伸一张小图。其中 **96 是原始分辨率**，32/48/64 是缩小的（信息有损但视觉更锐），**128/256 是插值放大的**（不会增加细节，只是把插值工作从系统手里接过来）。

> **一句话**：96px 档 = 原始数据，零损失；其它档 = 高质量预乘 LANCZOS 插值，好于系统拉伸，但不是数学意义上的无损。

---

## 二、三档尺寸是怎么定的

游戏内 `CURSOR_SIZE` 是个 **SLIDER**（连续滑块，不是离散档位），它对应的实际美术资源只有 3 张。我把这三张的几何关系反解出来了，结论是一条**等比数列，公比 1/√2**：

| 游戏档位 | 贴图 | 尺寸 | 相对比例 | 拟合出的缩放系数 |
|---|---|---|---|---|
| 1 | `cursor_small` | 48×48 | `0.50` | **0.5050**（残差 39 px） |
| 2 | `cursor_medium` | 64×64 | `0.7071` | **0.709167**（残差 4 px） |
| 3 | `cursor_large` | 96×96 | `1.00` | **1.0000**（残差 6 px） |

注意中档是 **1/√2 ≈ 0.7071**，不是 2/3。用 2/3 去拟合会产生 86 px 残差，用 1/√2 只有 5 px —— 差了 17 倍，这不可能巧合。

所以本包的三个档位直接对齐这条数列：

| 档位 | 增益 g | 视觉大小 | 说明 |
|---|---|---|---|
| `small` 小 | `0.50` | 与游戏「小」档一致 | 最接近 Windows 默认指针观感 |
| `medium` 中 | `0.7071` (1/√2) | 与游戏「中」档**完全一致** | 游戏内的等比中点 |
| `large` 大 | `1.00` | 96px 原始分辨率 | 最清晰，推荐 2K/4K 屏 |

**热点不随档位缩放。** 游戏里三档的热点固定在 `(8,8)`（箭头尖端所在像素），也就是说放大档位时是「笔身变大、笔尖不动」。本包沿用同一约定：画布 N 上热点落在 `(round(hx*N/96), round(hy*N/96))`，指针尖端的屏幕位置在任何档位都不变。

---

## 三、包里有什么

```
CrystalCursorPack\
├─ README.md                  本文件
├─ install.ps1                安装 / 切换 / 回滚脚本
├─ before-install-backup.json 安装前的系统指针方案（回滚用）
├─ _manifest.json             完整清单：每个文件的路径、字节数、类型、热点
├─ preview_small.png          小档预览（17 个角色，红十字标出热点）
├─ preview_medium.png         中档预览
├─ preview_large.png          大档预览
├─ compare_tiers.png          六角色 × 三档并排（按档位增益显示，直观看尺寸差）
├─ edge_sharpness.png         边缘锐度对比：96px 原样 1x / 2x / 4x 与 4x LANCZOS
├─ backup-applied.txt         首次安装时的注册表快照（仅供参考）
├─ cursors\
│   ├─ small\   Arknights_Crystal_<角色>_small.cur / .ani     （17 个）
│   ├─ medium\  Arknights_Crystal_<角色>_medium.cur / .ani    （17 个）
│   └─ large\   Arknights_Crystal_<角色>_large.cur / .ani     （17 个）
└─ extracted\
    ├─ Arknights_Crystal_<角色>_native96.png   17 张 96×96 原生分辨率 PNG（直接从源文件取，未经过缩放）
    ├─ small\   每档每个角色的 PNG 预览
    ├─ medium\
    └─ large\
```

### 17 个角色与热点

热点全部是**从源文件本身读出来的原生值**（ANI 的每一帧其实是内嵌的完整 `.cur` 文件，因此也自带热点），不是猜的：

| 角色 | 用途 | 源文件 | 热点 (96px) |
|---|---|---|---|
| Arrow | 正常选择 | `normal.cur` | (28, 20) |
| Help | 帮助选择 | `helpsel.cur` | (28, 20) |
| AppStarting | 后台运行 | `work.ani` | (28, 20) |
| Wait | 忙碌 | `busy.ani` | (48, 48) |
| Crosshair | 精确选择 | `cross.cur` | (48, 48) |
| IBeam | 文本选择 | `beam.cur` | (48, 48) |
| NWPen | 手写 | `pen.cur` | (8, 9) |
| No | 不可用 | `unavail1.ani` | (28, 20) |
| SizeNS | 垂直调整 | `sel_1.ani` | (48, 48) |
| SizeWE | 水平调整 | `sel_2.ani` | (48, 48) |
| SizeNWSE | 对角线调整 1 | `sel_3.ani` | (48, 48) |
| SizeNESW | 对角线调整 2 | `sel_4.ani` | (48, 48) |
| SizeAll | 移动 | `move.ani` | (48, 48) |
| UpArrow | 候选选择 | `up.cur` | (48, 4) |
| Hand | 链接选择 | `link.cur` | (28, 20) |
| Pin | 位置选择 | `pin.cur` | (28, 20) |
| Person | 人员选择 | `person.cur` | (28, 20) |

其中 **8 个是动画指针**（`AppStarting`、`Wait`、`No`、`SizeNS`、`SizeWE`、`SizeNWSE`、`SizeNESW`、`SizeAll`），本包**完整保留了动画**：`AppStarting`/`Wait` 与 5 个调整类各 72 帧，`No` 30 帧，帧数与原文件逐一相同；原本带 `rate` 延时数组的（`AppStarting`、`Wait`）也原样保留，其余保持「无 rate chunk、用 `anih` 的 `dispRate`」的原格式。

> ⚠️ **这是本包相对于许多「指针转换工具」的关键差异**：那些工具会把 `.ani` 压成静态首帧，装完你会发现「忙碌」光标不转了。本包不会。

---

## 四、怎么装

### 4.1 一键安装（推荐）

在 PowerShell 里进到包目录：

```powershell
cd G:\ArknightsCursorExtract\CrystalCursorPack

# 先看一眼当前状态和可用档位
.\install.ps1

# 安装「大」档（96px 原始分辨率）
.\install.ps1 -Tier large

# 或者换成「中」档（与游戏内「中」档完全一致）
.\install.ps1 -Tier medium

# 或者「小」档
.\install.ps1 -Tier small
```

装完**立即生效**（脚本会对 16 个可即时切换的角色调用 `SetSystemCursor`，不需要注销）。
若个别已打开的窗口没刷新，注销一次或重启 `explorer.exe` 即可。

### ⚠️ 4.1.1 重要：和 `PRTS-Motion-96.exe` 的冲突

你机器上有一个常驻程序 **`PRTS-Motion-96.exe`**（PID 会变），并且它注册了开机自启：

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
  PRTS-v8-Motion = "C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\PRTS-Motion-96.exe"
                   "C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf"
```

它是 PRTS Replica 的「动态指针」后台：会周期性重新套用那套 96x 方案（它自己的日志 `cursors-34497b84e5b0d7cf\motion.log` 里写着 `reapply 48x48 70 ms base=32`）。**它可能把本包换掉。**
`install.ps1` 每次安装结束都会自动检测并提示这个冲突。

**实测结论（40 秒连续监控）**：本次安装期间它**没有**覆盖本包 —— 但它是否在某个触发时机（如改变光标尺寸、锁屏、分辨率切换）重新套用，本包无法保证。

**如果指针被换回去了，二选一：**

```powershell
# 方案 A：只是临时结束它（重启后还会自启）
Stop-Process -Name 'PRTS-Motion-96' -Force
.\install.ps1 -Tier large

# 方案 B：连同开机自启一起移除（想彻底用本包时选这个）
Remove-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'PRTS-v8-Motion'
Stop-Process -Name 'PRTS-Motion-96' -Force
.\install.ps1 -Tier large
```

> 注意：方案 B 只删掉**自启项**，不删除 PRTS 包的任何文件、也不改它的源码。想恢复就把那条 `Run` 键按上面的命令原文加回去，或重装一次 PRTS Replica。
> 这一步是**可选**的 —— 只有当你发现指针被换回去时才需要做。

### 4.2 查看当前状态

```powershell
.\install.ps1 -Status
```

会显示当前方案名、箭头指针路径，以及是否正在使用本包。

### 4.3 一键回滚

```powershell
.\install.ps1 -Restore
```

从 `before-install-backup.json` 还原安装前的完整方案（也就是你原来的 **PRTS Replica v8 96x**）。
回滚同样是**立即生效**的（脚本会把还原后的 16 个角色重新喂给 `SetSystemCursor`）。

### 4.4 手动安装（不想跑脚本的话）

1. 打开「设置」→「个性化」→「主题」→「鼠标光标」
2. 逐个角色点「浏览」，到 `cursors\large\` 里选对应的 `Arknights_Crystal_<角色>_large.cur` / `.ani`
3. 点「另存为」，命名如「明日方舟 水晶指针 大」

> **首次安装遇到「PowerShell 禁止运行脚本」**：执行
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
> 然后重试即可（只影响当前窗口，安全）。

---

## 五、这套包是怎么做出来的（可复现）

### 5.1 工具与依赖

- **Python 3.11.9**（本机已有）
- **Pillow 12.3.0**（图像解码与 LANCZOS 重采样；仅此一个第三方依赖）
- 构建脚本：`G:\ArknightsCursorExtract\tools\build_crystal_pack.py`（纯标准库 + Pillow，无 numpy）

游戏侧的资源提取另用到 **UnityPy 1.25.4**；`.ani` 里的 LZHAM 数据块另需 **Python 3.10.11 + pylzham 0.1.3**（已落在 `G:\ArknightsCursorExtract\_lzham\py310\`，**导入名是 `lzham` 而不是 `pylzham`**）。

### 5.2 重建命令

```powershell
cd G:\ArknightsCursorExtract\tools
$env:PYTHONIOENCODING="utf-8"
python build_crystal_pack.py
```

脚本会读 `CrystalCursorPack\before-install-backup.json` 拿到 17 个角色的源文件路径，重建全部三档 × 17 角色，并刷新 `_manifest.json` 与三张预览图。

### 5.3 两个容易踩的格式坑（已解决，记录备查）

**`.cur` 容器**：`ICONDIR` 只有 **3 个 u16**（reserved / type / count），不是 4 个；每项 16 字节 `<BBBBHHII>`；DIB 头里的高度字段是**实际高度的 2 倍**（XOR + AND 两张位图叠起来的高度）；当位图是 32bpp 直通 alpha 时 AND 掩码可以全零，Windows 只看 alpha 通道。

**`.ani` 容器**：`RIFF` + `ACON`，顶层 `anih`(36 B) / `rate`(帧延时数组) / `LIST`。关键点——**`LIST` 的 type 字段是 `fram`**，子块从 LIST 数据起点 **+12 字节**开始（8 字节 chunk 头 + 4 字节 type），每个子块是 `icon`，**其载荷是一整个完整的 `.cur` 文件**。

最初我把 `fram` 当成 LIST 的**子 chunk** 去找，结果永远找不到帧；真实关系是 `fram` 属于 LIST 的 **type 字段**。同源文件里 `work.ani` 的 `LIST@352`、`icon` 从 364 开始、每个 38,078 B、间距 38,086 = 8 + 38078，算术完全闭合。

---

## 六、边界情况与已知限制

| 情况 | 本包的处理 |
|---|---|
| **「无损放大」无法对水晶美术成立** | 已在 §1.2 用实测数据说明原因（连续着色渲染图，156 个亮度档，零梯度仅 7%）。96px 档保持逐像素原样，其它档为预乘 LANCZOS 插值。**没有谎称无损。** |
| **游戏内 `CURSOR_SIZE` 是连续滑块** | 已反解出游戏实际只有 3 档美术，比例为 1 : 1/√2 : 1/2。本包三档直接对齐这条数列，因此任意滑块位置都能被三档覆盖。 |
| **资源被压缩/加密** | 游戏自带的三张指针贴图是 **TextureFormat 4 = RGBA32（未压缩）**，`m_CompleteImageSize` = `w*h*4` 精确成立（9216 / 16384 / 36864），导出 PNG 与原始 payload **逐字节 sha256 一致**。`ui\[uc]pc.ab` 的 LZHAM 块**没能解开**，已如实记录原因（解码器在大块上不可行），没有猜测其中内容。 |
| **多份同名/不同来源的资源** | 已全部列出：游戏内正牌指针 = `sharedassets0.assets` 的 3 张白色箭头；本包美术 = 第三方 PRTS Replica v8 96x（1408 个文件，`AppData\Local\PRTS\`）。两者出处、字节数、sha256 均已记录。 |
| **本机不存在更高分辨率源** | 已全盘搜过 `C:\Users\22442`、`G:\`、`D:\`、`C:\ProgramData`：不存在 256x 版本，也不存在安装包本体（只有 `PRTS-Motion-96.exe` 87,552 B）。所以 96px 就是本包能拿到的最高真实分辨率。 |
| **游戏文件安全** | 全程只读。所有工具与产物都在 `G:\Hypergryph Launcher\games\Arknights\` **之外**。安装脚本只写 `HKCU\Control Panel\Cursors`，不需要管理员权限。 |

---

## 七、卸载

```powershell
.\install.ps1 -Restore      # 还原安装前的 PRTS Replica v8 96x 方案
```

还原后直接删掉 `CrystalCursorPack` 目录即可，系统里不留残余（`HKCU` 里只剩你原来的方案）。
