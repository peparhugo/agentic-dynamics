import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import hljs from 'highlight.js';

let instance: Marked | null = null;

export function getMarked(): Marked {
  if (!instance) {
    instance = new Marked(
      markedHighlight({
        langPrefix: 'hljs language-',
        highlight(code: string, lang: string): string {
          if (lang && hljs.getLanguage(lang)) {
            try {
              return hljs.highlight(code, { language: lang }).value;
            } catch {
              // fall through
            }
          }
          return code;
        },
      }),
    );
  }
  return instance;
}
