// AIMETA P=Vite配置_构建和开发服务器配置|R=构建配置_代理配置|NR=不含业务逻辑|E=-|X=internal|A=Vite配置|D=vite|S=fs|RD=./README.ai
if (typeof globalThis.localStorage === 'undefined' || !globalThis.localStorage || typeof globalThis.localStorage.getItem !== 'function') {
  // @ts-ignore
  globalThis.localStorage = {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
    clear: () => {},
    key: () => null,
    length: 0
  }
}
import { fileURLToPath, URL } from 'node:url'

import { defineConfig, type UserConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'

const frontendHost = process.env.FRONTEND_HOST || '0.0.0.0'
const frontendPort = Number(process.env.FRONTEND_PORT || '6100')
const frontendHmrHost = process.env.FRONTEND_HMR_HOST || 'localhost'
const rawAllowedHosts = process.env.FRONTEND_ALLOWED_HOSTS
// 设为 true（不区分大小写）时禁用 Host 校验，方便远程/workspace 端口转发（如 cmux）访问
const frontendAllowedHosts =
  rawAllowedHosts && rawAllowedHosts.trim().toLowerCase() === 'true'
    ? true
    : (rawAllowedHosts || 'test.acecandy.cn')
        .split(',')
        .map(host => host.trim())
        .filter(Boolean)
const backendProxyHost = process.env.BACKEND_PROXY_HOST || '127.0.0.1'
const backendPort = Number(process.env.BACKEND_PORT || '6101')
const isProduction = process.env.NODE_ENV === 'production'
const enableVueDevTools = !isProduction && process.env.VITE_ENABLE_VUE_DEVTOOLS === 'true'

const vendorChunks: Array<[string, string[]]> = [
  ['vue-core', ['vue', 'vue-router', 'pinia', '@vue']],
  ['naive-ui-support', ['@css-render', 'css-render', 'vueuc', 'vdirs', 'vooks', 'evtd', 'seemly', 'treemate', 'date-fns', 'async-validator']],
  ['markdown-tools', ['marked', 'dompurify']],
  // 描红界格编辑器内核（TipTap + ProseMirror）：独立分包，仅写作台路由的异步弹窗引用时加载，
  // 登录/工作台/灵感等首屏不为编辑器付费。预算基线已经 build:budget 环境变量同步上调。
  ['tiptap-editor', ['@tiptap', 'prosemirror']],
]

const resolveVendorChunk = (id: string): string | undefined => {
  if (!id.includes('/node_modules/')) {
    return undefined
  }

  if (id.includes('/node_modules/naive-ui/')) {
    return undefined
  }

  for (const [chunkName, packages] of vendorChunks) {
    if (packages.some(packageName => id.includes(`/node_modules/${packageName}/`))) {
      return chunkName
    }
  }

  return 'vendor'
}

const loadVueDevToolsPlugin = async () => {
  if (!enableVueDevTools) {
    return []
  }

  // Node 25 会暴露不完整的 localStorage 对象，DevTools 包必须在上方 shim 完成后再加载。
  const { default: vueDevTools } = await import('vite-plugin-vue-devtools')
  return [vueDevTools()]
}

// https://vitejs.dev/config/
export default defineConfig(async (): Promise<UserConfig> => {
  const vueDevToolsPlugin = await loadVueDevToolsPlugin()

  return {
    plugins: [
      vue(),
      vueJsx(),
      ...vueDevToolsPlugin,
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
    server: {
      host: frontendHost,
      port: frontendPort,
      strictPort: true,
      allowedHosts: frontendAllowedHosts,
      hmr: {
        protocol: 'ws',
        host: frontendHmrHost,
        port: frontendPort,
        clientPort: frontendPort,
      },
      proxy: {
        '/api': {
          target: `http://${backendProxyHost}:${backendPort}`,
          changeOrigin: true,
        }
      }
    },
    build: {
      manifest: true,
      modulePreload: { polyfill: false },
      rollupOptions: {
        output: {
          manualChunks: resolveVendorChunk,
        },
      }
    },
  }
})
