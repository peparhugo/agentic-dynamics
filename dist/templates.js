"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateEngine = void 0;
const handlebars_1 = __importDefault(require("handlebars"));
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
const EXTENSIONS = ['.hbs', '.handlebars', '.html'];
const PARTIAL_EXTENSIONS = ['.hbs', '.handlebars'];
const DEFAULT_PAGE_TEMPLATE = `  <article>
    <h1>{{title}}</h1>
    {{#if meta}}<p class="meta">{{{meta}}}</p>{{/if}}
    {{{contentHtml}}}
  </article>
`;
const DEFAULT_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 0 auto; padding: 2rem 1rem; line-height: 1.6; }
    a { color: #2563eb; }
    .tags span { background: #e5e7eb; border-radius: 9999px; padding: 0.15rem 0.6rem; font-size: 0.8rem; margin-right: 0.35rem; }
    .meta { color: #6b7280; font-size: 0.9rem; }
  </style>
</head>
<body>
  <p><a href="index.html">&larr; All pages</a></p>
{{{body}}}
</body>
</html>
`;
function stripExtension(name) {
    for (const ext of EXTENSIONS) {
        if (name.endsWith(ext)) {
            return name.slice(0, -ext.length);
        }
    }
    return name;
}
async function readEntries(dir) {
    try {
        return await fs_1.promises.readdir(dir, { withFileTypes: true });
    }
    catch {
        return [];
    }
}
class TemplateEngine {
    constructor(root) {
        this.pageTemplates = new Map();
        this.layouts = new Map();
        this.root = path_1.default.resolve(root);
        this.hbs = handlebars_1.default.create();
        this.defaultPageTemplate = this.hbs.compile(DEFAULT_PAGE_TEMPLATE);
        this.defaultLayout = this.hbs.compile(DEFAULT_LAYOUT);
    }
    async load() {
        await this.loadPartials();
        await this.loadLayouts();
        await this.loadPageTemplates();
    }
    async loadPartials() {
        const dir = path_1.default.join(this.root, 'partials');
        for (const entry of await readEntries(dir)) {
            if (!entry.isFile()) {
                continue;
            }
            const ext = path_1.default.extname(entry.name);
            if (!PARTIAL_EXTENSIONS.includes(ext)) {
                continue;
            }
            const name = entry.name.slice(0, -ext.length);
            const source = await fs_1.promises.readFile(path_1.default.join(dir, entry.name), 'utf8');
            this.hbs.registerPartial(name, this.hbs.compile(source));
        }
    }
    async loadLayouts() {
        const dir = path_1.default.join(this.root, 'layouts');
        for (const entry of await readEntries(dir)) {
            if (!entry.isFile()) {
                continue;
            }
            const ext = path_1.default.extname(entry.name);
            if (!EXTENSIONS.includes(ext)) {
                continue;
            }
            const name = entry.name.slice(0, -ext.length);
            const source = await fs_1.promises.readFile(path_1.default.join(dir, entry.name), 'utf8');
            this.layouts.set(name, this.hbs.compile(source));
        }
    }
    async loadPageTemplates() {
        for (const entry of await readEntries(this.root)) {
            if (!entry.isFile()) {
                continue;
            }
            const ext = path_1.default.extname(entry.name);
            if (!EXTENSIONS.includes(ext)) {
                continue;
            }
            const name = entry.name.slice(0, -ext.length);
            const source = await fs_1.promises.readFile(path_1.default.join(this.root, entry.name), 'utf8');
            this.pageTemplates.set(name, this.hbs.compile(source));
        }
    }
    render(name, context) {
        const template = this.pageTemplates.get(stripExtension(name));
        if (template) {
            return template(context);
        }
        return this.defaultPageTemplate(context);
    }
    renderLayout(name, context) {
        const layout = this.layouts.get(stripExtension(name));
        if (layout) {
            return layout(context);
        }
        return this.defaultLayout(context);
    }
}
exports.TemplateEngine = TemplateEngine;
//# sourceMappingURL=templates.js.map