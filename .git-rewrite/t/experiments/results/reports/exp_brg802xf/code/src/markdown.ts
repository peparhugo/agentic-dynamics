import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

// Configure markdown-it with highlight.js
export function createMarkdown(): MarkdownIt {
  const md = new MarkdownIt({
    html: true,
    linkify: true,
    typographer: false,
    highlight: (str: string, lang?: string) => {
      if (lang && hljs.getLanguage(lang)) {
        try {
          const { value } = hljs.highlight(str, { language: lang, ignoreIllegals: true });
          return `<pre><code class="hljs language-${lang}">${value}</code></pre>`;
        } catch (_) {
          // fall back to auto
        }
      }
      try {
        const { value } = hljs.highlightAuto(str);
        return `<pre><code class="hljs">${value}</code></pre>`;
      } catch (_) {
        return `<pre><code>${escapeHtml(str)}</code></pre>`;
      }
    }
  });
  return md;
}

function escapeHtml(html: string): string {
  return html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
