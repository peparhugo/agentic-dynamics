import hljs from "highlight.js";
import { Marked } from "marked";

const marked = new Marked({
  async: false,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value;
      } catch {
        return code;
      }
    }
    return hljs.highlightAuto(code).value;
  },
});

export function markdownToHtml(markdown: string): string {
  return marked.parse(markdown) as string;
}
