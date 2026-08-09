import { marked, type Renderer } from "marked";
import hljs from "highlight.js";

const renderer: Renderer = {
  code({ text, lang }: { text: string; lang?: string }): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        const highlighted = hljs.highlight(text, { language: lang }).value;
        return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>\n`;
      } catch {
        // fall through to plain code block
      }
    }
    return `<pre><code>${escapeHtml(text)}</code></pre>\n`;
  },
};

marked.use({ renderer });

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}
