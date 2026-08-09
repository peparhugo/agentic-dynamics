import MarkdownIt from "markdown-it";
import hljs from "highlight.js";

const md: MarkdownIt = new MarkdownIt({
  html: true,
  linkify: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      const { value } = hljs.highlight(code, { language: lang, ignoreIllegals: true });
      return `<pre><code class="hljs language-${lang}">${value}</code></pre>`;
    }
    return `<pre><code class="hljs">${md.utils.escapeHtml(code)}</code></pre>`;
  },
});

/** Render markdown to HTML with syntax-highlighted code blocks. */
export function renderMarkdown(src: string): string {
  return md.render(src);
}
