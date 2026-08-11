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
const DEFAULT_PAGE_TEMPLATE = `<h1>{{title}}</h1>
{{#if date}}
<p>Date: {{date}}</p>
{{/if}}
{{#if tags.length}}
<p>Tags: {{#each tags}}{{this}}{{#unless @last}}, {{/unless}}{{/each}}</p>
{{/if}}
{{{content}}}
<p><a href="index.html">Back to index</a></p>`;
const DEFAULT_INDEX_TEMPLATE = `<h1>Site Index</h1>
<ul>
{{#each pages}}
<li><a href="{{slug}}.html">{{title}}</a></li>
{{/each}}
</ul>`;
const DEFAULT_LAYOUT_NAME = 'default';
const DEFAULT_PAGE_NAME = 'page';
const DEFAULT_INDEX_NAME = 'index';
class TemplateEngine {
    constructor(templatesDir) {
        this.compiled = {};
        this.builtins = {};
        this.templatesDir = path_1.default.resolve(templatesDir);
        this.builtins[`layout:${DEFAULT_LAYOUT_NAME}`] = handlebars_1.default.compile(DEFAULT_LAYOUT);
        this.builtins[`page:${DEFAULT_PAGE_NAME}`] = handlebars_1.default.compile(DEFAULT_PAGE_TEMPLATE);
        this.builtins[`page:${DEFAULT_INDEX_NAME}`] = handlebars_1.default.compile(DEFAULT_INDEX_TEMPLATE);
        this.loadPartials();
    }
    loadPartials() {
        const partialsDir = path_1.default.join(this.templatesDir, 'partials');
        if (!fs_1.default.existsSync(partialsDir))
            return;
        const entries = fs_1.default.readdirSync(partialsDir, { withFileTypes: true });
        for (const entry of entries) {
            if (!entry.isFile() || !entry.name.endsWith('.hbs'))
                continue;
            const partialPath = path_1.default.join(partialsDir, entry.name);
            const partialName = entry.name.replace(/\.hbs$/, '');
            const source = fs_1.default.readFileSync(partialPath, 'utf-8');
            handlebars_1.default.registerPartial(partialName, source);
        }
    }
    loadFromDisk(kind, name) {
        const subdir = kind === 'layout' ? 'layouts' : '';
        const dir = subdir ? path_1.default.join(this.templatesDir, subdir) : this.templatesDir;
        const filePath = path_1.default.join(dir, `${name}.hbs`);
        if (!fs_1.default.existsSync(filePath)) {
            return null;
        }
        const cacheKey = `disk:${kind}:${name}`;
        if (this.compiled[cacheKey]) {
            return this.compiled[cacheKey];
        }
        const source = fs_1.default.readFileSync(filePath, 'utf-8');
        const compiled = handlebars_1.default.compile(source);
        this.compiled[cacheKey] = compiled;
        return compiled;
    }
    getTemplate(kind, name) {
        const diskTemplate = this.loadFromDisk(kind, name);
        if (diskTemplate)
            return diskTemplate;
        const builtinKey = `${kind}:${name}`;
        const builtin = this.builtins[builtinKey];
        if (builtin)
            return builtin;
        const defaultKey = kind === 'layout'
            ? `layout:${DEFAULT_LAYOUT_NAME}`
            : `page:${DEFAULT_PAGE_NAME}`;
        return this.builtins[defaultKey];
    }
    renderPage(page) {
        const name = page.frontmatter.template || DEFAULT_PAGE_NAME;
        const template = this.getTemplate('page', name);
        return template({
            title: page.frontmatter.title,
            date: page.frontmatter.date,
            tags: page.frontmatter.tags,
            content: page.html,
            slug: page.slug,
        });
    }
    renderIndex(pages) {
        const template = this.getTemplate('page', DEFAULT_INDEX_NAME);
        const flatPages = pages.map((p) => ({
            slug: p.slug,
            title: p.frontmatter.title,
            date: p.frontmatter.date,
            tags: p.frontmatter.tags,
            content: p.html,
        }));
        return template({ pages: flatPages });
    }
    renderLayout(title, body, layoutName) {
        const name = layoutName || DEFAULT_LAYOUT_NAME;
        const layout = this.getTemplate('layout', name);
        return layout({ title, body });
    }
}
exports.TemplateEngine = TemplateEngine;
//# sourceMappingURL=templates.js.map