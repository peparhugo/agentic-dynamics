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
exports.SsgEngine = void 0;
const fs_1 = require("fs");
const path = __importStar(require("path"));
const plugin_1 = require("./plugin");
const DEFAULT_TEMPLATES_DIR = 'templates';
const CONTENT_EXTENSIONS = ['.md', '.markdown', '.mdown'];
function slugify(filename) {
    const base = filename.replace(/\.(md|markdown|mdown)$/i, '');
    return base
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}
async function collectMarkdownFiles(dir) {
    const entries = await fs_1.promises.readdir(dir, { withFileTypes: true });
    const files = [];
    for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            files.push(...(await collectMarkdownFiles(full)));
        }
        else if (entry.isFile() &&
            CONTENT_EXTENSIONS.includes(path.extname(entry.name).toLowerCase())) {
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
async function dirExists(dir) {
    try {
        const stat = await fs_1.promises.stat(dir);
        return stat.isDirectory();
    }
    catch {
        return false;
    }
}
/**
 * Core SSG engine.
 *
 * Owns the plugin pipeline and orchestrates the lifecycle hooks:
 * `onStart` -> `beforeBuild` -> `onFile` (per content file) -> `afterBuild`
 * -> write outputs -> `onEnd`. Plugins transform pages and contribute output
 * files; the engine is responsible for discovery, ordering, and writing.
 */
class SsgEngine {
    constructor(plugins, options, config = {}) {
        const normalized = {
            ...options,
            templatesDir: options.templatesDir ?? DEFAULT_TEMPLATES_DIR,
        };
        this.pipeline = new plugin_1.PluginPipeline(plugins);
        this.context = {
            config,
            options: normalized,
            pages: [],
            outputFiles: new Map(),
            engine: this,
        };
    }
    getContext() {
        return this.context;
    }
    /**
     * Run a full build lifecycle (used by the `build` command).
     */
    async build() {
        await this.pipeline.run('onStart', this.context);
        const pages = await this.collectPages();
        await this.pipeline.run('onEnd', this.context);
        await this.writeOutputs();
        return pages;
    }
    /**
     * Rebuild content without running start/end hooks (used by the dev server
     * to refresh the site on file changes).
     */
    async rebuild() {
        const pages = await this.collectPages();
        await this.writeOutputs();
        return pages;
    }
    async collectPages() {
        this.context.outputFiles.clear();
        await this.pipeline.run('beforeBuild', this.context);
        await this.collectContent();
        await this.pipeline.run('afterBuild', this.context);
        return this.context.pages;
    }
    /**
     * Run the serve lifecycle. The dev-server plugin starts the server during
     * `onStart`; the resulting server handle is returned to the caller.
     */
    async serve() {
        const devPlugin = this.pipeline
            .getPlugins()
            .find((plugin) => plugin.name === 'dev-server');
        if (!devPlugin || typeof devPlugin.getServer !== 'function') {
            throw new Error('dev-server plugin not loaded');
        }
        await this.pipeline.run('onStart', this.context);
        return devPlugin.getServer();
    }
    async collectContent() {
        const { contentDir } = this.context.options;
        if (!(await dirExists(contentDir))) {
            throw new Error(`content directory not found: ${contentDir}`);
        }
        const files = await collectMarkdownFiles(contentDir);
        files.sort();
        const pages = [];
        for (const file of files) {
            const source = await fs_1.promises.readFile(file, 'utf8');
            const slug = makeSlug(file, contentDir);
            const page = {
                slug,
                title: slug,
                tags: [],
                content: source,
                html: source,
                sourcePath: file,
            };
            await this.pipeline.run('onFile', page, this.context);
            pages.push(page);
        }
        this.context.pages = pages;
    }
    async writeOutputs() {
        const { outputDir } = this.context.options;
        await fs_1.promises.mkdir(outputDir, { recursive: true });
        for (const [name, content] of this.context.outputFiles) {
            await fs_1.promises.writeFile(path.join(outputDir, name), content, 'utf8');
        }
    }
}
exports.SsgEngine = SsgEngine;
