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
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const config_1 = require("./config");
const markdown_plugin_1 = require("../plugins/markdown-plugin");
const template_plugin_1 = require("../plugins/template-plugin");
const cache_1 = require("./cache");
function getDefaultPlugins() {
    return [
        new markdown_plugin_1.MarkdownPlugin(),
        new template_plugin_1.TemplatePlugin(),
    ];
}
class SsgEngine {
    constructor(additionalPlugins) {
        const config = (0, config_1.loadConfig)();
        const configPlugins = config.plugins || [];
        if (configPlugins.length > 0) {
            this.plugins = [...configPlugins, ...(additionalPlugins || [])];
        }
        else {
            this.plugins = [...getDefaultPlugins(), ...(additionalPlugins || [])];
        }
    }
    build(contentDir, outputDir, templatesDir, options) {
        const absoluteContent = path.resolve(contentDir);
        const absoluteOutput = path.resolve(outputDir);
        if (!fs.existsSync(absoluteContent)) {
            throw new Error(`Content directory does not exist: ${absoluteContent}`);
        }
        const cachePath = path.join(absoluteOutput, '.ssg-cache.json');
        const incremental = options?.incremental === true;
        const clean = options?.clean === true;
        if (clean && fs.existsSync(cachePath)) {
            (0, cache_1.removeCache)(cachePath);
        }
        let cache = null;
        if (incremental) {
            cache = (0, cache_1.loadCache)(cachePath);
            if (!cache) {
                cache = (0, cache_1.createEmptyManifest)();
            }
        }
        const templatesHash = templatesDir && fs.existsSync(templatesDir)
            ? (0, cache_1.computeTemplatesHash)(path.resolve(templatesDir))
            : '';
        const skippedSlugs = new Set();
        const ctx = {
            contentDir: absoluteContent,
            outputDir: absoluteOutput,
            templatesDir,
            cache,
            cachePath: incremental ? cachePath : undefined,
            skippedSlugs,
            templatesHash,
        };
        for (const plugin of this.plugins) {
            if (plugin.setContext)
                plugin.setContext(ctx);
        }
        for (const plugin of this.plugins) {
            if (plugin.onStart)
                plugin.onStart();
        }
        const files = fs.readdirSync(absoluteContent).filter((f) => f.endsWith('.md'));
        const pages = [];
        const newCacheManifest = { version: 1, pages: {}, templatesHash };
        let pagesBuilt = 0;
        let pagesSkipped = 0;
        for (const file of files) {
            const slug = path.basename(file, '.md');
            const filePath = path.join(absoluteContent, file);
            const sourceHash = (0, cache_1.hashFile)(filePath);
            const cachedEntry = cache?.pages[slug];
            const canSkip = incremental && cachedEntry &&
                cachedEntry.sourceHash === sourceHash &&
                cachedEntry.templatesHash === templatesHash;
            if (canSkip) {
                pagesSkipped++;
                skippedSlugs.add(slug);
                const outputPath = path.join(absoluteOutput, `${slug}.html`);
                if (!fs.existsSync(outputPath)) {
                    if (!fs.existsSync(absoluteOutput)) {
                        fs.mkdirSync(absoluteOutput, { recursive: true });
                    }
                    fs.writeFileSync(outputPath, cachedEntry.outputHtml);
                }
                newCacheManifest.pages[slug] = cachedEntry;
                const page = {
                    slug,
                    title: cachedEntry.title || slug,
                    date: cachedEntry.date,
                    tags: cachedEntry.tags,
                    template: cachedEntry.template,
                    layout: cachedEntry.layout,
                    content: '',
                    html: cachedEntry.outputHtml,
                };
                pages.push(page);
            }
            else {
                pagesBuilt++;
                const content = fs.readFileSync(filePath, 'utf-8');
                const page = {
                    slug,
                    title: slug,
                    content,
                    html: '',
                };
                pages.push(page);
            }
        }
        for (const plugin of this.plugins) {
            if (plugin.beforeBuild)
                plugin.beforeBuild();
        }
        for (const page of pages) {
            if (!skippedSlugs.has(page.slug)) {
                for (const plugin of this.plugins) {
                    if (plugin.onFile)
                        plugin.onFile(page);
                }
            }
        }
        pages.sort((a, b) => {
            if (a.date && b.date) {
                return b.date.localeCompare(a.date);
            }
            if (a.date)
                return -1;
            if (b.date)
                return 1;
            return a.title.localeCompare(b.title);
        });
        for (const plugin of this.plugins) {
            if (plugin.afterBuild)
                plugin.afterBuild(pages);
        }
        for (const plugin of this.plugins) {
            if (plugin.onEnd)
                plugin.onEnd();
        }
        for (const page of pages) {
            if (!skippedSlugs.has(page.slug)) {
                newCacheManifest.pages[page.slug] = {
                    sourceHash: (0, cache_1.hashFile)(path.join(absoluteContent, `${page.slug}.md`)),
                    templatesHash,
                    outputHtml: page.html || '',
                    title: page.title,
                    date: page.date,
                    tags: page.tags,
                    template: page.template,
                    layout: page.layout,
                };
            }
        }
        if (incremental) {
            (0, cache_1.saveCache)(cachePath, newCacheManifest);
            const stats = { pagesBuilt, pagesSkipped };
            console.log(`Build complete: ${stats.pagesBuilt} built, ${stats.pagesSkipped} skipped`);
        }
    }
}
exports.SsgEngine = SsgEngine;
//# sourceMappingURL=engine.js.map