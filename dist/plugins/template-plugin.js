import fs from 'fs';
import path from 'path';
import { TemplateEngine, createDefaultLayout, createDefaultIndexLayout, createDefaultNavPartial } from '../template.js';
export class TemplatePlugin {
    constructor() {
        this.name = 'template';
        this.templateEngine = null;
        this.beforeBuild = this.beforeBuild.bind(this);
        this.onFile = this.onFile.bind(this);
        this.afterBuild = this.afterBuild.bind(this);
    }
    async beforeBuild(context) {
        const { templatesDir = './templates', layoutsDir = './templates/layouts', partialsDir = './templates/partials' } = context;
        if (fs.existsSync(templatesDir)) {
            this.ensureDefaultTemplates(templatesDir, layoutsDir, partialsDir);
            this.templateEngine = new TemplateEngine({
                templatesDir,
                layoutsDir,
                partialsDir
            });
            context.templateEngine = this.templateEngine;
        }
    }
    async onFile(page, context) {
        const { outputDir } = context;
        const html = this.generatePageHtml(page, this.templateEngine);
        const outputPath = path.join(outputDir, `${page.slug}.html`);
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }
        fs.writeFileSync(outputPath, html, 'utf-8');
    }
    async afterBuild(context) {
        const { outputDir, pages } = context;
        const html = this.generateIndexHtml(pages, this.templateEngine);
        const indexPath = path.join(outputDir, 'index.html');
        fs.writeFileSync(indexPath, html, 'utf-8');
    }
    generatePageHtml(page, templateEngine) {
        const title = page.metadata.title || page.slug;
        const layoutName = page.metadata.layout || 'default.hbs';
        if (!templateEngine) {
            const date = page.metadata.date ? `<p class="date">${page.metadata.date}</p>` : '';
            const tags = page.metadata.tags && page.metadata.tags.length > 0
                ? `<div class="tags">${page.metadata.tags.map((tag) => `<span class="tag">${tag}</span>`).join('')}</div>`
                : '';
            return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${this.escapeHtml(title)}</title>
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
    <h1>${this.escapeHtml(title)}</h1>
    ${date}
    ${tags}
    <div class="content">
      ${page.content}
    </div>
  </article>
</body>
</html>`;
        }
        return templateEngine.renderWithLayout(page.content, layoutName, {
            title: title,
            date: page.metadata.date,
            tags: page.metadata.tags || [],
            slug: page.slug,
            ...page.metadata
        });
    }
    generateIndexHtml(pages, templateEngine) {
        const sortedPages = pages.sort((a, b) => {
            const dateA = new Date(a.metadata.date || '').getTime();
            const dateB = new Date(b.metadata.date || '').getTime();
            return dateB - dateA;
        });
        if (!templateEngine) {
            const pageLinks = sortedPages
                .map((page) => {
                const title = page.metadata.title || page.slug;
                const dateStr = page.metadata.date ? ` (${page.metadata.date})` : '';
                return `<li><a href="${page.slug}.html">${this.escapeHtml(title)}</a>${dateStr}</li>`;
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
        const pageList = sortedPages.map(page => ({
            title: page.metadata.title || page.slug,
            slug: page.slug,
            date: page.metadata.date
        }));
        return templateEngine.render('index.hbs', 'index.hbs', { pages: pageList });
    }
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (char) => map[char]);
    }
    ensureDefaultTemplates(templatesDir, layoutsDir, partialsDir) {
        if (!fs.existsSync(templatesDir)) {
            fs.mkdirSync(templatesDir, { recursive: true });
        }
        if (!fs.existsSync(layoutsDir)) {
            fs.mkdirSync(layoutsDir, { recursive: true });
        }
        if (!fs.existsSync(partialsDir)) {
            fs.mkdirSync(partialsDir, { recursive: true });
        }
        const defaultLayoutPath = path.join(layoutsDir, 'default.hbs');
        if (!fs.existsSync(defaultLayoutPath)) {
            fs.writeFileSync(defaultLayoutPath, createDefaultLayout(), 'utf-8');
        }
        const indexLayoutPath = path.join(layoutsDir, 'index.hbs');
        if (!fs.existsSync(indexLayoutPath)) {
            fs.writeFileSync(indexLayoutPath, createDefaultIndexLayout(), 'utf-8');
        }
        const indexTemplatePath = path.join(templatesDir, 'index.hbs');
        if (!fs.existsSync(indexTemplatePath)) {
            fs.writeFileSync(indexTemplatePath, '{{{body}}}', 'utf-8');
        }
        const navPartialPath = path.join(partialsDir, 'nav.hbs');
        if (!fs.existsSync(navPartialPath)) {
            fs.writeFileSync(navPartialPath, createDefaultNavPartial(), 'utf-8');
        }
    }
}
//# sourceMappingURL=template-plugin.js.map