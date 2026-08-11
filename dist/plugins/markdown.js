"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
exports.parseMarkdownFile = parseMarkdownFile;
exports.readContentDirectory = readContentDirectory;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
function parseMarkdownFile(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    const { data, content } = (0, gray_matter_1.default)(raw);
    const slug = path_1.default.basename(filePath, '.md');
    const parsed = marked_1.marked.parse(content);
    const html = typeof parsed === 'object' && parsed !== null && 'html' in parsed
        ? parsed.html
        : parsed;
    const date = data.date instanceof Date
        ? data.date.toISOString().split('T')[0]
        : data.date || '';
    return {
        title: data.title || slug,
        date,
        tags: data.tags || [],
        content: html,
        slug,
        layout: data.layout || undefined,
        template: data.template || undefined,
    };
}
function readContentDirectory(contentDir) {
    if (!fs_1.default.existsSync(contentDir)) {
        return [];
    }
    const entries = fs_1.default.readdirSync(contentDir);
    const pages = [];
    for (const entry of entries) {
        if (entry.endsWith('.md')) {
            const page = parseMarkdownFile(path_1.default.join(contentDir, entry));
            if (page) {
                pages.push(page);
            }
        }
    }
    return pages;
}
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
        this.pages = [];
    }
    beforeBuild(options) {
        this.pages = readContentDirectory(options.contentDir);
    }
    onFile(page) {
        return page;
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
//# sourceMappingURL=markdown.js.map