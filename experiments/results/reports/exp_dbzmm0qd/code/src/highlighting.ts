import hljs from "highlight.js";

const LANG_RE = /^language-(\S+)/;

export function highlightCode(html: string): string {
  return html.replace(/<pre><code class="([^"]*)">([\s\S]*?)<\/code><\/pre>/g, (match, classes, code) => {
    const m = classes.match(LANG_RE);
    if (!m) return match;

    const lang = m[1];
    let highlighted: string;

    try {
      if (hljs.getLanguage(lang)) {
        highlighted = hljs.highlight(decodeEntities(code), { language: lang }).value;
      } else {
        highlighted = hljs.highlightAuto(decodeEntities(code)).value;
      }
    } catch {
      return match;
    }

    return `<pre><code class="hljs ${classes}">${highlighted}</code></pre>`;
  });
}

function decodeEntities(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}
