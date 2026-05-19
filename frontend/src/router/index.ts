// AIMETA P=路由配置_所有页面路由定义|R=路由表_导航守卫_权限控制|NR=不含组件实现|E=router:index|X=internal|A=router实例|D=vue-router|S=none|RD=./README.ai
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { queryClient } from '@/lib/queryClient'
import { currentUserQueryOptions } from '@/queries/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'workspace-entry',
      redirect: '/workspace',
      meta: { requiresAuth: true, layout: 'app' },
    },
    {
      path: '/workspace',
      name: 'novel-workspace',
      component: () => import('../views/NovelWorkspace.vue'),
      meta: {
        requiresAuth: true,
        layout: 'app',
        label: '工作台',
        description: '继续最近项目，查看创作进度，并进入新项目流程。',
      },
    },
    {
      path: '/inspiration',
      name: 'inspiration-mode',
      component: () => import('../views/InspirationMode.vue'),
      meta: {
        requiresAuth: true,
        layout: 'app',
        label: '灵感',
        description: '通过对话整理世界观、角色和故事蓝图。',
      },
    },
    {
      path: '/projects/:id',
      name: 'project-detail',
      component: () => import('../views/NovelDetail.vue'),
      props: true,
      meta: {
        requiresAuth: true,
        layout: 'app',
        label: '小说档案',
        description: '查看项目设定、角色、章节、伏笔和分析材料。',
      },
    },
    {
      path: '/projects/:id/write',
      name: 'project-write',
      component: () => import('../views/WritingDesk.vue'),
      props: true,
      meta: {
        requiresAuth: true,
        layout: 'app',
        label: '写作台',
        description: '生成章节、评审版本，并维护当前正文。',
      },
    },
    {
      path: '/detail/:id',
      redirect: (to) => `/projects/${to.params.id}`,
    },
    {
      path: '/novel/:id',
      redirect: (to) => `/projects/${to.params.id}/write`,
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/Login.vue'),
      meta: { layout: 'auth' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/Register.vue'),
      meta: { layout: 'auth' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: {
        requiresAuth: true,
        requiresAdmin: true,
        layout: 'app',
        label: '管理',
        description: '维护用户、提示词、项目、更新日志和系统配置。',
      },
    },
    {
      path: '/admin/novels/:id',
      name: 'admin-project-detail',
      component: () => import('../views/AdminNovelDetail.vue'),
      props: true,
      meta: {
        requiresAuth: true,
        requiresAdmin: true,
        layout: 'app',
        label: '管理档案',
        description: '以管理员身份查看小说项目材料。',
      },
    },
    {
      path: '/admin/novel/:id',
      redirect: (to) => `/admin/novels/${to.params.id}`,
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
      meta: {
        requiresAuth: true,
        layout: 'app',
        label: '模型设置',
        description: '配置个人 LLM、向量模型和 AI 阶段路由。',
      },
    },
  ],
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // 有 token 但缺少用户信息时，通过 Query 缓存恢复会话。
  if (authStore.token && !authStore.user) {
    try {
      const user = await queryClient.fetchQuery(currentUserQueryOptions(authStore.token))
      authStore.setUser(user)
    } catch {
      // 登录态恢复失败时交由后续守卫重定向，避免产品界面产生控制台噪声。
      authStore.logout()
    }
  }

  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  const requiresAdmin = to.matched.some((record) => record.meta.requiresAdmin)
  const isAuthenticated = authStore.isAuthenticated
  const isAdmin = authStore.user?.is_admin

  const mustChangePassword = authStore.user?.is_admin && authStore.mustChangePassword

  if (requiresAuth && !isAuthenticated) {
    next('/login')
  } else if (requiresAdmin && !isAdmin) {
    next('/workspace') // Redirect to a non-admin page if not an admin
  } else if (isAuthenticated && mustChangePassword) {
    if (to.name !== 'admin' || to.query.tab !== 'password') {
      next({ name: 'admin', query: { tab: 'password' } })
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
