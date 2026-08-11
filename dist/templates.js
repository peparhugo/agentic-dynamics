"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateEngine = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const handlebars_1 = __importDefault(require("handlebars"));
const DEFAULT_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{title}}</title>
</head>
<body>
  {{{body}}}
</body>
</html>`;
const DEFAULT_PAGE_TEMPLATE = `
  <header>
    <h1>{{title}}</h1>
    {{#if date}}<time>{{date}}</time>{{/if}}
    {{#if tags}}<p>Tags: {{tags}}</p>{{/if}}
  </header>
  <main>
    {{{content}}}
  </main>
  <footer>
    <a href="index.html">&larr; Back to index</a>
  </footer>`;
const DEFAULT_INDEX_TEMPLATE = `
  <header>
    <h1>Blog</h1>
  </header>
  <main>
    {{#if pages.length}}
      {{#each pages}}
    <article>
      <h2><a href="{{slug}}.html">{{title}}</a></h2>
      {{#if date}}<time>{{date}}</time>{{/if}}
      {{#if tags}}<p>Tags: {{tags}}</p>{{/if}}
    </article>
      {{/each}}
    {{else}}
    <p>No posts yet.</p>
    {{/if}}
  </main>`;
class TemplateEngine {
    constructor(config) {
        this.pageTemplates = new Map();
        this.layouts = new Map();
        this.initialized = false;
        this.templatesDir = config.templatesDir;
    }
    init() {
        if (this.initialized)
            return;
        this.initialized = true;
        if (!fs_1.default.existsSync(this.templatesDir))
            return;
        const partialsDir = path_1.default.join(this.templatesDir, 'partials');
        if (fs_1.default.existsSync(partialsDir)) {
            for (const file of fs_1.default.readdirSync(partialsDir)) {
                if (file.endsWith('.hbs')) {
                    const name = file.replace(/\.hbs$/, '');
                    const content = fs_1.default.readFileSync(path_1.default.join(partialsDir, file), 'utf-8');
                    handlebars_1.default.registerPartial(name, content);
                }
            }
        }
        const layoutsDir = path_1.default.join(this.templatesDir, 'layouts');
        if (fs_1.default.existsSync(layoutsDir)) {
            for (const file of fs_1.default.readdirSync(layoutsDir)) {
                if (file.endsWith('.hbs')) {
                    const name = file.replace(/\.hbs$/, '');
                    const content = fs_1.default.readFileSync(path_1.default.join(layoutsDir, file), 'utf-8');
                    this.layouts.set(name, handlebars_1.default.compile(content));
                }
            }
        }
        for (const file of fs_1.default.readdirSync(this.templatesDir)) {
            const fullPath = path_1.default.join(this.templatesDir, file);
            if (file.endsWith('.hbs') && !fs_1.default.statSync(fullPath).isDirectory()) {
                const name = file.replace(/\.hbs$/, '');
                const content = fs_1.default.readFileSync(fullPath, 'utf-8');
                this.pageTemplates.set(name, handlebars_1.default.compile(content));
            }
        }
    }
    renderPage(page) {
        this.init();
        const templateName = page.frontmatter.template || 'default';
        const layoutName = page.frontmatter.layout || 'default';
        const pageTemplate = this.pageTemplates.get(templateName);
        const pageBody = pageTemplate
            ? pageTemplate({
                title: page.frontmatter.title,
                date: page.frontmatter.date || '',
                tags: page.frontmatter.tags.length
                    ? page.frontmatter.tags.join(', ')
                    : '',
                content: page.html,
                slug: page.slug,
            })
            : handlebars_1.default.compile(DEFAULT_PAGE_TEMPLATE)({
                title: page.frontmatter.title,
                date: page.frontmatter.date || '',
                tags: page.frontmatter.tags.length
                    ? page.frontmatter.tags.join(', ')
                    : '',
                content: page.html,
                slug: page.slug,
            });
        const layout = this.layouts.get(layoutName);
        return layout
            ? layout({
                title: page.frontmatter.title,
                body: pageBody,
            })
            : handlebars_1.default.compile(DEFAULT_LAYOUT)({
                title: page.frontmatter.title,
                body: pageBody,
            });
    }
    renderIndex(pages, indexLayout, indexTemplate) {
        this.init();
        const sorted = [...pages].sort((a, b) => b.frontmatter.date.localeCompare(a.frontmatter.date));
        const indexData = sorted.map((p) => ({
            title: p.frontmatter.title,
            date: p.frontmatter.date || '',
            tags: p.frontmatter.tags.length ? p.frontmatter.tags.join(', ') : '',
            slug: p.slug,
        }));
        const itName = indexTemplate || 'index';
        const ilName = indexLayout || 'default';
        const it = this.pageTemplates.get(itName);
        const indexBody = it
            ? it({ pages: indexData })
            : handlebars_1.default.compile(DEFAULT_INDEX_TEMPLATE)({ pages: indexData });
        const layout = this.layouts.get(ilName);
        return layout
            ? layout({ title: 'Blog', body: indexBody })
            : handlebars_1.default.compile(DEFAULT_LAYOUT)({ title: 'Blog', body: indexBody });
    }
}
exports.TemplateEngine = TemplateEngine;
