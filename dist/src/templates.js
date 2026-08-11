"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateEngine = void 0;
const handlebars_1 = __importDefault(require("handlebars"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const DEFAULT_PAGE_TEMPLATE = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{title}}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
  </header>
  <main>
    <article>
      <h1>{{title}}</h1>
      {{#if date}}<time datetime="{{date}}">{{date}}</time>{{/if}}
      {{#if tagsStr}}<p>Tags: {{tagsStr}}</p>{{/if}}
      <div>{{{body}}}</div>
    </article>
  </main>
</body>
</html>`;
const DEFAULT_INDEX_TEMPLATE = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Index</title>
</head>
<body>
  <header>
    <h1>All Pages</h1>
  </header>
  <main>
    <ul>
{{#each pages}}      <li>
        <a href="{{slug}}.html">{{title}}</a>
        {{#if date}}<span>{{date}}</span>{{/if}}
        {{#if tagsStr}}<span>Tags: {{tagsStr}}</span>{{/if}}
      </li>
{{/each}}
    </ul>
  </main>
</body>
</html>`;
const DEFAULT_LAYOUT = '{{{body}}}';
class TemplateEngine {
    constructor() {
        this.customTemplates = new Map();
        this.customLayouts = new Map();
        this.initialized = false;
        this.pageTemplate = handlebars_1.default.compile(DEFAULT_PAGE_TEMPLATE, { noEscape: true });
        this.indexTemplate = handlebars_1.default.compile(DEFAULT_INDEX_TEMPLATE, { noEscape: true });
        this.layoutTemplate = handlebars_1.default.compile(DEFAULT_LAYOUT);
    }
    init(templatesDir) {
        if (!fs_1.default.existsSync(templatesDir)) {
            return;
        }
        const partialsDir = path_1.default.join(templatesDir, 'partials');
        if (fs_1.default.existsSync(partialsDir)) {
            const partialFiles = fs_1.default.readdirSync(partialsDir);
            for (const file of partialFiles) {
                if (file.endsWith('.hbs')) {
                    const name = path_1.default.basename(file, '.hbs');
                    const content = fs_1.default.readFileSync(path_1.default.join(partialsDir, file), 'utf-8');
                    handlebars_1.default.registerPartial(name, content);
                }
            }
        }
        const layoutsDir = path_1.default.join(templatesDir, 'layouts');
        if (fs_1.default.existsSync(layoutsDir)) {
            const layoutFiles = fs_1.default.readdirSync(layoutsDir);
            for (const file of layoutFiles) {
                if (file.endsWith('.hbs')) {
                    const name = path_1.default.basename(file, '.hbs');
                    const content = fs_1.default.readFileSync(path_1.default.join(layoutsDir, file), 'utf-8');
                    this.customLayouts.set(name, handlebars_1.default.compile(content));
                }
            }
        }
        const entries = fs_1.default.readdirSync(templatesDir);
        for (const entry of entries) {
            const fullPath = path_1.default.join(templatesDir, entry);
            const stat = fs_1.default.statSync(fullPath);
            if (stat.isFile() && entry.endsWith('.hbs')) {
                const name = path_1.default.basename(entry, '.hbs');
                const content = fs_1.default.readFileSync(fullPath, 'utf-8');
                this.customTemplates.set(name, handlebars_1.default.compile(content));
            }
        }
        this.initialized = true;
    }
    renderPage(page) {
        const templateName = page.frontmatter.template;
        const template = templateName ? this.customTemplates.get(templateName) : undefined;
        const compiledTemplate = template || this.pageTemplate;
        const { title, date, tags } = page.frontmatter;
        const tagsStr = tags ? tags.join(', ') : '';
        const pageHtml = compiledTemplate({
            title,
            date: date || null,
            tagsStr: tagsStr || null,
            body: page.html,
        });
        const layoutName = page.frontmatter.layout;
        const layout = layoutName ? this.customLayouts.get(layoutName) : undefined;
        const compiledLayout = layout || this.layoutTemplate;
        return compiledLayout({
            title,
            date: date || null,
            tagsStr: tagsStr || null,
            body: pageHtml,
            content: page.html,
            pages: [],
        });
    }
    renderIndex(pages) {
        const items = pages.map((p) => ({
            title: p.frontmatter.title,
            date: p.frontmatter.date || null,
            tagsStr: p.frontmatter.tags ? p.frontmatter.tags.join(', ') : null,
            slug: p.slug,
        }));
        return this.indexTemplate({ pages: items });
    }
}
exports.TemplateEngine = TemplateEngine;
