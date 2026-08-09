import hljs from 'highlight.js';

export function highlightCode(code: string, lang: string): string {
  if (lang && hljs.getLanguage(lang)) {
    try {
      return hljs.highlight(code, { language: lang }).value;
    } catch {
      // ignore highlighting errors
    }
  }
  return code;
}
