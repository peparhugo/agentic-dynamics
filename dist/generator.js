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
exports.build = build;
const fs_1 = require("fs");
const path = __importStar(require("path"));
const markdown_1 = require("./markdown");
const render_1 = require("./render");
const CONTENT_EXTENSIONS = ['.md', '.markdown', '.mdown'];
function slugify(filename) {
    const base = filename.replace(/\.(md|markdown|mdown)$/i, '');
    return base
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}
async function collectMarkdownFiles(dir, baseDir) {
    const entries = await fs_1.promises.readdir(dir, { withFileTypes: true });
    const files = [];
    for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            files.push(...(await collectMarkdownFiles(full, baseDir)));
        }
        else if (entry.isFile() && CONTENT_EXTENSIONS.includes(path.extname(entry.name).toLowerCase())) {
            files.push(full);
        }
    }
    return files;
}
function makeSlug(file, contentDir) {
    const rel = path.relative(contentDir, file);
    const parsed = path.parse(rel);
    const joined = parsed.dir ? path.join(parsed.dir, parsed.name) : parsed.name;
    return slugify(joined.replace(/\\/g, '/'));
}
async function readPages(contentDir) {
    if (!(await dirExists(contentDir))) {
        throw new Error(`content directory not found: ${contentDir}`);
    }
    const files = await collectMarkdownFiles(contentDir, contentDir);
    files.sort();
    const pages = [];
    for (const file of files) {
        const source = await fs_1.promises.readFile(file, 'utf8');
        pages.push((0, markdown_1.parseMarkdown)(source, file, makeSlug(file, contentDir)));
    }
    return pages;
}
async function dirExists(dir) {
    try {
        const stat = await fs_1.promises.stat(dir);
        return stat.isDirectory();
    }
    catch {
        return false;
    }
}
async function build(options) {
    const { contentDir, outputDir } = options;
    const pages = await readPages(contentDir);
    await fs_1.promises.mkdir(outputDir, { recursive: true });
    for (const page of pages) {
        const html = (0, render_1.renderPageHtml)(page);
        await fs_1.promises.writeFile(path.join(outputDir, `${page.slug}.html`), html, 'utf8');
    }
    const indexHtml = (0, render_1.renderIndexHtml)(pages);
    await fs_1.promises.writeFile(path.join(outputDir, 'index.html'), indexHtml, 'utf8');
    return pages;
}
