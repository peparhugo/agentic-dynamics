import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

const md: MarkdownIt = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      const { value } = hljs.highlight(code, { language: lang, ignoreIllegals: true });
      return `<pre><code class="hljs language-${lang}">${value}</code></pre>`;
    }
    const { value } = hljs.highlightAuto(code);
    return `<pre><code class="hljs">${value}</code></pre>`;
  },
});

/** Render markdown to HTML with syntax-highlighted code blocks. */
export function renderMarkdown(markdown: string): string {
  return md.render(markdown);
}

/** Strip markdown/HTML to produce a plain-text excerpt of at most `maxLength` chars. */
export function excerptFrom(markdown: string, maxLength = 200): string {
  const text = renderMarkdown(markdown)
    .replace(/<[^>]+>/g, ' ')
    .replace(/&[a-z#0-9]+;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).replace(/\s+\S*$/, '')}…`;
}
