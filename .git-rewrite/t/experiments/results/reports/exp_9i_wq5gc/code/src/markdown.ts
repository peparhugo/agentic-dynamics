import hljs from 'highlight.js';
import { marked } from 'marked';

// Configure marked with highlight.js
marked.use({
  highlight(code, lang) {
    try {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    } catch {
      return code;
    }
  },
});

export function renderMarkdown(md: string): string {
  return marked.parse(md) as string;
}
