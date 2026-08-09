import { marked, type TokenizerAndRendererExtension } from "marked";
import { markedHighlight } from "marked-highlight";
import hljs from "highlight.js";

const highlightExtension = markedHighlight({
  langPrefix: "hljs language-",
  highlight(code: string, lang: string) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return code;
  },
});

marked.use(highlightExtension);

export function renderMarkdown(markdown: string): string {
  return marked.parse(markdown, { async: false }) as string;
}
