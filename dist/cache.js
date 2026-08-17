"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CACHE_FILENAME = exports.CACHE_VERSION = void 0;
exports.hashContent = hashContent;
exports.hashFile = hashFile;
exports.defaultManifest = defaultManifest;
exports.loadManifest = loadManifest;
exports.saveManifest = saveManifest;
exports.computeTemplateHash = computeTemplateHash;
const crypto_1 = __importDefault(require("crypto"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const templates_1 = require("./templates");
exports.CACHE_VERSION = 1;
exports.CACHE_FILENAME = '.ssg-cache.json';
function hashContent(content) {
    return crypto_1.default.createHash('sha256').update(content).digest('hex');
}
function hashFile(file) {
    try {
        return hashContent(fs_1.default.readFileSync(file, 'utf8'));
    }
    catch {
        return null;
    }
}
function defaultManifest() {
    return { version: exports.CACHE_VERSION, pages: {} };
}
function loadManifest(file) {
    try {
        if (!fs_1.default.existsSync(file)) {
            return defaultManifest();
        }
        const parsed = JSON.parse(fs_1.default.readFileSync(file, 'utf8'));
        if (parsed &&
            parsed.version === exports.CACHE_VERSION &&
            parsed.pages &&
            typeof parsed.pages === 'object' &&
            !Array.isArray(parsed.pages)) {
            return parsed;
        }
    }
    catch {
        // Fall through to a fresh manifest on any parse error.
    }
    return defaultManifest();
}
function saveManifest(file, manifest) {
    fs_1.default.mkdirSync(path_1.default.dirname(file), { recursive: true });
    fs_1.default.writeFileSync(file, JSON.stringify(manifest, null, 2));
}
/**
 * Compute the template fingerprint for a page: the resolved template and
 * layout sources (or their built-in defaults) plus every registered partial.
 * Any change to one of these files changes the fingerprint and invalidates the
 * page's cache entry.
 */
function computeTemplateHash(options, templateName, layoutName) {
    const templatesDir = path_1.default.resolve(options.templatesDir ?? 'templates');
    const layoutsDir = path_1.default.join(templatesDir, 'layouts');
    const partialsDir = path_1.default.join(templatesDir, 'partials');
    const defaultTemplate = options.defaultTemplate ?? templates_1.DEFAULT_TEMPLATE_NAME;
    const defaultLayout = options.defaultLayout ?? templates_1.DEFAULT_LAYOUT_NAME;
    const templateFile = (0, templates_1.resolveTemplateFile)(templatesDir, templateName, defaultTemplate);
    const layoutFile = layoutName === false ? null : (0, templates_1.resolveLayoutFile)(layoutsDir, layoutName, defaultLayout);
    const parts = [];
    parts.push(templateFile ? (hashFile(templateFile) ?? '') : templates_1.DEFAULT_TEMPLATE_SOURCE);
    parts.push(layoutName === false ? '' : layoutFile ? (hashFile(layoutFile) ?? '') : templates_1.DEFAULT_LAYOUT_SOURCE);
    for (const partialFile of (0, templates_1.listPartialFiles)(partialsDir)) {
        parts.push(`${partialFile}:${hashFile(partialFile) ?? ''}`);
    }
    return hashContent(parts.join('\n'));
}
//# sourceMappingURL=cache.js.map