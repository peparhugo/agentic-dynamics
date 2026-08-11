"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateEngine = void 0;
const handlebars_1 = __importDefault(require("handlebars"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
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
const DEFAULT_PAGE_TEMPLATE = `<main>
  <article>
    <h1>{{title}}</h1>
    {{#if dateFormatted}}<div class="date">{{dateFormatted}}</div>{{/if}}
    {{#if tagsStr}}<div class="tags">Tags: {{tagsStr}}</div>{{/if}}
    {{{content}}}
  </article>
</main>
<footer>
  <a href="index.html">Back to index</a>
</footer>`;
const DEFAULT_INDEX_TEMPLATE = `<main>
  <h1>Pages</h1>
  <ul>
    {{#each pages}}
    <li><a href="{{slug}}.html">{{title}}</a>{{#if dateFormatted}} — {{dateFormatted}}{{/if}}{{#if tagsStr}} [{{tagsStr}}]{{/if}}</li>
    {{/each}}
  </ul>
</main>`;
class TemplateEngine {
    constructor(templateDir) {
        this.hbs = handlebars_1.default.create();
        this.templateDir = templateDir || null;
        this.templates = new Map();
        this.layouts = new Map();
        this.layouts.set('default', this.hbs.compile(DEFAULT_LAYOUT));
        this.templates.set('default', this.hbs.compile(DEFAULT_PAGE_TEMPLATE));
        this.indexTemplate = this.hbs.compile(DEFAULT_INDEX_TEMPLATE);
        if (this.templateDir && fs_1.default.existsSync(this.templateDir)) {
            this.loadPartials();
            this.loadLayouts();
            this.loadTemplates();
        }
    }
    loadPartials() {
        const partialsDir = path_1.default.join(this.templateDir, 'partials');
        if (!fs_1.default.existsSync(partialsDir))
            return;
        const files = fs_1.default.readdirSync(partialsDir);
        for (const file of files) {
            if (file.endsWith('.hbs') || file.endsWith('.handlebars')) {
                const name = path_1.default.basename(file, path_1.default.extname(file));
                const content = fs_1.default.readFileSync(path_1.default.join(partialsDir, file), 'utf-8');
                this.hbs.registerPartial(name, content);
            }
        }
    }
    loadLayouts() {
        const layoutsDir = path_1.default.join(this.templateDir, 'layouts');
        if (!fs_1.default.existsSync(layoutsDir))
            return;
        const files = fs_1.default.readdirSync(layoutsDir);
        for (const file of files) {
            if (file.endsWith('.hbs') || file.endsWith('.handlebars')) {
                const name = path_1.default.basename(file, path_1.default.extname(file));
                const content = fs_1.default.readFileSync(path_1.default.join(layoutsDir, file), 'utf-8');
                this.layouts.set(name, this.hbs.compile(content));
            }
        }
    }
    loadTemplates() {
        const files = fs_1.default.readdirSync(this.templateDir);
        for (const file of files) {
            if (!(file.endsWith('.hbs') || file.endsWith('.handlebars')))
                continue;
            const name = path_1.default.basename(file, path_1.default.extname(file));
            const content = fs_1.default.readFileSync(path_1.default.join(this.templateDir, file), 'utf-8');
            if (name === 'index') {
                this.indexTemplate = this.hbs.compile(content);
            }
            else {
                this.templates.set(name, this.hbs.compile(content));
            }
        }
    }
    renderPage(data, templateName, layoutName) {
        const tplName = templateName || 'default';
        const layName = layoutName || 'default';
        const template = this.templates.get(tplName) || this.templates.get('default');
        const body = template(data);
        const layout = this.layouts.get(layName) || this.layouts.get('default');
        return layout({ ...data, body });
    }
    renderIndex(data) {
        const body = this.indexTemplate(data);
        const layout = this.layouts.get('default');
        return layout({ title: data.title, body });
    }
}
exports.TemplateEngine = TemplateEngine;
//# sourceMappingURL=template-engine.js.map