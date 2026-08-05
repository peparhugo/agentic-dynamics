import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

// Configure markdown-it with highlight.js
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: (str, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        const highlighted = hljs.highlight(str, { language: lang, ignoreIllegals: true }).value;
        return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`;
      } catch {
        // fall through
      }
    }
    const escaped = md.utils.escapeHtml(str);
    return `<pre><code class="hljs">${escaped}</code></pre>`;
  },
});

export function renderMarkdown(markdown: string): string {
  return md.render(markdown);
}
