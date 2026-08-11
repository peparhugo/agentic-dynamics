"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const template_engine_1 = require("../template-engine");
function toTemplateData(page) {
    const { title, date, tags } = page.frontmatter;
    return {
        title,
        date,
        dateFormatted: date ? new Date(date).toLocaleDateString('en-US') : undefined,
        tags,
        tagsStr: tags && tags.length > 0 ? tags.join(', ') : undefined,
        content: page.html,
        slug: page.slug,
    };
}
class TemplatePlugin {
    constructor() {
        this.name = 'template';
        this.engine = null;
    }
    onStart(context) {
        const { templateDir } = context.options;
        this.engine = new template_engine_1.TemplateEngine(templateDir);
    }
    onFile(page, context) {
        if (!this.engine)
            return;
        const cache = context.cache;
        const isFromCache = !!page._fromCache;
        const incremental = !!context.incremental;
        if (isFromCache && incremental && cache) {
            const cachedHTML = cache.getCachedHTML(page.slug);
            if (cachedHTML) {
                const outPath = path_1.default.join(context.outputDir, `${page.slug}.html`);
                fs_1.default.writeFileSync(outPath, cachedHTML, 'utf-8');
                return;
            }
        }
        const data = toTemplateData(page);
        const pageHTML = this.engine.renderPage(data, page.frontmatter.template, page.frontmatter.layout);
        const outPath = path_1.default.join(context.outputDir, `${page.slug}.html`);
        fs_1.default.writeFileSync(outPath, pageHTML, 'utf-8');
        if (incremental && cache && !isFromCache) {
            cache.setCachedHTML(page.slug, pageHTML);
        }
    }
    afterBuild(context) {
        if (!this.engine)
            return;
        const indexData = {
            title: 'My Static Site',
            pages: context.pages.map(toTemplateData),
        };
        const indexHTML = this.engine.renderIndex(indexData);
        fs_1.default.writeFileSync(path_1.default.join(context.outputDir, 'index.html'), indexHTML, 'utf-8');
    }
}
exports.TemplatePlugin = TemplatePlugin;
//# sourceMappingURL=template-plugin.js.map