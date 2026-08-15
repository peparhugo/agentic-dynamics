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
class SsgEngine {
    constructor(options, config, plugins) {
        this.pages = [];
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
        const pages = [];
        for (const file of files) {
            const raw = await fs_1.promises.readFile(file, 'utf8');
            const { data, body } = (0, frontmatter_1.parseFrontmatter)(raw);
            const slug = slugFor(contentDir, file);
            let page = {
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
                    const result = await plugin.onFile(page, ctx);
                    if (result) {
                        page = result;
                    }
                }
            }
            pages.push(page);
        }
        this.pages = pages;
        await fs_1.promises.mkdir(outputDir, { recursive: true });
        for (const page of pages) {
            await fs_1.promises.mkdir(path_1.default.dirname(page.outputPath), { recursive: true });
            const html = page.html ?? this.template.renderPage(page);
            await fs_1.promises.writeFile(page.outputPath, html, 'utf8');
        }
        await fs_1.promises.writeFile(path_1.default.join(outputDir, 'index.html'), this.template.renderIndex(pages), 'utf8');
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
}
exports.SsgEngine = SsgEngine;
//# sourceMappingURL=engine.js.map