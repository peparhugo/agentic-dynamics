import hljs from "highlight.js";
import { marked } from "marked";

marked.use({
  renderer: {
    code({ text, lang }: { text: string; lang?: string }): string {
      if (lang && hljs.getLanguage(lang)) {
        try {
          const highlighted = hljs.highlight(text, { language: lang }).value;
          return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`;
        } catch {
          // fall through
        }
      }
      const auto = hljs.highlightAuto(text).value;
      return `<pre><code class="hljs">${auto}</code></pre>`;
    },
  },
});

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}
