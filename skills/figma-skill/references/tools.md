# Figma MCP 工具参考

## 目录

- [会话与 URL](#会话与-url)
- [工具选择](#工具选择)
- [节点规则](#节点规则)
- [返回结果的处理](#返回结果的处理)
- [各工具备注](#各工具备注)
- [Figma 专用 skills](#figma-专用-skills)

## 会话与 URL

### 先建会话

文件工具之前先调用：

```text
create_session(fileKey, task)
```

- `task` 用一句短描述，例如“读取 CRM Pro 设计规范”。
- 同一个任务复用返回的 `sessionId`。
- 换文件时新建会话；新文件先 `create_new_file`，再 `create_session`。
- 读-only 任务也要建会话，不要因为“只是读”就跳过。

### URL 解析

| URL 形态 | fileKey | fileType |
|---|---|---|
| `figma.com/design/:fileKey/:name?node-id=:nodeId` | `:fileKey` | design |
| `figma.com/design/:fileKey/branch/:branchKey/:name` | `:branchKey` | design（branch） |
| `figma.com/file/:fileKey/:name` | `:fileKey` | design（legacy） |
| `figma.com/board/:fileKey/:name` | `:fileKey` | figjam |
| `figma.com/slides/:fileKey/:name` | `:fileKey` | slides |
| `figma.com/make/:makeFileKey/:name` | `:makeFileKey` | make |

节点 ID：

- URL 里是 `node-id=0-1`，MCP 参数要 `0:1`。
- URL 编码可能是 `0%3A1`，先 decode。
- branch URL 用 `branchKey` 当 `fileKey`，不要用原 fileKey。
- 没有 `node-id` 时，先对页面根节点或文件根节点列目录。

用脚本：

```bash
python scripts/figma_url.py "<url>"
```

输出：

```json
{
  "fileKey": "VHr...",
  "nodeId": "0:1",
  "branchKey": null,
  "fileType": "design"
}
```

## 工具选择

| 任务 | 首选 | 不要用 |
|---|---|---|
| 列画板/组件 | `get_metadata`（页面节点，只取顶层） | `get_screenshot` 整页 |
| 查 Token | `get_variable_defs`（frame/component） | `get_variable_defs`（page） |
| 看结构 + 样式 | `get_design_context` | 只靠 metadata |
| 看视觉 | `get_screenshot`（单节点） | 整页截图 |
| 找工作区组件 | `search_design_system` | 直接猜组件名 |
| 查库 | `get_libraries` | — |
| 导出资源 | `download_assets` | 截图代替 SVG |
| 读 FigJam | `get_figjam` | `get_design_context` |
| 写入 Figma | `use_figma` | 手改 JSON |

## 节点规则

### page ≠ frame ≠ component

- **page**：只适合列顶层画板；查变量会返回 `nothing selected`。
- **frame**：一个页面/画板；适合 metadata、变量、截图。
- **component**：一个组件；适合精确尺寸、变体、变量绑定。
- **instance**：页面里的组件实例；尺寸可能被覆盖，查组件本体更可靠。

### 最小范围

```text
页面根节点
  → 目标 frame
  → 目标区块
  → 目标 component
```

每往下一层，返回量都会显著减少。不要从页面根节点直接拉 `get_design_context`。

### 节点 ID

- 用冒号格式：`0:1`、`12:345`。
- 不要用 URL 的连字符格式：`0-1`。
- 实例节点可能带 `I` 前缀；按 MCP 返回的原样传。

## 返回结果的处理

### 结果超限

`get_metadata` 对整页调用时可能返回十几万字符，超过工具结果上限，结果会被保存到 `tool-results/` 下的临时文件。

处理：

```bash
PYTHONUTF8=1 python scripts/parse_metadata.py "<saved-result-file>" --max-depth 3
```

- Windows 默认编码可能是 GBK；读文件时显式 `encoding="utf-8"`。
- 不要假设 `jq` 可用；环境里经常没有。
- 如果文件里有多个 JSON 条目，脚本会逐个尝试解析。

### 返回文本 vs JSON

MCP 结果可能是：

- 直接 JSON
- `{"content":[{"type":"text","text":"..."}]}`
- `[{"type":"text","text":"..."}]`
- XML/文本形式的节点树

`scripts/parse_metadata.py` 会依次尝试 JSON、MCP content 包装、XML、正则兜底。

### 不要从 metadata 推样式

`get_metadata` 主要给结构：`id`、`name`、`type`、`absoluteBoundingBox`、`children`。颜色、字体、圆角、阴影、变量绑定要去 `get_variable_defs` 或 `get_design_context` 拿。

## 各工具备注

### `create_session`

- 必填 `fileKey`。
- 返回 `sessionId`；后续文件工具带上。
- 任务描述写清楚，便于服务端复用上下文。

### `get_metadata`

- 传 `nodeId`。
- 页面级只取顶层；大页面会超限。
- 适合：列画板、列组件、读 bounds、找子节点 ID。
- 不适合：读颜色/字体/变量。

### `get_variable_defs`

- 传具体 frame/component 的 `nodeId`。
- 页面节点返回 `nothing selected`。
- 返回变量名和值；不一定覆盖圆角、阴影、间距、状态色。
- 变量名与代码 Token 名可能不同，单独做映射。

### `get_design_context`

- 先加载 `figma-design-to-code` skill。
- 输出是“参考实现”，不是最终代码；要按项目组件和 Token 适配。
- 适合：设计转代码、读样式细节、看响应式提示。
- 不要对整页调用；选目标区块。

### `get_screenshot`

- 传单节点 `nodeId`。
- 保存路径用绝对路径；调用后确认文件存在。
- 大画板容易超时；降 scale、换小节点，或后台执行。
- 整页截图只用于总览，不用于量尺寸。

### `search_design_system`

- 建会话后调用。
- 用于找工作区已有组件、变量、样式；先搜再建新组件。
- 搜不到再考虑新建，避免重复造组件。

### `get_libraries`

- 建会话后调用。
- 查文件启用了哪些库；组件来源不清楚时先看库。

### `download_assets`

- 传节点 ID 和目标格式。
- 导出后检查文件名、尺寸、目录；不要假设路径。
- 图标优先 SVG，图片按项目要求 WebP/PNG。

### `get_figjam`

- 仅用于 `/board/` 链接。
- 设计文件不要用它。

### `use_figma`

- 先加载 `figma-use` skill。
- 写操作前确认目标页面/节点，避免覆盖用户内容。
- 生成/修改后用 `get_screenshot` 或 metadata 验证结果。

### `create_new_file`

- 先建文件，拿到 fileKey，再 `create_session`。
- 不要把新文件内容写到现有文件里。

## Figma 专用 skills

这些 skill 是工具的前置条件，不要跳过：

| 操作 | 先加载 |
|---|---|
| `use_figma` | `figma-use` |
| `get_design_context`（设计转代码） | `figma-design-to-code` |
| 把页面生成到 Figma | `figma-generate-design` |
| 在 Figma 建设计系统 | `figma-generate-library` |
| Code Connect 映射 | `figma-code-connect` |
| FigJam 操作 | `figma-use-figjam` |
| 生成图表 | `figma-generate-diagram` |

## 环境检查

- `figma-desktop` server 可能 `ECONNREFUSED`；plugin 版 Figma MCP 可能仍然可用。
- 工具在列表里但不可调用时，先用 ToolSearch 加载 schema。
- 连接失败时明确告诉用户是哪个 server 失败，不要假装读到了文件。
