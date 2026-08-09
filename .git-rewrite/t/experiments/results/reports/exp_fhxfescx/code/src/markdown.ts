import { Marked } from "marked";
import { markedHighlight } from "marked-highlight";
import hljs from "highlight.js";

/**
 * A single shared Marked instance with syntax highlighting.
 * Reused across all pages for throughput: highlight.js language
 * grammars are compiled once and cached.
 */
const marked = new Marked(
  markedHighlight({
    langPrefix: "hljs language-",
    highlight(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
  })
);

export function renderMarkdown(body: string): string {
  return marked.parse(body, { async: false }) as string;
}
