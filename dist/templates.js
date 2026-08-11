"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateEngine = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const handlebars_1 = __importDefault(require("handlebars"));
class TemplateEngine {
    constructor(templatesDir) {
        this.templatesDir = templatesDir;
        this.layoutsDir = path_1.default.join(templatesDir, 'layouts');
        this.partialsDir = path_1.default.join(templatesDir, 'partials');
        this.compiledLayouts = new Map();
        this.compiledTemplates = new Map();
        this.initialized = fs_1.default.existsSync(templatesDir);
        if (this.initialized) {
            this.loadPartials();
            this.loadLayouts();
            this.loadTemplates();
        }
    }
    loadPartials() {
        if (!fs_1.default.existsSync(this.partialsDir))
            return;
        const files = fs_1.default.readdirSync(this.partialsDir);
        for (const file of files) {
            if (file.endsWith('.hbs')) {
                const name = path_1.default.basename(file, '.hbs');
                const content = fs_1.default.readFileSync(path_1.default.join(this.partialsDir, file), 'utf-8');
                handlebars_1.default.registerPartial(name, content);
            }
        }
    }
    loadLayouts() {
        if (!fs_1.default.existsSync(this.layoutsDir))
            return;
        const files = fs_1.default.readdirSync(this.layoutsDir);
        for (const file of files) {
            if (file.endsWith('.hbs')) {
                const name = path_1.default.basename(file, '.hbs');
                const content = fs_1.default.readFileSync(path_1.default.join(this.layoutsDir, file), 'utf-8');
                this.compiledLayouts.set(name, handlebars_1.default.compile(content));
            }
        }
    }
    loadTemplates() {
        const files = fs_1.default.readdirSync(this.templatesDir);
        for (const file of files) {
            if (file.endsWith('.hbs')) {
                const name = path_1.default.basename(file, '.hbs');
                const content = fs_1.default.readFileSync(path_1.default.join(this.templatesDir, file), 'utf-8');
                this.compiledTemplates.set(name, handlebars_1.default.compile(content));
            }
        }
    }
    getLayout(name) {
        const layoutName = name || 'default';
        return this.compiledLayouts.get(layoutName) || null;
    }
    getTemplate(name) {
        if (!name)
            return null;
        return this.compiledTemplates.get(name) || null;
    }
    render(data) {
        if (!this.initialized)
            return null;
        let bodyHtml;
        const pageTemplate = this.getTemplate(data.template);
        if (pageTemplate) {
            bodyHtml = pageTemplate(data);
        }
        else {
            bodyHtml = data.content;
        }
        const layout = this.getLayout(data.layout);
        if (layout) {
            return layout({ ...data, body: bodyHtml });
        }
        return bodyHtml;
    }
    renderIndex(pages) {
        if (!this.initialized)
            return null;
        const layout = this.getLayout('index') || this.getLayout('default');
        if (!layout)
            return null;
        const listItems = pages
            .map((page) => `<li><a href="${page.slug}.html">${page.title}</a>${page.date ? ` <time>${page.date}</time>` : ''}${page.tags.length ? ` [${page.tags.join(', ')}]` : ''}</li>`)
            .join('\n');
        const content = `<h1>All Pages</h1>\n<ul>\n${listItems}\n</ul>`;
        return layout({ body: content, content, title: 'All Pages', tags: [], date: '' });
    }
}
exports.TemplateEngine = TemplateEngine;
//# sourceMappingURL=templates.js.map