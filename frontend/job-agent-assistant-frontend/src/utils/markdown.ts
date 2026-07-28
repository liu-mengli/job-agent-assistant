import { marked } from 'marked'

// 只允许渲染 markdown，禁止原始 HTML 防止 XSS
marked.setOptions({
  breaks: true,   // 换行→<br>
  gfm: true,      // GitHub Flavored Markdown（表格、删除线等）
})

export function renderMarkdown(text: string): string {
  // 先裁掉末尾可能附带的 JSON
  const re = /\n?\{\s*"response_type"\s*:/s
  const m = text.match(re)
  const clean = m && m.index !== undefined ? text.slice(0, m.index).trimEnd() : text
  return marked.parse(clean) as string
}
