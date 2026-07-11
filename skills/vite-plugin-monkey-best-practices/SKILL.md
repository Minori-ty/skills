---
name: vite-plugin-monkey-best-practices
description: >-
  Comprehensive guidance for building userscripts with vite-plugin-monkey. Use when
  scaffolding, configuring, or debugging userscript projects — especially for GM_api
  usage, CDN externalization, Web Workers, CSP issues, React externalization, and the
  non-blocking download pipeline architecture. Covers Tampermonkey, Violentmonkey,
  Greasemonkey, and ScriptCat.
---

# vite-plugin-monkey Best Practices

This skill provides comprehensive guidance for developing userscripts using
[vite-plugin-monkey](https://github.com/lisonge/vite-plugin-monkey) — a Vite plugin that
bundles your code into `.user.js` files for userscript managers like Tampermonkey,
Violentmonkey, Greasemonkey, and ScriptCat.

## Core Mental Model

vite-plugin-monkey works in two modes:

- **Serve**: Injects your code as a script tag into target pages, with HMR. The dev script
  appears in your userscript manager with a `server:` name prefix by default.
- **Build**: Uses Vite's library mode to produce a self-contained `.user.js` file with an
  auto-generated userscript metadata block (`// ==UserScript== ... // ==/UserScript==`).

The plugin hooks into Rollup's `generateBundle` to transform the ESM output into a format
suitable for userscript managers (IIFE or SystemJS for dynamic imports). This is why it
**must be the last plugin** in the Vite plugins array — it needs the final bundle from all
other plugins.

```
Your source code
  → other Vite plugins (Vue/React/Svelte, auto-import, etc.)
  → Vite library-mode build
  → vite-plugin-monkey (generateBundle: wrap in IIFE/SystemJS, inject userscript header)
  → .user.js output
```

## Project Setup

### Scaffolding a new project

```bash
pnpm create monkey
# or: npm create monkey / yarn create monkey
```

This provides templates for: `empty` / `empty-ts`, `vanilla` / `vanilla-ts`, `vue` /
`vue-ts`, `react` / `react-ts`, `svelte` / `svelte-ts`, `solid` / `solid-ts`.

### Adding to an existing Vite project

```bash
pnpm add -D vite-plugin-monkey
```

### Plugin ordering (critical)

The plugin must be the **last item** in the plugins array. If you use `unplugin-auto-import`,
place it before `monkey()`:

```ts
// vite.config.ts
import { defineConfig } from 'vite';
import monkey from 'vite-plugin-monkey';
import AutoImport from 'unplugin-auto-import/vite';
import { util } from 'vite-plugin-monkey';

export default defineConfig({
  plugins: [
    AutoImport({ imports: [util.unimportPreset] }),  // BEFORE monkey
    monkey({ entry: './src/main.ts' }),               // LAST
  ],
});
```

## Configuration

### Always configure `entry`

The `entry` field is required. Point it at your main userscript entry file:

```ts
monkey({
  entry: './src/main.ts',
  userscript: {
    name: 'My Userscript',
    namespace: 'https://example.com',
    version: '1.0.0',
    match: ['https://*.example.com/*'],
    description: 'Does something useful',
    license: 'MIT',
  },
})
```

### Use `build.metaFileName` for efficient updates

Set `build.metaFileName: true` to generate a separate `.meta.js` file containing only the
userscript header. Point `updateURL` at this small file so userscript managers don't
download the full script on every update check:

```ts
monkey({
  userscript: {
    updateURL: 'https://example.com/my-script.meta.js',
    downloadURL: 'https://example.com/my-script.user.js',
  },
  build: {
    fileName: 'my-script.user.js',
    metaFileName: true,  // generates my-script.meta.js
  },
})
```

### Understand `build.autoGrant`

`autoGrant` defaults to `true`. The plugin analyzes the final bundle to detect which GM_*
APIs are actually called and automatically adds the corresponding `@grant` directives. This
is almost always what you want. Only set it to `false` if you need to manually manage
`@grant` directives in the `userscript.grant` field.

### `server.mountGmApi` — prefer ESM imports instead

Setting `server.mountGmApi: true` mounts GM APIs onto `unsafeWindow`/`globalThis` so you
can use them as global variables. However, this is **not recommended** because:

- No TypeScript type hints without extra configuration
- Pollutes the global scope
- Doesn't work the same way in serve vs build

Prefer ESM imports (see GM_api Usage below). The `mountGmApi` option exists primarily for
compatibility with legacy code.

### Server options

```ts
monkey({
  server: {
    open: true,         // Auto-open install URL in browser (default on Win/Mac)
    prefix: 'server:',  // Name prefix in userscript manager to distinguish dev vs build
    // prefix: false,   // Disable the prefix
    mountGmApi: false,  // Keep false; use ESM imports instead
  },
})
```

During development, the plugin watches for userscript metadata changes and automatically
reopens the install URL. The `server:` prefix (configurable) helps distinguish the dev
script from the built one in your userscript manager's dashboard.

## GM_api Usage Patterns

> **Critical rule**: GM APIs (`GM_xmlhttpRequest`, `GM_setValue`, `GM_cookie`, etc.)
> **do not exist** as bare globals, nor on `window`, nor on `globalThis`. Accessing them
> as `GM_xmlhttpRequest`, `window.GM_xmlhttpRequest`, or `globalThis.GM_xmlhttpRequest`
> will be `undefined` in both dev and build mode. The only valid way to access GM APIs is
> through the configured client alias (default `$`):
>
> ```ts
> // ✅ Correct — import from '$'
> import { GM_xmlhttpRequest, GM_setValue } from '$';
>
> // ❌ Wrong — these are all undefined
> console.log(GM_xmlhttpRequest);        // undefined
> console.log(window.GM_xmlhttpRequest);  // undefined
> console.log(globalThis.GM_xmlhttpRequest); // undefined
> ```
>
> This is a design choice: the plugin injects GM APIs through ESM exports, not globals.
> The only exception is when `server.mountGmApi: true` (not recommended), which mounts
> them to `unsafeWindow` — but even then, prefer ESM imports for type safety and
> consistency between dev and build modes.

### Pattern 1: ESM Import (Recommended)

Import GM APIs from the configured client alias (default `$`):

```ts
// main.ts
import { GM_cookie, GM_setValue, GM_getValue, unsafeWindow, monkeyWindow, GM_addElement } from '$';

GM_addElement(document.body, 'div', { innerHTML: 'hello' });

// monkeyWindow → always the userscript sandbox window
// unsafeWindow → always the host page's window
if (unsafeWindow === window) {
  console.log('Running in host page scope (serve mode, no sandbox)');
} else {
  console.log('Running in userscript sandbox scope');
}
```

For TypeScript, add to your `vite-env.d.ts`:

```ts
/// <reference types="vite-plugin-monkey/client" />
```

If you use a custom `clientAlias`:

```ts
// vite.config.ts
monkey({ clientAlias: '@gm' })
```

```ts
// vite-env.d.ts
declare module '@gm' {
  export * from 'vite-plugin-monkey/dist/client';
}
```

### Pattern 2: unplugin-auto-import (Zero-import convenience)

Use `unplugin-auto-import` with `util.unimportPreset` to use GM APIs without any import
statements:

```ts
// vite.config.ts
import AutoImport from 'unplugin-auto-import/vite';
import monkey, { util } from 'vite-plugin-monkey';

export default defineConfig({
  plugins: [
    AutoImport({ imports: [util.unimportPreset] }),
    monkey({ entry: './src/main.ts' }),
  ],
});
```

```ts
// main.ts — no imports needed
console.log({ GM_cookie, unsafeWindow, monkeyWindow, GM_addElement });
GM_setValue('key', 'value');
```

The auto-import plugin injects the imports at build time, and the monkey plugin detects the
usage for `@grant` generation. This is especially convenient in large codebases.

### Available GM APIs

| Category | APIs |
|---|---|
| cookie | `GM_cookie` (`.list`, `.set`, `.delete`) |
| xmlhttpRequest | `GM_xmlhttpRequest` |
| value | `GM_getValue`, `GM_setValue`, `GM_deleteValue`, `GM_listValues` |
| info | `GM_info` |
| addElement | `GM_addElement` |
| addStyle | `GM_addStyle` |
| download | `GM_download` |
| resource | `GM_getResourceText`, `GM_getResourceURL` |
| log | `GM_log` |
| menu | `GM_registerMenuCommand`, `GM_unregisterMenuCommand` |
| notification | `GM_notification` |
| clipboard | `GM_setClipboard` |
| tab | `GM_openInTab`, `GM_getTabs`, `GM_saveTab` |
| webRequest | `GM_webRequest` |
| context | `monkeyWindow`, `unsafeWindow` |
| GM object | `GM.cookie`, `GM.xmlHttpRequest`, `GM.notification`, etc. |

The `GM.*` dot-notation forms are also detected by `autoGrant`.

## Managing External Dependencies

External dependencies keep your `.user.js` file small and avoid Greasyfork's size limits.

### JavaScript libraries via `externalGlobals`

```ts
import monkey, { cdn, util } from 'vite-plugin-monkey';

monkey({
  build: {
    externalGlobals: {
      // Simple: module-name → global variable (you must manually add @require)
      vue: 'Vue',
      // With auto-generated @require URL:
      pinia: cdn.jsdelivr('Pinia', 'dist/pinia.iife.prod.js'),
      lodash: cdn.unpkg('_', 'lodash.min.js'),
    },
  },
})
```

Available CDN helpers: `cdn.jsdelivr()`, `cdn.unpkg()`, `cdn.cdnjs()`, `cdn.npmmirror()`,
`cdn.zhimg()`, `cdn.elemecdn()`, `cdn.bdstatic()`, `cdn.jsdelivrFastly()`.

> **外部化两条路径**：取决于库是否有浏览器可直接执行的 IIFE/UMD 构建产物。
>
> **路径 A — 有 IIFE/UMD**（如 Vue、React 18、Lodash、Pinia）：使用 `cdn.jsdelivr()` 等 CDN helper 生成 `@require` URL，简单直接。CJS 和 ESM 文件不是浏览器可执行的，无法走这条路径。
>
> **路径 B — 没有 IIFE/UMD**（如 React 19 及其他纯 ESM/CJS 库）：通过 importmap + esm.sh 动态注入 ESM 模块，挂载到 `unsafeWindow`，`externalGlobals` 指向 `unsafeWindow.XXX`。完整方案见 [React 章节](#react)（以 React 19 为示例，但此模式适用于任何没有 IIFE/UMD 的库）。

### CSS/assets via `externalResource`

```ts
monkey({
  build: {
    externalResource: {
      'element-plus/dist/index.css': cdn.jsdelivr(),
      'some-font': {
        resourceName: (pkg) => pkg.importName,
        resourceUrl: (pkg) => `https://unpkg.com/${pkg.name}@${pkg.version}/${pkg.resolveName}`,
        loader: (pkg) => {
          const css = GM_getResourceText(pkg.resourceName);
          GM_addStyle(css);
          return css;
        },
      },
    },
  },
})
```

### CDN function helper pattern

The CDN functions receive `(version, name, importName, resolveName)`. You can use array
form for advanced control:

```ts
externalGlobals: [
  ['vue', cdn.jsdelivr('Vue', 'dist/vue.global.prod.js')],
  ['pinia', cdn.jsdelivr('Pinia', 'dist/pinia.iife.prod.js')],
]
```

## Critical Pitfalls and Solutions

### 1. IIFE/UMD Mix Problem

When a UMD library (e.g., Element Plus) depends on an IIFE library (e.g., Vue), the UMD
library can't find the global variable because `var` declarations in IIFE scripts don't
become properties of `window` in the userscript sandbox scope.

**Solution**: Append a data URL that copies the variable to `window`:

```ts
import monkey, { cdn, util } from 'vite-plugin-monkey';

monkey({
  build: {
    externalGlobals: {
      vue: cdn
        .jsdelivr('Vue', 'dist/vue.global.prod.js')
        .concat(util.dataUrl(';window.Vue=Vue;')),
      'element-plus': cdn.jsdelivr('ElementPlus', 'dist/index.full.min.js'),
    },
  },
})
```

This is a common source of `XXX is not defined` errors at runtime.

### 2. Script Appears Not to Run (No Console Errors)

If your code looks correct and there are no errors in the console, but the script seems to
not be running at all, the most common cause is that the userscript manager extension has
not been granted permission to run userscripts. Each userscript manager has its own
mechanism:

- **Tampermonkey**: Check that the extension is enabled in the browser's extension
  management page, and that "Allow access to file URLs" is enabled if you're testing on
  local files.
- **Violentmonkey**: Click the extension icon and verify it shows as active (not dimmed).
- **ScriptCat**: Check the extension's permissions in the browser settings.

All userscript managers also have a global on/off toggle — look at the extension icon in
the browser toolbar. A dimmed or grayed-out icon usually means the extension is disabled
for the current site or globally.

**Checklist**:
1. Is the extension icon active (colored, not grayed out)?
2. Does the extension have permissions for the target site?
3. In the manager's dashboard, is your script listed and enabled (toggle switch on)?
4. Does your script's `@match` pattern actually match the current page URL?

### 3. CSP (Content Security Policy) During Development — Some Sites Work, Some Don't

In `vite serve` mode, the dev server injects a script tag from `http://127.0.0.1:5173` into
the target page. Many websites enforce a strict Content Security Policy that blocks
cross-origin scripts. This manifests in two common error patterns, each with a different
root cause and solution.

**Error pattern 1 — CSP `script-src` violation**:

```
http://127.0.0.1:5173/__vite-plugin-monkey.entry.js' violates the following
Content Security Policy directive: "script-src 'report-sample'
'nonce-M8IuXby8zkBNVu9VE1GDHw' 'unsafe-inline'". Note that 'script-src-elem'
was not explicitly set, so 'script-src' is used as a fallback. The action has
been blocked.
```

**Cause**: The target website's CSP headers explicitly restrict which origins can load
scripts, and `127.0.0.1:5173` is not in the allowlist. This is a server-side policy set by
the website.

**Solutions (in order of preference)**:

1. **Test on a site with a relaxed CSP** during development. Keep a tab open to a simple
   site (e.g., `https://example.com`, or a personal blog without strict CSP) specifically
   for userscript development.

2. **Use the browser extension
   [Disable-CSP](https://github.com/lisonge/Disable-CSP)** to temporarily disable CSP
   headers during development. Remember to disable it when not developing — it weakens
   security on all sites.

3. **Build and test the production script**: Run `vite build`, then install the resulting
   `.user.js` file directly into your userscript manager. The built script runs from the
   manager's sandbox and is not subject to page CSP.

**Error pattern 2 — CORS loopback address block**:

```
Access to script at 'http://127.0.0.1:5173/__vite-plugin-monkey.entry.js'
from origin 'https://www.jsdelivr.com' has been blocked by CORS policy:
Permission was denied for this request to access the `loopback` address space.
```

**Cause**: This is NOT a website CSP issue. This is a **browser-level security setting**
that blocks websites from accessing local network resources (loopback addresses like
`127.0.0.1` or `localhost`). Some browsers (Chrome/Edge) have a permission called "Allow
sites to access applications and services on this device" (or "允许站点访问该设备上的应用和服务"
in Chinese). When this is disabled, any website is blocked from connecting to
`127.0.0.1:5173`.

**Solution**: Open the browser's site settings for the target website (click the lock/tune
icon in the address bar → Site settings), and enable the option that allows the site to
access local network resources:

- **Chrome/Edge (English)**: "Allow sites to access applications and services on this
  device" → Enable
- **Chrome/Edge (中文)**: "允许站点访问该设备上的应用和服务" → 开启
- The exact wording varies by browser version, but it's always a per-site toggle related to
  local/loopback network access.

Once enabled, reload the page and the script will run. Note that this setting is per-site
— you only need to enable it for the sites you're developing against.

This is only a dev-mode concern. The built `.user.js` runs from the userscript manager's
sandbox and is not affected by page CSP or loopback restrictions.

### 4. Greasyfork Code Rules

Greasyfork prohibits obfuscated or minified code. vite-plugin-monkey sets
`viteConfig.build.minify = false` by default for this reason. If you're not publishing to
Greasyfork and want minification, explicitly set `build.minify: true` in your Vite config.

### 5. @vitejs/plugin-legacy Compatibility

When using `@vitejs/plugin-legacy`, you must set `renderLegacyChunks: false`:

```ts
import legacy from '@vitejs/plugin-legacy';
import monkey from 'vite-plugin-monkey';

export default defineConfig({
  plugins: [
    legacy({ renderLegacyChunks: false, modernPolyfills: true }),
    monkey({ entry: './src/main.ts' }),  // last
  ],
});
```

### 6. Dynamic Imports Require SystemJS

If your code uses `import()` (dynamic imports), the plugin wraps the output in SystemJS
format. The default SystemJS loader is loaded from jsdelivr CDN. You can customize this:

```ts
monkey({
  build: {
    systemjs: 'inline',  // inline the minimal SystemJS loader
    // Or provide a custom CDN URL:
    systemjs: cdn.jsdelivr()[1],
  },
})
```

Using `'inline'` makes the script fully self-contained but increases file size slightly.

### 7. `top-level await` Support

Top-level await is fully supported. During the build, the plugin automatically transforms
the IIFE wrapper into an async IIFE when top-level await is detected. No extra
configuration needed.

## Web Workers

Tampermonkey does **not** support loading external worker files. All workers must be
inlined into the userscript itself.

> **Important for TypeScript worker files**: Every `.ts` worker file must include the
> `/// <reference lib="webworker" />` directive at the very top. Without it, TypeScript
> defaults to the `Window` lib and resolves `postMessage` to
> [`Window.postMessage`](https://developer.mozilla.org/docs/Web/API/Window/postMessage)
> (where the second argument is `targetOrigin: string`), rather than the correct
> [`Worker.postMessage`](https://developer.mozilla.org/docs/Web/API/Worker/postMessage)
> (where the second argument is `transfer?: Transferable[]`). This causes confusing
> overload errors like `"类型'ArrayBufferLike[]'的参数不能赋给类型'string'的参数"` when
> trying to transfer buffers.
>
> ```ts
> /// <reference lib="webworker" />
> // rest of worker code
> self.postMessage(buf, [buf]);  // ✅ correct: transfer list
> ```

**Default recommendation**: Always use the **TypeScript ESM** approach (`import Worker from './worker?worker&inline'`) for new code. This gives you type safety, proper ESM `import`/`export`, and Vite transpilation — all for free in build mode. Classic workers (string-based `new Blob([code])`) should only be used when the user explicitly asks for them, e.g. because they need `importScripts()` to load external libraries from CDN at runtime. Even then, consider whether those libraries can be imported as ESM inside a `?worker&inline` worker instead.

**When a user reports "my worker isn't running", follow this diagnostic flow:**

1. **Is the worker file a `.ts` file?**
   - **No (`.js` / string-based worker)**: If it's a plain JS file or inline string via
     `new Blob([code])`, it should work in both dev and build. Check for other issues
     (syntax errors, wrong path, logic bugs).
   - **Yes (`.ts`)** → go to step 2.

2. **Are they running in dev mode (`vite serve`) or build mode (`vite build`)?**
   - **Build mode**: The worker should work if using `import Worker from './worker?worker&inline'`. Vite transpiles TS, resolves ESM imports, and produces a clean Blob URL. If it still fails, check if they forgot the `&inline` suffix or if `@match` patterns are correct.
   - **Dev mode** → this is the problem. Go to step 3.

3. **How are they importing the `.ts` worker in dev mode?**
   - **`?raw` + Blob**: The raw source contains TypeScript type annotations (`: string`,
     `interface Foo`, etc.) that browsers can't parse → **syntax error**. Fix: remove all
     type annotations from the `.ts` file, or switch to `?worker&inline` (build only).
   - **`?worker&inline`**: Vite doesn't bundle workers in dev mode, it serves them as
     separate modules. Tampermonkey can't load external worker files → **worker fails to
     initialize silently**. Fix: `vite build` and test the production `.user.js`.

**Bottom line for `.ts` workers**: Don't expect them to work in dev mode. Use `import Worker from './worker?worker&inline'` for production builds, and test worker logic by building the script. The complexity of making workers work in dev mode (custom Vite plugin) is rarely worth it.

### Classic Workers (`.js` with `importScripts`)

Classic workers that use `importScripts()` to load external URLs can be converted to inline
Blob workers relatively easily:

```ts
// main.ts — classic JS worker via Blob inline
const workerCode = `
  importScripts('https://example.com/some-lib.js');
  self.onmessage = (e) => {
    // worker logic
    self.postMessage(result);
  };
`;
const blob = new Blob([workerCode], { type: 'application/javascript' });
const worker = new Worker(URL.createObjectURL(blob));
```

This approach works in both dev and build mode since it's just string-based code injection.

### TypeScript Workers (`.ts`) — Dev Mode Problem

If you try to inline a `.ts` worker file as a raw string and convert it to a Blob, the
source code still contains TypeScript type annotations. Browsers cannot parse these
annotations and will throw syntax errors:

```
// This will FAIL in the browser at dev time:
import workerSource from './worker.ts?raw';
const blob = new Blob([workerSource], { type: 'application/javascript' });
// ❌ Browser can't parse `: string`, `interface Foo`, etc.
```

**Exception**: If the `.ts` worker file contains zero type annotations (pure JavaScript with
`.ts` extension, no type syntax), it will work in dev mode via `?raw` + Blob.

### ESM Workers with TypeScript (Recommended for Production)

Use Vite's built-in worker import syntax:

```ts
// main.ts
import Worker from './worker?worker&inline';
const worker = new Worker({ name: 'worker' });
```

The `?worker&inline` suffix tells Vite to bundle the worker as an inline `Blob` URL. This
works correctly in `vite build` mode — Vite transpiles TypeScript, resolves ESM imports,
and produces a clean JavaScript blob that browsers can execute.

**However, in `vite serve` (dev mode), this does NOT work.** Vite does not bundle workers
during development; it serves them as separate modules. Since Tampermonkey can't load
external worker files, the worker will fail to initialize.

### Fixing Dev Mode Workers: A Minimal Plugin

If you genuinely need `?worker&inline` to work during `vite serve`, here is a minimal Vite
plugin that intercepts the generated worker wrapper and replaces the external URL with an
inline Blob URL (with automatic cleanup via `setTimeout(0)` revoke):

```ts
import type { Plugin } from 'vite';

/**
 * In dev mode Vite's worker plugin generates a URL-based WorkerWrapper:
 *   export default function WorkerWrapper(options) {
 *     return new Worker("/...?worker_file&type=module", options);
 *   }
 *
 * We intercept the generated code, bundle the worker source with rolldown,
 * and replace just the URL string with an IIFE that creates a Blob URL,
 * schedules cleanup, and returns the URL — nothing else in Vite's wrapper changes.
 */
export function fixDevWebworker(): Plugin {
  return {
    name: 'fix-dev-webworker',
    enforce: 'post',
    apply: 'serve',

    async transform(code, id) {
      if (!id.endsWith('?worker&inline')) return null;

      const cleanPath = id.replace(/\?worker&inline$/, '');

      const { rolldown } = await import('rolldown');
      const bundle = await rolldown({
        input: cleanPath,
        platform: 'browser',
      });

      let bundledCode: string;
      try {
        const result = await bundle.generate({ format: 'iife' });
        bundledCode = result.output[0].code;
      } finally {
        await bundle.close();
      }

      // Replace just the URL string — Vite's WorkerWrapper receives it as-is.
      // IIFE: create Blob URL → schedule revoke via setTimeout(0) →
      //       return URL → new Worker(url, options) loads it synchronously
      return code.replace(
        /"\/[^"]+"/,
        `(()=>{const u=URL.createObjectURL(new Blob([${JSON.stringify(bundledCode)}],{type:'application/javascript'}));setTimeout(()=>URL.revokeObjectURL(u),0);return u})()`,
      );
    },
  };
}
```

**How it works**: Vite's built-in worker plugin in dev mode generates a wrapper that does
`new Worker("/some-url?worker_file&type=module", options)`. This plugin intercepts that
generated code via `transform`, bundles the worker source into an IIFE using rolldown, and
replaces just the external URL string with an IIFE expression. The IIFE creates a Blob URL,
schedules `URL.revokeObjectURL` via `setTimeout(0)` to run after the Worker synchronously
loads the code, and returns the URL. Vite's wrapper receives the URL as
`new Worker(url, options)` — the rest of the generated code is untouched.

**Why Blob URL over data URI**: `URL.createObjectURL` avoids data URI length limits,
encoding issues with UTF-8, and is the standard browser API for inline resources.
The `setTimeout(0)` revoke is safe because `new Worker(blobUrl)` loads the script
synchronously — by the time the microtask fires, the Worker is already initialized.

**Usage in vite.config.ts**:

```ts
import { fixDevWebworker } from './fix-dev-webworker'

export default defineConfig({
  plugins: [
    // ... other plugins ...
    monkey({ entry: 'src/main.ts' }),
    fixDevWebworker(), // after monkey
  ],
})
```

**Note**: This requires `rolldown` as a dev dependency. If you'd rather not maintain this,
the simplest approach remains: `vite build` and test the production `.user.js`.

**Summary of worker strategies**:

| Worker type | Dev mode | Build mode | Recommendation |
|---|---|---|---|
| Classic JS (string) via Blob | ✅ Works | ✅ Works | Good for simple inline workers |
| `.ts` file via `?raw` + Blob | ⚠️ Only if no types in file | ❌ Not recommended | Avoid; use `?worker&inline` instead |
| `.ts` via `?worker&inline` | ❌ Not supported | ✅ Works | **Use this for production** |
| `fixDevWebworker` plugin | ✅ Works | ✅ Not needed | Requires `rolldown` dep; uses Blob URL + `revokeObjectURL` |

### What Workers Are For: CPU-Bound Tasks Only

Web Workers run in a separate thread without access to the DOM. Their only purpose in a
userscript context is to offload **CPU-intensive computation** from the main thread, so the
page stays responsive. Worker ↔ main thread communication happens via `postMessage`.

**Good candidates for workers** (CPU-bound, no DOM needed):

| Category | Libraries | Why it fits |
|---|---|---|
| Compression | [`fflate`](https://github.com/101arrowz/fflate), `pako`, `jszip` | gzip/zlib/zip/deflate is purely algorithmic; no DOM required |
| Encoding/decoding | `base64` utils, `msgpack`, `protobuf` | Binary/text conversion is pure data processing |
| Hashing | `hash-wasm`, `crypto-js`, `spark-md5` | Hashing large files is compute-heavy |
| Parsing | `marked` (Markdown), `csv-parse`, `fast-xml-parser` | Parsing large documents into structured data |
| Image processing | Custom pixel manipulation, `jimp` (limited) | Pixel array math is CPU-intensive |

**NOT suitable for workers** (requires DOM, Service Worker, or main-thread APIs):

| Category | Libraries | Why NOT in worker |
|---|---|---|
| File saving/streaming | [`StreamSaver.js`](https://github.com/jimmywarting/StreamSaver.js), `FileSaver.js` | Needs WritableStream / Service Worker / DOM APIs — must run on main thread |
| DOM manipulation | Any UI framework, jQuery, `htmx` | Workers have no access to `document` or `window` |
| Network requests | `axios`, `fetch` (mostly fine in worker, but…) | `GM_xmlhttpRequest` is NOT available in workers; use `fetch` if CORS allows |
| Clipboard | `clipboard.js` | Needs `navigator.clipboard` which is main-thread only |

### The Streaming Pattern: Main Thread + Worker

A common mistake is trying to put everything in the worker. The correct architecture for a
download-and-save flow:

```
Main thread                          Worker thread
─────────                           ────────────
1. Initiate StreamSaver/             
   create writable stream            
                                     
2. Fetch data or receive             3. Compress/encode/transform
   compressed chunks                    data (CPU-heavy)
                                     
4. Receive transformed               5. postMessage result
   chunks via postMessage             
                                     
6. Write chunks to stream             
   (StreamSaver)                     
```

Concrete example — compressing and saving a large file:

```ts
// main.ts (main thread)
import { GM_xmlhttpRequest } from '$';
// StreamSaver MUST be on main thread
import streamSaver from 'streamsaver';

// Create worker for compression
import CompressWorker from './compress?worker&inline';
const worker = new CompressWorker();

// Set up the writable stream on main thread
const fileStream = streamSaver.createWriteStream('output.zip');

// Send data to worker for compression
worker.postMessage({ type: 'compress', data: rawBuffer });

// Receive compressed chunks from worker, write to stream
worker.onmessage = (e) => {
  const writer = fileStream.getWriter();
  writer.write(e.data.chunk);
  if (e.data.done) writer.close();
};

// Worker code (compress.ts)
// import { gzip } from 'fflate'; // fflate is pure computation, worker-safe
self.onmessage = (e) => {
  // Heavy compression happens here, not blocking the main thread
  const compressed = gzip(e.data.data);
  self.postMessage({ chunk: compressed, done: true });
};
```

**The rule of thumb**: If a library touches `document`, `window` (beyond `self`), Service
Workers, `WritableStream`, or the filesystem — it stays on the main thread. If it only does
math, encoding, parsing, or compression on raw data — it can go in the worker. Split the
work accordingly: main thread handles I/O, worker handles computation.

### Production Architecture: Non-Blocking Download Pipeline

When building a userscript that downloads many resources, compresses them, and saves to disk
— a naive sequential `for` loop will freeze the UI on every step. The following three-layer
architecture keeps the page responsive by separating concerns across threads and using
asynchronous I/O throughout.

**Core pipeline** (demonstrated with a ZIP downloader):

```
┌──────────────────────────────────────────────────┐
│  Layer 1: 并发下载 (主线程, 异步 I/O)              │
│                                                    │
│  p-limit(3) 控制并发                               │
│    GM_xmlhttpRequest ──► ArrayBuffer               │
│    buffer Map<index, {filename, data}>             │
│    serial writeLock 保序写入                        │
│                                                    │
│    → postMessage(data, [data.buffer])              │
│              │                    transfer 零拷贝   │
├──────────────┼───────────────────────────────────┤
│  Layer 2: Worker 压缩 (独立线程, CPU 计算)         │
│                                                    │
│    fflate::Zip / gzip / pako                       │
│    CPU 密集计算不阻塞主线程 UI                       │
│                                                    │
│    → postMessage(chunk, [chunk.buffer])            │
│              │                    transfer 零拷贝   │
├──────────────┼───────────────────────────────────┤
│  Layer 3: 流式写磁盘 (主线程, 异步 I/O)            │
│                                                    │
│    StreamSaver ──► writer.write(chunk)             │
│    或 Blob 内存兜底                                 │
└──────────────────────────────────────────────────┘
```

**Why each layer doesn't block the UI**:

| Layer | Runs on | Blocking? | Why |
|---|---|---|---|
| `GM_xmlhttpRequest` | Main thread (async) | No | Network I/O is callback-based; browser handles it off-thread |
| fflate compression | Worker thread | No | Separate thread — main thread is idle while worker crunches |
| StreamSaver write | Main thread | No | `writer.write()` returns immediately; actual disk I/O is async |

**Key pattern 1: Concurrent download + ordered serialization**

Downloads are I/O-bound and benefit from concurrency, but ZIP archives require files to be
added in order (fflate's `Zip` is a stateful stream). The solution is to decouple download
order from write order:

```ts
const limit = pLimit(3);  // 3 concurrent downloads
const buffer = new Map<number, { filename: string; data: Uint8Array }>();
let nextToWrite = 0;
let writeLock: Promise<void> = Promise.resolve();

items.map((item, sortedIndex) =>
  limit(async () => {
    // 1. Download (concurrent — 3 at a time)
    const arrayBuf = await downloadWithRetry(item.url, signal);
    const data = new Uint8Array(arrayBuf);
    buffer.set(sortedIndex, { filename: item.filename, data });

    // 2. Wait for your turn, then flush all consecutive entries
    const prev = writeLock;
    let resolveLock!: () => void;
    writeLock = new Promise<void>(r => { resolveLock = r; });
    await prev;  // ← serialization point: only one writer at a time
    try {
      while (buffer.has(nextToWrite)) {
        const entry = buffer.get(nextToWrite)!;
        buffer.delete(nextToWrite);
        zipWriter.add(entry.filename, entry.data);  // sends to worker
        nextToWrite++;
      }
    } finally {
      resolveLock();  // release the lock for the next downloader
    }
  })
);
```

The key insight: downloads happen in parallel, but writes are serialized through a Promise
chain (`writeLock`). The `while` loop flushes all consecutive ready entries at once — if
entries 0, 1, 2 all finish before entry 0 writes, they all go in one batch. No blocking,
no busy-waiting.

**Key pattern 2: Transferable zero-copy between main and worker**

Every `ArrayBuffer` passed between threads uses the transfer list (`[buffer]`), which
transfers **ownership** without copying a single byte:

```
Main thread                     Worker thread
──────────                      ─────────────
download → ArrayBuffer (N KB)
           │
           │ postMessage({filename, data}, [data.buffer])
           │ 主线程释放所有权                         ──► fflate 消费
           │                                              │
           │          ◄── postMessage({chunk}, [chunk.buffer])
           │              Worker 释放所有权
           │
StreamSaver.write(chunk)
chunk 写入磁盘后 GC 回收
```

```ts
// main → worker: transfer downloaded data (zero copy)
this.worker.postMessage(
  { type: 'add', filename, data },
  [data.buffer],  // ← ownership transfers to worker
);

// worker → main: transfer compressed chunk (zero copy)
self.postMessage(
  { type: 'chunk', data: chunk },
  [chunk.buffer],  // ← ownership transfers back to main
);
```

Without the transfer list, `postMessage` performs a structured clone (full copy) — for a
100MB ZIP that's 100MB of wasted memory and CPU. With transfer, the same data moves between
threads with zero overhead.

**Key pattern 3: Streaming output with fallback**

StreamSaver writes chunks to disk as they arrive, keeping memory usage flat regardless of
total output size. But if StreamSaver fails to initialize (some browsers/sites block Service
Workers), fall back to in-memory Blob:

```ts
class ZipWriter {
  private writer: WritableStreamDefaultWriter | null = null;
  private chunks: BlobPart[] = [];
  private streaming = false;

  constructor(filename: string) {
    try {
      this.writer = createWriteStream(filename).getWriter();
      this.streaming = true;
    } catch {
      this.streaming = false;  // fallback to in-memory Blob
    }
  }

  private handleChunk(data: Uint8Array): void {
    if (this.streaming) {
      this.writer!.write(data);    // → disk, fire-and-forget
    } else {
      this.chunks.push(data);      // → memory buffer
    }
  }

  async finish(): Promise<Blob | null> {
    if (this.streaming) {
      this.writer!.close();
      return null;  // already saved to disk
    }
    return new Blob(this.chunks, { type: 'application/zip' });
  }
}
```

**When to use this architecture**:

- Downloading 10+ resources and bundling them (ZIP, tar, etc.)
- Batch processing: fetch → transform (compress/encode/hash) → save
- Any userscript where the user would notice the page freezing during work

**When it's overkill**:

- Fetching 1–3 small resources — just use `GM_xmlhttpRequest` directly
- No CPU-heavy processing — skip the Worker layer
- No file output — skip StreamSaver, just use `GM_download` or an `<a>` click

## CSS Handling

### Default behavior

The plugin handles CSS imports by generating a helper function that calls `GM_addStyle` if
available, falling back to creating a `<style>` element. This works for most cases.

### Shadow DOM / style isolation

Enable `styleImport: true` (the default) and import CSS with the `?style` query parameter
to get `HTMLStyleElement` instances:

```ts
// main.ts
import style1 from './style1.css?style';
import style2 from 'normalize.css?style';

const container = document.createElement('div').attachShadow({ mode: 'open' });
container.append(style1, style2);  // HMR works when style1.css changes
const style3 = style1.cloneNode(true);  // still has HMR
```

For TypeScript, add to `vite-env.d.ts`:

```ts
/// <reference types="vite-plugin-monkey/style" />
```

### Custom CSS injection

Override the default CSS injection logic with `build.cssSideEffects`:

```ts
monkey({
  build: {
    cssSideEffects: (css) => `(a)=>GM_addStyle(a)`,
  },
})
```

## Building a Library That Wraps GM_api

When you're building a library that uses GM APIs and want to distribute it for both
vite-plugin-monkey users (ESM `import`) and traditional `@require` users (IIFE):

### Library source

```ts
// src/index.ts
import { GM_setValue } from 'vite-plugin-monkey/dist/client';

export const setValue = (name: string, value: unknown) => {
  console.log('you invoke setValue', name, value);
  GM_setValue(name, value);
};
```

### Build configuration (example with tsup)

```ts
// tsup.config.ts
import { defineConfig } from 'tsup';

const outExtension = (ctx: { format: 'esm' | 'cjs' | 'iife' }) => ({
  js: { esm: '.mjs', cjs: '.cjs', iife: '.iife.js' }[ctx.format],
});

export default defineConfig([
  {
    // ESM build: for vite-plugin-monkey users (npm import)
    entry: ['src/index.ts'],
    outDir: 'dist',
    format: ['esm'],
    dts: true,
    external: ['vite-plugin-monkey/dist/client'],  // EXCLUDE from bundle
    outExtension,
  },
  {
    // IIFE build: for traditional @require users
    entry: ['src/index.ts'],
    outDir: 'dist',
    format: ['iife'],
    globalName: 'GmExtra',
    minify: true,
    target: 'es2015',
    outExtension,
    esbuildOptions: (options) => {
      options.alias = {
        // Redirect to native (no-op) implementation
        'vite-plugin-monkey/dist/client': 'vite-plugin-monkey/dist/native',
      };
    },
  },
]);
```

The key insight: **externalize** `vite-plugin-monkey/dist/client` in the ESM build (the
consumer's plugin will provide the implementation). **Redirect** to
`vite-plugin-monkey/dist/native` in the IIFE build (direct `GM_*` global access).

## Framework-Specific Patterns

### Vue

```bash
pnpm create monkey  # choose vue-ts
```

Use Vue's Composition API with `<script setup lang="ts">`. Import GM APIs in your component
files or use `unplugin-auto-import` for zero-import convenience. The Vue template includes
vite-plugin-monkey already configured.

### React

```bash
pnpm create monkey  # choose react-ts
```

> **React 外部化问题诊断**：当用户反馈"React 无法外部化"、"外部化无效"、"`module is not defined`"、"脚本没反应"等问题时，**首先确认 React 版本**：
>
> 1. 如果项目根目录有 `package.json`，**主动读取**其中的 `react` 字段获取版本号，直接按版本给出对应的外部化方案。**不要询问用户版本号** —— 自己读。
> 2. 如果项目没有 `package.json`（比如用户只在聊天中提到），再询问用户。
>
> 版本分流：
> - **React 19.x** → 没有 UMD/IIFE 构建，传统 `@require` + `cdn.jsdelivr()` **绝对无效**。唯一的外部化方案是下方 `vite-plugin-react19-external` 插件。
> - **React 18.x / 17.x / 16.x** → 有 UMD 构建，可使用传统 CDN 方式：`cdn.jsdelivr('React', 'umd/react.production.min.js')`。如果仍失败，检查 CDN 文件路径是否存在、IIFE/UMD 混用问题（见 [Pitfall 1](#1-iifeumd-mix-problem)）。

**React 19 没有 UMD/IIFE 构建**，无法走传统 `@require` + `cdn.jsdelivr()` 路线。但可以通过 **importmap + ESM** 方式从 esm.sh CDN 加载并挂载到 `unsafeWindow`，实现外部化。

推荐使用 `vite-plugin-react19-external` 插件，**入口文件零侵入**——无需修改 `main.tsx`，所有逻辑集中在 `vite.config.ts`：

```ts
// vite.config.ts
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import monkey from 'vite-plugin-monkey'
import { react19ExternalPlugin, react19ExternalGlobals } from './vite-plugin-react19-external'

export default defineConfig({
    plugins: [
        react(),
        monkey({
            entry: 'src/main.tsx',
            build: {
                externalGlobals: react19ExternalGlobals(),
            },
        }),
        react19ExternalPlugin(), // 默认入口 'src/main.tsx'，必须在 monkey 之后（enforce: 'post'）
    ],
})
```

插件做的事情（全自动，无需手动干预）：

1. **注入引导代码** —— 在入口文件顶部自动插入 `ensureReact()` 代码，包含 importmap 注入、module script 注入、轮询等待 React 就绪。
2. **SystemJS 懒求值** —— 将 `System.set`（立即求值）替换为 `System.register`（懒求值），确保在 `ensureReact()` 完成之前不访问 `unsafeWindow.React`。
3. **IIFE 参数重赋值** —— 在 `ensureReact()` 之后将 IIFE 参数重新指向已就绪的 `unsafeWindow.React`。

插件完整源码（[vite-plugin-react19-external.ts](vite-plugin-react19-external.ts)）：

```ts
/**
 * vite-plugin-react19-external — 将 React 19 外部化（通过 esm.sh importmap），
 * 避免把 ~200KB 的 React 打进 .user.js。
 *
 * React 19 没有 UMD/IIFE 构建产物，传统 @require + cdn.jsdelivr() 路线走不通。
 * 本方案走 importmap + ESM 路线，完全通过一个插件自动处理，无需修改入口文件。
 */

import path from 'node:path'
import { type Plugin } from 'vite'

// ---------------------------------------------------------------------------
// 类型
// ---------------------------------------------------------------------------

export interface React19ExternalOptions {
    /** React 版本号（用于 esm.sh CDN URL），默认 "19.2.7" */
    version?: string
    /** 加载超时（毫秒），默认 15_000 */
    timeout?: number
    /** 轮询间隔（毫秒），默认 50 */
    pollInterval?: number
}

export interface GlobalsOptions {
    /** 是否外部化 react，默认 true */
    react?: boolean
    /** 是否外部化 react-dom，默认 true */
    dom?: boolean
    /** 是否外部化 react/jsx-runtime，默认 true */
    jsxRuntime?: boolean
}

// ---------------------------------------------------------------------------
// import specifier → IIFE 参数名 / unsafeWindow 变量名 映射
// ---------------------------------------------------------------------------

const REACT_GLOBAL_MAP: Record<string, string> = {
    react: 'unsafeWindow.React',
    react_dom: 'unsafeWindow.ReactDOM',
    react_dom_client: 'unsafeWindow.__ReactDOMClient',
    react_jsx_runtime: 'unsafeWindow.__ReactJSXRuntime',
}

const ALL_PARAM_NAMES = Object.keys(REACT_GLOBAL_MAP)

// ---------------------------------------------------------------------------
// externalGlobals 配置生成
// ---------------------------------------------------------------------------

export function react19ExternalGlobals(opts: GlobalsOptions = {}): Record<string, string> {
    const { react = true, dom = true, jsxRuntime = true } = opts

    const globals: Record<string, string> = {}

    if (react) globals['react'] = 'unsafeWindow.React'
    if (jsxRuntime) globals['react/jsx-runtime'] = 'unsafeWindow.__ReactJSXRuntime'
    if (dom) {
        globals['react-dom'] = 'unsafeWindow.ReactDOM'
        globals['react-dom/client'] = 'unsafeWindow.__ReactDOMClient'
    }

    return globals
}

// ---------------------------------------------------------------------------
// 引导代码生成（注入到入口文件）
// ---------------------------------------------------------------------------

function ensureReactBootstrap(opts: React19ExternalOptions = {}): string {
    const version = opts.version ?? '19.2.7'
    const timeout = opts.timeout ?? 15_000
    const pollInterval = opts.pollInterval ?? 50

    return `
import { GM_addElement, unsafeWindow } from '$';

async function __ensureReact__() {
  var pw = unsafeWindow;
  if (pw.React && pw.ReactDOM) return;

  // 1. 注入 importmap（全局唯一）
  if (!document.querySelector('script[type="importmap"]')) {
    GM_addElement(document.head, 'script', {
      type: 'importmap',
      textContent: JSON.stringify({
        imports: {
          'react': 'https://esm.sh/react@${version}',
          'react/jsx-runtime': 'https://esm.sh/react@${version}/jsx-runtime',
          'react-dom': 'https://esm.sh/react-dom@${version}',
          'react-dom/client': 'https://esm.sh/react-dom@${version}/client',
        },
      }),
    });
  }

  // 2. 注入 module script —— 把 ESM 导入的 React 挂到 window（即 unsafeWindow）
  GM_addElement(document.head, 'script', {
    type: 'module',
    textContent: [
      'import * as __React from "react";',
      'import * as __ReactDOM from "react-dom";',
      'import * as __ReactDOMClient from "react-dom/client";',
      'import * as __JSXRuntime from "react/jsx-runtime";',
      'window.React=__React;',
      'window.ReactDOM=__ReactDOM;',
      'window.__ReactDOMClient=__ReactDOMClient;',
      'window.__ReactJSXRuntime=__JSXRuntime;',
    ].join(''),
  });

  // 3. 轮询等待（内联 module script 无可靠 onload 回调）
  const start = Date.now();
  while (!pw.React) {
    if (Date.now() - start > ${timeout}) {
      throw new Error('React externalization timeout — CDN unreachable');
    }
    await new Promise(r => setTimeout(r, ${pollInterval}));
  }
}

await __ensureReact__();
`
}

// ---------------------------------------------------------------------------
// Vite 插件
// ---------------------------------------------------------------------------

export function react19ExternalPlugin(entry: string = 'src/main.tsx', opts: React19ExternalOptions = {}): Plugin {
    let resolvedEntry = ''

    // 匹配 System.set("user:xxx", (()=>{...})()) 立即求值模式
    const EAGER_SET_RE =
        /System\.set\("(user:[^"]+)",\s*\(\(\)\s*=>\s*\{\s*const\s+(_\w*)\s*=\s*([^;]+);\('default'\s+in\s+_\w*\)\|\|\s*\(_\w*\.default\s*=\s*_\w*\);\s*return\s+_\w*\s*\}\)\(\)\)/g

    // 匹配 await __ensureReact__() 或 await(__ensureReact__())
    const ENSURE_RE = /\bawait\s*\(?\s*__ensureReact__\s*\([^)]*\)\s*\)?\s*;?/

    return {
        name: 'vite-plugin-react19-external',
        enforce: 'post',
        apply: 'build',

        configResolved(config) {
            resolvedEntry = path.resolve(config.root, entry)
        },

        // ---- Step 1: 向入口文件注入 ensureReact 引导代码 ----
        transform(code, id) {
            if (path.normalize(id) !== resolvedEntry) return null
            return ensureReactBootstrap(opts) + code
        },

        // ---- Step 2: 处理 bundle 格式的时序问题 ----
        generateBundle(_, bundle) {
            for (const chunk of Object.values(bundle)) {
                if (chunk.type !== 'chunk' || !chunk.code) continue

                // SystemJS 格式：System.set → System.register（懒求值）
                chunk.code = chunk.code.replace(
                    EAGER_SET_RE,
                    (_: string, name: string, varName: string, expr: string) =>
                        `System.register("${name}",[],function(e){return{execute:function(){var ${varName}=${expr};('default' in ${varName})||(${varName}.default=${varName});e(${varName})}}})`,
                )

                // IIFE 格式：在 __ensureReact__() 之后注入参数重赋值
                const presentParams = ALL_PARAM_NAMES.filter((name) => {
                    const re = new RegExp(`\\b${name}\\b`)
                    return re.test(chunk.code)
                })

                if (presentParams.length === 0) continue

                const reassignStmts = presentParams.map((p) => `${p}=__toESM(${REACT_GLOBAL_MAP[p]})`).join(';')

                chunk.code = chunk.code.replace(ENSURE_RE, (match) => `${match}${reassignStmts};`)
            }
        },
    }
}
```

**为什么必须用 esm.sh 而不是 jsdelivr？** jsdelivr 的 `+esm` 模式不支持子路径 —— `react-dom/client`、`react/jsx-runtime` 这类路径会解析失败。esm.sh 是专门为 npm 包提供 ESM 的 CDN，子路径解析正确。

**为什么插件必须用 `GM_addElement`？** 油猴沙箱中普通 `document.createElement` + `appendChild` 创建的 DOM 不会暴露给页面上下文，`<script type="module">` 无法执行。`GM_addElement` 会将元素插入到页面上下文中，module script 才能正确解析 importmap。

> **⚠️ 审查 React 19 外部化配置时的检查清单**：
>
> 1. `react19ExternalPlugin()` 是否在 `vite.config.ts` 的 plugins 中，且排在 `monkey()` **之后**？
> 2. `build.externalGlobals` 是否使用了 `react19ExternalGlobals()`（而非手写 `cdn.jsdelivr()`）？
> 3. 插件文件 `vite-plugin-react19-external.ts` 是否存在于项目中？

**不想折腾外部化？** 两种替代方案：

1. **打包进脚本**（默认）—— React 打进 `.user.js`，零配置，最省心。
2. **降级到 React 18** —— 最后一个有 UMD 的版本，可用传统 CDN 方式：

   ```ts
   externalGlobals: {
       react: cdn.jsdelivr('React', 'umd/react.production.min.js'),
       'react-dom': cdn.jsdelivr('ReactDOM', 'umd/react-dom.production.min.js'),
   },
   ```

### Svelte / Solid

Both frameworks work well with vite-plugin-monkey. The templates handle the configuration.

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Solution |
|---|---|---|
| Script doesn't run, no errors in console | Userscript manager not enabled or script toggled off | Check extension icon is active, script is enabled, `@match` matches the URL |
| Script works on some sites but not others (dev mode) | Target site has strict CSP blocking `127.0.0.1` | Test on a site with relaxed CSP, use Disable-CSP extension, or `vite build` and test the built script |
| CSP `script-src` violation blocking `__vite-plugin-monkey.entry.js` | Strict CSP on target site | Test on simpler site, use Disable-CSP extension, or build and install `.user.js` |
| CORS error blocking `loopback` address to `127.0.0.1:5173` | Browser setting blocks sites from accessing local network (`127.0.0.1`) | Enable "Allow sites to access applications and services on this device" in browser site settings |
| Worker fails to load in dev mode | `?worker&inline` doesn't work in `vite serve` | Use the `fixDevWebworker` plugin, or build the `.user.js` and test in production mode |
| Worker throws syntax error (dev mode) | `.ts` worker source has type annotations browser can't parse | Remove types, use `?worker&inline` (build only), or use classic JS worker strings |
| `GM_xmlhttpRequest` / `GM_xxx` is undefined | Using bare global or `window.GM_xxx` instead of ESM import | Import from `$`: `import { GM_xxx } from '$'` — GM APIs do not exist as globals |
| `module is not defined` when loading React from CDN / 404 `umd/react.production.min.js` | React 19 has no IIFE/UMD build — all files are CJS/ESM, cannot be loaded via `@require` | Bundle inline, pin to React 18, or use the [importmap approach](#react) |
| `XXX is not defined` at runtime | IIFE/UMD mix with CDN deps | Use `util.dataUrl(';window.XXX=XXX;')` |
| Build works but userscript won't install | Missing or invalid userscript header | Check `userscript.name`, `namespace`, `version` |
| `@grant` directives missing | `autoGrant` is `false` or GM API usage not detected | Set `autoGrant: true` (default) |
| Dynamic import fails at runtime | SystemJS not configured | Check `build.systemjs` setting |
| Plugin ordering issues | monkey plugin not last | Move `monkey()` to the end of the plugins array |
| TypeScript can't find GM API types | Missing type reference | Add `/// <reference types="vite-plugin-monkey/client" />` |
| Greasyfork rejects script | Code is minified | Ensure `build.minify` is not set to `true` (default is `false`) |

## Configuration Checklist for Production

When preparing a userscript for release, verify:

- [ ] `entry` points to the correct main file
- [ ] `userscript.name`, `namespace`, `version` are set
- [ ] `userscript.match` / `include` / `exclude` patterns are correct
- [ ] `build.fileName` ends with `.user.js`
- [ ] `build.metaFileName` is set if using `updateURL`
- [ ] `build.externalGlobals` externalizes large dependencies via CDN
- [ ] IIFE/UMD dependencies have `util.dataUrl` workaround applied if needed
- [ ] `build.autoGrant` is `true` (or `@grant` directives are manually specified)
- [ ] `viteConfig.build.minify` is not enabled (for Greasyfork compliance)
- [ ] The plugin is the **last** in the plugins array
- [ ] TypeScript types are referenced in `vite-env.d.ts`
- [ ] The `.meta.js` file is uploaded alongside the `.user.js` file to your host

## Reference: Full MonkeyOption Type

For reference, the complete configuration interface (from `vite-plugin-monkey` source):

```ts
interface MonkeyOption {
  entry: string;                              // required: entry file path
  userscript?: MonkeyUserScript;              // userscript metadata header
  clientAlias?: string;                       // alias for client imports (default: '$')
  align?: number | false;                     // comment indentation (default: 2)
  generate?: (options: {                      // custom header generation
    userscript: string;
    mode: 'serve' | 'build' | 'meta';
  }) => Thenable<string>;
  styleImport?: boolean;                      // CSS → HTMLStyleElement (default: true)
  server?: {
    open?: boolean;                           // auto-open browser (default: Win/Mac)
    prefix?: string | ((name: string) => string) | false;  // dev name prefix (default: 'server:')
    mountGmApi?: boolean;                     // mount GM APIs to unsafeWindow (default: false)
  };
  build?: {
    fileName?: string;                        // output .user.js filename
    metaFileName?: string | boolean | ((fileName: string) => string);  // .meta.js generation
    externalGlobals?: ExternalGlobals;        // external JS → @require
    autoGrant?: boolean;                      // auto-detect @grant (default: true)
    externalResource?: ExternalResource;      // external assets → @resource
    systemjs?: 'inline' | ModuleToUrlFc;      // dynamic import support
    cssSideEffects?: string | ((css: string) => void);  // custom CSS injection
  };
}
```
