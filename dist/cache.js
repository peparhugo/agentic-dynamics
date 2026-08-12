"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CacheManager = exports.CACHE_VERSION = exports.CACHE_FILE = void 0;
exports.hashContent = hashContent;
exports.hashTemplates = hashTemplates;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const crypto_1 = __importDefault(require("crypto"));
exports.CACHE_FILE = '.ssg-cache.json';
exports.CACHE_VERSION = 1;
const BUILTIN_TEMPLATE_HASH = 'builtin-templates';
function hashContent(content) {
    return crypto_1.default.createHash('sha256').update(content, 'utf8').digest('hex');
}
function hashTemplates(templatesDir) {
    if (!templatesDir || !fs_1.default.existsSync(templatesDir)) {
        return BUILTIN_TEMPLATE_HASH;
    }
    const files = [];
    const walk = (dir) => {
        const entries = fs_1.default
            .readdirSync(dir, { withFileTypes: true })
            .sort((a, b) => a.name.localeCompare(b.name));
        for (const entry of entries) {
            const full = path_1.default.join(dir, entry.name);
            if (entry.isDirectory()) {
                walk(full);
            }
            else if (entry.isFile()) {
                files.push(full);
            }
        }
    };
    walk(templatesDir);
    if (files.length === 0)
        return BUILTIN_TEMPLATE_HASH;
    const hasher = crypto_1.default.createHash('sha256');
    for (const file of files) {
        hasher.update(path_1.default.relative(templatesDir, file));
        hasher.update(fs_1.default.readFileSync(file));
    }
    return hasher.digest('hex');
}
class CacheManager {
    constructor(cacheFile, templatesDir, contentDir, outputDir) {
        this.cacheFile = cacheFile;
        this.templatesDir = templatesDir;
        this.contentDir = contentDir;
        this.outputDir = outputDir;
        this.entries = {};
        this.templateHash = hashTemplates(templatesDir);
        this.load();
    }
    load() {
        if (!fs_1.default.existsSync(this.cacheFile))
            return;
        try {
            const data = JSON.parse(fs_1.default.readFileSync(this.cacheFile, 'utf8'));
            if (data &&
                data.version === exports.CACHE_VERSION &&
                data.entries &&
                typeof data.entries === 'object') {
                this.entries = data.entries;
            }
        }
        catch {
            this.entries = {};
        }
    }
    getTemplateHash() {
        return this.templateHash;
    }
    hashSourceContent(content) {
        return hashContent(content);
    }
    isUnchanged(relPath, sourceHash) {
        const entry = this.entries[relPath];
        if (!entry)
            return false;
        if (entry.templateHash !== this.templateHash)
            return false;
        const currentSourceHash = sourceHash ??
            hashContent(fs_1.default.readFileSync(path_1.default.join(this.contentDir, relPath), 'utf8'));
        if (entry.sourceHash !== currentSourceHash)
            return false;
        return true;
    }
    getPage(relPath) {
        return this.entries[relPath]?.page;
    }
    getEntry(relPath) {
        return this.entries[relPath];
    }
    record(relPath, page, html, renderMs) {
        const prev = this.entries[relPath];
        if (prev && prev.page.slug && prev.page.slug !== page.slug) {
            const oldOut = path_1.default.join(this.outputDir, `${prev.page.slug}.html`);
            if (fs_1.default.existsSync(oldOut))
                fs_1.default.rmSync(oldOut);
        }
        const sourceHash = hashContent(fs_1.default.readFileSync(path_1.default.join(this.contentDir, relPath), 'utf8'));
        this.entries[relPath] = {
            sourceHash,
            templateHash: this.templateHash,
            page,
            html,
            renderMs,
        };
    }
    removeStale(activeFiles, outputDir) {
        for (const rel of Object.keys(this.entries)) {
            if (activeFiles.includes(rel))
                continue;
            const entry = this.entries[rel];
            const out = path_1.default.join(outputDir, `${entry.page.slug}.html`);
            if (fs_1.default.existsSync(out))
                fs_1.default.rmSync(out);
            delete this.entries[rel];
        }
    }
    save() {
        fs_1.default.mkdirSync(path_1.default.dirname(this.cacheFile), { recursive: true });
        const manifest = { version: exports.CACHE_VERSION, entries: this.entries };
        fs_1.default.writeFileSync(this.cacheFile, JSON.stringify(manifest, null, 2), 'utf8');
    }
}
exports.CacheManager = CacheManager;
