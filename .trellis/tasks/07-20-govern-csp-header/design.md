# Design: nginx CSP

## 策略

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'
```

各指令理由：
- `default-src 'self'`：默认同源
- `script-src 'self'`：外联 JS（关 polyfill 后无内联），强制外联最大化 XSS 防护
- `style-src 'self' 'unsafe-inline'`：Naive UI css-render 动态注入 `<style>` + Vue 运行时设 element.style
- `img-src 'self' data: blob:`：内联 SVG + 可能的 blob URL
- `font-src 'self' data:`：@fontsource 字体打包进 bundle
- `connect-src 'self'`：API/SSE 同源（/api/ 代理）
- `frame-ancestors 'none'`：防 clickjacking（配合 X-Frame-Options DENY 兼容旧浏览器）
- `object-src 'none'`：禁 Flash/Java 插件
- `base-uri 'self'`：防 `<base>` 注入
- `form-action 'self'`：防表单外部提交（OAuth 是 302 重定向不受限）

## 改动

### 1. frontend/vite.config.ts

`build` 配置加 `modulePreload.polyfill=false`：

```ts
build: {
  manifest: true,
  modulePreload: { polyfill: false },
  rollupOptions: { output: { manualChunks: resolveVendorChunk } },
}
```

避免 Vite 注入内联 modulepreload polyfill `<script>`（现代浏览器原生支持 modulepreload，无需 polyfill）。

### 2. deploy/nginx.conf

server 级 + 图片/js-css location 重复加（与现有 4 安全头 add_header 一致，因 location 内 add_header 覆盖 server 级）：

```
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'" always;
```

## 测试

- 前端 build 后 `rg "<script>" dist/index.html` 确认无内联 script（应为 `<script type="module" src=...>` 外联）
- 前端四件套：vue-tsc --build + vitest + eslint + vite build
- 后端 pytest（test_dev_script_static.py 端口检查仍通过）
