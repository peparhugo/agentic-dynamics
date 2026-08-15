"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.SsgCache = exports.DEFAULT_CACHE_FILE = exports.CACHE_VERSION = void 0;
exports.hashContent = hashContent;
exports.snapshotPage = snapshotPage;
exports.applyParsedPage = applyParsedPage;
const crypto_1 = require("crypto");
const fs_1 = require("fs");
const path = __importStar(require("path"));
/**
 * Incremental build cache.
 *
 * A `.ssg-cache.json` manifest records, for every page slug, the hash of the
 * raw source content, the hash of the templates used to render it, and the
 * previously computed page data / rendered HTML. On an incremental build a
 * page is only re-parsed and re-rendered when its source or its templates
 * changed; otherwise the cached output is reused.
 */
exports.CACHE_VERSION = 1;
exports.DEFAULT_CACHE_FILE = '.ssg-cache.json';
function hashContent(content) {
    return (0, crypto_1.createHash)('sha256').update(content, 'utf8').digest('hex');
}
/**
 * The cache lives on disk as a JSON manifest, but a fresh instance with an
 * empty manifest is returned whenever the file is missing, unreadable, or
 * written by an incompatible version so builds never fail on a stale cache.
 */
class SsgCache {
    constructor(cacheFilePath, manifest) {
        this.cacheFilePath = cacheFilePath;
        this.manifest = manifest ?? { version: exports.CACHE_VERSION, files: {} };
    }
    static async load(cacheFilePath) {
        try {
            const raw = await fs_1.promises.readFile(cacheFilePath, 'utf8');
            const parsed = JSON.parse(raw);
            if (!parsed || parsed.version !== exports.CACHE_VERSION || !parsed.files) {
                return new SsgCache(cacheFilePath);
            }
            return new SsgCache(cacheFilePath, parsed);
        }
        catch {
            return new SsgCache(cacheFilePath);
        }
    }
    get(key) {
        return this.manifest.files[key];
    }
    set(key, entry) {
        this.manifest.files[key] = entry;
    }
    get entries() {
        return this.manifest.files;
    }
    async save() {
        await fs_1.promises.mkdir(path.dirname(this.cacheFilePath), { recursive: true });
        await fs_1.promises.writeFile(this.cacheFilePath, JSON.stringify(this.manifest, null, 2), 'utf8');
    }
}
exports.SsgCache = SsgCache;
/** Deep-copy the page fields the markdown plugin produces. */
function snapshotPage(page) {
    return {
        slug: page.slug,
        title: page.title,
        date: page.date,
        tags: page.tags ? [...page.tags] : [],
        content: page.content,
        html: page.html,
        sourcePath: page.sourcePath,
        template: page.template,
        layout: page.layout,
        data: page.data ? { ...page.data } : undefined,
    };
}
/** Copy parsed page fields from `source` onto `target` in place. */
function applyParsedPage(source, target) {
    target.slug = source.slug;
    target.title = source.title;
    target.date = source.date;
    target.tags = source.tags;
    target.content = source.content;
    target.html = source.html;
    target.sourcePath = source.sourcePath;
    target.template = source.template;
    target.layout = source.layout;
    target.data = source.data;
}
