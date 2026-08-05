import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import mdhl from 'markdown-it-highlightjs';

export function createMarkdown(): MarkdownIt {
  const md: MarkdownIt = new MarkdownIt({
    html: true,
    linkify: true,
    typographer: true,
    highlight: (str: string, lang: string) => {
      if (lang && hljs.getLanguage(lang)) {
        try {
          return `<pre><code class="hljs language-${lang}">${hljs.highlight(str, { language: lang, ignoreIllegals: true }).value}</code></pre>`;
        } catch {}
      }
      const escaped = md.utils.escapeHtml(str);
      return `<pre><code class="hljs">${escaped}</code></pre>`;
    }
  });
  // plugin ensures CSS classes, but we already provide custom highlight; still helpful for consistency
  md.use(mdhl, { auto: true, code: true });
  return md;
}
