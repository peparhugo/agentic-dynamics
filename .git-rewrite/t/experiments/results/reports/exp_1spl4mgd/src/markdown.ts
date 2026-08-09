import { Marked } from "marked";
import { markedHighlight } from "marked-highlight";
import hljs from "highlight.js";

/** Create a markdown renderer with syntax highlighting for fenced code blocks. */
export function createMarkdownRenderer(): (markdown: string) => string {
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
  marked.setOptions({ gfm: true });

  return (markdown: string) => marked.parse(markdown) as string;
}
