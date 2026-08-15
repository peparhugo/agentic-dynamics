"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.build = build;
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
const frontmatter_1 = require("./frontmatter");
const markdown_1 = require("./markdown");
const render_1 = require("./render");
const templates_1 = require("./templates");
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
async function build(options) {
    const contentDir = path_1.default.resolve(options.content);
    const outputDir = path_1.default.resolve(options.output);
    const templatesDir = options.templates ?? './templates';
    const engine = new templates_1.TemplateEngine(templatesDir);
    await engine.load();
    const files = (await findMarkdownFiles(contentDir)).sort();
    const pages = [];
    for (const file of files) {
        const raw = await fs_1.promises.readFile(file, 'utf8');
        const { data, body } = (0, frontmatter_1.parseFrontmatter)(raw);
        const contentHtml = (0, markdown_1.markdownToHtml)(body);
        const slug = slugFor(contentDir, file);
        pages.push({
            slug,
            title: titleFor(slug, data),
            date: data.date,
            tags: (0, frontmatter_1.normalizeTags)(data.tags),
            contentHtml,
            sourcePath: file,
            outputPath: path_1.default.join(outputDir, `${slug}.html`),
            template: data.template,
            layout: data.layout,
            data,
        });
    }
    await fs_1.promises.mkdir(outputDir, { recursive: true });
    for (const page of pages) {
        await fs_1.promises.mkdir(path_1.default.dirname(page.outputPath), { recursive: true });
        await fs_1.promises.writeFile(page.outputPath, (0, render_1.renderPage)(page, engine), 'utf8');
    }
    await fs_1.promises.writeFile(path_1.default.join(outputDir, 'index.html'), (0, render_1.renderIndex)(pages, engine), 'utf8');
    return pages;
}
//# sourceMappingURL=build.js.map