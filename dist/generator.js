"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.readContentDirectory = exports.parseMarkdownFile = void 0;
exports.generateSite = generateSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const plugin_1 = require("./plugin");
const markdown_1 = require("./plugins/markdown");
const template_1 = require("./plugins/template");
const templates_1 = require("./templates");
const cache_1 = require("./cache");
var markdown_2 = require("./plugins/markdown");
Object.defineProperty(exports, "parseMarkdownFile", { enumerable: true, get: function () { return markdown_2.parseMarkdownFile; } });
Object.defineProperty(exports, "readContentDirectory", { enumerable: true, get: function () { return markdown_2.readContentDirectory; } });
function scanContentFiles(contentDir) {
    if (!fs_1.default.existsSync(contentDir))
        return [];
    return fs_1.default.readdirSync(contentDir)
        .filter((e) => e.endsWith('.md'))
        .map((name) => ({ name, fullPath: path_1.default.join(contentDir, name) }));
}
function generateSite(contentDir, outputDir, templatesDir, buildOpts) {
    const incremental = buildOpts?.incremental ?? false;
    const clean = buildOpts?.clean ?? false;
    const plugins = [
        new markdown_1.MarkdownPlugin(),
        new template_1.TemplatePlugin(),
        ...(0, plugin_1.loadPluginsFromConfig)(),
    ];
    const options = { contentDir, outputDir, templatesDir, incremental, clean };
    for (const p of plugins)
        if (p.onStart)
            p.onStart();
    for (const p of plugins)
        if (p.beforeBuild)
            p.beforeBuild(options);
    const contentFiles = scanContentFiles(contentDir);
    if (contentFiles.length === 0) {
        console.log(`No markdown files found in ${contentDir}`);
        for (const p of plugins)
            if (p.onEnd)
                p.onEnd();
        return 0;
    }
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const engine = templatesDir ? new templates_1.TemplateEngine(templatesDir) : null;
    const useTemplates = engine && engine.initialized;
    const cache = new cache_1.BuildCache(contentDir, outputDir, templatesDir);
    if (clean) {
        cache.clear();
    }
    else if (incremental) {
        cache.load();
    }
    let builtCount = 0;
    let skippedCount = 0;
    const allPages = [];
    const knownSlugs = new Set();
    for (const file of contentFiles) {
        let page = (0, markdown_1.parseMarkdownFile)(file.fullPath);
        if (!page)
            continue;
        knownSlugs.add(page.slug);
        if (incremental && cache.shouldSkipFile(file.fullPath, page.slug)) {
            skippedCount++;
            allPages.push(page);
            continue;
        }
        builtCount++;
        for (const p of plugins) {
            if (p.onFile)
                page = p.onFile(page);
        }
        const html = useTemplates
            ? (engine.render(page) || (0, template_1.renderPage)(page))
            : (0, template_1.renderPage)(page);
        cache.cacheHtml(page.slug, html);
        fs_1.default.writeFileSync(path_1.default.join(outputDir, `${page.slug}.html`), html);
        allPages.push(page);
        cache.updateManifest(file.fullPath, page.slug);
    }
    cache.removeStaleEntries(knownSlugs);
    const indexHtml = useTemplates
        ? (engine.renderIndex(allPages) || (0, template_1.renderIndex)(allPages))
        : (0, template_1.renderIndex)(allPages);
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'index.html'), indexHtml);
    builtCount++; // index always counts as built
    const indexFileCount = 1;
    cache.stats = {
        totalPages: builtCount + skippedCount,
        pagesBuilt: builtCount,
        pagesSkipped: skippedCount,
        timeSaved: '0ms',
    };
    if (incremental) {
        cache.finalize();
        cache.persist();
        cache.reportStats();
    }
    for (const p of plugins)
        if (p.afterBuild)
            p.afterBuild(options);
    for (const p of plugins)
        if (p.onEnd)
            p.onEnd();
    const total = contentFiles.length + indexFileCount;
    console.log(`Generated ${total} files in ${outputDir}`);
    return total;
}
//# sourceMappingURL=generator.js.map