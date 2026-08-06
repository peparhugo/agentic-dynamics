import hljs from 'highlight.js';
import { markedHighlight } from 'marked-highlight';
import { Marked } from 'marked';

export function setupHighlighting(marked: Marked): void {
  marked.use(
    markedHighlight({
      langPrefix: 'hljs language-',
      highlight(code: string, lang: string) {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return code;
      },
    })
  );
}
