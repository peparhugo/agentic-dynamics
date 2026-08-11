"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CacheManager = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const crypto_1 = __importDefault(require("crypto"));
class CacheManager {
    constructor(cachePath) {
        this.manifest = null;
        this.htmlCache = new Map();
        this.pageCache = new Map();
        this.frontmatterCache = new Map();
        this._pageEntries = new Map();
        this._pagesBuilt = 0;
        this._pagesSkipped = 0;
        this._currentTemplatesHash = '';
        this.cachePath = cachePath;
    }
    get pagesBuilt() {
        return this._pagesBuilt;
    }
    get pagesSkipped() {
        return this._pagesSkipped;
    }
    get currentTemplatesHash() {
        return this._currentTemplatesHash;
    }
    incrementBuilt() {
        this._pagesBuilt++;
    }
    incrementSkipped() {
        this._pagesSkipped++;
    }
    getStats() {
        return { pagesBuilt: this._pagesBuilt, pagesSkipped: this._pagesSkipped };
    }
    load() {
        try {
            if (fs_1.default.existsSync(this.cachePath)) {
                const raw = fs_1.default.readFileSync(this.cachePath, 'utf-8');
                const manifest = JSON.parse(raw);
                this.manifest = manifest;
                for (const [slug, entry] of Object.entries(manifest.pages)) {
                    const page = {
                        frontmatter: entry.frontmatter,
                        html: entry.html,
                        slug,
                    };
                    this.pageCache.set(slug, page);
                    this.frontmatterCache.set(slug, entry.frontmatter);
                    this.htmlCache.set(slug, entry.renderedHTML);
                    this._pageEntries.set(slug, {
                        sourceHash: entry.sourceHash,
                        templateName: entry.templateName,
                        layoutName: entry.layoutName,
                    });
                }
                return manifest;
            }
        }
        catch {
            // Corrupt cache - ignore
        }
        return null;
    }
    getManifest() {
        return this.manifest;
    }
    save(newManifest) {
        const manifest = newManifest || this.manifest;
        if (manifest) {
            fs_1.default.writeFileSync(this.cachePath, JSON.stringify(manifest, null, 2), 'utf-8');
            this.manifest = manifest;
        }
    }
    delete() {
        if (fs_1.default.existsSync(this.cachePath)) {
            fs_1.default.unlinkSync(this.cachePath);
        }
        this.manifest = null;
        this.htmlCache.clear();
        this.pageCache.clear();
        this.frontmatterCache.clear();
        this._pageEntries.clear();
        this._pagesBuilt = 0;
        this._pagesSkipped = 0;
    }
    setPageEntry(slug, sourceHash, templateName, layoutName) {
        this._pageEntries.set(slug, { sourceHash, templateName, layoutName });
    }
    buildManifest(templatesHash) {
        const pages = {};
        for (const [slug, entry] of this._pageEntries) {
            const frontmatter = this.frontmatterCache.get(slug);
            const page = this.pageCache.get(slug);
            const renderedHTML = this.htmlCache.get(slug);
            if (frontmatter && page && renderedHTML !== undefined) {
                pages[slug] = {
                    sourceHash: entry.sourceHash,
                    templateName: entry.templateName,
                    layoutName: entry.layoutName,
                    frontmatter,
                    html: page.html,
                    renderedHTML,
                };
            }
        }
        return { pages, templatesHash };
    }
    computeFileHash(filePath) {
        if (!fs_1.default.existsSync(filePath)) {
            return '';
        }
        const content = fs_1.default.readFileSync(filePath);
        return crypto_1.default.createHash('md5').update(content).digest('hex');
    }
    computeTemplatesHash(templateDir) {
        if (!templateDir || !fs_1.default.existsSync(templateDir)) {
            this._currentTemplatesHash = 'default-templates';
            return this._currentTemplatesHash;
        }
        const hash = crypto_1.default.createHash('md5');
        this.hashDirectory(templateDir, hash);
        this._currentTemplatesHash = hash.digest('hex');
        return this._currentTemplatesHash;
    }
    hashDirectory(dir, hash) {
        if (!fs_1.default.existsSync(dir))
            return;
        const entries = fs_1.default.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name));
        for (const entry of entries) {
            const fullPath = path_1.default.join(dir, entry.name);
            if (entry.isDirectory()) {
                hash.update(entry.name);
                this.hashDirectory(fullPath, hash);
            }
            else if (entry.name.endsWith('.hbs') || entry.name.endsWith('.handlebars')) {
                hash.update(entry.name);
                hash.update(fs_1.default.readFileSync(fullPath));
            }
        }
    }
    isPageDirty(slug, sourceHash, templateName, layoutName, templatesChanged) {
        if (!this.manifest || !this.manifest.pages[slug]) {
            return true;
        }
        if (templatesChanged) {
            return true;
        }
        const cached = this.manifest.pages[slug];
        if (cached.sourceHash !== sourceHash) {
            return true;
        }
        if (cached.templateName !== templateName) {
            return true;
        }
        if (cached.layoutName !== layoutName) {
            return true;
        }
        return false;
    }
    getCachedPage(slug) {
        return this.pageCache.get(slug);
    }
    setCachedPage(slug, page) {
        this.pageCache.set(slug, { ...page });
    }
    getCachedHTML(slug) {
        return this.htmlCache.get(slug);
    }
    setCachedHTML(slug, html) {
        this.htmlCache.set(slug, html);
    }
    getCachedFrontmatter(slug) {
        return this.frontmatterCache.get(slug);
    }
    setCachedFrontmatter(slug, fm) {
        this.frontmatterCache.set(slug, { ...fm });
    }
}
exports.CacheManager = CacheManager;
//# sourceMappingURL=cache.js.map