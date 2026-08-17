"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const templates_1 = require("../templates");
function pageSummary(page) {
    return {
        slug: page.slug,
        title: page.title,
        date: page.date,
        tags: page.tags,
        url: `${page.slug}.html`,
    };
}
function buildPageContext(page, pages) {
    return {
        ...page.frontmatter,
        title: page.title,
        date: page.date,
        tags: page.tags,
        slug: page.slug,
        content: page.html,
        body: page.html,
        site: {
            pages: pages.map(pageSummary),
        },
    };
}
/**
 * Built-in plugin that renders each page through the template engine and writes
 * the resulting HTML to the output directory. Rendering happens on the
 * `afterBuild` hook so every page (and its metadata) is available for the
 * `site.pages` context used by templates and partials.
 */
class TemplatePlugin {
    constructor(context) {
        this.context = context;
        this.name = 'template';
        this.engine = new templates_1.TemplateEngine(context.templatesDir, {
            defaultTemplate: context.options.defaultTemplate ?? templates_1.DEFAULT_TEMPLATE_NAME,
            defaultLayout: context.options.defaultLayout ?? templates_1.DEFAULT_LAYOUT_NAME,
        });
    }
    afterBuild() {
        const { pages, outputDir } = this.context;
        for (const page of pages) {
            if (page.cached) {
                continue;
            }
            const rendered = this.engine.render(page.template, page.layout, buildPageContext(page, pages));
            const outFile = path_1.default.join(outputDir, `${page.slug}.html`);
            fs_1.default.mkdirSync(path_1.default.dirname(outFile), { recursive: true });
            fs_1.default.writeFileSync(outFile, rendered);
        }
    }
}
exports.TemplatePlugin = TemplatePlugin;
//# sourceMappingURL=template-plugin.js.map