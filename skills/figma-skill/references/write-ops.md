# Figma 写入操作（use_figma）避坑

读操作失败只是拿不到数据；写操作失败会改坏画布，而且 **Plugin API 没有 undo**。
这份文档只解决一件事：让每次写入都可断言、可回退、可验收。

## 为什么写操作用起来总是报错

| 根因 | 表现 |
| --- | --- |
| 隐式前置条件多（字体、页面上下文、sizing） | 报错信息不指向真正原因，比如改个行高报“字体未加载” |
| 对象假设错误不会报错 | 拿错节点照样执行，静默改坏结构 |
| 调用之间无状态 | 上一轮的 ID、布局、选中上下文全部失效 |
| 尺寸靠 auto-layout 推断 | 一个 `layoutMode` 赋值就把显式尺寸重置成 AUTO |

## 写前三件事

### 1. 先 dump 目标父链，再动手

要改、要删、要替换的节点，先返回它的父链、`name`、宽高、`layoutMode`：

```js
let n = await figma.getNodeByIdAsync('19:134');
const chain = [];
while (n && n.type !== 'PAGE' && chain.length < 5) {
  chain.push({ name: n.name, type: n.type, w: Math.round(n.width), h: Math.round(n.height),
               layout: 'layoutMode' in n ? n.layoutMode : null });
  n = n.parent;
}
return chain;
```

**断言规则：宽高不对就是拿错了节点。** 20×20 的复选框不可能有一个 364 宽的父节点；出现这种组合先停手。
节点名不可信，尺寸和结构可信。

### 2. 先建后删，不要先删后建

```js
const parent = oldNode.parent;
const index = parent.children.indexOf(oldNode);
parent.insertChild(index, newNode);   // 先插
oldNode.remove();                     // 后删
```

- 删除不可撤销，误删只能靠克隆同构兄弟节点重建（见文末）。
- 新节点在最终父节点里创建，不要先建在页面顶层再 `appendChild` 搬走。

### 3. 一次调用只做一组能复述的改动

- 一次调用只 `setCurrentPageAsync` 一次；多页面拆成多个并行调用。
- 返回 `createdNodeIds`、`mutatedNodeIds` 和关键尺寸；下一轮用**字符串字面量**引用这些 ID。
- 占位 helper（例如“先创建一个空实例稍后填充”）要先验证返回的节点非空、子节点数量正确，再继续。

## 高频报错表

| 报错 / 症状 | 真正原因 | 修复 |
| --- | --- | --- |
| `Cannot write to node with unloaded font "…"` | 改文本或文本样式（包括 `lineHeight`）前没加载字体 | 先 `await figma.loadFontAsync({family, style})`；改样式前加载该样式用到的每个字重 |
| `Setting figma.currentPage is not supported` | 用了同步 setter | `await figma.setCurrentPageAsync(page)`；每次调用上下文回到首页 |
| 节点渲染成纯黑 / 变量不生效 | `setBoundVariableForPaint` 返回**新** paint，且保留传入的 base color | 接住返回值；base color 传真实 hex，不要传 `{0,0,0}` |
| 图标底变竖条 / 被压扁 / 文字溢出 | 设置 `layoutMode` 会把 sizing 重置为 AUTO；子节点还会被父 auto-layout 拉伸 | 先 `primaryAxisSizingMode/counterAxisSizingMode='FIXED'` 再 `resize(w,h)`；子节点设 `layoutSizingHorizontal/Vertical='FIXED'` |
| `Expected 'FIXED' \| 'AUTO', received 'FILL'` | 两套 enum 混用 | 子节点用 `layoutSizing*`（FIXED/HUG/FILL），容器自身用 `*AxisSizingMode`（FIXED/AUTO） |
| 图标背后多出白色方块 | `createNodeFromSvg` 的根是 FRAME，自带 `#FFFFFF` fill | `svgRoot.fills = []`；矢量描边重新绑定变量 |
| 改完字阶后整页错位 | 文本样式的 `lineHeight` 是 `unit:'PIXELS'` 的绝对值 | 统一改 `{unit:'PERCENT', value:…}`；这是全局样式，改一次全站生效 |
| 改组件后实例没变 | 实例上有 override | 先改组件，再检查实例的 `fills/strokes.boundVariables` 是否被覆盖 |
| `figma.notify is not implemented` | 插件环境不支持 | 不用；通过 `return` 回传结果 |
| 上一轮的节点 ID 找不到 | 调用间无状态 + 页面上下文重置 | ID 用字面量传；不要依赖上一轮的变量或选中状态 |
| 画布上出现孤立 Frame | 先建了占位/包容器但重挂失败 | 建容器时就在最终位置创建；收尾扫描页面顶层节点 |
| `Invalid selector: unexpected character '/' at position N` | `query()` 是类 CSS 选择器，节点名里的 `/` 等字符被当成语法（如 `IconButton/arrow-left`） | 改用 `page.findAll(n => n.type === 'FRAME' && n.name === '…')`；`query()` 只用于简单名字 |
| `Cannot read property 'Symbol.iterator' of undefined` / `findAll: no such property on TEXT node` | 对叶子节点（RECTANGLE/TEXT/VECTOR）取 `.children` 或调 `.findAll` | 先守卫 `'children' in node` / `'findAll' in node`；全树搜索用 `page.findAll` |
| 连线/装饰撑高卡片或被排进流 | 普通子节点参与 auto-layout | `insertChild(0, …)` → `layoutPositioning='ABSOLUTE'` → 设 x/y |
| 重建的图标/圆环描边粗细不对 | 用 `arcData.innerRadius` 目测画环 | 能 clone 原节点就别重画；`innerRadius = 1 - stroke/(size/2)` |

## 写后验收：先数值，后截图

每次写入后 `return` 这些可断言的值，而不是“看起来对了”：

```js
return {
  createdNodeIds, mutatedNodeIds,
  contentBottom,                    // 内容底边，和导航/版本号 y 对比判断是否溢出
  blackFills,                       // 纯黑填充数，应为 0
  strayWhiteSvgRoots,               // SVG 根节点残留白底数，应为 0
  unboundPaints,                    // 未绑定变量的颜色数
  orphanTopLevelNodes,              // 页面顶层的意外节点
};
```

截图放在数值通过之后。注意 `get_screenshot` 的 `maxDimension` **只缩小不放大**：
412×892 的节点即使传 1600 也只返回 412×892。要看细节就本地裁剪后放大：

```bash
PYTHONUTF8=1 python -c "
from PIL import Image
im = Image.open('screen.png')
im.crop((40,412,180,462)).resize((140*8,50*8), Image.NEAREST).save('crop8.png')
"
```

Windows 上用 `python`，不要加 `-I`（会跳过用户 site-packages，PIL 直接找不到）。

## 误删 / 改错结构后的恢复

1. 不要凭记忆重画；先 dump 同层级兄弟节点的完整结构（尺寸、padding、gap、文字样式、图标）。
2. `clone()` 兄弟节点，改文案/图标/语义色，插回原 index。
3. 核对父容器总高与改前一致（例如卡片 107 → 误删后 75 → 恢复后 107）。
4. 交付时如实说明“重建了该行”，不要声称是原样恢复。

## 写入自检

- [ ] 改/删前已 dump 父链，宽高与预期一致
- [ ] 新节点先插入、旧节点后删除
- [ ] 每个调用只切一次页面，ID 以字面量回传
- [ ] 文本与文本样式修改前已加载字体
- [ ] 尺寸用 FIXED + resize 显式指定
- [ ] 变量 paint 接住返回值，base color 用真实 hex
- [ ] SVG 根节点 fill 已清空
- [ ] 返回了关键尺寸，黑填充/白底/未绑定色为 0
- [ ] 节点查找没在带 `/` 的名字上用 `query()`；取 `.children` 前有 `'children' in`
- [ ] 装饰性节点（连线、覆盖层）用 `layoutPositioning='ABSOLUTE'`
