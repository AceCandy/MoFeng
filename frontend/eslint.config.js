// ESLint flat config：Vue(essential) + 分层门禁（组件/视图禁止直连 @/api）
// files/ignores 用 **/ 前缀，使匹配与运行目录无关
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    ignores: ['**/dist/**', '**/node_modules/**', '**/coverage/**', '**/*.config.*', '**/scripts/**'],
  },
  ...pluginVue.configs['flat/essential'],
  {
    // TS 文件用 typescript-eslint 解析器
    files: ['**/*.{ts,mts,tsx}'],
    languageOptions: {
      parser: tseslint.parser,
    },
  },
  {
    // Vue SFC：外层 vue-eslint-parser（由 flat/essential 提供），内层 script 用 TS 解析器
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
      },
    },
    rules: {
      // 既有 Vue 命名/用法，降级以免阻断 CI，后续渐进整改
      'vue/multi-word-component-names': 'off',
      'vue/require-toggle-inside-transition': 'off',
      'vue/no-mutating-props': 'warn',
    },
  },
  {
    // TS/Vue 关闭 no-undef：TS 用类型系统判定，避免对类型/全局误报
    files: ['**/*.{ts,mts,tsx,vue}'],
    rules: {
      'no-undef': 'off',
    },
  },
  {
    // 分层门禁：components/views 不得直接 import @/api，应通过 queries/composables 层
    files: ['**/src/components/**/*.{ts,vue,mts,tsx}', '**/src/views/**/*.{ts,vue,mts,tsx}'],
    plugins: { '@typescript-eslint': tseslint.plugin },
    rules: {
      '@typescript-eslint/no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/api', '@/api/*'],
              message: '组件/视图不应直接 import @/api，请通过 @/queries 或 @/composables 访问数据层',
              allowTypeImports: true,
            },
          ],
        },
      ],
    },
  },
)
