import matter from 'gray-matter';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre><code class="hljs language-${lang}">${hljs.highlight(code, { language: lang }).value}</code></pre>`;
      } catch {
        // fallthrough
      }
    }
    const escaped = md.utils.escapeHtml(code);
    return `<pre><code class="hljs">${escaped}</code></pre>`;
  }
});

export function parseMarkdown(input: string) {
  const { data, content } = matter(input);
  const frontmatter = data as Record<string, unknown>;
  const html = md.render(content);
  return { frontmatter, contentHtml: html, rawBody: content };
}
