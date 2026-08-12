"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.renderIndex = exports.renderPage = exports.DEFAULT_OUTPUT_DIR = exports.DEFAULT_CONTENT_DIR = void 0;
exports.findMarkdownFiles = findMarkdownFiles;
exports.readPages = readPages;
exports.sortPages = sortPages;
exports.buildSite = buildSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const markdown_1 = require("./markdown");
const template_1 = require("./template");
exports.DEFAULT_CONTENT_DIR = 'content';
exports.DEFAULT_OUTPUT_DIR = 'dist';
var template_2 = require("./template");
Object.defineProperty(exports, "renderPage", { enumerable: true, get: function () { return template_2.renderPage; } });
Object.defineProperty(exports, "renderIndex", { enumerable: true, get: function () { return template_2.renderIndex; } });
function findMarkdownFiles(contentDir) {
    const results = [];
    const walk = (dir) => {
        const entries = fs_1.default.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
            const full = path_1.default.join(dir, entry.name);
            if (entry.isDirectory()) {
                walk(full);
            }
            else if (entry.isFile() && /\.mdx?$/i.test(entry.name)) {
                results.push(full);
            }
        }
    };
    walk(contentDir);
    results.sort();
    return results;
}
function readPages(contentDir) {
    const files = findMarkdownFiles(contentDir);
    return files.map((file) => (0, markdown_1.parseMarkdown)(fs_1.default.readFileSync(file, 'utf8'), path_1.default.relative(contentDir, file)));
}
function sortPages(pages) {
    return [...pages].sort((a, b) => {
        const da = a.date ? new Date(a.date).getTime() : 0;
        const db = b.date ? new Date(b.date).getTime() : 0;
        if (da !== db)
            return db - da;
        return a.title.localeCompare(b.title);
    });
}
function buildSite(contentDir, outputDir, templatesDir = template_1.DEFAULT_TEMPLATES_DIR) {
    if (!fs_1.default.existsSync(contentDir)) {
        throw new Error(`content directory not found: ${contentDir}`);
    }
    const pages = sortPages(readPages(contentDir));
    const engine = new template_1.TemplateEngine(templatesDir);
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const files = [];
    for (const page of pages) {
        const name = `${page.slug}.html`;
        fs_1.default.writeFileSync(path_1.default.join(outputDir, name), (0, template_1.renderPage)(page, engine), 'utf8');
        files.push(name);
    }
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), (0, template_1.renderIndex)(pages, engine), 'utf8');
    files.push('index.html');
    return { pages: pages.length, outputDir, files };
}
