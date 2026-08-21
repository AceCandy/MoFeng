// AIMETA P=Vite配置启动测试|R=localStorage兼容_DevTools配置加载|NR=不测试业务页面|E=test:config:vite|X=internal|A=vite-config|D=vitest,vite,node-child-process|S=test|RD=../../README.ai
import { execFileSync } from 'node:child_process'

import { describe, expect, it } from 'vitest'

describe('vite config startup contracts', () => {
  it('loads Vue DevTools with an incomplete Node localStorage', () => {
    const output = execFileSync(process.execPath, ['--input-type=module', '--eval', `
      globalThis.localStorage = {}
      const { loadConfigFromFile } = await import('vite')
      const loaded = await loadConfigFromFile(
        { command: 'serve', mode: 'test', isSsrBuild: false, isPreview: false },
        'vite.config.ts',
        process.cwd(),
      )
      if (!loaded || typeof globalThis.localStorage.getItem !== 'function') {
        throw new Error('Vite config did not install the localStorage shim')
      }
      const pluginNames = loaded.config.plugins
        ?.flat(Infinity)
        .map(plugin => plugin && typeof plugin === 'object' ? plugin.name : null)
      if (!pluginNames?.includes('vite-plugin-vue-devtools')) {
        throw new Error('Vue DevTools plugin was not loaded')
      }
      process.stdout.write('loaded')
    `], {
      cwd: process.cwd(),
      encoding: 'utf8',
      env: {
        ...process.env,
        NODE_ENV: 'development',
        VITE_ENABLE_VUE_DEVTOOLS: 'true',
      },
    })

    expect(output).toBe('loaded')
  })
})
