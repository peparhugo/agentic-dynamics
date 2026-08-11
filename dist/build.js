"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const plugin_1 = require("./plugin");
const cache_1 = require("./cache");
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
function build(options) {
    const plugins = (0, plugin_1.loadPlugins)();
    const ctx = { options, pages: [] };
    for (const plugin of plugins) {
        plugin.onStart?.(ctx);
    }
    const templatesDir = path_1.default.resolve(options.templatesDir || './templates');
    const templateHash = (0, cache_1.computeTemplateHash)(templatesDir);
    const contentDir = path_1.default.resolve(options.contentDir);
    const cacheFile = path_1.default.resolve(contentDir, '..', '.ssg-cache.json');
    const cacheManager = new cache_1.CacheManager(cacheFile);
    const incremental = !!options.incremental;
    const clean = !!options.clean;
    if (clean) {
        cacheManager.clear();
    }
    if (incremental && !clean) {
        cacheManager.load();
    }
    for (const plugin of plugins) {
        plugin.beforeBuild?.(ctx);
    }
    const pages = readPages(options.contentDir);
    ctx.pages = pages;
    const absOutputDir = path_1.default.resolve(options.outputDir);
    fs_1.default.mkdirSync(absOutputDir, { recursive: true });
    const absContentDir = path_1.default.resolve(options.contentDir);
    let pagesBuilt = 0;
    let pagesSkipped = 0;
    for (const page of pages) {
        const filePath = path_1.default.join(absContentDir, `${page.slug}.md`);
        const raw = fs_1.default.readFileSync(filePath, 'utf-8');
        const contentHash = (0, cache_1.computeHash)(raw);
        if (incremental && !clean) {
            const cached = cacheManager.get(filePath, contentHash, templateHash);
            if (cached) {
                page.html = cached.html;
                pagesSkipped++;
                continue;
            }
        }
        for (const plugin of plugins) {
            plugin.onFile?.(page, ctx);
        }
        pagesBuilt++;
        if (incremental && !clean && page.html !== undefined) {
            cacheManager.set(filePath, contentHash, templateHash, page.html);
        }
    }
    for (const page of pages) {
        if (page.html !== undefined) {
            const outPath = path_1.default.join(absOutputDir, `${page.slug}.html`);
            fs_1.default.writeFileSync(outPath, page.html, 'utf-8');
        }
    }
    if (ctx._renderIndex) {
        const pagesData = pages.map((page) => ({
            title: page.frontmatter.title,
            slug: page.slug,
            date: page.frontmatter.date || null,
        }));
        const indexHtml = ctx._renderIndex(pagesData);
        fs_1.default.writeFileSync(path_1.default.join(absOutputDir, 'index.html'), indexHtml, 'utf-8');
    }
    for (const plugin of plugins) {
        plugin.afterBuild?.(ctx);
    }
    for (const plugin of plugins) {
        plugin.onEnd?.(ctx);
    }
    if (incremental && !clean) {
        cacheManager.updateTemplateHash(templateHash);
        cacheManager.save();
    }
    return {
        pagesBuilt,
        pagesSkipped,
        totalPages: pages.length,
    };
}
//# sourceMappingURL=build.js.map