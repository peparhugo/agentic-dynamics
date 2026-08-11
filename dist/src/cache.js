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
exports.hashContent = hashContent;
exports.hashFile = hashFile;
exports.computeTemplatesHash = computeTemplatesHash;
exports.loadCache = loadCache;
exports.saveCache = saveCache;
exports.removeCache = removeCache;
exports.createEmptyManifest = createEmptyManifest;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const crypto = __importStar(require("crypto"));
function hashContent(content) {
    return crypto.createHash('sha256').update(content).digest('hex');
}
function hashFile(filePath) {
    if (!fs.existsSync(filePath))
        return '';
    return hashContent(fs.readFileSync(filePath, 'utf-8'));
}
function computeTemplatesHash(templatesDir) {
    if (!templatesDir || !fs.existsSync(templatesDir))
        return '';
    const hashes = [];
    const walkDir = (dir) => {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
                walkDir(fullPath);
            }
            else if (entry.isFile() && (entry.name.endsWith('.hbs') || entry.name.endsWith('.html'))) {
                hashes.push(hashFile(fullPath));
            }
        }
    };
    walkDir(templatesDir);
    return hashContent(hashes.sort().join(''));
}
function loadCache(cachePath) {
    if (!fs.existsSync(cachePath))
        return null;
    try {
        const data = JSON.parse(fs.readFileSync(cachePath, 'utf-8'));
        if (data && data.version === 1 && typeof data.pages === 'object') {
            return data;
        }
        return null;
    }
    catch {
        return null;
    }
}
function saveCache(cachePath, manifest) {
    const dir = path.dirname(cachePath);
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(cachePath, JSON.stringify(manifest, null, 2));
}
function removeCache(cachePath) {
    if (fs.existsSync(cachePath)) {
        fs.unlinkSync(cachePath);
    }
}
function createEmptyManifest() {
    return { version: 1, pages: {}, templatesHash: '' };
}
//# sourceMappingURL=cache.js.map