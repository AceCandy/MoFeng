<!-- AIMETA P=墨风编辑器_描红界格编辑器内核|R=编辑器_描红落墨|NR=不含数据请求|E=component:MofengEditor|X=internal|A=编辑器组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div
    class="mofeng-editor"
    :class="{ 'mofeng-editor--readonly': readonly }"
    :data-provenance="provenance"
  >
    <!-- 落墨工具条：仅 AI 描红稿的可编辑态、且仍有描红段落时出现 -->
    <div v-if="showLuomoTools" class="mofeng-editor__toolbar">
      <span class="mofeng-editor__toolbar-hint">
        描红稿 · 待落墨 {{ miaohongParagraphCount }} 段
      </span>
      <button
        type="button"
        class="mofeng-editor__seal-btn"
        aria-label="全文落墨"
        @click="luomoAll"
      >
        全文落墨
      </button>
    </div>

    <div
      ref="surfaceRef"
      class="mofeng-editor__surface"
      @mouseover="handleSurfaceMouseOver"
      @mouseleave="handleSurfaceMouseLeave"
    >
      <!-- 段级界格 gutter:hover 描红段落时出现该段的「落墨」小按钮 -->
      <div v-if="showLuomoTools" class="mofeng-editor__gutter">
        <div
          v-for="row in visibleGutterRows"
          :key="row.index"
          class="mofeng-editor__gutter-row"
          :data-paragraph-index="row.index"
          :style="{ top: `${row.top}px`, height: `${row.height}px` }"
        >
          <button
            type="button"
            class="mofeng-editor__gutter-btn"
            :class="{ 'is-visible': hoveredParagraphIndex === row.index }"
            :aria-label="`落墨第 ${row.index + 1} 段`"
            @click="luomoParagraph(row.index)"
          >
            落墨
          </button>
        </div>
      </div>

      <!-- 方格稿纸行笺:repeating-linear-gradient 行线 + 左右朱丝栏 + 熟宣底(规格 §3) -->
      <div class="mofeng-editor__paper" @click.self="focusEditor">
        <div v-if="showPlaceholder" class="mofeng-editor__placeholder">{{ placeholder }}</div>
        <EditorContent :editor="editor" class="mofeng-editor__content-host" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Document } from '@tiptap/extension-document'
import { HardBreak } from '@tiptap/extension-hard-break'
import { Paragraph } from '@tiptap/extension-paragraph'
import { Text } from '@tiptap/extension-text'
import { UndoRedo } from '@tiptap/extensions'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import type { Editor, JSONContent } from '@tiptap/core'
import type { Node as PMNode } from '@tiptap/pm/model'
import { MiaohongMark } from './miaohongMark'

const MIAOHONG_MARK_NAME = 'miaohong'

/**
 * 纯文本 → TipTap 文档 JSON。
 *
 * 往返无损策略(与 ChapterContent 的按换行分段兼容):
 * - 段落间只认「恰好两个 \n」为分隔,段内单个 \n 映射为 hardBreak;
 *   序列化时段落以 \n\n 连接、hardBreak 还原为 \n,二者构成双射,
 *   打开不编辑直接保存时文本与原值逐字相等。
 * - 载入时归一 \r\n? → \n,并对全文首尾 trim(序列化同样 trim,
 *   首尾空白差异按任务约定抹平);段内空白逐字保留。
 * - markAllMiaohong 时全文文字挂 miaohong mark(AI 描红稿载入)。
 */
const textToDocJSON = (raw: string, markAllMiaohong: boolean): JSONContent => {
  const text = (raw ?? '').replace(/\r\n?/g, '\n').trim()
  if (!text) return { type: 'doc', content: [{ type: 'paragraph' }] }

  const marks: JSONContent['marks'] = markAllMiaohong ? [{ type: MIAOHONG_MARK_NAME }] : undefined
  return {
    type: 'doc',
    content: text.split('\n\n').map((chunk) => {
      const inline: JSONContent[] = []
      chunk.split('\n').forEach((line, lineIndex) => {
        if (lineIndex > 0) inline.push({ type: 'hardBreak' })
        if (line) inline.push(marks ? { type: 'text', text: line, marks } : { type: 'text', text: line })
      })
      return inline.length > 0 ? { type: 'paragraph', content: inline } : { type: 'paragraph' }
    }),
  }
}

/** TipTap 文档 → 纯文本(textToDocJSON 的逆映射,见上方的无损策略说明)。 */
const docToPlainText = (doc: PMNode): string => {
  const paragraphs: string[] = []
  doc.forEach((node) => {
    if (node.type.name !== 'paragraph') return
    let text = ''
    node.forEach((child) => {
      if (child.isText) text += child.text ?? ''
      else if (child.type.name === 'hardBreak') text += '\n'
    })
    paragraphs.push(text)
  })
  return paragraphs.join('\n\n').trim()
}

const paragraphHasMiaohong = (node: PMNode): boolean => {
  let found = false
  node.descendants((child) => {
    if (found) return false
    if (child.isText && child.marks.some((mark) => mark.type.name === MIAOHONG_MARK_NAME)) {
      found = true
      return false
    }
    return true
  })
  return found
}

interface GutterRow {
  index: number
  top: number
  height: number
  miaohong: boolean
}

interface Props {
  /** 纯文本,段落间 \n\n 连接 */
  modelValue: string
  /** 文本出处:'ai' 时全文以描红 mark 载入,默认 'ink'(作家正文) */
  provenance?: 'ink' | 'ai'
  placeholder?: string
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  provenance: 'ink',
  placeholder: '',
  readonly: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  /** 描红段落数变化(含挂载后的首次统计) */
  'luomo-stats': [miaohongParagraphs: number]
}>()

const surfaceRef = ref<HTMLElement | null>(null)
const docText = ref('')
const lastSerialized = ref('')
const miaohongParagraphCount = ref(0)
const miaohongParagraphSet = ref<Set<number>>(new Set())
const gutterRows = ref<GutterRow[]>([])
const paragraphEls = ref<HTMLElement[]>([])
const hoveredParagraphIndex = ref<number | null>(null)

const showLuomoTools = computed(
  () => props.provenance === 'ai' && !props.readonly && miaohongParagraphCount.value > 0,
)
const visibleGutterRows = computed(() =>
  showLuomoTools.value ? gutterRows.value.filter((row) => row.miaohong) : [],
)
const showPlaceholder = computed(() => docText.value === '' && props.placeholder !== '')

const contentAriaLabel = props.readonly
  ? '只读文稿'
  : props.placeholder || '文稿编辑区'

const editor = useEditor({
  editable: !props.readonly,
  content: textToDocJSON(props.modelValue, props.provenance === 'ai'),
  extensions: [
    Document,
    Paragraph,
    Text,
    HardBreak,
    UndoRedo,
    MiaohongMark,
  ],
  editorProps: {
    attributes: {
      class: 'mofeng-editor__content',
      role: 'textbox',
      'aria-multiline': 'true',
      'aria-label': contentAriaLabel,
      ...(props.readonly ? { 'aria-readonly': 'true' } : {}),
    },
  },
  onCreate: ({ editor: instance }) => {
    const text = docToPlainText(instance.state.doc)
    docText.value = text
    lastSerialized.value = text
    syncMiaohongState(instance)
    scheduleLayoutRefresh()
  },
  onUpdate: ({ editor: instance }) => {
    const text = docToPlainText(instance.state.doc)
    lastSerialized.value = text
    docText.value = text
    emit('update:modelValue', text)
    syncMiaohongState(instance)
    scheduleLayoutRefresh()
  },
})

/** 重算描红段落集合与计数,计数变化时抛出 luomo-stats。 */
const syncMiaohongState = (instance: Editor) => {
  const marked = new Set<number>()
  instance.state.doc.forEach((node, _offset, index) => {
    if (node.type.name === 'paragraph' && paragraphHasMiaohong(node)) {
      marked.add(index)
    }
  })
  miaohongParagraphSet.value = marked
  if (marked.size !== miaohongParagraphCount.value) {
    miaohongParagraphCount.value = marked.size
    emit('luomo-stats', marked.size)
  }
}

// 外部 modelValue 变化时重建文档;自己 emit 回去的值(与 lastSerialized 相等)直接跳过,避免光标跳动
watch(
  () => props.modelValue,
  (value) => {
    const instance = editor.value
    if (!instance) return
    const next = value ?? ''
    if (next === lastSerialized.value) return
    // v3 setContent 默认 emitUpdate: true,必须显式关掉,否则会回环触发 update:modelValue
    instance.commands.setContent(textToDocJSON(next, props.provenance === 'ai'), {
      emitUpdate: false,
    })
    const text = docToPlainText(instance.state.doc)
    lastSerialized.value = text
    docText.value = text
    syncMiaohongState(instance)
    scheduleLayoutRefresh()
  },
)

watch(
  () => props.readonly,
  (readonly) => {
    const instance = editor.value
    if (!instance) return
    instance.setEditable(!readonly)
    if (readonly) {
      instance.view.dom.setAttribute('aria-readonly', 'true')
    } else {
      instance.view.dom.removeAttribute('aria-readonly')
    }
  },
)

// —— 段落布局(gutter 定位用):以表面容器为基准量取每个 <p> 的偏移 ——
// jsdom 等测试环境没有 requestAnimationFrame,回退 setTimeout
const nextFrame = (cb: () => void) => {
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(cb)
  } else {
    setTimeout(cb, 16)
  }
}

let layoutToken = 0

const scheduleLayoutRefresh = () => {
  const token = ++layoutToken
  void nextTick(() => {
    nextFrame(() => {
      if (token === layoutToken) refreshLayout()
    })
  })
}

const refreshLayout = () => {
  const instance = editor.value
  const surface = surfaceRef.value
  if (!instance || !surface) return
  const contentDom = instance.view.dom as HTMLElement
  const paragraphs = Array.from(contentDom.children).filter(
    (el): el is HTMLElement => el instanceof HTMLElement && el.tagName === 'P',
  )
  paragraphEls.value = paragraphs
  const surfaceRect = surface.getBoundingClientRect()
  gutterRows.value = paragraphs.map((el, index) => {
    const rect = el.getBoundingClientRect()
    return {
      index,
      top: rect.top - surfaceRect.top,
      height: rect.height,
      miaohong: miaohongParagraphSet.value.has(index),
    }
  })
}

onMounted(() => {
  scheduleLayoutRefresh()
  window.addEventListener('resize', scheduleLayoutRefresh)
})

onBeforeUnmount(() => {
  layoutToken += 1 // 使待执行的布局回调失效
  window.removeEventListener('resize', scheduleLayoutRefresh)
})

// —— hover 跟踪:hover 描红段落或其 gutter 行时亮出该段「落墨」按钮 ——
const handleSurfaceMouseOver = (event: MouseEvent) => {
  if (!showLuomoTools.value) return
  const target = event.target as HTMLElement | null
  if (!target) return
  const paragraph = target.closest('p')
  if (paragraph) {
    const index = paragraphEls.value.indexOf(paragraph as HTMLElement)
    if (index >= 0) hoveredParagraphIndex.value = index
    return
  }
  const row = target.closest<HTMLElement>('.mofeng-editor__gutter-row')
  if (row?.dataset.paragraphIndex != null) {
    hoveredParagraphIndex.value = Number(row.dataset.paragraphIndex)
  }
  // 落在稿纸留白区时保持当前 hover 不变,保证按钮可被移动到并点击
}

const handleSurfaceMouseLeave = () => {
  hoveredParagraphIndex.value = null
}

// —— 落墨:颜色/底纹/界栏过渡 220ms(规格 §4 要求 140–280ms),楷转宋允许瞬间切换 ——
const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

const removeMiaohongInRanges = (ranges: { from: number; to: number }[]) => {
  const instance = editor.value
  if (!instance) return
  const { state, view } = instance
  const markType = state.schema.marks[MIAOHONG_MARK_NAME]
  if (!markType) return
  const { tr } = state
  ranges.forEach(({ from, to }) => tr.removeMark(from, to, markType))
  if (tr.docChanged) view.dispatch(tr)
}

/**
 * 先给目标段落挂上过渡态 class(保持朱色/底纹/界栏),再移除 mark,
 * 两帧后撤掉 class,段落按 CSS transition 由朱转墨、界栏淡出。
 */
const withLuomoTransition = (els: (HTMLElement | undefined)[], apply: () => void) => {
  const targets = els.filter((el): el is HTMLElement => Boolean(el))
  if (prefersReducedMotion || targets.length === 0) {
    apply()
    return
  }
  targets.forEach((el) => el.classList.add('mofeng-p--luomoing'))
  apply()
  nextFrame(() => {
    nextFrame(() => {
      targets.forEach((el) => el.classList.remove('mofeng-p--luomoing'))
    })
  })
}

/** 去掉全部 miaohong mark(全文落墨)。 */
const luomoAll = () => {
  const instance = editor.value
  if (!instance || miaohongParagraphSet.value.size === 0) return
  const targets = [...miaohongParagraphSet.value].map((index) => paragraphEls.value[index])
  withLuomoTransition(targets, () => {
    removeMiaohongInRanges([{ from: 0, to: instance.state.doc.content.size }])
  })
}

/** 去掉指定段落的 miaohong mark(单段落墨)。 */
const luomoParagraph = (index: number) => {
  const instance = editor.value
  if (!instance || index < 0) return
  const ranges: { from: number; to: number }[] = []
  instance.state.doc.forEach((node, offset, nodeIndex) => {
    if (nodeIndex === index) {
      ranges.push({ from: offset + 1, to: offset + node.nodeSize - 1 })
    }
  })
  if (ranges.length === 0) return
  withLuomoTransition([paragraphEls.value[index]], () => {
    removeMiaohongInRanges(ranges)
  })
}

/** 当前仍带描红 mark 的段落数(实时从文档统计)。 */
const getMiaohongParagraphCount = (): number => {
  const instance = editor.value
  if (!instance) return 0
  let count = 0
  instance.state.doc.forEach((node) => {
    if (node.type.name === 'paragraph' && paragraphHasMiaohong(node)) count += 1
  })
  return count
}

const focusEditor = () => {
  if (props.readonly) return
  editor.value?.commands.focus('end')
}

defineExpose({ luomoAll, luomoParagraph, getMiaohongParagraphCount })
</script>

<style scoped>
.mofeng-editor {
  /* --paper-line = 正文行高(15px × 1.8 = 27px),稿纸行线与文字行共用此周期(规格 §3) */
  --paper-line: 27px;
  --mofeng-paper-pad-y: 14px;
  /* 全局 --md-font-kai 暂为宋体别名(tokens 代理注明楷体栈切换留给描红稿组件落地),
     在编辑器内核域内局部落地规格 §2 的真楷体栈,不影响未改造表面 */
  --md-font-kai: 'Kaiti SC', 'STKaiti', 'KaiTi', 'AR PL UKai CN', 'AR PL KaitiM GB', 'TW-Kai', serif;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* —— 落墨工具条 —— */
.mofeng-editor__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mofeng-editor__toolbar-hint {
  font-family: var(--md-font-kai);
  font-size: 12px;
  color: var(--md-miaohong, #b8402f);
}

/* 朱砂落印主按钮(规格 §5):方章微圆角 2px、朱砂底、熟宣字 */
.mofeng-editor__seal-btn {
  border: none;
  border-radius: 2px;
  background-color: var(--md-miaohong, #b8402f);
  color: var(--md-surface);
  font-family: var(--md-font-serif);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-indent: 0.12em;
  padding: 8px 16px;
  cursor: pointer;
  transition:
    background-color 140ms var(--md-easing-standard),
    transform 140ms var(--md-easing-standard);
}

.mofeng-editor__seal-btn:hover:not(:disabled) {
  background-color: var(--md-miaohong-strong, #9c3323);
}

.mofeng-editor__seal-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.mofeng-editor__seal-btn:focus-visible {
  outline: 1px solid var(--md-luomo, var(--md-on-surface));
  outline-offset: 2px;
}

.mofeng-editor__seal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* —— 稿纸表面 —— */
.mofeng-editor__surface {
  position: relative;
}

.mofeng-editor__paper {
  position: relative;
  background-color: var(--md-surface); /* 熟宣底,不用纯白 */
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent calc(var(--paper-line) - 1px),
    var(--md-miaohong-line, rgba(184, 64, 47, 0.22)) calc(var(--paper-line) - 1px),
    var(--md-miaohong-line, rgba(184, 64, 47, 0.22)) var(--paper-line)
  );
  /* 让第一条行线落在首行文字的底部 */
  background-position: 0 var(--mofeng-paper-pad-y);
  /* 左侧 56px 留白容纳段级 gutter,左右留白均 ≥32px(规格 §3) */
  padding: var(--mofeng-paper-pad-y) 40px 24px 56px;
}

.mofeng-editor__paper:focus-within {
  outline: 1px solid var(--md-luomo, var(--md-on-surface)); /* 焦点态 1px 焦墨框线 */
  outline-offset: 1px;
}

/* 左右朱丝栏竖线(规格 §3) */
.mofeng-editor__paper::before,
.mofeng-editor__paper::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--md-miaohong-line-strong, rgba(184, 64, 47, 0.38));
  pointer-events: none;
}

.mofeng-editor__paper::before {
  left: 0;
}

.mofeng-editor__paper::after {
  right: 0;
}

.mofeng-editor__placeholder {
  position: absolute;
  top: var(--mofeng-paper-pad-y);
  /* 56px 稿纸左留白 + 10px 段落内缩,与正文起点对齐 */
  left: 66px;
  font-family: var(--md-font-serif);
  font-size: var(--md-body-large);
  line-height: var(--paper-line);
  color: var(--md-on-surface-variant);
  opacity: 0.55;
  pointer-events: none;
}

/* —— ProseMirror 内容区(PM 注入的 DOM 需要 :deep) —— */
.mofeng-editor__paper :deep(.mofeng-editor__content) {
  outline: none;
  white-space: pre-wrap;
  font-family: var(--md-font-serif); /* 落墨正文 = 宋体 */
  font-size: var(--md-body-large); /* 15px,与 27px 行线对齐 */
  line-height: var(--paper-line);
  color: var(--md-luomo, var(--md-on-surface)); /* 焦墨 */
  caret-color: var(--md-luomo, var(--md-on-surface));
  min-height: calc(var(--paper-line) * 5);
}

.mofeng-editor__paper :deep(.mofeng-editor__content p) {
  margin: 0 0 var(--paper-line) 0; /* 段距 = 一行,网格不错位 */
  padding-left: 10px; /* 给描红界栏让出位置,所有段落统一缩进避免跳动 */
  text-indent: 2em; /* 与阅读视图一致的中文稿纸段首缩进 */
  /* 落墨过程:朱→墨、底纹与界栏淡出,220ms 落在规格 §4 的 140–280ms 区间 */
  transition:
    color 220ms var(--md-easing-standard),
    background-color 220ms var(--md-easing-standard),
    box-shadow 220ms var(--md-easing-standard);
}

.mofeng-editor__paper :deep(.mofeng-editor__content p:last-child) {
  margin-bottom: 0;
}

/* 描红三信号(规格 §4):
   ① 色 --md-miaohong;② 字族 --md-font-kai 楷体(挂在 span[data-miaohong]);
   ③ 面 --md-miaohong-wash 底纹 + 左缘 1px 界栏(挂在所在段落) */
.mofeng-editor__paper :deep(span[data-miaohong]) {
  color: var(--md-miaohong, #b8402f);
  font-family: var(--md-font-kai);
}

.mofeng-editor__paper :deep(.mofeng-editor__content p:has(span[data-miaohong])),
.mofeng-editor__paper :deep(.mofeng-editor__content p.mofeng-p--luomoing) {
  background-color: var(--md-miaohong-wash, rgba(184, 64, 47, 0.05));
  box-shadow: -1px 0 0 var(--md-miaohong-line-strong, rgba(184, 64, 47, 0.38));
}

/* 落墨过渡态:mark 移除后仍短暂保持朱色楷体,待 class 撤去后过渡回焦墨宋体 */
.mofeng-editor__paper :deep(.mofeng-editor__content p.mofeng-p--luomoing) {
  color: var(--md-miaohong, #b8402f);
  font-family: var(--md-font-kai);
}

/* —— 段级界格 gutter —— */
.mofeng-editor__gutter {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 48px;
  z-index: 2;
}

.mofeng-editor__gutter-row {
  position: absolute;
  left: 0;
  width: 48px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

/* 「落墨」小按钮:淡朱描边方印 */
.mofeng-editor__gutter-btn {
  margin-top: 1px;
  opacity: 0;
  pointer-events: none;
  border: 1px solid var(--md-miaohong, #b8402f);
  border-radius: 2px;
  background-color: var(--md-surface);
  color: var(--md-miaohong, #b8402f);
  font-family: var(--md-font-kai);
  font-size: 12px;
  line-height: 1.8;
  padding: 1px 6px;
  cursor: pointer;
  transition:
    opacity 140ms var(--md-easing-standard),
    background-color 140ms var(--md-easing-standard),
    color 140ms var(--md-easing-standard);
}

.mofeng-editor__gutter-btn.is-visible,
.mofeng-editor__gutter-btn:focus-visible {
  opacity: 1;
  pointer-events: auto;
}

.mofeng-editor__gutter-btn:hover {
  background-color: var(--md-miaohong, #b8402f);
  color: var(--md-surface);
}

.mofeng-editor__gutter-btn:focus-visible {
  outline: 1px solid var(--md-luomo, var(--md-on-surface));
  outline-offset: 1px;
}

@media (prefers-reduced-motion: reduce) {
  .mofeng-editor__paper :deep(.mofeng-editor__content p),
  .mofeng-editor__gutter-btn,
  .mofeng-editor__seal-btn {
    transition: none;
  }
}
</style>
