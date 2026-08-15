import * as fs from 'fs';
import * as path from 'path';
import { parseMarkdown } from './parser.js';
import { TemplateEngine } from './template-engine.js';
export class SiteGenerator {
    constructor(options) {
        this.templateEngine = null;
        this.contentDir = options.contentDir;
        this.outputDir = options.outputDir;
        this.templatesDir = options.templatesDir || './templates';
        if (fs.existsSync(this.templatesDir)) {
            this.templateEngine = new TemplateEngine(this.templatesDir);
        }
    }
    ensureDir(dirPath) {
        if (!fs.existsSync(dirPath)) {
            fs.mkdirSync(dirPath, { recursive: true });
        }
    }
    getMarkdownFiles() {
        if (!fs.existsSync(this.contentDir)) {
            return [];
        }
        return fs
            .readdirSync(this.contentDir)
            .filter((file) => file.endsWith('.md'))
            .sort();
    }
    renderPageWithTemplate(title, content, templateName, layoutName, data) {
        if (!this.templateEngine) {
            return this.generatePageHtml(title, content);
        }
        const pageData = {
            title: this.escapeHtml(title),
            content,
            ...data,
        };
        const template = templateName || 'page';
        const layout = layoutName || 'default';
        try {
            if (this.templateEngine.hasLayout(layout)) {
                return this.templateEngine.renderPageTemplate(template, pageData, layout);
            }
        }
        catch {
            // Fall back to default HTML if template rendering fails
        }
        return this.generatePageHtml(title, content);
    }
    generatePageHtml(title, content) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${this.escapeHtml(title)}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
      color: #333;
    }
    h1, h2, h3, h4, h5, h6 { margin-top: 1.5em; }
    code {
      background: #f0f0f0;
      padding: 2px 6px;
      border-radius: 3px;
      font-family: 'Courier New', monospace;
    }
    pre {
      background: #f5f5f5;
      padding: 10px;
      border-radius: 5px;
      overflow-x: auto;
    }
    pre code { background: none; padding: 0; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .nav { margin-bottom: 20px; }
    .nav a { margin-right: 15px; }
  </style>
</head>
<body>
  <div class="nav">
    <a href="index.html">← Home</a>
  </div>
  <h1>${this.escapeHtml(title)}</h1>
  <div>${content}</div>
</body>
</html>`;
    }
    generateIndexHtml(pages) {
        const pagesList = pages
            .map((page) => `    <li>
      <a href="${this.escapeHtml(page.url)}">${this.escapeHtml(page.title)}</a>
      ${page.date ? `<span style="color: #666; margin-left: 10px;">${this.escapeHtml(page.date)}</span>` : ''}
      ${page.tags.length > 0 ? `<div style="margin-top: 5px;"><small>${page.tags.map((tag) => `<span style="display: inline-block; background: #eee; padding: 2px 8px; border-radius: 3px; margin-right: 5px;">${this.escapeHtml(tag)}</span>`).join('')}</small></div>` : ''}
    </li>`)
            .join('\n');
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Static Site</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
      color: #333;
    }
    h1 { margin-top: 0; }
    ul { list-style: none; padding: 0; }
    li {
      padding: 15px;
      border: 1px solid #eee;
      margin-bottom: 10px;
      border-radius: 5px;
    }
    li:hover { background: #f9f9f9; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <h1>Pages</h1>
  ${pages.length > 0 ? `<ul>\n${pagesList}\n  </ul>` : '<p>No pages found.</p>'}
</body>
</html>`;
    }
    escapeHtml(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
    async build() {
        this.ensureDir(this.outputDir);
        const markdownFiles = this.getMarkdownFiles();
        const pages = [];
        for (const file of markdownFiles) {
            const filePath = path.join(this.contentDir, file);
            const content = fs.readFileSync(filePath, 'utf-8');
            const parsed = await parseMarkdown(content);
            const title = parsed.frontmatter.title || file.replace('.md', '');
            const slug = file.replace('.md', '.html');
            const outputPath = path.join(this.outputDir, slug);
            const templateName = parsed.frontmatter.template ? String(parsed.frontmatter.template) : undefined;
            const layoutName = parsed.frontmatter.layout ? String(parsed.frontmatter.layout) : undefined;
            const pageHtml = this.renderPageWithTemplate(
                title,
                parsed.html,
                templateName,
                layoutName,
                parsed.frontmatter
            );
            fs.writeFileSync(outputPath, pageHtml);
            pages.push({
                filename: file,
                title,
                date: parsed.frontmatter.date ? String(parsed.frontmatter.date) : undefined,
                tags: Array.isArray(parsed.frontmatter.tags)
                    ? parsed.frontmatter.tags.map((tag) => String(tag))
                    : [],
                url: slug,
                template: templateName,
                layout: layoutName,
            });
        }
        const indexPath = path.join(this.outputDir, 'index.html');
        fs.writeFileSync(indexPath, this.generateIndexHtml(pages));
        console.log(`✓ Generated ${pages.length} page(s) to ${this.outputDir}`);
    }
}
//# sourceMappingURL=generator.js.map