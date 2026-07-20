# nginx CSP 安全响应头

## Goal

P2 决策收尾：nginx 加 Content-Security-Policy 严格策略，补一层 XSS 纵深防御。前端无外部资源，可用 `'self'` 严格策略。

## Background

调研结果：
- `index.html` 极简（仅外联 `/src/main.ts`），无内联 script/style/无外部 CDN
- 字体 `@fontsource` 打包进 bundle（`font-src 'self'`）
- 图片用 `data:image/svg+xml` 内联（`img-src data:`）
- Naive UI 用 css-render 动态注入 `<style>`（`style-src 'unsafe-inline'`）
- 无 `eval` / `new Function`
- API 同源 `/api/`（`connect-src 'self'`）
- Vite 默认 `modulePreload.polyfill=true` 会注入内联 script（违反 `script-src 'self'`），需关

## Requirements

- **vite.config**：`build.modulePreload.polyfill = false`（避免内联 script 被挡）
- **nginx.conf**：加 `Content-Security-Policy` header（server 级 + 图片/js-css location 重复，与现有 4 安全头一致）
- **策略**：`default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'`
- 前端 build 确认无内联 script

## Acceptance Criteria

- [ ] vite build 后 dist/index.html 无内联 `<script>`
- [ ] nginx.conf 含 CSP header（server 级 + 图片/js-css location 重复）
- [ ] 前端四件套绿（vue-tsc + vitest + eslint + build）
- [ ] 后端 pytest 绿（含 test_dev_script_static.py 端口检查）
- [ ] 独立复核通过

## Notes

- `style-src 'unsafe-inline'` 不可省：Naive UI css-render 运行时注入 `<style>` + Vue 设 element.style。
- `script-src` 不加 `'unsafe-inline'`：关 polyfill 后无内联 script，强制外联，最大化 XSS 防护。
- 无浏览器环境无法做运行时 console 验证，靠 build 产物静态分析 + 策略审查兜底。
