"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SsgEngine = void 0;
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
const frontmatter_1 = require("./frontmatter");
const markdown_1 = require("./plugins/markdown");
const template_1 = require("./plugins/template");
const cache_1 = require("./cache");
const MARKDOWN_EXT = /\.(md|markdown)$/i;
async function findMarkdownFiles(dir) {
    const results = [];
    let entries;
    try {
        entries = await fs_1.promises.readdir(dir, { withFileTypes: true });
    }
    catch {
        return results;
    }
    for (const entry of entries) {
        const full = path_1.default.join(dir, entry.name);
        if (entry.isDirectory()) {
            results.push(...(await findMarkdownFiles(full)));
        }
        else if (entry.isFile() && MARKDOWN_EXT.test(entry.name)) {
            results.push(full);
        }
    }
    return results;
}
function slugFor(contentDir, filePath) {
    const relative = path_1.default.relative(contentDir, filePath);
    const withoutExt = relative.replace(MARKDOWN_EXT, '');
    return withoutExt.split(path_1.default.sep).join('/');
}
function titleFor(slug, data) {
    if (data.title && data.title.trim()) {
        return data.title.trim();
    }
    const segments = slug.split('/').filter(Boolean);
    return segments[segments.length - 1] ?? slug;
}
function cachedToPage(cached, sourcePath) {
    return {
        slug: cached.slug,
        title: cached.title,
        date: cached.date,
        tags: cached.tags,
        contentHtml: cached.contentHtml,
        sourcePath,
        outputPath: cached.outputPath,
        template: cached.template,
        layout: cached.layout,
        data: cached.data,
        content: cached.content,
        html: cached.html,
    };
}
function pageToCache(page, sourceHash, templateHash, buildTimeMs) {
    return {
        slug: page.slug,
        title: page.title,
        date: page.date,
        tags: page.tags,
        contentHtml: page.contentHtml,
        sourcePath: page.sourcePath,
        outputPath: page.outputPath,
        template: page.template,
        layout: page.layout,
        data: page.data,
        content: page.content,
        html: page.html,
        sourceHash,
        templateHash,
        buildTimeMs,
    };
}
class SsgEngine {
    constructor(options, config, plugins) {
        this.pages = [];
        this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
        this.options = options;
        this.config = config;
        this.markdown = new markdown_1.MarkdownPlugin();
        this.template = new template_1.TemplatePlugin(options.templates ?? './templates');
        this.plugins = [this.markdown, this.template, ...plugins];
        this.context = {
            options,
            config,
            cwd: process.cwd(),
        };
    }
    get builtPages() {
        return this.pages;
    }
    get buildStats() {
        return { ...this.stats };
    }
    async run() {
        const ctx = this.context;
        for (const plugin of this.plugins) {
            if (plugin.onStart) {
                await plugin.onStart(ctx);
            }
        }
        for (const plugin of this.plugins) {
            if (plugin.beforeBuild) {
                await plugin.beforeBuild(ctx);
            }
        }
        const contentDir = path_1.default.resolve(this.options.content);
        const outputDir = path_1.default.resolve(this.options.output);
        const files = (await findMarkdownFiles(contentDir)).sort();
        const incremental = this.options.incremental === true;
        const clean = this.options.clean === true;
        const cache = new cache_1.CacheManager(outputDir);
        if (clean) {
            await cache.clear();
        }
        const manifest = incremental ? await cache.load() : undefined;
        const templatesHash = incremental
            ? await (0, cache_1.computeTemplatesHash)(this.options.templates ?? './templates')
            : '';
        this.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
        const pages = [];
        const nextPages = {};
        for (const file of files) {
            const started = Date.now();
            const sourceHash = await (0, cache_1.hashFile)(file);
            const cached = manifest?.pages[file];
            const sourceChanged = !cached || cached.sourceHash !== sourceHash;
            const templateChanged = !cached || cached.templateHash !== templatesHash;
            if (incremental && cached && !sourceChanged && !templateChanged) {
                const page = cachedToPage(cached, file);
                pages.push(page);
                nextPages[file] = cached;
                this.stats.pagesSkipped += 1;
                this.stats.timeSavedMs += cached.buildTimeMs ?? 0;
                continue;
            }
            let page;
            if (incremental && cached && !sourceChanged) {
                page = cachedToPage(cached, file);
                page.html = this.template.renderPage(page);
            }
            else {
                const raw = await fs_1.promises.readFile(file, 'utf8');
                const { data, body } = (0, frontmatter_1.parseFrontmatter)(raw);
                const slug = slugFor(contentDir, file);
                let built = {
                    slug,
                    title: titleFor(slug, data),
                    date: data.date,
                    tags: (0, frontmatter_1.normalizeTags)(data.tags),
                    contentHtml: '',
                    content: body,
                    sourcePath: file,
                    outputPath: path_1.default.join(outputDir, `${slug}.html`),
                    template: data.template,
                    layout: data.layout,
                    data,
                };
                for (const plugin of this.plugins) {
                    if (plugin.onFile) {
                        const result = await plugin.onFile(built, ctx);
                        if (result) {
                            built = result;
                        }
                    }
                }
                built.html = this.renderPageHtml(built);
                page = built;
            }
            const buildTimeMs = Date.now() - started;
            this.stats.pagesBuilt += 1;
            pages.push(page);
            nextPages[file] = pageToCache(page, sourceHash, templatesHash, buildTimeMs);
        }
        this.pages = pages;
        await fs_1.promises.mkdir(outputDir, { recursive: true });
        for (const page of pages) {
            await fs_1.promises.mkdir(path_1.default.dirname(page.outputPath), { recursive: true });
            const html = page.html ?? this.renderPageHtml(page);
            await fs_1.promises.writeFile(page.outputPath, html, 'utf8');
        }
        await fs_1.promises.writeFile(path_1.default.join(outputDir, 'index.html'), this.template.renderIndex(pages), 'utf8');
        if (incremental) {
            await cache.save({
                version: 1,
                templatesHash,
                pages: nextPages,
            });
        }
        for (const plugin of this.plugins) {
            if (plugin.afterBuild) {
                await plugin.afterBuild(pages, ctx);
            }
        }
        for (const plugin of this.plugins) {
            if (plugin.onEnd) {
                await plugin.onEnd(ctx);
            }
        }
        return pages;
    }
    renderPageHtml(page) {
        return page.html ?? this.template.renderPage(page);
    }
}
exports.SsgEngine = SsgEngine;
//# sourceMappingURL=engine.js.map