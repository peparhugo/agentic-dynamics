import { marked } from "marked";
import hljs from "highlight.js";

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

marked.use({
  renderer: {
    code({ text, lang }: { text: string; lang?: string }): string {
      if (lang && hljs.getLanguage(lang)) {
        return `<pre><code class="hljs language-${lang}">${hljs.highlight(text, { language: lang }).value}</code></pre>`;
      }
      return `<pre><code>${escapeHtml(text)}</code></pre>`;
    },
  },
});

export function renderMarkdown(content: string): string {
  return marked.parse(content) as string;
}
