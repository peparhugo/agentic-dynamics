"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplatePlugin = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const handlebars_1 = __importDefault(require("handlebars"));
function loadPartialDir(partialsDir) {
    if (!fs_1.default.existsSync(partialsDir))
        return;
    const entries = fs_1.default.readdirSync(partialsDir, { withFileTypes: true });
    for (const entry of entries) {
        if (!entry.isFile() || !entry.name.endsWith('.hbs'))
            continue;
        const name = path_1.default.basename(entry.name, '.hbs');
        const content = fs_1.default.readFileSync(path_1.default.join(partialsDir, entry.name), 'utf-8');
        handlebars_1.default.registerPartial(name, content);
    }
}
function createTemplateEnv(templatesDir) {
    handlebars_1.default.registerPartial('nav', '');
    const partialsDir = path_1.default.join(templatesDir, 'partials');
    loadPartialDir(partialsDir);
    const layoutsDir = path_1.default.join(templatesDir, 'layouts');
    const compiledTemplates = {};
    const compiledLayouts = {};
    if (fs_1.default.existsSync(templatesDir)) {
        const entries = fs_1.default.readdirSync(templatesDir, { withFileTypes: true });
        for (const entry of entries) {
            if (!entry.isFile() || !entry.name.endsWith('.hbs'))
                continue;
            const name = path_1.default.basename(entry.name, '.hbs');
            const content = fs_1.default.readFileSync(path_1.default.join(templatesDir, entry.name), 'utf-8');
            compiledTemplates[name] = handlebars_1.default.compile(content);
        }
    }
    if (fs_1.default.existsSync(layoutsDir)) {
        const entries = fs_1.default.readdirSync(layoutsDir, { withFileTypes: true });
        for (const entry of entries) {
            if (!entry.isFile() || !entry.name.endsWith('.hbs'))
                continue;
            const name = path_1.default.basename(entry.name, '.hbs');
            const content = fs_1.default.readFileSync(path_1.default.join(layoutsDir, entry.name), 'utf-8');
            compiledLayouts[name] = handlebars_1.default.compile(content);
        }
    }
    return { compiledTemplates, compiledLayouts };
}
function resolveTemplate(templateName, compiledTemplates, defaultName) {
    const name = templateName || defaultName;
    const tmpl = compiledTemplates[name];
    if (!tmpl) {
        throw new Error(`Template not found: ${name}`);
    }
    return tmpl;
}
function resolveLayout(layoutName, compiledLayouts, defaultName) {
    if (layoutName === '')
        return null;
    const name = layoutName || defaultName;
    if (!compiledLayouts[name]) {
        if (layoutName) {
            throw new Error(`Layout not found: ${layoutName}`);
        }
        return null;
    }
    return compiledLayouts[name];
}
function renderPage(pageHtml, templateName, layoutName, title, date, tags, tagsList, slug, env) {
    const template = resolveTemplate(templateName, env.compiledTemplates, 'page');
    const layout = resolveLayout(layoutName, env.compiledLayouts, 'default');
    const context = {
        title,
        date: date || null,
        tags: tags || [],
        tagsList,
        content: pageHtml,
        slug,
    };
    const renderedContent = template(context);
    if (!layout) {
        return renderedContent;
    }
    return layout({
        title,
        body: renderedContent,
    });
}
function renderIndex(pages, env) {
    const template = resolveTemplate(undefined, env.compiledTemplates, 'index');
    const layout = resolveLayout(undefined, env.compiledLayouts, 'default');
    const context = {
        title: 'My Site',
        pages,
    };
    const renderedContent = template(context);
    if (!layout) {
        return renderedContent;
    }
    return layout({
        title: 'My Site',
        body: renderedContent,
    });
}
exports.TemplatePlugin = {
    name: 'template',
    beforeBuild(ctx) {
        const templatesDir = path_1.default.resolve(ctx.options.templatesDir || './templates');
        if (!fs_1.default.existsSync(templatesDir)) {
            throw new Error(`Templates directory not found: ${templatesDir}`);
        }
        const env = createTemplateEnv(templatesDir);
        ctx._templateEnv = env;
        ctx._renderIndex = function (pagesList) {
            return renderIndex(pagesList, env);
        };
        ctx._renderPage = function (pageHtml, templateName, layoutName, title, date, tags, tagsList, slug) {
            return renderPage(pageHtml, templateName, layoutName, title, date, tags, tagsList, slug, env);
        };
    },
    onFile(page, ctx) {
        const templateName = page.frontmatter.template;
        const layoutName = page.frontmatter.layout;
        const tagsList = page.frontmatter.tags && page.frontmatter.tags.length > 0
            ? page.frontmatter.tags.join(', ')
            : '';
        page.html = ctx._renderPage(page.content, templateName, layoutName, page.frontmatter.title, page.frontmatter.date, page.frontmatter.tags, tagsList, page.slug);
    },
};
//# sourceMappingURL=template.js.map