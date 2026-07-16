<template>
  <!-- 案头宣纸盖印·引首闲章 (写作辅助控制) -->
  <button
    type="button"
    class="writing-desk-seal-stamp md-ripple"
    :class="{ 'is-active': isActive }"
    :title="isActive ? '折叠右侧辅助面板' : '展开右侧辅助面板'"
    @click="$emit('toggle')"
  >
    <!-- 印信篆字 (阴刻朱砂白文) -->
    <span class="stamp-seal-char">{{ isActive ? '閉' : '輔' }}</span>
  </button>
</template>

<script setup lang="ts">
interface Props {
  isActive: boolean
}
defineProps<Props>()
defineEmits(['toggle'])
</script>

<style scoped>
/* 宣纸引首闲章本体 */
.writing-desk-seal-stamp {
  position: absolute;
  right: 0;
  top: 135px;
  z-index: 30; /* 高于工作区，低于弹窗与 drawer 遮罩层 */
  display: flex;
  align-items: center;
  justify-content: center;
  height: 38px;
  width: 38px; /* 默认正方形印章尺寸 */
  padding: 0;
  cursor: pointer;
  border: 1px solid #9c2720;
  border-right: none; /* 右侧贴合分界线，呈无缝盖印状态 */

  /* 运用左圆角、右直角设计，完美模拟盖在纸张右边缘的引首章印记 */
  border-radius: 6px 0 0 6px / 8px 0 0 8px;

  /* 精致沉稳的朱砂印泥色彩渐变 */
  background: linear-gradient(135deg, #c94036 0%, #b83c32 50%, #a32720 100%);

  /* 核心国风魔力：混合相乘模式！
     它会让朱砂红与米黄色的稿纸底纹像素完美混合，呈现出极其逼真的“印泥渗入宣纸”拓印质感 */
  mix-blend-mode: multiply;
  opacity: 0.92;

  /* 盖印后的轻微纸张受压凹凸质感与边缘斑驳微影 */
  box-shadow:
    -1px 2px 4px rgba(107, 21, 16, 0.25),
    inset 1px 1px 1px rgba(255, 255, 255, 0.15),
    inset -1px -1px 2px rgba(0, 0, 0, 0.15);

  transition:
    transform 0.3s cubic-bezier(0.25, 1, 0.5, 1),
    background 0.3s ease,
    opacity 0.3s ease,
    box-shadow 0.3s ease;
  overflow: hidden;
  white-space: nowrap;
}

/* 水墨印痕伪元素：当 hover 时，仿佛墨香未干，在宣纸边缘向外轻柔地晕染开一缕浅墨痕 */
.writing-desk-seal-stamp::before {
  content: '';
  position: absolute;
  inset: -12px;
  border-radius: 50%;
  /* 极轻微向外渐隐的水墨晕染渐变 */
  background: radial-gradient(circle, rgba(28, 32, 34, 0.25) 0%, rgba(28, 32, 34, 0.08) 50%, rgba(28, 32, 34, 0) 70%);
  transform: scale(0.4);
  opacity: 0;
  z-index: -1;
  pointer-events: none;
  transition:
    transform 0.6s cubic-bezier(0.16, 1, 0.3, 1),
    opacity 0.5s ease;
}

/* 闲章 Hover 时：保持宽度恒定，仅作优雅缩放并显金泥温润流光 */
.writing-desk-seal-stamp:hover {
  transform: scale(1.08);
  opacity: 0.98;
  background: linear-gradient(135deg, #d4433b 0%, #b83c32 50%, #b02c25 100%);
  box-shadow:
    -2px 3px 8px rgba(107, 21, 16, 0.35),
    inset 1px 1px 1px rgba(255, 255, 255, 0.2);
}

.writing-desk-seal-stamp:hover::before {
  transform: scale(2.2); /* 墨晕在宣纸上优雅晕散 */
  opacity: 1;
}

/* 阴刻古朴篆字 */
.stamp-seal-char {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: var(--md-radius-xs);

  /* 白文阴刻金石托底，使文字如同在章体上镂空透出底部的宣纸暖白 */
  background-color: rgba(28, 32, 34, 0.15);
  color: #faf6ed !important; /* 古香古色的泥金白文 */
  font-family: var(--md-font-serif);
  font-size: 13px;
  font-weight: 800;
  text-shadow: 1px 1px 1px rgba(107, 21, 16, 0.5);
  border: 1px dashed rgba(250, 246, 237, 0.18);
  box-shadow: inset 1px 1px 0px rgba(28, 32, 34, 0.18);
  transition: transform 0.4s cubic-bezier(0.25, 1, 0.5, 1);
}

.writing-desk-seal-stamp:hover .stamp-seal-char {
  transform: scale(1.08) rotate(15deg); /* 悬停时篆字微偏，增添意趣 */
}

/* 移动端/窄屏响应式适配：精美贴合于右下角 */
@media (max-width: 1199px) {
  .writing-desk-seal-stamp {
    top: auto;
    bottom: 30px; /* 贴靠右下角 */
    right: 0;
    width: 38px;
    height: 38px;
    border-radius: 6px 0 0 6px / 8px 0 0 8px;
    box-shadow: -2px 2px 6px rgba(107, 21, 16, 0.3);
  }

  .writing-desk-seal-stamp:hover {
    width: 38px;
    border-radius: 6px 0 0 6px / 8px 0 0 8px;
    transform: scale(1.05); /* 仅做轻微点击缩放提示 */
  }
}
</style>
