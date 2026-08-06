import hljs from 'highlight.js';
import { marked } from 'marked';

export function setupMarked(): void {
  marked.setOptions({
    async: false,
  });
}

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown) as string;
}

export function highlightCode(html: string): string {
  return html.replace(
    /<pre><code(?:\s+class="language-([^"]*)")?>([\s\S]*?)<\/code><\/pre>/g,
    (_match, lang, code) => {
      const decoded = code
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&amp;/g, '&')
        .replace(/&quot;/g, '"');
      const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext';
      const highlighted = hljs.highlight(decoded, { language }).value;
      return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`;
    },
  );
}
