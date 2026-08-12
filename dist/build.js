"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildSite = buildSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const parse_1 = require("./parse");
const template_1 = require("./template");
function collectMarkdownFiles(dir) {
    const files = [];
    if (!fs_1.default.existsSync(dir)) {
        return files;
    }
    const entries = fs_1.default.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
        const full = path_1.default.join(dir, entry.name);
        if (entry.isDirectory()) {
            files.push(...collectMarkdownFiles(full));
        }
        else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
            files.push(full);
        }
    }
    return files;
}
function buildSite(contentDir, outputDir) {
    const files = collectMarkdownFiles(contentDir);
    const pages = files.map((f) => (0, parse_1.readMarkdownFile)(f));
    pages.sort((a, b) => a.slug.localeCompare(b.slug));
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const filesWritten = [];
    for (const page of pages) {
        const filePath = path_1.default.join(outputDir, `${page.slug}.html`);
        fs_1.default.writeFileSync(filePath, (0, template_1.renderPage)(page), 'utf8');
        filesWritten.push(filePath);
    }
    const indexPath = path_1.default.join(outputDir, 'index.html');
    fs_1.default.writeFileSync(indexPath, (0, template_1.renderIndex)(pages), 'utf8');
    filesWritten.push(indexPath);
    return { pages, filesWritten };
}
