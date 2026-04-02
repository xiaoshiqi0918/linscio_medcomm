import { Node, mergeAttributes } from '@tiptap/core'

export const QuizBlock = Node.create({
  name: 'quizBlock',
  group: 'block',
  content: 'block+',
  addAttributes() {
    return {
      questionIndex: { default: 1 },
      correctAnswer: { default: '' },
      explanation: { default: '' },
    }
  },
  parseHTML() {
    return [{ tag: 'div[data-type="quiz-block"]' }]
  },
  renderHTML({ HTMLAttributes, node }) {
    const idx = node?.attrs?.questionIndex ?? 1
    return [
      'div',
      mergeAttributes({ 'data-type': 'quiz-block' }, HTMLAttributes),
      ['div', { class: 'quiz-header' }, `题目 ${idx}`],
      ['div', { class: 'quiz-body' }, 0],
    ]
  },
})
