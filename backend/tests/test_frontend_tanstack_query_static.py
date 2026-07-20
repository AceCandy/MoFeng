from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"
FRONTEND_SRC = FRONTEND_ROOT / "src"


def _source(path: str) -> str:
    return (FRONTEND_SRC / path).read_text(encoding="utf-8")


def _composables_source(pattern: str) -> str:
    """读取匹配的 composable 源码拼接（#22 重构后 query/mutation 下沉到 composable）。"""
    parts = []
    for path in sorted(FRONTEND_SRC.glob(pattern)):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _package_source() -> str:
    return (FRONTEND_ROOT / "package.json").read_text(encoding="utf-8")


def test_vue_query_is_installed_and_registered_with_shared_client():
    package_json = _package_source()
    main_ts = _source("main.ts")
    query_client = _source("lib/queryClient.ts")

    assert '"@tanstack/vue-query"' in package_json
    assert "VueQueryPlugin" in main_ts
    assert "queryClient" in main_ts
    assert "app.use(VueQueryPlugin, { queryClient })" in main_ts
    assert "new QueryClient" in query_client
    assert "retry: shouldRetryQuery" in query_client
    assert "refetchOnWindowFocus: false" in query_client


def test_novel_queries_own_server_state_keys_and_refresh_paths():
    source = _source("queries/novel.ts")

    for text in [
        "useQuery",
        "useMutation",
        "useQueryClient",
        "novelQueryKeys",
        "projects: () => [...novelQueryKeys.all, 'projects']",
        "detail: (projectId: string) => [...novelQueryKeys.all, 'detail', projectId]",
        "chapter: (projectId: string, chapterNumber: number)",
        "useNovelProjectsQuery",
        "useNovelProjectQuery",
        "useNovelChapterQuery",
        "useCreateNovelMutation",
        "useDeleteNovelsMutation",
        "useImportNovelMutation",
        "useConverseConceptStreamMutation",
        "useGenerateBlueprintMutation",
        "useSaveBlueprintMutation",
        "useUpdateBlueprintMutation",
        "useNovelSectionQuery",
        "useNovelChapterDetailQuery",
        "useEmotionCurveQuery",
        "useAnalyzeEmotionMutation",
        "useForeshadowingQuery",
        "invalidateQueries",
    ]:
        assert text in source


def test_workspace_reads_query_loading_error_and_refetch_state():
    source = _source("views/NovelWorkspace.vue")

    for text in [
        "useNovelProjectsQuery",
        "useDeleteNovelsMutation",
        "useImportNovelMutation",
        "projectsQuery",
        "projectsLoading",
        "projectsError",
        "projectsQuery.refetch()",
    ]:
        assert text in source

    assert "novelStore.loadProjects" not in source
    assert "novelStore.projects" not in source
    assert "NovelAPI.importNovel" not in source


def test_writing_desk_reads_project_and_chapter_through_query_cache():
    source = _source("views/WritingDesk.vue") + "\n" + _composables_source("composables/useWritingDesk*.ts")

    for text in [
        "useNovelProjectQuery",
        "useNovelChapterQuery",
        "useNovelMutationRefresh",
        "projectQuery",
        "chapterQuery",
        "refreshProjectQueries",
        "chapterQuery.refetch()",
    ]:
        assert text in source

    assert "novelStore.loadProject" not in source
    assert "novelStore.loadChapter" not in source


def test_inspiration_flow_uses_query_mutations_and_local_conversation_state():
    source = _source("views/InspirationMode.vue")
    confirmation = _source("components/BlueprintConfirmation.vue")

    for text in [
        "useCreateNovelMutation",
        "useNovelProjectQuery",
        "useConverseConceptStreamMutation",
        "useGenerateBlueprintMutation",
        "useSaveBlueprintMutation",
        "currentConversationState",
        "currentProject",
    ]:
        assert text in source

    for removed in [
        "useNovelStore",
        "novelStore.",
        "novelStore.isLoading",
        "novelStore.currentProject",
    ]:
        assert removed not in source

    assert "useGenerateBlueprintMutation" in confirmation
    assert "useNovelStore" not in confirmation
    assert "novelStore." not in confirmation


def test_inspiration_stream_unblocks_input_before_background_cache_refresh():
    query_source = _source("queries/novel.ts")
    stream_source = _source("api/novel.ts")

    converse_block = query_source.split("export function useConverseConceptStreamMutation", 1)[1].split(
        "export function useGenerateBlueprintMutation",
        1,
    )[0]

    assert "void refreshProjectQueries().catch" in converse_block
    assert "await refreshProjectQueries()" not in converse_block
    assert "return finishWithFinal(message.data as T)" in stream_source
    assert "final 事件已经包含下一轮输入控件" in stream_source


def test_http_errors_keep_payload_for_inspiration_conflict_redirect():
    # HttpRequestError 下沉到 @/utils/errors，确认 payload 字段保留 + http.ts 仍传递 payload
    errors_source = _source("utils/errors.ts")
    http_source = _source("api/http.ts")

    assert "payload: unknown" in errors_source
    assert "this.payload = options.payload" in errors_source
    assert "payload," in http_source


def test_detail_shell_uses_query_project_cache_for_editing_paths():
    source = _source("components/shared/NovelDetailShell.vue") + "\n" + _composables_source("composables/useShell*.ts")

    for text in [
        "useNovelProjectQuery",
        "useNovelSectionQuery",
        "useUpdateBlueprintMutation",
        "projectQuery",
        "sectionQuery",
        "overviewQuery",
        "updateBlueprintMutation",
    ]:
        assert text in source

    for removed in [
        "AdminAPI",
        "NovelAPI",
        "useNovelStore",
        "novelStore.",
        "novelStore.currentProject",
        "novelStore.loadProject",
        "novelStore.setCurrentProject",
        "sectionLoading = reactive",
        "sectionError = reactive",
    ]:
        assert removed not in source


def test_detail_subsections_use_query_cache_for_loading_error_and_refresh():
    chapters = _source("components/novel-detail/ChaptersSection.vue")
    emotion = _source("components/novel-detail/EmotionCurveSection.vue")
    foreshadowing = _source("components/novel-detail/ForeshadowingSection.vue")

    for text in [
        "useNovelChapterDetailQuery",
        "chapterQuery",
        "chapterQuery.refetch()",
    ]:
        assert text in chapters

    for removed in [
        "AdminAPI",
        "NovelAPI",
        "chapterCache = new Map",
        "isLoading = ref(false)",
        "error = ref<string | null>(null)",
    ]:
        assert removed not in chapters

    for text in [
        "useEmotionCurveQuery",
        "useAnalyzeEmotionMutation",
        "emotionQuery",
        "analyzeEmotionMutation",
        "emotionQuery.refetch()",
    ]:
        assert text in emotion

    for removed in [
        "useAuthStore",
        "await fetch(",
        "isLoading = ref(false)",
        "error = ref<string | null>(null)",
    ]:
        assert removed not in emotion

    for text in [
        "useForeshadowingQuery",
        "foreshadowingQuery",
        "foreshadowingQuery.refetch()",
    ]:
        assert text in foreshadowing

    for removed in [
        "useAuthStore",
        "await fetch(",
        "isLoading = ref(false)",
        "error = ref<string | null>(null)",
    ]:
        assert removed not in foreshadowing


def test_admin_queries_own_server_state_and_invalidation():
    source = _source("queries/admin.ts")

    for text in [
        "useQuery",
        "useMutation",
        "useQueryClient",
        "adminQueryKeys",
        "useAdminStatisticsQuery",
        "useAdminUsersQuery",
        "useCreateAdminUserMutation",
        "useUpdateAdminUserMutation",
        "useDeleteAdminUserMutation",
        "useAdminNovelsQuery",
        "useAdminPromptsQuery",
        "useAdminUpdateLogsQuery",
        "useSystemConfigsQuery",
        "useUpsertSystemConfigMutation",
        "usePatchSystemConfigMutation",
        "useDeleteSystemConfigMutation",
        "useChangePasswordMutation",
        "invalidateQueries",
    ]:
        assert text in source


def test_admin_components_use_query_state_instead_of_direct_admin_api_calls():
    component_expectations = {
        "components/admin/Statistics.vue": [
            "useAdminStatisticsQuery",
            "statisticsQuery",
            "statisticsQuery.refetch()",
        ],
        "components/admin/NovelManagement.vue": [
            "useAdminNovelsQuery",
            "novelsQuery",
            "novelsQuery.refetch()",
        ],
        "components/admin/UserManagement.vue": [
            "useAdminUsersQuery",
            "useCreateAdminUserMutation",
            "useUpdateAdminUserMutation",
            "useDeleteAdminUserMutation",
        ],
        "components/admin/PromptManagement.vue": [
            "useAdminPromptsQuery",
            "useCreateAdminPromptMutation",
            "useUpdateAdminPromptMutation",
            "useDeleteAdminPromptMutation",
        ],
        "components/admin/UpdateLogManagement.vue": [
            "useAdminUpdateLogsQuery",
            "useCreateAdminUpdateLogMutation",
            "useUpdateAdminUpdateLogMutation",
            "useDeleteAdminUpdateLogMutation",
        ],
        "components/admin/SettingsManagement.vue": [
            "useSystemConfigsQuery",
            "useUpsertSystemConfigMutation",
            "usePatchSystemConfigMutation",
            "useDeleteSystemConfigMutation",
            "useRemoteVersionQuery",
        ],
        "components/admin/PasswordManagement.vue": [
            "useChangePasswordMutation",
            "changePasswordMutation",
        ],
    }

    for path, required_texts in component_expectations.items():
        source = _source(path)
        for text in required_texts:
            assert text in source, f"{path}: 缺少 {text}"
        assert "AdminAPI." not in source


def test_llm_queries_own_model_routing_server_state_and_mutations():
    source = _source("queries/llm.ts")

    for text in [
        "useQuery",
        "useMutation",
        "useQueryClient",
        "llmQueryKeys",
        "useLLMConfigBundleQuery",
        "useProviderModelsQuery",
        "useSaveProviderMutation",
        "useToggleProviderMutation",
        "useDeleteProviderMutation",
        "useSaveUserModelMutation",
        "useUpdateUserModelMutation",
        "useDeleteUserModelMutation",
        "useSaveStageRoutesMutation",
        "invalidateQueries",
    ]:
        assert text in source


def test_personal_model_routing_uses_query_cache_for_bundle_and_mutations():
    source = _source("components/llm-settings/PersonalModelRouting.vue") + "\n" + _composables_source("composables/useModelBundle.ts") + "\n" + _composables_source("components/llm-settings/use*.ts")

    for text in [
        "@/queries/llm",
        "useLLMConfigBundleQuery",
        "useProviderModelsQuery",
        "useSaveProviderMutation",
        "useToggleProviderMutation",
        "useDeleteProviderMutation",
        "useSaveUserModelMutation",
        "useUpdateUserModelMutation",
        "useDeleteUserModelMutation",
        "useSaveStageRoutesMutation",
        "bundleQuery",
        "bundleQuery.refetch()",
    ]:
        assert text in source

    for removed in [
        "getLLMConfigBundle()",
        "await createProvider(",
        "await updateProvider(",
        "await deleteProvider(",
        "await getProviderModels(",
        "await createUserModel(",
        "await updateUserModel(",
        "await deleteUserModel(",
        "await saveStageRoutes(",
        "isLoading = ref(false)",
    ]:
        assert removed not in source


def test_inspiration_model_readiness_uses_llm_query_cache():
    source = _source("views/InspirationMode.vue")

    for text in [
        "useLLMConfigBundleQuery",
        "llmConfigBundleQuery",
        "llmConfigBundleQuery.refetch()",
    ]:
        assert text in source

    assert "getLLMConfigBundle" not in source


def test_optimizer_requests_are_mutations_not_direct_api_calls():
    query_source = _source("queries/novel.ts")
    writing_desk = _source("views/WritingDesk.vue") + "\n" + _composables_source("composables/useWritingDeskOptimize.ts")
    chapter_content = _source("components/writing-desk/workspace/ChapterContent.vue")

    for text in [
        "useOptimizeChapterMutation",
        "useOptimizeRecommendedVersionMutation",
        "useApplyOptimizationMutation",
    ]:
        assert text in query_source

    for source in [writing_desk, chapter_content]:
        assert "OptimizerAPI" not in source

    for text in [
        "useOptimizeRecommendedVersionMutation",
        "useApplyOptimizationMutation",
        "optimizeRecommendedVersionMutation",
        "applyOptimizationMutation",
    ]:
        assert text in writing_desk

    for text in [
        "useOptimizeChapterMutation",
        "useApplyOptimizationMutation",
        "optimizeChapterMutation",
        "applyOptimizationMutation",
    ]:
        assert text in chapter_content


def test_novel_pinia_store_no_longer_owns_server_state_or_api_calls():
    source = _source("stores/novel.ts")

    for removed in [
        "@/api/novel",
        "NovelAPI",
        "projects = ref",
        "currentProject = ref",
        "isLoading = ref",
        "error = ref",
        "loadProjects",
        "loadProject",
        "loadChapter",
        "createProject",
        "generateBlueprint",
        "saveBlueprint",
        "deleteProjects",
        "setCurrentProject",
    ]:
        assert removed not in source


def test_auth_queries_own_auth_requests_and_cache_keys():
    source = _source("queries/auth.ts")

    for text in [
        "useQuery",
        "useMutation",
        "useQueryClient",
        "authQueryKeys",
        "authOptionsQueryOptions",
        "currentUserQueryOptions",
        "useAuthOptionsQuery",
        "useLoginMutation",
        "useSendVerificationCodeMutation",
        "useRegisterMutation",
        "queryClient.setQueryData(authQueryKeys.currentUser(), user)",
        "authStore.setSession",
    ]:
        assert text in source


def test_auth_store_keeps_only_client_session_state():
    source = _source("stores/auth.ts")

    for text in [
        "setToken",
        "setUser",
        "setSession",
        "logout",
        "isAuthenticated",
        "mustChangePassword",
    ]:
        assert text in source

    for removed in [
        "fetch(",
        "fetchWithAuth",
        "API_BASE_URL",
        "authOptions",
        "authOptionsLoaded",
        "allowRegistration",
        "enableLinuxdoLogin",
        "fetchAuthOptions",
        "fetchUser",
        "async login",
        "async register",
    ]:
        assert removed not in source


def test_login_and_register_pages_use_auth_queries_not_store_requests():
    login = _source("views/Login.vue")
    register = _source("views/Register.vue")

    for text in [
        "useAuthOptionsQuery",
        "useLoginMutation",
        "authOptionsQuery",
        "loginMutation",
    ]:
        assert text in login

    for removed in [
        "authStore.fetchAuthOptions",
        "authStore.login",
        "const isLoading = ref(false)",
    ]:
        assert removed not in login

    for text in [
        "useAuthOptionsQuery",
        "useSendVerificationCodeMutation",
        "useRegisterMutation",
        "authOptionsQuery",
        "sendCodeMutation",
        "registerMutation",
    ]:
        assert text in register

    for removed in [
        "fetch(",
        "authStore.fetchAuthOptions",
        "authStore.register",
        "const sending = ref(false)",
        "const isRegistering = ref(false)",
    ]:
        assert removed not in register


def test_session_restore_uses_query_client_fetch_query():
    main_ts = _source("main.ts")
    router = _source("router/index.ts")
    password = _source("components/admin/PasswordManagement.vue")

    for source in [main_ts, router, password]:
        assert "currentUserQueryOptions" in source
        assert "queryClient.fetchQuery" in source
        assert ".fetchUser(" not in source

    assert "authStore.setToken(token)" in main_ts
