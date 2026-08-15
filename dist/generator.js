import fs from 'fs';
import path from 'path';
import { parseMarkdownWithYaml } from './parser.js';
function slugFromFilename(filename) {
    return filename.replace(/\.md$/, '');
}
function generatePageHtml(page) {
    const title = page.metadata.title || page.slug;
    const date = page.metadata.date ? `<p class="date">${page.metadata.date}</p>` : '';
    const tags = page.metadata.tags && page.metadata.tags.length > 0
        ? `<div class="tags">${page.metadata.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}</div>`
        : '';
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
    a { color: #0066cc; }
    .date { color: #666; font-size: 0.9em; }
    .tags { margin: 10px 0; }
    .tag { display: inline-block; background: #f0f0f0; padding: 2px 8px; margin: 2px; border-radius: 3px; font-size: 0.9em; }
    nav { border-bottom: 1px solid #ddd; margin-bottom: 20px; padding-bottom: 10px; }
  </style>
</head>
<body>
  <nav>
    <a href="index.html">← Home</a>
  </nav>
  <article>
    <h1>${escapeHtml(title)}</h1>
    ${date}
    ${tags}
    <div class="content">
      ${page.content}
    </div>
  </article>
</body>
</html>`;
}
function generateIndexHtml(pages) {
    const pageLinks = pages
        .sort((a, b) => {
        const dateA = new Date(a.metadata.date || '').getTime();
        const dateB = new Date(b.metadata.date || '').getTime();
        return dateB - dateA;
    })
        .map(page => {
        const title = page.metadata.title || page.slug;
        const dateStr = page.metadata.date ? ` (${page.metadata.date})` : '';
        return `<li><a href="${page.slug}.html">${escapeHtml(title)}</a>${dateStr}</li>`;
    })
        .join('\n    ');
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Home</title>
  <style>
    body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
    a { color: #0066cc; }
    li { margin: 8px 0; }
  </style>
</head>
<body>
  <h1>Pages</h1>
  <ul>
    ${pageLinks}
  </ul>
</body>
</html>`;
}
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, char => map[char]);
}
export async function generate(options) {
    const { contentDir, outputDir } = options;
    if (!fs.existsSync(contentDir)) {
        throw new Error(`Content directory not found: ${contentDir}`);
    }
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }
    const files = fs.readdirSync(contentDir).filter(file => file.endsWith('.md'));
    if (files.length === 0) {
        throw new Error(`No markdown files found in ${contentDir}`);
    }
    const pages = [];
    for (const file of files) {
        const filePath = path.join(contentDir, file);
        const content = fs.readFileSync(filePath, 'utf-8');
        const parsed = await parseMarkdownWithYaml(content);
        const page = {
            slug: slugFromFilename(file),
            filename: file,
            content: parsed.content,
            metadata: parsed.metadata
        };
        pages.push(page);
        const pageHtml = generatePageHtml(page);
        const outputPath = path.join(outputDir, `${page.slug}.html`);
        fs.writeFileSync(outputPath, pageHtml, 'utf-8');
    }
    const indexHtml = generateIndexHtml(pages);
    const indexPath = path.join(outputDir, 'index.html');
    fs.writeFileSync(indexPath, indexHtml, 'utf-8');
    console.log(`Generated site with ${pages.length} page(s) in ${outputDir}`);
}
//# sourceMappingURL=generator.js.map