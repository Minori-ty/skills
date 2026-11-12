# 启动交接验证

默认不切换 dark 模式，不加固定延时，不默认全量测试或反复构建两个变体。

## 先识别画面阶段

- 圆角卡片尚未撑满：系统展开动画，不能测静态坐标。
- 底色半透明或叠着业务内容：交接/退场，不能测静态颜色和边界。
- 已到首页：启动较快，不代表资源未生效。
- 图文完整但有系统栏：核查原生窗口、Activity、Flutter 的隐藏时机和真实内容视口。

debug/release 时序依设备和初始化而变，**不存在通用的 0.4～0.6 秒安全区**。先采少量点，依据结果调整一次；稳定帧太短就说明未捕获，不反复试拍或为截图延长启动。确需逐帧分析时再按授权录屏。

## 截图和量测

```bash
python <skill-dir>/scripts/capture_splash.py --pkg com.example.app \
  --series 0.20,0.40 --out D:/Temp/splash/shots
python <skill-dir>/scripts/verify_alignment.py --scan --ref D:/Temp/splash/reference.png
python <skill-dir>/scripts/verify_alignment.py --shot D:/Temp/splash/shots/splash_0.40.png \
  --ref D:/Temp/splash/reference.png --device D:/Temp/splash/device.json \
  --band logo:306:426 --band title:462:497 --pad 6
```

区间按实际图替换。参考 PNG 应与设计画布同尺寸；4 倍图不是 1 倍参考。`render_svg.py --reference` 可输出原尺寸参考。

搜索默认在期望区域外扩 6px，并以相邻 band 的中间界线限界，避免把另一行文字算进去。偏移较大可调整 `--pad`，但先排除错误阶段。脚本报告中心位移、宽高误差和最大边界偏差；缺失元素或参考/截图尺寸不符时返回非零退出码。

2px/6px 是诊断阈值，不是“无感”的自动保证。软边自然变化约 1～3px，优先看硬边及中心。渐变可能被识别为墨迹，应人工核对区域或调整 `--threshold`；脚本不能证明两帧之间无闪烁。

## 检查范围

- 默认相关资源、主题与 XML 检查；改 Dart 做相关静态检查，改初始化逻辑做相关现有测试。
- 用户要求发布验收时再安装 release，保留数据，不卸载、不改变登录或定位选择。
- 只有明确要求才使用 `--night yes/no`，记录并恢复原模式；恢复失败报告。默认 `keep` 不读写夜间配置。
- 单设备校准不代表其他尺寸；换 density、系统栏或缩放方式后重算。没采到的系统最早阶段不得宣称已验证。

交付区分编译通过、debug 稳定帧量测、release 实际启动和人工视觉确认。保留必要截图、校准信息和日志，不默认生成长报告。
