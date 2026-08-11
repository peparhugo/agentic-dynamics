"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CacheManager = void 0;
exports.computeHash = computeHash;
exports.computeTemplateHash = computeTemplateHash;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const crypto_1 = __importDefault(require("crypto"));
function computeHash(content) {
    return crypto_1.default.createHash('sha256').update(content).digest('hex');
}
function computeTemplateHash(templatesDir) {
    const absDir = path_1.default.resolve(templatesDir);
    if (!fs_1.default.existsSync(absDir)) {
        return '';
    }
    const hashes = [];
    collectTemplateHashes(absDir, hashes);
    hashes.sort();
    return computeHash(hashes.join(''));
}
function collectTemplateHashes(dir, hashes) {
    if (!fs_1.default.existsSync(dir))
        return;
    const entries = fs_1.default.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
        const fullPath = path_1.default.join(dir, entry.name);
        if (entry.isDirectory()) {
            collectTemplateHashes(fullPath, hashes);
        }
        else if (entry.isFile() && entry.name.endsWith('.hbs')) {
            const content = fs_1.default.readFileSync(fullPath, 'utf-8');
            hashes.push(computeHash(content));
        }
    }
}
class CacheManager {
    constructor(manifestPath) {
        this.manifestPath = manifestPath;
        this.manifest = { templateHash: '', pages: {} };
    }
    load() {
        try {
            if (fs_1.default.existsSync(this.manifestPath)) {
                const raw = fs_1.default.readFileSync(this.manifestPath, 'utf-8');
                const parsed = JSON.parse(raw);
                if (parsed && parsed.pages) {
                    this.manifest = parsed;
                }
            }
        }
        catch {
            this.manifest = { templateHash: '', pages: {} };
        }
    }
    save() {
        const dir = path_1.default.dirname(this.manifestPath);
        if (!fs_1.default.existsSync(dir)) {
            fs_1.default.mkdirSync(dir, { recursive: true });
        }
        fs_1.default.writeFileSync(this.manifestPath, JSON.stringify(this.manifest, null, 2), 'utf-8');
    }
    clear() {
        this.manifest = { templateHash: '', pages: {} };
        if (fs_1.default.existsSync(this.manifestPath)) {
            fs_1.default.unlinkSync(this.manifestPath);
        }
    }
    get(filePath, contentHash, templateHash) {
        if (this.manifest.templateHash !== templateHash) {
            return null;
        }
        const entry = this.manifest.pages[filePath];
        if (!entry || entry.contentHash !== contentHash || entry.templateHash !== templateHash) {
            return null;
        }
        return entry;
    }
    set(filePath, contentHash, templateHash, html) {
        this.manifest.pages[filePath] = {
            contentHash,
            templateHash,
            html,
        };
    }
    updateTemplateHash(templateHash) {
        this.manifest.templateHash = templateHash;
    }
}
exports.CacheManager = CacheManager;
//# sourceMappingURL=cache.js.map