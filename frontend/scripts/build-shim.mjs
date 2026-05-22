// scripts/build-shim.mjs
// 前置注入全球 localStorage 浏览器环境 mock，防止 devtools 静态分析求值报错
globalThis.localStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {},
  clear: () => {},
  key: () => null,
  length: 0
};

// 使用物理路径相对导入 vite cli 脚本，完美绕过 Node package.json exports 模块沙箱限制
import('../node_modules/vite/bin/vite.js');
