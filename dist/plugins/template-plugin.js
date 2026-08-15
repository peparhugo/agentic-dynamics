import * as fs from 'fs';
import { TemplateEngine } from '../template-engine.js';
export class TemplatePlugin {
    constructor() {
        this.name = 'template';
        this.version = '1.0.0';
        this.templateEngine = null;
    }
    async beforeBuild(context) {
        if (context.templatesDir && fs.existsSync(context.templatesDir)) {
            this.templateEngine = new TemplateEngine(context.templatesDir);
        }
    }
    async onFile(context, file) {
        if (!file.parsed) {
            return;
        }
        const title = file.parsed.frontmatter.title || file.filename.replace('.md', '');
        const templateName = file.parsed.frontmatter.template
            ? String(file.parsed.frontmatter.template)
            : undefined;
        const layoutName = file.parsed.frontmatter.layout ? String(file.parsed.frontmatter.layout) : undefined;
        file.pageMetadata = {
            filename: file.filename,
            title,
            date: file.parsed.frontmatter.date ? String(file.parsed.frontmatter.date) : undefined,
            tags: Array.isArray(file.parsed.frontmatter.tags)
                ? file.parsed.frontmatter.tags.map((tag) => String(tag))
                : [],
            url: file.filename.replace('.md', '.html'),
            template: templateName,
            layout: layoutName,
        };
        file.html = this.renderPageWithTemplate(title, file.parsed.html, templateName, layoutName, file.parsed.frontmatter);
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
    escapeHtml(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}
//# sourceMappingURL=template-plugin.js.map