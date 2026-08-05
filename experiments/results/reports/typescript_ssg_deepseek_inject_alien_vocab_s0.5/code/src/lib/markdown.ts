import { marked } from "marked";
import hljs from "highlight.js";

export function initMarked(): void {
  marked.use({
    renderer: {
      code(this: marked.Renderer, code: string, lang?: string): string {
        if (lang && hljs.getLanguage(lang)) {
          try {
            const highlighted = hljs.highlight(code, { language: lang }).value;
            return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`;
          } catch {
            // fall through
          }
        }
        return `<pre><code>${escapeHtml(code)}</code></pre>`;
      },
    },
  });

  marked.setOptions({
    gfm: true,
    breaks: false,
  });
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function markdownToHtml(markdown: string): string {
  const result = marked.parse(markdown);
  return typeof result === "string" ? result : "";
}
