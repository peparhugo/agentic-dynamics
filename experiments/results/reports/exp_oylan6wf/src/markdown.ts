import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import hljs from 'highlight.js';

const marked = new Marked(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code: string, lang: string): string {
      const language = hljs.getLanguage(lang) ? lang : 'plaintext';
      return hljs.highlight(code, { language }).value;
    },
  }),
);
marked.setOptions({ gfm: true });

/** Render Markdown to HTML with syntax-highlighted code blocks. */
export function renderMarkdown(md: string): string {
  return marked.parse(md) as string;
}

/**
 * Extract a plain-text excerpt: first non-empty paragraph, stripped of
 * markdown-ish syntax, truncated to maxLength.
 */
export function extractExcerpt(md: string, maxLength = 240): string {
  const withoutCode = md.replace(/```[\s\S]*?```/g, '');
  const firstPara =
    withoutCode
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .find((p) => p && !p.startsWith('#')) ?? '';
  const text = firstPara
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '') // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // links -> text
    .replace(/[*_`>#]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return text.length > maxLength ? `${text.slice(0, maxLength - 1).trimEnd()}\u2026` : text;
}
