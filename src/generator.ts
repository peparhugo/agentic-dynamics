import { ParsedPage, PageFrontmatter } from './parser';

export function generatePageHTML(page: ParsedPage): string {
  const { frontmatter, html, slug } = page;
  const date = frontmatter.date ? new Date(frontmatter.date).toLocaleDateString() : '';
  const tagsList = Array.isArray(frontmatter.tags) ? frontmatter.tags.join(', ') : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(frontmatter.title)}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 2rem;
      color: #333;
    }
    h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
    .meta { color: #666; font-size: 0.95rem; margin-bottom: 2rem; }
    .tag { display: inline-block; background: #e0e0e0; padding: 0.25rem 0.75rem; border-radius: 1rem; margin-right: 0.5rem; font-size: 0.9rem; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .nav { margin-bottom: 2rem; }
    .nav a { margin-right: 1rem; }
  </style>
</head>
<body>
  <div class="nav">
    <a href="index.html">← Back to index</a>
  </div>
  <article>
    <h1>${escapeHtml(frontmatter.title)}</h1>
    <div class="meta">
      ${date ? `<div>Published: ${date}</div>` : ''}
      ${tagsList ? `<div class="tags">${frontmatter.tags!.map((tag: string) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
    </div>
    <div class="content">
      ${html}
    </div>
  </article>
</body>
</html>`;
}

export function generateIndexHTML(pages: ParsedPage[]): string {
  const sortedPages = pages.sort((a, b) => {
    const dateA = a.frontmatter.date ? new Date(a.frontmatter.date).getTime() : 0;
    const dateB = b.frontmatter.date ? new Date(b.frontmatter.date).getTime() : 0;
    return dateB - dateA;
  });

  const pageList = sortedPages
    .map(page => {
      const date = page.frontmatter.date ? new Date(page.frontmatter.date).toLocaleDateString() : 'No date';
      return `<li>
  <a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.frontmatter.title)}</a>
  <span class="date">${date}</span>
</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Site Index</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 2rem;
      color: #333;
    }
    h1 { font-size: 2.5rem; margin-bottom: 2rem; }
    ul { list-style: none; padding: 0; }
    li {
      padding: 1rem 0;
      border-bottom: 1px solid #e0e0e0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .date { color: #999; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>Site Index</h1>
  <p>${pages.length} page${pages.length !== 1 ? 's' : ''} found</p>
  <ul>
${pageList}
  </ul>
</body>
</html>`;
}

function escapeHtml(text: string): string {
  const map: { [key: string]: string } = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, char => map[char]);
}
