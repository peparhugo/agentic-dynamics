import { marked } from "marked";
import hljs from "highlight.js";

export function configureMarked(): void {
  marked.use({
    gfm: true,
    renderer: {
      code({ text, lang }: { text: string; lang?: string }): string {
        if (lang && hljs.getLanguage(lang)) {
          try {
            const highlighted = hljs.highlight(text, { language: lang }).value;
            return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`;
          } catch {
            // Fall through
          }
        }
        return `<pre><code>${escapeHtml(text)}</code></pre>`;
      },
    },
  });
}

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
