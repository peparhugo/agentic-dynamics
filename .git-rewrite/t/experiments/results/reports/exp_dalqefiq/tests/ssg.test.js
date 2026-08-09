"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const vitest_1 = require("vitest");
const node_path_1 = __importDefault(require("node:path"));
const promises_1 = __importDefault(require("node:fs/promises"));
const build_1 = require("../src/build");
const server_1 = require("../src/server");
const tmpOut = node_path_1.default.join(process.cwd(), 'tmp_out');
const fixtures = node_path_1.default.join(process.cwd(), 'tests/fixtures');
(0, vitest_1.describe)('frontmatter parsing and build', () => {
    (0, vitest_1.it)('builds pages, excludes drafts by default, generates tags and rss', async () => {
        await promises_1.default.rm(tmpOut, { recursive: true, force: true });
        const { pages, tags } = await (0, build_1.buildSite)({
            srcDir: node_path_1.default.join(fixtures, 'src'),
            templatesDir: node_path_1.default.join(fixtures, 'templates'),
            outDir: tmpOut,
            baseUrl: 'http://example.com',
            includeDrafts: false,
            clean: true
        });
        (0, vitest_1.expect)(pages.length).toBe(1);
        const html = await promises_1.default.readFile(node_path_1.default.join(tmpOut, 'post1.html'), 'utf8');
        (0, vitest_1.expect)(html).toContain('<h1>My Site</h1>');
        (0, vitest_1.expect)(html).toContain('First Post');
        // Syntax highlighting included
        (0, vitest_1.expect)(html).toContain('hljs');
        // Tag index pages
        const tagHtml = await promises_1.default.readFile(node_path_1.default.join(tmpOut, 'tags', 'news', 'index.html'), 'utf8');
        (0, vitest_1.expect)(tagHtml).toContain('Tags');
        // RSS exists
        const rss = await promises_1.default.readFile(node_path_1.default.join(tmpOut, 'feed.xml'), 'utf8');
        (0, vitest_1.expect)(rss).toContain('<rss');
        (0, vitest_1.expect)(Array.from(tags.keys())).toContain('news');
    });
});
(0, vitest_1.describe)('CLI flag behavior (drafts, live reload)', () => {
    (0, vitest_1.it)('includes drafts when includeDrafts = true', async () => {
        await promises_1.default.rm(tmpOut, { recursive: true, force: true });
        const { pages } = await (0, build_1.buildSite)({
            srcDir: node_path_1.default.join(fixtures, 'src'),
            templatesDir: node_path_1.default.join(fixtures, 'templates'),
            outDir: tmpOut,
            includeDrafts: true,
            clean: true
        });
        (0, vitest_1.expect)(pages.find(p => p.relPath === 'draft.md')).toBeTruthy();
    });
});
(0, vitest_1.describe)('dev server', () => {
    let stop = null;
    (0, vitest_1.afterAll)(async () => { if (stop)
        await stop(); });
    (0, vitest_1.it)('serves with live reload script emitted', async () => {
        await promises_1.default.rm(tmpOut, { recursive: true, force: true });
        const srv = await (0, server_1.startDevServer)({
            srcDir: node_path_1.default.join(fixtures, 'src'),
            templatesDir: node_path_1.default.join(fixtures, 'templates'),
            outDir: tmpOut,
            includeDrafts: true,
            port: 5599,
            clean: true
        });
        stop = srv.stop;
        const html = await promises_1.default.readFile(node_path_1.default.join(tmpOut, 'post1.html'), 'utf8');
        (0, vitest_1.expect)(html).toContain('/_livereload.js');
    });
});
//# sourceMappingURL=ssg.test.js.map