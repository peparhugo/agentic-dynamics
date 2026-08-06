import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

/**
 * Markdown renderer with syntax highlighting for fenced code blocks.
 * Known languages get hljs token markup; unknown/absent languages are escaped.
 */
export const md: MarkdownIt = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      const { value } = hljs.highlight(code, { language: lang, ignoreIllegals: true });
      return `<pre class="hljs"><code class="language-${lang}">${value}</code></pre>`;
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(code)}</code></pre>`;
  },
});

export function renderMarkdown(source: string): string {
  return md.render(source);
}
