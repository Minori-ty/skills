# 几何：为什么系统层老是差几十像素

## 问题在哪

Android 的系统起始窗口（`LaunchTheme.windowBackground`）在 Flutter 引擎起来
之前就开始画。要让它和 Flutter 首帧"看不出交接"，两层必须**画同一张画、落在同一
个像素**。

绝大多数失败案例都不是画错了，是**坐标换算少乘了一步**。Flutter 那层通常不是
按屏幕像素 1:1 排版的 —— 设计稿是固定画布（比如 412×892），靠 `FittedBox` 缩放
铺满视口。系统层不知道这件事，于是两边各画各的。

## 三个数，一起算

```
视口宽/高（dp） = 屏幕像素 / (density / 160)
s              = min(视口宽 / 画布宽, 视口高 / 画布高)      // contain
letterbox      = (视口高 − 画布高 × s) / 2                  // contain 上下的余量
```

`s` 是**整套方案的根**。真机上任何元素都只有 `设计尺寸 × s` 大，任何 y 坐标
都只有 `letterbox + 设计y × s`。

> 例：1280×2772 @520dpi → 视口 393.85×852.92dp，画布 412×892
> → `s = 0.9559373`，`letterbox = 0.1135dp`
>
> 也就是说 96dp 的标记在真机上只有 **91.77dp**。漏掉 `s` 的典型症状：
> 交接瞬间元素"缩一下"（差 4.6%）。

## 位图密度：`4×s`，不是 `4`

位图放 `drawable-xxxhdpi` 时，Android 认为它的尺寸是 **`px / 4` dp**。要让这个
尺寸等于 `设计尺寸 × s`：

```
px = 设计尺寸 × s × 4      →      pixelRatio / 缩放系数 = 4 × s
```

取 `4` 的话 intrinsic 会大 `1/s` 倍（本机 4.6%），交接时元素缩一下。

`drawable-nodpi` 能做到 1:1 物理像素，但那只在标定的那台机器上成立，换机就错；
`xxxhdpi` + `4×s` 是"这台机器像素级准、别的机器 dp 级准"的折中，更稳。

## `android:bottom` 的两个锚法

`<item android:bottom="X">` 把 item 的可用框从底部裁掉 X：

| `gravity` | 效果 | 公式 |
|---|---|---|
| `center` | 中心落在 `(视口高 − X)/2` | `X = 视口高 − 2 × (letterbox + 设计y × s)` |
| `bottom\|center_horizontal` | 底边距窗口底 X | `X = (视口高 − (letterbox + 画布高×s)) + 设计y × s` |

`center` 那条容易记错成"X = 距底距离"。它其实是**两倍**的关系：裁掉 X，
中心上移 X/2。

`layer-list` 没有百分比定位，所以这两个 X 天然是**单机标定**的。换机型必须重算
（`emit_xml.py` 会自动算，`probe_device.py` 会自动读设备）。

## 位图内部：把"相对关系"焊死在图里

标记和它下面的标语，如果拆成两个 item，就得在 XML 里再写一遍那个间距 ——
一个数字，两处维护，早晚打架。

做法是**合成一张位图**：内部间距由渲染代码决定（和 Flutter 那层的 Column 用同一
组常量），XML 里只留一个 `bottom`。底部锁标同理单独一张，因为它锚在屏幕底。

底板四周留 ~12dp 透明边：标记带投影（向下 3 + 模糊 10 − 收缩 5 = 8dp），
`RepaintBoundary`／位图边界太紧会把影子切成硬边。衬边**左右上下对称**，
内容中心 == 位图中心，所以不影响 `bottom` 的计算。

## PIL 还原 Flutter 的排版与阴影

| Flutter | PIL |
|---|---|
| `leadingDistribution: even` + `height` | `halfLeading = (line − (ascent+descent))/2`，基线 = `halfLeading + ascent` |
| `letterSpacing` | 逐字画，`x += getlength(ch) + tracking`；**居中要用含尾字距的总宽** |
| `BoxShadow(blurRadius: B)` | `sigma = B × 0.57735 + 0.5`（Skia `ConvertRadiusToSigma`） |
| `spreadRadius: S` | 正数外扩、负数内收；**`RRect.inflate` 同步收圆角**（24 → 19） |
| `color.withValues(alpha: a)` | `fill = rgb + (round(a×255),)`，直接在 RGBA 画布上画 |

`spreadRadius` 的符号是这里最阴的坑：设计稿写 `-5`（让影子只从底下漏一条），
按 `+5` 算会得到一圈往外发散的灰雾，尺寸对但一眼就"不是这个味道"。

## 字体：仅重新排字时读取设备字体

SVG 文字已转轮廓或复用既有位图时，无需拉字体。只有重新渲染文本时才需要以下检查。

中文/日文/韩文字形各版本有差异，`NotoSansCJK-Regular.ttc` 里按
`JP(0) / KR(1) / SC(2) / TC(3) / HK(4)` 排。桌面上的 Noto Sans SC 与设备上的
不是同一版，字宽能差 1~2px。

```
adb pull /system/fonts/NotoSansCJK-Regular.ttc
ImageFont.truetype(ttc, size, index=2)     # SC 面，别硬编码 0
```

拼音字母类的品牌字（Poppins 等）用工程 `assets/fonts/` 里那份，和 Flutter 一致。

## 常见错误对照表

| 症状 | 原因 |
|---|---|
| 元素整体大/小 4% 左右，交接时"缩一下" | 位图密度取了 4 而不是 `4×s` |
| 元素整体偏上/偏下几十到几百 px | `bottom` 用了「距画布底」而非「距屏幕底」，或漏了 `letterbox` |
| 中心锚的元素偏移是位移量的两倍 | 记反了 `android:bottom` 与中心的关系 |
| 淡出时看到两枚 logo | 两层画的是两张不同的图（常见：系统层还是旧品牌图） |
| 深色下闪白 | 只改了 `values/`，没做 `values-night/`（底色 + 位图各一套） |
| 构建报 `Failed to parse XML file` | 注释里画了减号分隔线（连续两个减号在 XML 里非法） |
| 交接时文字错位 2~3px | 位图里的字体和 Flutter 用的不是同一份 |


## 适用边界

上述公式针对 contain 与全屏内容视口。probe_device.py 使用 wm size 计算完整屏幕；存在系统栏预留或不同的切口布局时先核实真实视口。单机校准不能保证其他尺寸相同；跨设备要求应使用实际约束或独立校准，不将参考机的 s 固定为通用常量。

完整 SVG 可直接栅格化为同源图片，再复用到原生和 Flutter。不要为了套用分组样板重新画文字、品牌图形或添加原设计没有的版本号。
