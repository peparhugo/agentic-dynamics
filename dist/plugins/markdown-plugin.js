"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.MarkdownPlugin = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
function slugify(filename) {
    const name = path_1.default.basename(filename, path_1.default.extname(filename));
    return name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}
function readMarkdownFiles(contentDir) {
    if (!fs_1.default.existsSync(contentDir)) {
        return [];
    }
    return fs_1.default.readdirSync(contentDir)
        .filter(f => f.endsWith('.md'))
        .map(f => path_1.default.join(contentDir, f));
}
function parseFrontmatterFromFile(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    return (0, gray_matter_1.default)(raw);
}
function parsePage(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    const { data, content } = (0, gray_matter_1.default)(raw);
    const html = marked_1.marked.parse(content);
    const slug = slugify(path_1.default.basename(filePath));
    const frontmatter = {
        title: data.title || slug,
        date: data.date,
        tags: data.tags,
        template: data.template,
        layout: data.layout,
    };
    return { frontmatter, html, slug };
}
class MarkdownPlugin {
    constructor() {
        this.name = 'markdown';
    }
    beforeBuild(context) {
        const { contentDir } = context.options;
        const cache = context.cache;
        const incremental = !!context.incremental;
        const templatesChanged = !!context.templatesChanged;
        const files = readMarkdownFiles(contentDir);
        if (!files.length) {
            return;
        }
        const manifest = cache ? cache.getManifest() : null;
        for (const file of files) {
            const slug = slugify(path_1.default.basename(file));
            const sourceHash = cache ? cache.computeFileHash(file) : '';
            const { data } = parseFrontmatterFromFile(file);
            const templateName = data.template || 'default';
            const layoutName = data.layout || 'default';
            if (incremental && cache && manifest) {
                if (!cache.isPageDirty(slug, sourceHash, templateName, layoutName, templatesChanged)) {
                    const cachedPage = cache.getCachedPage(slug);
                    if (cachedPage) {
                        cachedPage._fromCache = true;
                        context.pages.push(cachedPage);
                        cache.setPageEntry(slug, sourceHash, templateName, layoutName);
                        continue;
                    }
                }
            }
            const page = parsePage(file);
            context.pages.push(page);
            if (incremental && cache) {
                cache.setCachedPage(slug, page);
                cache.setCachedFrontmatter(slug, page.frontmatter);
                cache.setPageEntry(slug, sourceHash, templateName, layoutName);
                cache.incrementBuilt();
            }
        }
    }
}
exports.MarkdownPlugin = MarkdownPlugin;
//# sourceMappingURL=markdown-plugin.js.map