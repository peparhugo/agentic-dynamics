import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

export function createMarkdownRenderer() {
  const md = new MarkdownIt({
    html: true,
    linkify: true,
    typographer: true,
    highlight(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        try {
          const out = hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
          return `<pre><code class="hljs language-${lang}">${out}</code></pre>`;
        } catch {
          // fallthrough
        }
      }
      const escaped = md.utils.escapeHtml(code);
      return `<pre><code class="hljs">${escaped}</code></pre>`;
    }
  });
  return md;
}
