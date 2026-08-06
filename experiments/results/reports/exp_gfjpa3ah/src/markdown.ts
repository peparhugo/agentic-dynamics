import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import hljs from 'highlight.js';

const marked = new Marked(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code: string, lang: string): string {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
  }),
);

marked.setOptions({ gfm: true });

/** Render Markdown to HTML with syntax-highlighted code blocks. */
export function renderMarkdown(markdown: string): string {
  return marked.parse(markdown) as string;
}

/** Derive a plain-text excerpt from markdown (first paragraph, capped). */
export function extractExcerpt(markdown: string, maxLength = 200): string {
  const firstBlock = markdown
    .split(/\n\s*\n/)
    .map((b) => b.trim())
    .find((b) => b && !b.startsWith('#') && !b.startsWith('```') && !b.startsWith('!['));
  if (!firstBlock) return '';
  const text = firstBlock
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // links -> text
    .replace(/[*_`>#]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return text.length > maxLength ? `${text.slice(0, maxLength - 1).trimEnd()}\u2026` : text;
}
