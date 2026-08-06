import hljs from 'highlight.js';

export function highlightCode(code: string, lang?: string): string {
  if (lang && hljs.getLanguage(lang)) {
    try {
      const result = hljs.highlight(code, { language: lang });
      return `<pre><code class="hljs language-${lang}">${result.value}</code></pre>`;
    } catch {
      // fall through to auto-detection
    }
  }

  try {
    const result = hljs.highlightAuto(code);
    if (result.language) {
      return `<pre><code class="hljs language-${result.language}">${result.value}</code></pre>`;
    }
  } catch {
    // fall through to plain
  }

  return `<pre><code>${escapeHtml(code)}</code></pre>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
