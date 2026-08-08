import { Mark } from '@tiptap/core'

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    miaohong: {
      /** 把选区文字标记为描红稿（淡朱楷体，待作家审定落墨）。 */
      setMiaohong: () => ReturnType
      /** 去掉选区文字的描红标记（落墨，文字转为焦墨宋体正文）。 */
      unsetMiaohong: () => ReturnType
    }
  }
}

/**
 * 描红 Mark ——「描红界格」世界观的核心载体。
 *
 * 语义：AI 产出、尚未被作家落墨审定的文字。渲染三信号全部由 CSS 完成：
 * 色与字族挂在 `span[data-miaohong]`（--md-miaohong + --md-font-kai），
 * 面信号（淡朱底纹 + 左缘界栏）挂在所在段落 `p:has(span[data-miaohong])`。
 *
 * 不带 attributes：描红只表达「待落墨」这一二元状态，作者归属由容器的
 * `data-provenance` 承担，不在 mark 上冗余。
 */
export const MiaohongMark = Mark.create({
  name: 'miaohong',

  parseHTML() {
    return [
      {
        tag: 'span[data-miaohong]',
      },
    ]
  },

  renderHTML() {
    return ['span', { 'data-miaohong': '' }, 0]
  },

  addCommands() {
    return {
      setMiaohong:
        () =>
        ({ commands }) =>
          commands.setMark(this.name),
      unsetMiaohong:
        () =>
        ({ commands }) =>
          commands.unsetMark(this.name),
    }
  },
})

export default MiaohongMark
