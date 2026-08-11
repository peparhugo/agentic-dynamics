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
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const os = __importStar(require("os"));
const build_1 = require("../src/build");
const cache_1 = require("../src/cache");
function tmpDir() {
    return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-incr-test-'));
}
function writeMarkdown(dir, slug, content, frontmatter = '') {
    const fm = frontmatter ? `${frontmatter}\n` : '';
    fs.writeFileSync(path.join(dir, `${slug}.md`), `---\n${fm}---\n${content}`);
}
function writeTemplate(dir, name, content) {
    if (name.includes('/')) {
        const subdir = path.join(dir, path.dirname(name));
        fs.mkdirSync(subdir, { recursive: true });
    }
    fs.writeFileSync(path.join(dir, name), content);
}
function setupTemplatesDir(templateDir) {
    fs.mkdirSync(path.join(templateDir, 'layouts'), { recursive: true });
    fs.mkdirSync(path.join(templateDir, 'partials'), { recursive: true });
    writeTemplate(templateDir, 'default.hbs', `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{{title}}</title></head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  <h1>{{title}}</h1>
  {{#if date}}<p class="date">{{date}}</p>{{/if}}
  {{#if tags}}{{#each tags}}<span class="tag">{{this}}</span>{{/each}}{{/if}}
  <hr>
  {{{html}}}
</body>
</html>`);
    writeTemplate(templateDir, 'index.hbs', `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Index</title></head>
<body>
  <h1>All Pages</h1>
  <ul>
    {{#each pages}}
      <li><a href="{{slug}}.html">{{title}}</a>{{#if date}} <span>{{date}}</span>{{/if}}</li>
    {{/each}}
  </ul>
  {{#unless pages.length}}<p>No pages found.</p>{{/unless}}
</body>
</html>`);
    writeTemplate(templateDir, 'layouts/default.hbs', `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{{title}}</title></head>
<body>
  {{> header}}
  {{{body}}}
  {{> footer}}
</body>
</html>`);
    writeTemplate(templateDir, 'partials/header.hbs', '<header>HEADER</header>');
    writeTemplate(templateDir, 'partials/footer.hbs', '<footer>FOOTER</footer>');
}
function getFileMtime(filePath) {
    return fs.statSync(filePath).mtimeMs;
}
describe('incremental builds', () => {
    let contentDir;
    let outputDir;
    beforeEach(() => {
        contentDir = tmpDir();
        outputDir = tmpDir();
    });
    afterEach(() => {
        fs.rmSync(contentDir, { recursive: true, force: true });
        fs.rmSync(outputDir, { recursive: true, force: true });
    });
    function doBuild(options) {
        (0, build_1.build)(contentDir, outputDir, undefined, options);
    }
    describe('basic incremental behavior', () => {
        it('builds all pages on first run', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            writeMarkdown(contentDir, 'page2', 'Content 2', 'title: Page 2');
            doBuild({ incremental: true });
            expect(fs.existsSync(path.join(outputDir, 'page1.html'))).toBe(true);
            expect(fs.existsSync(path.join(outputDir, 'page2.html'))).toBe(true);
            expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
        });
        it('creates cache file after incremental build', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            doBuild({ incremental: true });
            const cachePath = path.join(outputDir, '.ssg-cache.json');
            expect(fs.existsSync(cachePath)).toBe(true);
            const manifest = (0, cache_1.loadCache)(cachePath);
            expect(manifest).not.toBeNull();
            expect(manifest.pages['page1']).toBeDefined();
            expect(manifest.pages['page1'].title).toBe('Page 1');
        });
        it('skips rebuild of unchanged pages', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            writeMarkdown(contentDir, 'page2', 'Content 2', 'title: Page 2');
            doBuild({ incremental: true });
            const page1Mtime = getFileMtime(path.join(outputDir, 'page1.html'));
            const page2Mtime = getFileMtime(path.join(outputDir, 'page2.html'));
            doBuild({ incremental: true });
            const page1Mtime2 = getFileMtime(path.join(outputDir, 'page1.html'));
            const page2Mtime2 = getFileMtime(path.join(outputDir, 'page2.html'));
            expect(page1Mtime2).toBe(page1Mtime);
            expect(page2Mtime2).toBe(page2Mtime);
        });
        it('rebuilds only changed pages on incremental run', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            writeMarkdown(contentDir, 'page2', 'Content 2', 'title: Page 2');
            doBuild({ incremental: true });
            const page1Mtime = getFileMtime(path.join(outputDir, 'page1.html'));
            const page2Mtime = getFileMtime(path.join(outputDir, 'page2.html'));
            writeMarkdown(contentDir, 'page1', 'Updated Content 1', 'title: Page 1 Updated');
            doBuild({ incremental: true });
            const page1Mtime2 = getFileMtime(path.join(outputDir, 'page1.html'));
            const page2Mtime2 = getFileMtime(path.join(outputDir, 'page2.html'));
            expect(page1Mtime2).toBeGreaterThan(page1Mtime);
            expect(page2Mtime2).toBe(page2Mtime);
        });
        it('reflects changes in rebuilt page content', () => {
            writeMarkdown(contentDir, 'test', 'Old content', 'title: Old Title');
            doBuild({ incremental: true });
            let html = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
            expect(html).toContain('Old Title');
            expect(html).toContain('Old content');
            writeMarkdown(contentDir, 'test', 'New content', 'title: New Title');
            doBuild({ incremental: true });
            html = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
            expect(html).toContain('New Title');
            expect(html).toContain('New content');
        });
        it('rebuilds when a new page is added', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            doBuild({ incremental: true });
            const page1Mtime = getFileMtime(path.join(outputDir, 'page1.html'));
            expect(fs.existsSync(path.join(outputDir, 'page2.html'))).toBe(false);
            writeMarkdown(contentDir, 'page2', 'Content 2', 'title: Page 2');
            doBuild({ incremental: true });
            const page1Mtime2 = getFileMtime(path.join(outputDir, 'page1.html'));
            expect(fs.existsSync(path.join(outputDir, 'page2.html'))).toBe(true);
            expect(page1Mtime2).toBe(page1Mtime);
        });
        it('handles removed pages', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            writeMarkdown(contentDir, 'page2', 'Content 2', 'title: Page 2');
            doBuild({ incremental: true });
            expect(fs.existsSync(path.join(outputDir, 'page1.html'))).toBe(true);
            expect(fs.existsSync(path.join(outputDir, 'page2.html'))).toBe(true);
            fs.unlinkSync(path.join(contentDir, 'page2.md'));
            doBuild({ incremental: true });
            const cachePath = path.join(outputDir, '.ssg-cache.json');
            const manifest = (0, cache_1.loadCache)(cachePath);
            expect(manifest.pages['page2']).toBeUndefined();
        });
        it('rebuilds all pages when cache is missing', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            writeMarkdown(contentDir, 'page2', 'Content 2', 'title: Page 2');
            doBuild({ incremental: true });
            const cachePath = path.join(outputDir, '.ssg-cache.json');
            fs.unlinkSync(cachePath);
            const page1Mtime = getFileMtime(path.join(outputDir, 'page1.html'));
            doBuild({ incremental: true });
            const page1Mtime2 = getFileMtime(path.join(outputDir, 'page1.html'));
            expect(page1Mtime2).toBeGreaterThan(page1Mtime);
            expect(fs.existsSync(cachePath)).toBe(true);
        });
        it('does a clean build when --clean is passed', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            doBuild({ incremental: true });
            const cachePath = path.join(outputDir, '.ssg-cache.json');
            expect(fs.existsSync(cachePath)).toBe(true);
            writeMarkdown(contentDir, 'page2', 'Content 2', 'title: Page 2');
            doBuild({ incremental: true, clean: true });
            expect(fs.existsSync(path.join(outputDir, 'page1.html'))).toBe(true);
            expect(fs.existsSync(path.join(outputDir, 'page2.html'))).toBe(true);
            const manifest = (0, cache_1.loadCache)(cachePath);
            expect(manifest.pages['page1']).toBeDefined();
            expect(manifest.pages['page2']).toBeDefined();
        });
        it('does not create cache file for non-incremental builds', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            doBuild({ incremental: false });
            const cachePath = path.join(outputDir, '.ssg-cache.json');
            expect(fs.existsSync(cachePath)).toBe(false);
        });
        it('still generates correct index.html with incremental builds', () => {
            writeMarkdown(contentDir, 'alpha', 'A', 'title: Alpha');
            writeMarkdown(contentDir, 'beta', 'B', 'title: Beta');
            doBuild({ incremental: true });
            let indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
            expect(indexHtml).toContain('href="alpha.html"');
            expect(indexHtml).toContain('href="beta.html"');
            writeMarkdown(contentDir, 'gamma', 'C', 'title: Gamma');
            doBuild({ incremental: true });
            indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
            expect(indexHtml).toContain('href="alpha.html"');
            expect(indexHtml).toContain('href="beta.html"');
            expect(indexHtml).toContain('href="gamma.html"');
        });
    });
    describe('incremental builds with templates', () => {
        let templatesDir;
        beforeEach(() => {
            templatesDir = tmpDir();
            setupTemplatesDir(templatesDir);
        });
        afterEach(() => {
            fs.rmSync(templatesDir, { recursive: true, force: true });
        });
        it('rebuilds pages when templates change', () => {
            writeMarkdown(contentDir, 'post', '# Hello', 'title: My Post');
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            const postMtime = getFileMtime(path.join(outputDir, 'post.html'));
            writeTemplate(templatesDir, 'default.hbs', `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>UPDATED - {{title}}</title></head>
<body>
  <h1>{{title}}</h1>
  {{{html}}}
</body>
</html>`);
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            const postMtime2 = getFileMtime(path.join(outputDir, 'post.html'));
            expect(postMtime2).toBeGreaterThan(postMtime);
            const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
            expect(html).toContain('UPDATED');
        });
        it('skips pages when only source and templates are unchanged', () => {
            writeMarkdown(contentDir, 'post1', 'Content 1', 'title: Post 1');
            writeMarkdown(contentDir, 'post2', 'Content 2', 'title: Post 2');
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            const post1Mtime = getFileMtime(path.join(outputDir, 'post1.html'));
            const post2Mtime = getFileMtime(path.join(outputDir, 'post2.html'));
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            expect(getFileMtime(path.join(outputDir, 'post1.html'))).toBe(post1Mtime);
            expect(getFileMtime(path.join(outputDir, 'post2.html'))).toBe(post2Mtime);
        });
        it('rebuilds pages when partial templates change', () => {
            writeMarkdown(contentDir, 'post', '# Hello', 'title: My Post');
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            let html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
            expect(html).toContain('HEADER');
            writeTemplate(templatesDir, 'partials/header.hbs', '<header>UPDATED HEADER</header>');
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
            expect(html).toContain('UPDATED HEADER');
        });
        it('rebuilds pages when layout templates change', () => {
            writeMarkdown(contentDir, 'post', '# Hello', 'title: My Post');
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            let html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
            expect(html).toContain('FOOTER');
            writeTemplate(templatesDir, 'layouts/default.hbs', `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{{title}}</title></head>
<body>
  {{> header}}
  {{{body}}}
  <footer>CHANGED FOOTER</footer>
</body>
</html>`);
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
            expect(html).toContain('CHANGED FOOTER');
        });
        it('still generates correct output with templates and incremental', () => {
            writeMarkdown(contentDir, 'one', 'First', 'title: One');
            writeMarkdown(contentDir, 'two', 'Second', 'title: Two');
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            expect(fs.readFileSync(path.join(outputDir, 'one.html'), 'utf-8')).toContain('<h1>One</h1>');
            expect(fs.readFileSync(path.join(outputDir, 'two.html'), 'utf-8')).toContain('<h1>Two</h1>');
            writeMarkdown(contentDir, 'two', 'Updated Second', 'title: Two Updated');
            (0, build_1.build)(contentDir, outputDir, templatesDir, { incremental: true });
            const html1 = fs.readFileSync(path.join(outputDir, 'one.html'), 'utf-8');
            const html2 = fs.readFileSync(path.join(outputDir, 'two.html'), 'utf-8');
            expect(html1).toContain('<h1>One</h1>');
            expect(html2).toContain('<h1>Two Updated</h1>');
        });
    });
    describe('cache integrity', () => {
        it('caches the correct page metadata', () => {
            writeMarkdown(contentDir, 'meta', 'Body content', 'title: Cached Meta\ndate: 2024-12-01\ntags:\n  - tag1\n  - tag2');
            doBuild({ incremental: true });
            const cachePath = path.join(outputDir, '.ssg-cache.json');
            const manifest = (0, cache_1.loadCache)(cachePath);
            const entry = manifest.pages['meta'];
            expect(entry.title).toBe('Cached Meta');
            expect(entry.date).toBe('2024-12-01');
            expect(entry.tags).toEqual(['tag1', 'tag2']);
        });
        it('invalidates cache entry when source changes', () => {
            writeMarkdown(contentDir, 'old', 'Old content', 'title: Old');
            doBuild({ incremental: true });
            let cachePath = path.join(outputDir, '.ssg-cache.json');
            let manifest = (0, cache_1.loadCache)(cachePath);
            const oldHash = manifest.pages['old'].sourceHash;
            writeMarkdown(contentDir, 'old', 'New content', 'title: New');
            doBuild({ incremental: true });
            manifest = (0, cache_1.loadCache)(cachePath);
            const newHash = manifest.pages['old'].sourceHash;
            expect(newHash).not.toBe(oldHash);
            expect(manifest.pages['old'].title).toBe('New');
        });
    });
    describe('mixed incremental and non-incremental builds', () => {
        it('ignores stray cache when building without --incremental', () => {
            writeMarkdown(contentDir, 'page1', 'Content 1', 'title: Page 1');
            doBuild({ incremental: true });
            const cachePath = path.join(outputDir, '.ssg-cache.json');
            expect(fs.existsSync(cachePath)).toBe(true);
            writeMarkdown(contentDir, 'page1', 'Changed content', 'title: Changed');
            doBuild({ incremental: false });
            const html = fs.readFileSync(path.join(outputDir, 'page1.html'), 'utf-8');
            expect(html).toContain('Changed');
        });
    });
});
//# sourceMappingURL=incremental.test.js.map