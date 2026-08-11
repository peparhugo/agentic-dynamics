"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.BuildCache = void 0;
exports.hashFile = hashFile;
exports.hashContent = hashContent;
exports.hashDirectoryTemplates = hashTemplatesDir;
const crypto_1 = __importDefault(require("crypto"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
function gatherTemplateFiles(dir) {
    const files = [];
    if (!fs_1.default.existsSync(dir))
        return files;
    const entries = fs_1.default.readdirSync(dir);
    for (const entry of entries.sort()) {
        const fullPath = path_1.default.join(dir, entry);
        if (fs_1.default.statSync(fullPath).isDirectory()) {
            files.push(...gatherTemplateFiles(fullPath));
        }
        else if (entry.endsWith('.hbs')) {
            files.push(fullPath);
        }
    }
    return files;
}
function hashContent(content) {
    return crypto_1.default.createHash('md5').update(content).digest('hex');
}
function hashFile(filePath) {
    try {
        return hashContent(fs_1.default.readFileSync(filePath, 'utf-8'));
    }
    catch {
        return '';
    }
}
function hashTemplatesDir(templatesDir) {
    if (!fs_1.default.existsSync(templatesDir))
        return '';
    const files = gatherTemplateFiles(templatesDir);
    const combined = files.map((f) => fs_1.default.readFileSync(f, 'utf-8')).join('\n');
    return hashContent(combined);
}
function loadManifest(manifestPath) {
    try {
        if (fs_1.default.existsSync(manifestPath)) {
            return JSON.parse(fs_1.default.readFileSync(manifestPath, 'utf-8'));
        }
    }
    catch {
        // corrupted manifest
    }
    return null;
}
function saveManifest(manifestPath, manifest) {
    fs_1.default.mkdirSync(path_1.default.dirname(manifestPath), { recursive: true });
    fs_1.default.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
}
const AVG_MS_PER_PAGE = 50;
class BuildCache {
    constructor(contentDir, outputDir, templatesDir) {
        this.contentDir = contentDir;
        this.outputDir = outputDir;
        this.templatesDir = templatesDir;
        this.manifestPath = path_1.default.join(contentDir, '.ssg-cache.json');
        this.manifest = null;
        this.inMemoryHtmlCache = new Map();
        this.inMemoryFmCache = new Map();
        this._currentTplHash = null;
        this._currentTplHashComputed = false;
        this.stats = { totalPages: 0, pagesBuilt: 0, pagesSkipped: 0, timeSaved: '0ms' };
    }
    load() {
        this.manifest = loadManifest(this.manifestPath);
    }
    hasValidManifest() {
        return this.manifest !== null;
    }
    clear() {
        try {
            if (fs_1.default.existsSync(this.manifestPath)) {
                fs_1.default.unlinkSync(this.manifestPath);
            }
        }
        catch {
            // ignore
        }
        this.manifest = null;
        this.inMemoryHtmlCache.clear();
        this.inMemoryFmCache.clear();
        this._currentTplHash = null;
        this._currentTplHashComputed = false;
    }
    currentTemplateHash() {
        if (!this._currentTplHashComputed) {
            this._currentTplHashComputed = true;
            this._currentTplHash = this.templatesDir && fs_1.default.existsSync(this.templatesDir)
                ? hashTemplatesDir(this.templatesDir)
                : '';
        }
        return this._currentTplHash || '';
    }
    shouldSkipFile(sourcePath, slug) {
        if (!this.manifest)
            return false;
        const entry = this.manifest.pages[slug];
        if (!entry)
            return false;
        const currentSourceHash = hashFile(sourcePath);
        if (entry.hash !== currentSourceHash)
            return false;
        const outputPath = path_1.default.join(this.outputDir, `${slug}.html`);
        if (!fs_1.default.existsSync(outputPath))
            return false;
        if (this.templatesDir) {
            const tplHash = this.currentTemplateHash();
            if (this.manifest.templates !== tplHash)
                return false;
        }
        return true;
    }
    updateManifest(sourcePath, slug) {
        if (!this.manifest) {
            this.manifest = { pages: {} };
        }
        const currentHash = hashFile(sourcePath);
        this.manifest.pages[slug] = { hash: currentHash, slug, lastBuilt: Date.now() };
    }
    finalize() {
        if (this.manifest && this.templatesDir) {
            this.manifest.templates = this.currentTemplateHash();
        }
    }
    getCurrentTemplateHash() {
        return this.currentTemplateHash();
    }
    removeStaleEntries(knownSlugs) {
        if (!this.manifest)
            return;
        for (const key of Object.keys(this.manifest.pages)) {
            if (!knownSlugs.has(key)) {
                delete this.manifest.pages[key];
            }
        }
    }
    persist() {
        if (this.manifest) {
            saveManifest(this.manifestPath, this.manifest);
        }
    }
    cacheHtml(slug, html) {
        this.inMemoryHtmlCache.set(slug, html);
    }
    getCachedHtml(slug) {
        return this.inMemoryHtmlCache.get(slug);
    }
    cacheFrontmatter(slug, page) {
        this.inMemoryFmCache.set(slug, page);
    }
    getCachedFrontmatter(slug) {
        return this.inMemoryFmCache.get(slug);
    }
    computeSourceHash(sourcePath) {
        return hashFile(sourcePath);
    }
    reportStats(consoleLog = true) {
        const { pagesBuilt, pagesSkipped } = this.stats;
        const total = pagesBuilt + pagesSkipped;
        const savedMs = pagesSkipped * AVG_MS_PER_PAGE;
        this.stats.timeSaved = `${savedMs}ms`;
        if (consoleLog) {
            const pct = total > 0 ? Math.round((pagesSkipped / total) * 100) : 0;
            console.log(`Build stats: ${pagesBuilt} built, ${pagesSkipped} skipped (${savedMs}ms saved, ~${pct}% cached)`);
        }
    }
}
exports.BuildCache = BuildCache;
//# sourceMappingURL=cache.js.map