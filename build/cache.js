"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.BuildCache = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const crypto_1 = __importDefault(require("crypto"));
class BuildCache {
    constructor(cachePath) {
        this.data = null;
        this.cachePath = cachePath;
    }
    static computeHash(content) {
        return crypto_1.default.createHash('sha256').update(content).digest('hex');
    }
    static computeFileHash(filePath) {
        const content = fs_1.default.readFileSync(filePath, 'utf-8');
        return BuildCache.computeHash(content);
    }
    static computeTemplateHash(templateDir) {
        if (!fs_1.default.existsSync(templateDir))
            return '';
        const parts = [];
        const collectFiles = (dir, prefix) => {
            const entries = fs_1.default.readdirSync(dir, { withFileTypes: true });
            entries.sort((a, b) => a.name.localeCompare(b.name));
            for (const entry of entries) {
                const fullPath = path_1.default.join(dir, entry.name);
                const relPath = prefix ? `${prefix}/${entry.name}` : entry.name;
                if (entry.isDirectory()) {
                    collectFiles(fullPath, relPath);
                }
                else if (entry.name.endsWith('.hbs')) {
                    parts.push(relPath + ':' + BuildCache.computeFileHash(fullPath));
                }
            }
        };
        collectFiles(templateDir, '');
        return BuildCache.computeHash(parts.join('\n'));
    }
    load() {
        try {
            if (fs_1.default.existsSync(this.cachePath)) {
                const raw = fs_1.default.readFileSync(this.cachePath, 'utf-8');
                this.data = JSON.parse(raw);
                return true;
            }
        }
        catch {
            // invalid or corrupted cache, start fresh
        }
        if (!this.data) {
            this.data = {
                contentHashes: {},
                templateHash: '',
                pages: {},
            };
        }
        return false;
    }
    save() {
        if (this.data) {
            fs_1.default.writeFileSync(this.cachePath, JSON.stringify(this.data, null, 2));
        }
    }
    clear() {
        this.data = {
            contentHashes: {},
            templateHash: '',
            pages: {},
        };
        try {
            if (fs_1.default.existsSync(this.cachePath)) {
                fs_1.default.unlinkSync(this.cachePath);
            }
        }
        catch {
            // ignore
        }
    }
    isPopulated() {
        return (this.data !== null &&
            (Object.keys(this.data.contentHashes).length > 0 || this.data.templateHash !== ''));
    }
    getContentHash(relPath) {
        return this.data?.contentHashes[relPath];
    }
    setContentHash(relPath, hash) {
        if (this.data) {
            this.data.contentHashes[relPath] = hash;
        }
    }
    getTemplateHash() {
        return this.data?.templateHash || '';
    }
    setTemplateHash(hash) {
        if (this.data) {
            this.data.templateHash = hash;
        }
    }
    getCachedPage(slug) {
        return this.data?.pages[slug];
    }
    setCachedPage(slug, cached) {
        if (this.data) {
            this.data.pages[slug] = cached;
        }
    }
    removeCachedPage(slug) {
        if (this.data) {
            delete this.data.pages[slug];
        }
    }
    getIndexHtml() {
        return this.data?.indexHtml;
    }
    setIndexHtml(html) {
        if (this.data) {
            this.data.indexHtml = html;
        }
    }
    getIndexSlugs() {
        return this.data?.indexSlugs;
    }
    setIndexSlugs(slugs) {
        if (this.data) {
            this.data.indexSlugs = slugs;
        }
    }
    removeContentHash(relPath) {
        if (this.data) {
            delete this.data.contentHashes[relPath];
        }
    }
    getCachedSlugs() {
        return this.data ? Object.keys(this.data.pages) : [];
    }
    getAllContentHashes() {
        return this.data ? { ...this.data.contentHashes } : {};
    }
}
exports.BuildCache = BuildCache;
//# sourceMappingURL=cache.js.map