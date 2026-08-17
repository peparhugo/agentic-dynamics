"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_TEMPLATES_DIR = exports.DEFAULT_OUTPUT_DIR = exports.DEFAULT_CONTENT_DIR = void 0;
exports.buildPlugins = buildPlugins;
exports.createEngine = createEngine;
exports.buildSite = buildSite;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const plugin_1 = require("./plugin");
const markdown_1 = require("./markdown");
const config_1 = require("./config");
const markdown_plugin_1 = require("./plugins/markdown-plugin");
const template_plugin_1 = require("./plugins/template-plugin");
const cache_1 = require("./cache");
exports.DEFAULT_CONTENT_DIR = 'content';
exports.DEFAULT_OUTPUT_DIR = 'dist';
exports.DEFAULT_TEMPLATES_DIR = 'templates';
function listMarkdownFiles(dir) {
    if (!fs_1.default.existsSync(dir)) {
        return [];
    }
    const results = [];
    const entries = fs_1.default.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
        const full = path_1.default.join(dir, entry.name);
        if (entry.isDirectory()) {
            results.push(...listMarkdownFiles(full));
        }
        else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
            results.push(full);
        }
    }
    return results;
}
function deriveSlug(filePath, contentDir) {
    const relative = path_1.default.relative(contentDir, filePath);
    const parsed = path_1.default.parse(relative);
    return path_1.default.join(parsed.dir, parsed.name).split(path_1.default.sep).join('/');
}
function renderIndex(pages) {
    const items = pages
        .map((page) => {
        const date = page.date ? ` <span class="date">${(0, markdown_1.escapeHtml)(page.date)}</span>` : '';
        return `<li><a href="${(0, markdown_1.escapeHtml)(page.slug)}.html">${(0, markdown_1.escapeHtml)(page.title)}</a>${date}</li>`;
    })
        .join('\n');
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Index</title>
</head>
<body>
<h1>All Pages</h1>
<ul>
${items}
</ul>
</body>
</html>
`;
}
function resolvePluginModule(spec, context) {
    try {
        const resolved = require.resolve(spec, { paths: [process.cwd()] });
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const loaded = require(resolved);
        const exported = loaded && 'default' in loaded ? loaded.default : loaded;
        if (typeof exported === 'function') {
            const instance = new exported(context);
            return instance;
        }
        if (exported && typeof exported === 'object' && typeof exported.name === 'string') {
            return exported;
        }
    }
    catch {
        // Ignore plugins that cannot be resolved or instantiated.
    }
    return undefined;
}
/**
 * Assemble the plugin pipeline: the built-in markdown and template plugins run
 * first, followed by any plugins declared in the project configuration.
 */
function buildPlugins(context) {
    const plugins = [new markdown_plugin_1.MarkdownPlugin(), new template_plugin_1.TemplatePlugin(context)];
    const config = (0, config_1.loadConfig)(process.cwd());
    for (const spec of config.plugins ?? []) {
        const plugin = resolvePluginModule(spec, context);
        if (plugin) {
            plugins.push(plugin);
        }
    }
    return plugins;
}
function createEngine(options) {
    const contentDir = path_1.default.resolve(options.contentDir ?? exports.DEFAULT_CONTENT_DIR);
    const outputDir = path_1.default.resolve(options.outputDir ?? exports.DEFAULT_OUTPUT_DIR);
    const templatesDir = options.templatesDir ?? exports.DEFAULT_TEMPLATES_DIR;
    const context = {
        options,
        contentDir,
        outputDir,
        templatesDir,
        pages: [],
    };
    const pipeline = new plugin_1.PluginPipeline(buildPlugins(context));
    return { context, pipeline };
}
/**
 * Build the static site: read markdown from contentDir and write HTML files
 * (one per page plus an index.html) into outputDir. The core engine only
 * orchestrates the plugin pipeline; parsing and rendering are delegated to the
 * built-in MarkdownPlugin and TemplatePlugin.
 *
 * When `incremental` is set (and `clean` is not), the engine compares each
 * page's source and template fingerprints against the `.ssg-cache.json`
 * manifest and skips pages whose inputs are unchanged. Skipped pages are
 * reconstructed from the cache, so plugins (and the index) still see the full
 * page set while avoiding re-parsing and re-rendering.
 */
function buildSite(options) {
    const { context, pipeline } = createEngine(options);
    pipeline.runSync('onStart');
    pipeline.runSync('beforeBuild');
    const files = listMarkdownFiles(context.contentDir).sort();
    const cacheFile = options.cacheFile
        ? path_1.default.resolve(options.cacheFile)
        : path_1.default.join(context.outputDir, cache_1.CACHE_FILENAME);
    const incremental = options.incremental === true && options.clean !== true;
    const manifest = incremental ? (0, cache_1.loadManifest)(cacheFile) : (0, cache_1.defaultManifest)();
    const startedAt = Date.now();
    const pages = [];
    const nextManifest = { version: manifest.version, pages: {} };
    let built = 0;
    let skipped = 0;
    for (const file of files) {
        const slug = deriveSlug(file, context.contentDir);
        const sourceHash = (0, cache_1.hashFile)(file) ?? '';
        const cached = manifest.pages[slug];
        const sourceUnchanged = cached !== undefined && cached.sourceHash === sourceHash;
        let templateName;
        let layoutName;
        if (sourceUnchanged) {
            templateName = cached.template;
            layoutName = cached.layout;
        }
        else {
            const raw = fs_1.default.readFileSync(file, 'utf8');
            const { data } = (0, markdown_1.splitFrontmatter)(raw);
            templateName = typeof data.template === 'string' ? data.template : undefined;
            layoutName = data.layout;
        }
        const templateHash = (0, cache_1.computeTemplateHash)(context.options, templateName, layoutName);
        const outFile = path_1.default.join(context.outputDir, `${slug}.html`);
        const skip = incremental &&
            sourceUnchanged &&
            cached.templateHash === templateHash &&
            fs_1.default.existsSync(outFile);
        if (skip) {
            pages.push(pageFromCache(cached, slug, file));
            nextManifest.pages[slug] = cached;
            skipped++;
        }
        else {
            const page = {
                slug,
                title: '',
                date: undefined,
                tags: [],
                html: '',
                sourcePath: file,
                frontmatter: {},
                template: undefined,
                layout: undefined,
            };
            pipeline.runFileSync(page);
            pages.push(page);
            nextManifest.pages[slug] = {
                sourceHash,
                templateHash,
                title: page.title,
                date: page.date,
                tags: page.tags,
                html: page.html,
                frontmatter: page.frontmatter,
                template: page.template,
                layout: page.layout,
            };
            built++;
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
    context.pages = pages;
    fs_1.default.mkdirSync(context.outputDir, { recursive: true });
    pipeline.runSync('afterBuild');
    fs_1.default.writeFileSync(path_1.default.join(context.outputDir, 'index.html'), renderIndex(pages));
    (0, cache_1.saveManifest)(cacheFile, nextManifest);
    pipeline.runSync('onEnd');
    const elapsed = Date.now() - startedAt;
    const total = built + skipped;
    const timeSavedMs = total > 0 ? Math.round((elapsed / total) * skipped) : 0;
    return {
        pages,
        outputDir: context.outputDir,
        stats: { built, skipped, timeSavedMs },
    };
}
function pageFromCache(entry, slug, file) {
    return {
        slug,
        title: entry.title,
        date: entry.date,
        tags: entry.tags,
        html: entry.html,
        sourcePath: file,
        frontmatter: entry.frontmatter,
        template: entry.template,
        layout: entry.layout,
        cached: true,
    };
}
//# sourceMappingURL=engine.js.map