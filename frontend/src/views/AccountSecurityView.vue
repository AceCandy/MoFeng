<!-- AIMETA P=账户安全页_登录密码|R=账户安全宿主|NR=不含认证接口实现|E=route:/account/security#component:AccountSecurityView|X=ui|A=账户页|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="app-page account-security-page">
    <header class="account-security-page__header">
      <h1>账户与安全</h1>
      <p>更新登录密码，保护你的创作资料。</p>
    </header>
    <PasswordManagement />
  </div>
</template>

<script setup lang="ts">
import PasswordManagement from '@/components/admin/PasswordManagement.vue'
</script>

<style scoped>
.account-security-page {
  display: grid;
  gap: var(--md-spacing-6);
  width: min(100%, 720px);
  margin: 0 auto;
  padding: clamp(28px, 4vw, 60px);
}

.account-security-page__header {
  padding-bottom: var(--md-spacing-4);
  border-bottom: 1px solid var(--md-outline-variant);
}

.account-security-page__header h1 {
  margin: 0;
  color: var(--md-on-surface);
  font-family: var(--md-font-display);
  font-size: clamp(2rem, 4vw, 3rem);
  line-height: 1.1;
}

.account-security-page__header p {
  margin: var(--md-spacing-3) 0 0;
  color: var(--md-on-surface-variant);
}

@media (max-width: 600px) {
  .account-security-page {
    padding: var(--md-spacing-5) var(--md-spacing-4);
  }
}
</style>
