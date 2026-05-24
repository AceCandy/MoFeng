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

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

const frontendHost = process.env.FRONTEND_HOST || '0.0.0.0'
const frontendPort = Number(process.env.FRONTEND_PORT || '5173')
const frontendHmrHost = process.env.FRONTEND_HMR_HOST || 'localhost'
const frontendAllowedHosts = (process.env.FRONTEND_ALLOWED_HOSTS || 'test.acecandy.cn')
  .split(',')
  .map(host => host.trim())
  .filter(Boolean)
const backendProxyHost = process.env.BACKEND_PROXY_HOST || '127.0.0.1'
const backendPort = Number(process.env.BACKEND_PORT || '8000')
const isProduction = process.env.NODE_ENV === 'production'
const enableVueDevTools = !isProduction && process.env.VITE_ENABLE_VUE_DEVTOOLS === 'true'

const naiveUiCoreModuleNames = new Set([
  '_internal',
  '_mixins',
  '_utils',
  '_styles',
  '_locales',
  'styles',
  'config-provider',
])

const vendorChunks: Array<[string, string[]]> = [
  ['vue-core', ['vue', 'vue-router', 'pinia', '@vue']],
  ['naive-ui-support', ['@css-render', 'css-render', 'vueuc', 'vdirs', 'vooks', 'evtd', 'seemly', 'treemate', 'date-fns', 'async-validator']],
  ['chart-tools', ['chart.js']],
  ['markdown-tools', ['marked', 'dompurify']],
]

const normalizeChunkName = (name: string): string =>
  name.replace(/[^a-z0-9-_]/gi, '-')

const resolveNaiveUiChunk = (id: string): string | undefined => {
  const naiveUiPathMarker = '/node_modules/naive-ui/es/'
  if (!id.includes(naiveUiPathMarker)) {
    return undefined
  }

  const naiveUiPath = id.split(naiveUiPathMarker)[1]
  if (!naiveUiPath) {
    return 'naive-ui-core'
  }

  const moduleName = naiveUiPath.split('/')[0]
  if (!moduleName) {
    return 'naive-ui-core'
  }

  // Naive UI 内部能力聚合到 core，其余按组件目录拆分。
  if (moduleName.startsWith('_') || naiveUiCoreModuleNames.has(moduleName)) {
    return 'naive-ui-core'
  }

  if (moduleName === 'legacy-grid') {
    return 'naive-ui-grid'
  }

  return `naive-ui-${normalizeChunkName(moduleName)}`
}

const resolveVendorChunk = (id: string) => {
  if (!id.includes('/node_modules/')) {
    return undefined
  }

  const naiveUiChunk = resolveNaiveUiChunk(id)
  if (naiveUiChunk) {
    return naiveUiChunk
  }

  for (const [chunkName, packages] of vendorChunks) {
    if (packages.some(packageName => id.includes(`/node_modules/${packageName}/`))) {
      return chunkName
    }
  }

  return 'vendor'
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    enableVueDevTools && vueDevTools(),
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
    rollupOptions: {
      output: {
        manualChunks: resolveVendorChunk,
      },
    },
  },
})
