# Figma MCP 常见坑

## 目录

- [工具层](#工具层)
- [文件层](#文件层)
- [环境层](#环境层)
- [写入层](#写入层)
- [排查表](#排查表)

## 工具层

### 1. 页面节点查变量返回 `nothing selected`

**症状**：`get_variable_defs` 传 `0:1`（page）返回空或 `nothing selected`。

**原因**：变量是绑定在 frame/component/节点上的，page 本身不是可查询的选择。

**修复**：

1. 用 `get_metadata` 列出目标 frame 的 ID。
2. 对具体 frame/component 调 `get_variable_defs`。
3. 仍为空时，从组件节点或 `get_design_context` 补，并标注“未绑定变量”。

### 2. 整页 `get_metadata` 超限

**症状**：返回十几万字符，工具结果被截断或落盘。

**原因**：页面级 metadata 包含整棵树的所有节点。

**修复**：

1. 页面级只取顶层 frame/component。
2. 对单个 frame 调 metadata。
3. 仍太大时，只读目标子树，或让用户指定 node ID。
4. 用 `scripts/parse_metadata.py` 解析落盘文件。

### 3. metadata 没有颜色/字号

**症状**：拿到了节点树，但不知道颜色、字体、圆角、阴影。

**原因**：`get_metadata` 主要返回结构和 bounds，不返回样式值。

**修复**：

1. `get_variable_defs` 补颜色/字体。
2. 对组件节点再读 metadata，补尺寸、圆角、间距。
3. 需要实现代码时，加载 `figma-design-to-code` 后用 `get_design_context`。
4. 仍拿不到的值，标注“未读取”，不要猜。

### 4. 截图落到意外目录

**症状**：调用成功，但文件不在预期路径；或找不到文件。

**原因**：

- 保存路径是相对路径，实际基准目录和你想的不同。
- 在复合命令里 `cd` 到工作目录外，命令结束后 shell 回到原目录。

**修复**：

1. 用绝对路径保存。
2. 调用后立刻 `ls` / `test -f` 确认。
3. 不要依赖跨命令的 `cd`。

### 5. 大截图 120s 超时

**症状**：`get_screenshot` 长时间无返回，最终超时。

**原因**：整页/大画板渲染量大，或网络慢。

**修复**：

1. 只截单个 frame，不截整页。
2. 降低 scale。
3. 换更小的节点。
4. 超时后停止，不要反复重试同一个调用。
5. 用已有截图 + 变量继续分析，不阻塞。

### 6. URL 的 `node-id` 格式不对

**症状**：节点查不到，或返回空。

**原因**：URL 用 `0-1`，MCP 要 `0:1`；branch URL 的 fileKey 也不同。

**修复**：

1. 用 `scripts/figma_url.py` 解析。
2. 把 `-` 转成 `:`。
3. branch URL 用 `branchKey` 当 `fileKey`。
4. URL 编码 `%3A` 先 decode。

### 7. 结果太长被落盘，`jq` 又不可用

**症状**：工具结果提示保存到文件；环境里没有 `jq`。

**原因**：工具结果超过上下文上限，被写入 `tool-results/`；Windows 环境不一定装了 `jq`。

**修复**：

```bash
PYTHONUTF8=1 python scripts/parse_metadata.py "<file>" --max-depth 3
```

- 显式 `encoding="utf-8"`，避免 GBK 解码错误。
- 不要 `cat` 整个文件到终端；先看结构。
- 多个 JSON 条目逐个解析。

### 8. `get_design_context` 输出太长或太杂

**症状**：返回大量参考代码，和项目组件对不上。

**原因**：节点选得太大；或把参考代码当最终代码。

**修复**：

1. 只选目标区块，不选整页。
2. 先读 `figma-design-to-code` skill。
3. 把输出当参考，按项目组件/Token 重写。
4. 不需要的部分直接丢弃，不要整段复制。

## 文件层

### 9. 变量表 ≠ 完整设计系统

**症状**：按变量实现后，发现 disabled / focus / pressed / scrim 没有值。

**原因**：Figma 文件只把部分值绑成了变量；状态色、透明度、圆角、阴影常在样式或硬编码里。

**修复**：

- 变量、组件 metadata、截图三源交叉。
- 缺失状态单独列“规范缺口”，不要临时发明。
- 禁用态可用 38–50% 不透明度；焦点环用主色；这些是建议，不是 Figma 事实。

### 10. 暗色覆盖不全

**症状**：变量有暗色值，但浮层、空态、错误态没有暗色稿。

**原因**：文件只做了核心页面的暗色版本。

**修复**：

- 统计浅色/暗色画板数量。
- 检查浮层、状态页、表单是否有暗色。
- 缺失时按暗色规则推导，并标注“推导”。

### 11. 组件尺寸低于平台触控标准

**症状**：FilterChip 36、关闭按钮 44，低于 Android 48dp。

**原因**：视觉稿按视觉尺寸画，没有标点击区。

**修复**：

- 视觉尺寸可以保留。
- 点击区补到 48dp。
- 相邻目标间距 ≥ 8dp。
- 在规范里分别写“视觉尺寸”和“点击区”。

### 12. 边框对比度不足

**症状**：浅色边框在浅背景上几乎看不见。

**原因**：装饰性边框被当成控件边界。

**修复**：

- 控件边界/焦点 ≥ 3:1。
- 装饰性卡片描边可以低对比，但输入框、按钮、焦点环要更强。
- 实测，不目测；给出比值。

### 13. 变量名和代码 Token 名不一致

**症状**：Figma 叫 `color/primary`，代码叫 `CrmColors.primary`；直接按名字映射会错。

**原因**：设计和代码各自维护命名。

**修复**：

- 单独做 Token 映射表。
- 以值和用途为准，不以名字为准。
- 映射不确定时标注待确认。

## 环境层

### 14. `figma-desktop` 连不上

**症状**：`ECONNREFUSED` / `CONNECTION_CLOSED`。

**原因**：桌面版 MCP server 没启动，或端口不通。

**修复**：

1. 先确认是哪个 server 失败。
2. 换 plugin 版 Figma MCP（可能仍然可用）。
3. 仍不可用时明确告知用户，不要假装读到了文件。

### 15. 工具在列表里但调用失败

**症状**：知道工具名，但调用报 schema/参数错误。

**原因**：工具是 deferred，schema 还没加载。

**修复**：

- 先用 ToolSearch 加载对应工具 schema。
- 再按 schema 传参。

## 写入层

> 读操作失败只是拿不到数据；写操作失败会改坏画布，而且 Plugin API 没有 undo。
> 完整流程见 [write-ops.md](write-ops.md)。

### 16. 改文本/文本样式报 `Cannot write to node with unloaded font`

**症状**：`characters` 或 `textStyle.lineHeight` 一改就抛错。

**原因**：任何写在文本节点或文本样式上的操作都要求字体已加载。

**修复**：

1. 修改前 `await figma.loadFontAsync({ family, style })`。
2. 改文本样式时，加载该样式用到的**每一个**字重，不只是当前选中的那个。
3. 用 `getStyledTextSegments(['fontName'])` 读节点真实字体，不要硬编码默认字体。

### 17. 节点渲染成纯黑 / 变量没生效

**症状**：绑定变量后某个图标或卡片变成纯黑。

**原因**：`setBoundVariableForPaint(paint, 'color', variable)` 返回**新** paint，且保留传入的 base color；传了 `{0,0,0}` 时变量一旦解析失败就显示黑色。

**修复**：

1. 接住返回值并重新赋值：`node.fills = [paint]`。
2. base color 传真实 hex，不要传黑。

### 18. 图标被压扁 / 变成竖条 / 内容溢出

**症状**：40×40 的图标底渲染成 28×40 的竖条；文案把卡片撑破。

**原因**：设置 `layoutMode` 会把 sizing 重置为 AUTO，随后被父级 auto-layout 拉伸或按内容收缩。

**修复**：

1. 先 `primaryAxisSizingMode = 'FIXED'`、`counterAxisSizingMode = 'FIXED'`，再 `resize(w, h)`。
2. 作为 auto-layout 子节点时，同时设 `layoutSizingHorizontal/Vertical = 'FIXED'`。
3. 用数值验收：返回每个子节点的宽高，而不是看截图猜。

### 19. `Expected 'FIXED' | 'AUTO', received 'FILL'`

**症状**：设置尺寸时报 enum 不匹配。

**原因**：两套枚举混用。

**修复**：

- 子节点用 `layoutSizingHorizontal/Vertical`：`FIXED | HUG | FILL`。
- 容器自身用 `primaryAxisSizingMode/counterAxisSizingMode`：`FIXED | AUTO`。

### 20. 图标背后多出白色方块

**症状**：SVG 图标底上出现一个白底矩形盖住背景色。

**原因**：`figma.createNodeFromSvg()` 的根节点是 FRAME，自带 `#FFFFFF` 填充。

**修复**：

1. `svgRoot.fills = []`。
2. 矢量描边重新绑定语义色变量。

### 21. 改完字阶后整页错位

**症状**：改了一个标题样式，其他屏内容全部溢出。

**原因**：文本样式的 `lineHeight` 存的是 `unit: 'PIXELS'` 的绝对值（如 120px），不是百分比。

**修复**：

1. 统一改成 `{ unit: 'PERCENT', value: … }`。
2. 样式是全局的，改一次全站生效；改完逐屏核对 `contentBottom`。

### 22. 删错节点（凭名字猜容器）

**症状**：想改 20×20 的复选框，结果删掉了 364 宽的整行。

**原因**：只根据“图标节点”去取 `parent`，没有核对父节点的名称与尺寸。

**修复**：

1. 删除/替换前先 dump 父链：`name`、宽高、`layoutMode`。
2. **宽高与预期不符就停手**——名字不可信，尺寸可信。
3. 先 `insertChild` 新节点，再 `remove()` 旧节点。
4. 误删后不要凭记忆重画：`clone()` 同构兄弟节点、改文案、插回原 index，并核对父容器总高。

### 23. 跨调用节点丢失 / 页面顶层出现孤立 Frame

**症状**：上一轮返回的 ID 下一轮找不到；画布上多出一个空 Frame。

**原因**：`use_figma` 每次调用无状态，页面上下文重置到第一页；跨调用 `appendChild` 移动节点会静默失败。

**修复**：

1. ID 用字符串字面量传回，不依赖变量或选中状态。
2. 在最终父节点里直接创建，不要先建在页面顶层再搬。
3. 每次写操作收尾扫描页面顶层，清理孤立节点并返回其 ID。

### 24. 截图放大无效 / 本地裁图报 `No module named 'PIL'`

**症状**：`maxDimension: 1600` 仍返回 412×892；本地裁剪时 PIL 找不到。

**原因**：

- `maxDimension` 只缩小不放大，不会超过节点原始尺寸。
- Windows 上用 `python -I` 会跳过用户 site-packages，PIL 不可见。

**修复**：

```bash
PYTHONUTF8=1 python -c "
from PIL import Image
im = Image.open('screen.png')
im.crop((40,412,180,462)).resize((140*8,50*8), Image.NEAREST).save('crop8.png')
"
```

不要加 `-I`；只要节点原始尺寸足够，就本地裁剪 + `NEAREST` 放大看像素细节。

### 25. `node.query()` 报 `Invalid selector: unexpected character '/' at position N`

**症状**：`page.query('FRAME[name=IconButton/arrow-left]')` 直接抛错，脚本整段不执行。

**原因**：`query()` 是类 CSS 选择器，未加引号的 name 里的 `/`、空格等字符会被当成语法。而 Figma 文件里 `IconButton/arrow-left`、`Card/Stat` 这类命名非常常见。

**修复**：

1. 名字不是纯标识符时，用断言式查找：

```js
const hits = page.findAll(n => n.type === 'FRAME' && n.name === 'IconButton/arrow-left');
```

2. 先按 `type` 缩小范围，再比名字，比全树 query 更便宜。
3. `query()` 只留给简单名字（如 `TEXT[name=Title]`）。

### 26. 遍历报 `Symbol.iterator` / `findAll: no such property on TEXT node`

**症状**：`for (const c of node.children)` 或 `node.findAll(...)` 在 RECTANGLE / TEXT / VECTOR 上抛错。

**原因**：只有容器类节点（PAGE / FRAME / GROUP / COMPONENT / INSTANCE / SECTION）才有 `children` 和 `findAll`；叶子节点没有，代码却按结构假设去读。

**修复**：

```js
const walk = n => { if ('children' in n) for (const c of n.children) walk(c); };
if ('findAll' in node) { /* 子树搜索 */ }
```

- 全树搜索用 `page.findAll`，不要假设任意节点都能递归。
- 需要按类型过滤时用 `findAllWithCriteria({ types: [...] })`，比 `findAll(n => …)` 更省。

### 27. 截图下载后 Read 报图片损坏 / 不支持

**症状**：`get_screenshot` 成功，Read 报 unsupported image；改扩展名或转格式也无效，整轮会话卡住。

**原因**：下载不完整，或文件根本不是 PNG；接口只认真实 png/jpg/webp/gif 内容，扩展名不参与判断。

**修复**：先验魔数和 IHDR 尺寸，再交给 Read：

```bash
curl -f -L -o shot.png "<image_url>"
python -c "import struct; d=open('shot.png','rb').read(33); assert d[:8]==b'\x89PNG\r\n\x1a\n'; print(*struct.unpack('>II', d[16:24]))"
```

校验失败就重新截图，不要改名硬传。

### 28. 重建图标/圆环后描边粗细不对

**症状**：按截图重画进度环或箭头，线宽比原稿粗/细，看起来发糊或发虚。

**原因**：环形用 `arcData.innerRadius` 表示内半径相对外半径的比例，目测取值必偏。

**修复**：

1. 先找原节点，`strokeWeight` 就是事实值。
2. 新环按公式算：`innerRadius = 1 - stroke / (size / 2)`。
3. 能 `clone()` 原节点改色，就不要重画。

### 29. 连线/装饰把 auto-layout 卡片撑高或被重排

**症状**：往卡片里加的连接线把卡片高度撑开，或被排到文字下方。

**原因**：auto-layout 里的普通子节点参与布局；纯装饰元素必须绝对定位。

**修复**：

1. 先进父节点：`parent.insertChild(0, node)`。
2. 再设 `node.layoutPositioning = 'ABSOLUTE'`，然后设 `x/y`（相对父容器左上角）。
3. 插在 index 0，让装饰线位于内容下层。

## 排查表

| 症状 | 先查 | 再查 |
| --- | --- | --- |
| 变量为空 | nodeId 是不是 page | 换 frame/component |
| 节点查不到 | node-id 是否 `0:1` | branchKey 是否用对 |
| 结果超限 | 是否整页调用 | 按 frame 分层 |
| 截图失败 | 路径是否绝对 | 节点是否太大 |
| 样式缺失 | 是否只读了 metadata | 补 variable defs / design context |
| 连接失败 | 哪个 server | 换 plugin server |
| 解析报编码错 | 是否 UTF-8 | 设置 `PYTHONUTF8=1` |
| 设计对不上代码 | 是否直接复制参考代码 | 按项目 Token/组件重写 |
| 写入报 unloaded font | 是否先 loadFontAsync | 改样式也要加载全部字重 |
| 节点变纯黑 | 是否接住 paint 返回值 | base color 是否传了真实 hex |
| 图标被压扁/溢出 | 是否设了 FIXED sizing | 是否在 layoutMode 之后 resize |
| 改坏/删错节点 | 删前是否核对父链宽高 | 是否先建后删 |
| 截图细节看不清 | maxDimension 是否只缩小 | 本地裁剪 + NEAREST 放大 |
| `Invalid selector` | 名字里是否有 `/` 等符号 | 改用 `findAll` 断言 |
| 遍历报 `Symbol.iterator` / `findAll` 不存在 | 节点是不是叶子 | 先守卫 `'children' in` |
| Read 报图片损坏 | 文件魔数是否 PNG | 重新截图，不要改扩展名 |
| 连线撑高卡片 | 是否设了绝对定位 | `layoutPositioning='ABSOLUTE'` |
| 重建图标粗细不对 | 是否 clone 原节点 | `innerRadius = 1 - stroke/rOuter` |
