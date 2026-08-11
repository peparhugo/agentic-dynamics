"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
const handlebars_1 = __importDefault(require("handlebars"));
function readPages(contentDir) {
    const absDir = path_1.default.resolve(contentDir);
    if (!fs_1.default.existsSync(absDir)) {
        throw new Error(`Content directory not found: ${absDir}`);
    }
    const entries = fs_1.default.readdirSync(absDir, { withFileTypes: true });
    const pages = [];
    for (const entry of entries) {
        if (!entry.isFile() || !entry.name.endsWith('.md')) {
            continue;
        }
        const filePath = path_1.default.join(absDir, entry.name);
        const raw = fs_1.default.readFileSync(filePath, 'utf-8');
        const parsed = (0, gray_matter_1.default)(raw);
        const slug = entry.name.replace(/\.md$/, '');
        const rawData = parsed.data;
        if (!rawData.title || typeof rawData.title !== 'string') {
            throw new Error(`Missing title in frontmatter for: ${entry.name}`);
        }
        let date;
        if (rawData.date instanceof Date) {
            date = rawData.date.toISOString().split('T')[0];
        }
        else if (typeof rawData.date === 'string') {
            date = rawData.date;
        }
        let tags;
        if (Array.isArray(rawData.tags)) {
            tags = rawData.tags.map((t) => String(t));
        }
        const frontmatter = {
            title: rawData.title,
            date,
            tags,
        };
        if (rawData.template && typeof rawData.template === 'string') {
            frontmatter.template = rawData.template;
        }
        if (rawData.layout === false || rawData.layout === '') {
            frontmatter.layout = '';
        }
        else if (rawData.layout && typeof rawData.layout === 'string') {
            frontmatter.layout = rawData.layout;
        }
        pages.push({
            frontmatter,
            content: parsed.content,
            slug,
        });
    }
    pages.sort((a, b) => {
        if (a.frontmatter.date && b.frontmatter.date) {
            return new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime();
        }
        if (a.frontmatter.date)
            return -1;
        if (b.frontmatter.date)
            return 1;
        return a.frontmatter.title.localeCompare(b.frontmatter.title);
    });
    return pages;
}
function loadPartial(partialsDir, name) {
    const filePath = path_1.default.join(partialsDir, `${name}.hbs`);
    if (fs_1.default.existsSync(filePath)) {
        const content = fs_1.default.readFileSync(filePath, 'utf-8');
        handlebars_1.default.registerPartial(name, content);
    }
}
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
function compileFile(filePath) {
    if (!fs_1.default.existsSync(filePath)) {
        throw new Error(`Template not found: ${filePath}`);
    }
    const content = fs_1.default.readFileSync(filePath, 'utf-8');
    return handlebars_1.default.compile(content);
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
function renderPage(page, env) {
    const htmlContent = marked_1.marked.parse(page.content, { async: false });
    const templateName = page.frontmatter.template || 'page';
    const layoutName = page.frontmatter.layout || 'default';
    const template = resolveTemplate(page.frontmatter.template, env.compiledTemplates, 'page');
    const layout = resolveLayout(page.frontmatter.layout, env.compiledLayouts, 'default');
    const tagsList = page.frontmatter.tags && page.frontmatter.tags.length > 0
        ? page.frontmatter.tags.join(', ')
        : '';
    const context = {
        title: page.frontmatter.title,
        date: page.frontmatter.date || null,
        tags: page.frontmatter.tags || [],
        tagsList,
        content: htmlContent,
        slug: page.slug,
    };
    const renderedContent = template(context);
    if (!layout) {
        return renderedContent;
    }
    return layout({
        title: page.frontmatter.title,
        body: renderedContent,
    });
}
function renderIndex(pages, env) {
    const template = resolveTemplate(undefined, env.compiledTemplates, 'index');
    const layout = resolveLayout(undefined, env.compiledLayouts, 'default');
    const pagesData = pages.map((page) => ({
        title: page.frontmatter.title,
        slug: page.slug,
        date: page.frontmatter.date || null,
    }));
    const context = {
        title: 'My Site',
        pages: pagesData,
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
function build(options) {
    const { contentDir, outputDir } = options;
    const templatesDir = path_1.default.resolve(options.templatesDir || './templates');
    if (!fs_1.default.existsSync(templatesDir)) {
        throw new Error(`Templates directory not found: ${templatesDir}`);
    }
    const pages = readPages(contentDir);
    const env = createTemplateEnv(templatesDir);
    const absOutputDir = path_1.default.resolve(outputDir);
    fs_1.default.mkdirSync(absOutputDir, { recursive: true });
    for (const page of pages) {
        const html = renderPage(page, env);
        const outPath = path_1.default.join(absOutputDir, `${page.slug}.html`);
        fs_1.default.writeFileSync(outPath, html, 'utf-8');
    }
    const indexHtml = renderIndex(pages, env);
    fs_1.default.writeFileSync(path_1.default.join(absOutputDir, 'index.html'), indexHtml, 'utf-8');
}
//# sourceMappingURL=build.js.map