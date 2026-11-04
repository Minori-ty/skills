---
name: figma-skill
description: 通过 Figma MCP 读取、检查、截图、导出，以及用 use_figma 写入/修改 Figma 文件的工作流与避坑指南。只要任务涉及 Figma 链接、设计稿读取、变量/组件尺寸提取、设计评审、设计转代码、生成或修改 Figma 画板，或 Figma MCP 出现返回空、超时、结果超限、连接失败，就使用本 skill。先定位再读取，用最小节点拿到事实，写入前先断言节点身份，不靠记忆猜设计。
---

# Figma MCP 操作手册

这套流程解决的不是“怎么点 Figma”，而是 **怎么用最少的调用拿到可信的设计事实**。Figma 文件很大，MCP 返回也很重；范围一放大，token、超时和误读会同时出现。

## 适用时机

- 用户给出 Figma 链接，要求总结设计规范、Token、组件尺寸、页面结构
- 要评审设计稿、检查对比度/触控目标/暗色覆盖
- 要把设计稿落到代码，需要真实节点结构和样式
- 要在 Figma 里新建/修改画板、组件、状态（`use_figma`）
- Figma MCP 返回 `nothing selected`、空结果、超时、结果超限、连接失败
- 不确定某个值是不是变量，或变量名和代码 Token 对不上

## 五条原则

1. **先定位，再读取**：页面节点只用来列目录；不要对整页查变量、截图或拉设计上下文。
2. **最小节点**：一次只读一个 frame/component；能读组件就不读页面。
3. **三源交叉**：变量表 + 组件 metadata + 截图。任何一源都不完整：变量缺圆角/阴影/状态，metadata 缺样式值，截图缺精确数值。
4. **失败先降级**：超时换小节点，结果超限落盘解析，工具连不上换 server；不要硬等或反复重试同一个调用。
5. **事实与推断分开**：Figma 里没有的值，明确标“推断/建议”，不要写成规范。

## 标准流程

### 0. 建立会话

先解析 URL，拿到 `fileKey` 和 `nodeId`：

```bash
python scripts/figma_url.py "<figma-url>"
```

然后调用 `create_session(fileKey, task)`。同一个任务复用返回的 `sessionId`；换文件再建新会话。新建文件先 `create_new_file`，再 `create_session`。

### 1. 列目录，不读整页

对目标页面节点调 `get_metadata`，只取顶层 frame/component 的 `id`、`name`、`type` 和 bounds。

- 页面级 metadata 可能十几万字符，足以触发工具结果上限。
- 如果结果被落盘，用 `scripts/parse_metadata.py` 解析，不要用 `jq`（环境里经常没有）。
- 拿到 frame ID 后，后续只对这些 ID 操作。

### 2. 查变量

对具体 frame/component 调 `get_variable_defs`，不要传页面节点。

- 页面节点会返回 `nothing selected`。
- 变量通常覆盖颜色和字体；圆角、阴影、间距、状态色不一定在变量里。
- 把变量名映射到代码 Token 时，单独列一张表；不要假设命名一致。

### 3. 补结构尺寸

对关键组件节点再调一次 `get_metadata`，读 `absoluteBoundingBox`、子节点尺寸和间距。

- 变量给“值”，metadata 给“哪些节点用了这个值”。
- 圆角、阴影、点击区、图标尺寸经常只能从组件节点或 `get_design_context` 得到。
- 需要实现代码时，先加载 `figma-design-to-code` skill，再调 `get_design_context`；它的输出是参考，不是最终代码。

### 4. 截图验证

对单个 frame 调 `get_screenshot`：

- 用绝对路径保存，调用后 `ls` 确认文件真的在预期位置。
- 整页截图信息密度低，单帧截图才有用。
- 大画板容易超时；降低 scale、换更小的节点，或转后台后及时停止。
- 截图只用来核对视觉层级和状态，不用来量精确尺寸。

取回后**先验格式再 Read**。接口只认真实的 png/jpg/webp/gif，改扩展名无效：

```bash
curl -f -L -o shot.png "<image_url>"
python -c "import struct; d=open('shot.png','rb').read(33); assert d[:8]==b'\x89PNG\r\n\x1a\n'; print(*struct.unpack('>II', d[16:24]))"
```

魔数或尺寸校验失败就重新截图，不要把可疑文件交给 Read（会直接中断整轮会话）。

### 5. 输出

设计规范、评审、交接文档都按固定结构写，并附上证据来源（节点 ID / 变量名 / 实测对比度）。模板见 [references/workflows.md](references/workflows.md)。

## 写入与修改（use_figma）

读操作只影响结论，写操作会改画布，而且 **Plugin API 没有 undo**。完整规则见 [references/write-ops.md](references/write-ops.md)。

1. **先 dump 再改**：返回目标节点的父链、`name`、宽高、`layoutMode`。**宽高和预期不符就是拿错了节点**——名字不可信，尺寸可信。
2. **先建后删**：新节点先 `insertChild(index, …)`，确认无误再 `remove()` 旧节点。删除不可撤销。
3. **一次调用只切一次页面**；节点 ID 以字符串字面量回传，不依赖跨调用状态。
4. **字体先加载**：任何文本或文本样式修改前 `await figma.loadFontAsync(...)`，否则报 “unloaded font”。
5. **尺寸显式化**：设置 `layoutMode` 会把 sizing 重置为 AUTO，之后必须 `*AxisSizingMode='FIXED'` + `resize(w,h)`；子节点用 `layoutSizing*='FIXED'`。
6. **变量绑定接返回值**：`setBoundVariableForPaint` 返回新 paint 且保留传入的 base color，base color 必须传真实 hex。
7. **SVG 根节点要清 fill**：`createNodeFromSvg` 的根自带 `#FFFFFF` 填充，置空后再绑定描边色。
8. **先数值后截图**：返回 `contentBottom`、黑填充数、白底 SVG 数、孤立节点数；通过后再截图核对。
9. **装饰元素绝对定位**：连接线、覆盖层先 `insertChild`，再 `layoutPositioning='ABSOLUTE'` 并设 `x/y`；否则会被 auto-layout 排进流、撑高容器。

### 安全脚本模板

查找和遍历是最常报错的两处：Figma 里大量节点名带 `/`（如 `IconButton/arrow-left`），而 `query()` 是类 CSS 选择器，解析不了这类名字；叶子节点也没有 `children` / `findAll`。

```js
// 1) 按名字找：名字含 / 等字符时 query() 会抛 Invalid selector
const hits = page.findAll(n => n.type === 'FRAME' && n.name === 'IconButton/arrow-left');

// 2) 遍历：先守卫能力，叶子节点没有 children
const walk = n => {
  if ('children' in n) for (const c of n.children) walk(c);
};

// 3) 在 auto-layout 卡片里加一条不参与布局的连线（先插入，再绝对定位）
const line = figma.createRectangle();
line.resize(2, 24);
line.cornerRadius = 1;
line.fills = [figma.variables.setBoundVariableForPaint(
  { type: 'SOLID', color: { r: 0.02, g: 0.59, b: 0.41 } }, 'color', accentVar)];
card.insertChild(0, line);      // 必须先进父节点
line.layoutPositioning = 'ABSOLUTE';
line.x = 28; line.y = 49;       // 相对父容器左上角，不占 auto-layout 空间
```

## 工具选择

| 需要 | 工具 | 关键约束 |
|---|---|---|
| 建立文件会话 | `create_session` | 文件工具之前必须调用；复用 sessionId |
| 列 frame/component | `get_metadata` | 页面级只列目录；大结果会落盘 |
| 查颜色/字体变量 | `get_variable_defs` | 传具体 frame/component，不传 page |
| 读实现上下文 | `get_design_context` | 先加载 `figma-design-to-code` skill |
| 看视觉效果 | `get_screenshot` | 单节点、绝对路径、注意超时 |
| 找工作区组件/变量 | `search_design_system` | 建会话之后调用 |
| 查组件库 | `get_libraries` | 建会话之后调用 |
| 导出图片/SVG | `download_assets` | 传节点 ID；检查输出目录 |
| 读 FigJam | `get_figjam` | `/board/` 链接 |
| 写入/修改 Figma | `use_figma` | 先加载 `figma-use` skill；按 write-ops.md 的写前/写后规则执行 |
| 新建设计文件 | `create_new_file` → `create_session` | 先建文件再建会话 |

完整的参数、返回形态和 URL 规则见 [references/tools.md](references/tools.md)。

## 常见坑（先看这 10 条）

1. **页面节点查变量返回 `nothing selected`** → 换具体 frame/component ID。
2. **整页 `get_metadata` 超限** → 页面级只列目录，按 frame 逐个读。
3. **metadata 没有颜色/字号** → 用 `get_variable_defs` 补值，用组件 metadata 补尺寸。
4. **截图落到意外目录** → 用绝对路径；`cd` 到工作目录外不会保持。
5. **大截图 120s 超时** → 换小节点/低 scale；超时后停止，不要反复重试。
6. **URL 的 `node-id=0-1` 不能直接用** → 转成 `0:1`；branch URL 用 branchKey 当 fileKey。
7. **结果太长被落盘** → 用 `scripts/parse_metadata.py` + Python UTF-8 解析，不依赖 `jq`。
8. **`figma-desktop` 连不上** → 先确认 server 状态；plugin 版 Figma MCP 可能仍然可用。
9. **`query()` 报 `Invalid selector`** → 节点名里有 `/`（`IconButton/arrow-left`）；改用 `findAll(n => n.name === '…')`。
10. **遍历报 `Symbol.iterator` 或 `findAll` 不存在** → 对叶子节点（RECTANGLE/TEXT）取 `.children`；先守卫 `'children' in node` / `'findAll' in node`。

写入层最容易踩的 7 条：

1. **报错说字体，其实在改样式** → 改 text style 的 `lineHeight` 也要先 `loadFontAsync`。
2. **节点变纯黑** → `setBoundVariableForPaint` 没接返回值，或 base color 传了黑色。
3. **图标被压扁/文字溢出** → `layoutMode` 重置 sizing；显式 `FIXED` + `resize`。
4. **删错节点** → 只看名字不看尺寸；删前必须核对父链宽高。
5. **截图放大无效** → `maxDimension` 只缩小不放大，细节靠本地裁剪 + 放大。
6. **连线/装饰撑高卡片** → 忘了 `layoutPositioning='ABSOLUTE'`；先插入再设绝对定位。
7. **重建的图标粗细不对** → 环形用 `arcData.innerRadius`，按 `1 - stroke/rOuter` 算，别目测。

展开的原因和修复见 [references/pitfalls.md](references/pitfalls.md) 与 [references/write-ops.md](references/write-ops.md)。

## 失败降级顺序

```text
页面级 metadata 超限
  → 只取顶层 frame 列表
  → 对单个 frame 调 metadata
  → 仍超限：只读目标子树 / 让用户指定节点
```

```text
get_variable_defs 返回空
  → 确认 nodeId 不是 page
  → 换 frame / component 节点
  → 仍空：从 metadata + 截图推断，并标注“未绑定变量”
```

```text
截图超时
  → 降低 scale
  → 换更小节点
  → 转后台；超时即停止
  → 用已有截图 + 变量继续，不阻塞分析
```

```text
MCP 连接失败
  → 检查是 figma-desktop 还是 plugin server
  → 换可用 server
  → 仍不可用：明确告知用户，不要假装读到了文件
```

## 文件健康检查

拿到设计文件后，除了提取规范，还要快速检查这些“文件本身的坑”：

- **暗色覆盖**：浅色/暗色画板数量是否对等；浮层、空态、错误态是否有暗色稿。
- **交互状态**：disabled / focus / pressed / scrim 是否有 Token；没有就标注缺口。
- **触控目标**：Android 视觉尺寸可小于 48dp，但点击区必须补到 48dp。
- **对比度**：正文 4.5:1，大字号 3:1，控件边界/焦点 3:1；必须实测，不靠目测。
- **组件尺寸**：Chip、关闭按钮、输入框等是否低于平台最小触控尺寸。
- **变量完整性**：哪些值没有绑定变量；哪些是硬编码。
- **响应式**：是否只有单一断点；横屏/平板/大字号是否有规则。

## 输出模板

### 设计规范

```markdown
# <页面/系统> 设计规范
## 事实来源
- Figma fileKey / nodeId
- 读取时间
## 画布与栅格
## 颜色（含明暗）
## 字体与字阶
## 间距 / 圆角 / 阴影
## 组件尺寸
## 页面模式
## 状态
## 已知缺口
```

### 评审

```markdown
| 严重度 | 问题 | 当前值 | 规范值 | 理由 |
|---|---|---|---|---|
```

严重度用 **阻断 / 重要 / 建议**；每条必须有当前值和规范值，不能只写“偏低”。

### 交接

- Token 映射表（Figma 变量 → 代码 Token）
- 组件映射表（Figma 组件 → 代码组件）
- 资源清单（图标、图片、字体）
- 未决问题（变量缺失、状态缺失、断点缺失）

## 脚本

| 脚本 | 用途 |
|---|---|
| [scripts/figma_url.py](scripts/figma_url.py) | 解析 Figma URL，输出 fileKey / nodeId / branchKey / fileType |
| [scripts/parse_metadata.py](scripts/parse_metadata.py) | 解析被落盘的 metadata 结果，打印节点树 |

脚本只用 Python 标准库；Windows 下用 `python`，并设置 `PYTHONUTF8=1` 避免 GBK 解码错误。

## 自检

交付前确认：

- [ ] 每个结论都能追到节点 ID、变量名或实测值
- [ ] 没有对页面节点查变量
- [ ] 没有用整页截图代替单帧截图
- [ ] 没有把推断写成 Figma 事实
- [ ] 已标注变量缺失、暗色缺失、状态缺失
- [ ] 对比度是算出来的，不是目测的
- [ ] 截图/导出文件路径已确认存在
- [ ] 写入前已 dump 目标父链，宽高与预期一致
- [ ] 已返回 createdNodeIds / mutatedNodeIds 与关键尺寸
- [ ] 黑填充、白底 SVG 根、未绑定色已归零；页面顶层无孤立节点
- [ ] 节点查找/遍历有守卫：名字含 `/` 不用 `query`，取 `.children` 前判断 `'children' in node`
- [ ] 装饰/连线用 `layoutPositioning='ABSOLUTE'`，不参与 auto-layout
- [ ] 截图先验 PNG 魔数与尺寸，再交给 Read

## 参考资料

- [tools.md](references/tools.md) — 工具参数、返回形态、URL 与节点规则
- [workflows.md](references/workflows.md) — 设计规范提取、评审、设计转代码的完整步骤
- [pitfalls.md](references/pitfalls.md) — 症状 → 原因 → 修复
- [write-ops.md](references/write-ops.md) — use_figma 写入安全流程、报错表、写后验收、误删恢复
