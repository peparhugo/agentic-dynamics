"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CACHE_VERSION = exports.CACHE_FILENAME = void 0;
exports.defaultCacheFile = defaultCacheFile;
exports.loadManifest = loadManifest;
exports.saveManifest = saveManifest;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
exports.CACHE_FILENAME = '.ssg-cache.json';
exports.CACHE_VERSION = 1;
/** Returns the default location of the manifest within the output directory. */
function defaultCacheFile(outputDir) {
    return path_1.default.join(outputDir, exports.CACHE_FILENAME);
}
/** Loads the manifest from disk, returning an empty one when missing/corrupt. */
function loadManifest(cacheFile) {
    try {
        const raw = fs_1.default.readFileSync(cacheFile, 'utf-8');
        const parsed = JSON.parse(raw);
        if (parsed && parsed.version === exports.CACHE_VERSION && parsed.pages && typeof parsed.pages === 'object') {
            return { version: exports.CACHE_VERSION, pages: parsed.pages };
        }
    }
    catch {
        // Missing or corrupt cache -> treat as a clean build.
    }
    return { version: exports.CACHE_VERSION, pages: {} };
}
/** Persists the manifest to disk. */
function saveManifest(cacheFile, manifest) {
    fs_1.default.mkdirSync(path_1.default.dirname(cacheFile), { recursive: true });
    fs_1.default.writeFileSync(cacheFile, JSON.stringify(manifest, null, 2));
}
