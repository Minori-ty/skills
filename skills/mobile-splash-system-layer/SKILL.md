---
name: mobile-splash-system-layer
description: 使用同源静态画面对齐 Android 启动窗口、Activity 背景和 Flutter 首帧，修复启动闪白、图标重影、缩放或位置跳变，并按需量测真机偏差。适用于全屏启动图及 SVG 资源接入；不用于一般应用图标设计。
metadata:
  agent_created: true
---

# 启动屏系统层对齐

目标是静态启动画面完整、交接连续。先确定偏差发生在系统起始窗口、Activity 还是 Flutter 层，再修改对应层。不要承诺未实测的系统版本或设备表现。

## 默认范围

- **不生成 dark 变体、不切换设备夜间模式**。仅明确要求时才增加深色资源及验证。必要时让既有 night 主题继承同一启动配置，防止旧配置覆盖；不要创造深色设计。
- 先读现有入口、主题、Manifest 和资产。合并相关 XML 条目，保留启动图标颜色、权限、签名等已有配置，不覆盖整个文件。
- 技能脚本统一内置在技能目录，直接调用；不要复制或新建生成、截图、量测脚本到用户项目（包括 tool/），除非用户明确要求。临时字体、依赖、校准 JSON、日志、截图及必要临时脚本放 `D:/Temp/<任务名>/`。项目只保留源素材、必要最终资源和运行代码。
- 默认一次相关静态检查、必要的资源编译和少量截图。不默认新增 golden、测试入口或依赖，也不默认全量测试或反复构建 debug/release。改初始化逻辑时运行相关现有测试。
- 无连接设备时完成独立工作并说明未实测，不要求用户解锁或接设备。构建、安装、冷启动应在用户任务授权范围内进行；不卸载或改变业务设置。

## 平台与全屏交接

Android 12+ 系统可能替换传统 `windowBackground` 启动屏。**不写 `windowSplashScreen*` 并不能禁止系统接管**；一台设备成功不能推断所有 ROM 都支持。

- 保留用户选定的方案，先查是否已有原生 SplashScreen API 或插件，不维护两套冲突的资源。
- 需要完整 SVG 图文时接好原生背景，必要时在 Flutter 初始化阶段绘制同源画面。区分系统最早阶段和应用可控制阶段，不把 Flutter 截图称为系统层验证。
- 检查 `LaunchTheme`、`NormalTheme`、Activity 和 Flutter 的系统栏交接。启动图删掉状态栏图形，不等于原生窗口已经隐藏系统栏。
- 启动阶段隐藏系统栏，业务页面就绪后按项目原模式恢复。区分窗口 `FLAG_FULLSCREEN` 与 decor/insets 状态，避免主题使业务页永久全屏。采用适合目标 SDK 的 API，以实测为准。
- 只等待必要初始化；不要为展示启动图或截到画面增加固定延时。稳定帧太短时报告采样局限，不延长生产启动时长。

系统边界参考：[Android 启动屏迁移说明](https://developer.android.com/develop/ui/views/launch/splash-screen/migrate)。遇到新系统行为时核对官方资料。

## 选择资源路径

### 已有完整 SVG

先区分渲染层：Flutter 可通过现有 SVG 渲染依赖直接显示 SVG；Android 原生 windowBackground 不能直接加载 SVG 文件。简单图形可转换为 VectorDrawable，但不完整支持 SVG 特性；包含滤镜、投影等内容时通常栅格化更可靠。不要把原生限制泛化为 Flutter 也必须使用 PNG。选择 PNG 时按原始 `viewBox` 栅格化，复用轮廓、渐变、图形和投影，不重新画字或重建图标。文字已转轮廓时无需设备字体。使用 `scripts/render_svg.py`，依赖 `resvg-py` 可装到临时目录，不加应用运行时依赖。

```bash
python <skill-dir>/scripts/probe_device.py --canvas 412x892 --out D:/Temp/splash/device.json
python <skill-dir>/scripts/render_svg.py --svg assets/brand/splash.svg \
  --device D:/Temp/splash/device.json --out assets/brand/splash.png \
  --reference D:/Temp/splash/reference.png
```

上例 `<skill-dir>` 替换为已安装技能的绝对路径，不能在项目中创建同名 scripts 目录。画布从 SVG 或现有应用布局读取，不照搬例子尺寸。同一 PNG 可用于原生与 Flutter；注册实际路径，不默认拆成四份图片。`render_svg.py` 的输出按 xxxhdpi 校准，复制到对应原生密度目录；Flutter 层仍按设计比例 contain 布局。

### 确需重新排版

才参考 `assets/gen_splash_example.py`、`scripts/splash_parts.py`。品牌、版本、颜色、坐标均为示例，按真实设计替换；相关元素合成一组，投影留足边距。重新渲染中文时才拉设备字体。不要把样板复制到用户项目；确需定制时放任务临时目录，并显式指向技能内的辅助模块。

## 几何与主题

按需读 [geometry.md](references/geometry.md)。对于 `contain`：

- `s = min(viewWidth/designWidth, viewHeight/designHeight)`，`letterbox = (viewHeight-designHeight*s)/2`；同时考虑水平余量。
- xxxhdpi 的位图密度为 `4*s`，intrinsic 为设计尺寸乘 `s`。这是**当前设备校准方案**，不是所有屏幕均已对齐。
- `wm size` 是屏幕尺寸，不自动等于内容视口。`probe_device.py` 按全屏计算，仅确认内容包含系统栏与切口区域时直接采用。
- `android:bottom=X` 配 `gravity=center` 会让中心上移 X/2，不是元素距底 X。

```bash
python <skill-dir>/scripts/emit_xml.py --device D:/Temp/splash/device.json \
  --color @color/splash_bg_fill --elem splash_artwork=center:446 \
  --out android/app/src/main/res/drawable/splash_bg.xml
```

`center:Y` 是设计中心，`bottom:Y` 是设计底部间距。892 高的完整画面中心为 446，其他尺寸重算。按需参考 `assets/styles.xml.tmpl`，将条目合并到既有主题；确认最终解析的 `windowBackground` 引用 drawable，不能仅生成图片而主题仍引用纯色。XML 注释禁止连续两个减号。

## 验证与交付

排查交接或用户要求真机验收时，读 [verification.md](references/verification.md)。

- `probe_device.py`：屏幕、density 和 contain 几何，字体拉取可选。
- `capture_splash.py`：可配置时间点的少量冷启动截图，检查命令和图片有效性，默认保持显示模式。
- `verify_alignment.py`：按区域测量中心、尺寸与边界误差；`--pad` 控制搜索范围，`--threshold` 控制墨迹阈值。缺失元素、尺寸不符时失败，不能返回“零偏差通过”。

先确认截图属于展开、稳定、退场还是业务页，仅稳定画面能静态量测。渐变、阴影、抗锯齿需人工核对识别边界。默认相关静态检查即可；用户要求完整发布验收时才补 release 与更多运行检查。

简短说明改了哪些层、实际检查、设备与构建类型及未验证边界。区分位置偏移和尺寸变化，不把软边 1～3px 变化说成布局错误，不报告还原百分比。保留必要证据，清理中间文件。
