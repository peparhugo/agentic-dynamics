"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseFile = parseFile;
exports.parseDirectory = parseDirectory;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const gray_matter_1 = __importDefault(require("gray-matter"));
const marked_1 = require("marked");
const cache_1 = require("./cache");
function parseFile(filePath) {
    const raw = fs_1.default.readFileSync(filePath, 'utf-8');
    const { data, content } = (0, gray_matter_1.default)(raw);
    let dateStr = '';
    if (data.date instanceof Date) {
        dateStr = data.date.toISOString().split('T')[0];
    }
    else if (typeof data.date === 'string') {
        dateStr = data.date;
    }
    const frontmatter = {
        title: data.title || 'Untitled',
        date: dateStr,
        tags: Array.isArray(data.tags) ? data.tags : [],
        template: typeof data.template === 'string' ? data.template : undefined,
        layout: typeof data.layout === 'string' ? data.layout : undefined,
    };
    const html = marked_1.marked.parse(content);
    const slug = path_1.default.basename(filePath, '.md');
    return { frontmatter, html, slug };
}
function parseDirectory(contentDir, cache, stats) {
    if (!fs_1.default.existsSync(contentDir)) {
        if (cache && cache.isPopulated()) {
            for (const key of Object.keys(cache.getCachedSlugs())) {
                cache.removeCachedPage(key);
            }
            for (const key of Object.keys(cache.getAllContentHashes())) {
                cache.removeContentHash(key);
            }
        }
        return [];
    }
    const files = fs_1.default.readdirSync(contentDir).filter((f) => f.endsWith('.md'));
    const pages = files.map((file) => {
        const fullPath = path_1.default.join(contentDir, file);
        const slug = path_1.default.basename(file, '.md');
        if (cache && cache.isPopulated()) {
            const newHash = cache_1.BuildCache.computeFileHash(fullPath);
            const cachedHash = cache.getContentHash(file);
            if (cachedHash === newHash && cache.getCachedPage(slug)) {
                if (stats)
                    stats.skipped++;
                cache.setContentHash(file, newHash);
                const cached = cache.getCachedPage(slug);
                return { ...cached.page };
            }
            cache.setContentHash(file, newHash);
            cache.removeCachedPage(slug);
        }
        if (stats)
            stats.parsed++;
        const page = parseFile(fullPath);
        return page;
    });
    return pages.sort((a, b) => {
        if (!a.frontmatter.date && !b.frontmatter.date)
            return 0;
        if (!a.frontmatter.date)
            return 1;
        if (!b.frontmatter.date)
            return -1;
        return b.frontmatter.date.localeCompare(a.frontmatter.date);
    });
}
//# sourceMappingURL=parser.js.map