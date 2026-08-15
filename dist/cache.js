"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CacheManager = exports.CACHE_FILENAME = exports.CACHE_VERSION = void 0;
exports.hashString = hashString;
exports.hashFile = hashFile;
exports.computeTemplatesHash = computeTemplatesHash;
const fs_1 = require("fs");
const path_1 = __importDefault(require("path"));
const crypto_1 = __importDefault(require("crypto"));
exports.CACHE_VERSION = 1;
exports.CACHE_FILENAME = '.ssg-cache.json';
function hashString(input) {
    return crypto_1.default.createHash('sha256').update(input).digest('hex');
}
async function hashFile(filePath) {
    try {
        const content = await fs_1.promises.readFile(filePath);
        return hashString(content.toString('utf8'));
    }
    catch {
        return '';
    }
}
const TEMPLATE_EXTS = new Set(['.hbs', '.handlebars', '.html']);
async function collectTemplateFiles(root, dir, out) {
    let entries;
    try {
        entries = await fs_1.promises.readdir(dir, { withFileTypes: true });
    }
    catch {
        return;
    }
    for (const entry of entries) {
        const full = path_1.default.join(dir, entry.name);
        if (entry.isDirectory()) {
            await collectTemplateFiles(root, full, out);
        }
        else if (entry.isFile() &&
            TEMPLATE_EXTS.has(path_1.default.extname(entry.name).toLowerCase())) {
            const hash = await hashFile(full);
            out.push({ rel: path_1.default.relative(root, full), hash });
        }
    }
}
async function computeTemplatesHash(templatesDir) {
    const root = path_1.default.resolve(templatesDir);
    const files = [];
    await collectTemplateFiles(root, root, files);
    files.sort((a, b) => a.rel.localeCompare(b.rel));
    return hashString(files.map((f) => `${f.rel}:${f.hash}`).join('\n'));
}
class CacheManager {
    constructor(outputDir) {
        this.cachePath = path_1.default.join(path_1.default.resolve(outputDir), exports.CACHE_FILENAME);
    }
    async load() {
        try {
            const raw = await fs_1.promises.readFile(this.cachePath, 'utf8');
            const parsed = JSON.parse(raw);
            if (!parsed || parsed.version !== exports.CACHE_VERSION || !parsed.pages) {
                return undefined;
            }
            return parsed;
        }
        catch {
            return undefined;
        }
    }
    async save(manifest) {
        await fs_1.promises.mkdir(path_1.default.dirname(this.cachePath), { recursive: true });
        await fs_1.promises.writeFile(this.cachePath, JSON.stringify(manifest, null, 2), 'utf8');
    }
    async clear() {
        try {
            await fs_1.promises.rm(this.cachePath, { force: true });
        }
        catch {
            // ignore
        }
    }
}
exports.CacheManager = CacheManager;
//# sourceMappingURL=cache.js.map