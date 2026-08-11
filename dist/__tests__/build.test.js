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
function tmpDir() {
    return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
}
function writeMarkdown(dir, slug, content, frontmatter = '') {
    const fm = frontmatter ? `${frontmatter}\n` : '';
    fs.writeFileSync(path.join(dir, `${slug}.md`), `---\n${fm}---\n${content}`);
}
function writeTemplate(dir, name, content) {
    if (name.includes('/')) {
        const subdir = path.join(dir, path.dirname(name));
        fs.mkdirSync(subdir, { recursive: true });
        fs.writeFileSync(path.join(dir, name), content);
    }
    else {
        fs.writeFileSync(path.join(dir, name), content);
    }
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
  {{> nav}}
  <main>{{{body}}}</main>
  {{> footer}}
</body>
</html>`);
    writeTemplate(templateDir, 'partials/header.hbs', `<header><h1>{{title}}</h1></header>`);
    writeTemplate(templateDir, 'partials/footer.hbs', `<footer><hr><small>SSG Footer</small></footer>`);
    writeTemplate(templateDir, 'partials/nav.hbs', `<nav><a href="index.html">Home</a></nav>`);
}
describe('ssg build', () => {
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
    it('throws when content directory does not exist', () => {
        expect(() => (0, build_1.build)('/nonexistent/dir', outputDir)).toThrow(/Content directory does not exist/);
    });
    it('creates output directory if it does not exist', () => {
        writeMarkdown(contentDir, 'hello', 'Hello world', 'title: Hello');
        const nestedOutput = path.join(outputDir, 'nested', 'out');
        (0, build_1.build)(contentDir, nestedOutput);
        expect(fs.existsSync(nestedOutput)).toBe(true);
        expect(fs.existsSync(path.join(nestedOutput, 'index.html'))).toBe(true);
    });
    it('generates an index.html listing all pages', () => {
        writeMarkdown(contentDir, 'alpha', 'Content A', 'title: Alpha');
        writeMarkdown(contentDir, 'beta', 'Content B', 'title: Beta');
        (0, build_1.build)(contentDir, outputDir);
        const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
        expect(indexHtml).toContain('href="alpha.html"');
        expect(indexHtml).toContain('href="beta.html"');
        expect(indexHtml).toContain('Alpha');
        expect(indexHtml).toContain('Beta');
    });
    it('generates an HTML file for each markdown page', () => {
        writeMarkdown(contentDir, 'welcome', '# Welcome\n\nSome content', 'title: Welcome');
        writeMarkdown(contentDir, 'about', '## About\n\nAbout text', 'title: About');
        (0, build_1.build)(contentDir, outputDir);
        expect(fs.existsSync(path.join(outputDir, 'welcome.html'))).toBe(true);
        expect(fs.existsSync(path.join(outputDir, 'about.html'))).toBe(true);
    });
    it('parses markdown to HTML', () => {
        writeMarkdown(contentDir, 'test', '# Heading\n\n**bold** text', 'title: Test');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
        expect(html).toContain('<h1>Heading</h1>');
        expect(html).toContain('<strong>bold</strong>');
    });
    it('uses frontmatter title in the HTML page', () => {
        writeMarkdown(contentDir, 'mypage', 'Content', 'title: My Custom Title');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'mypage.html'), 'utf-8');
        expect(html).toContain('<title>My Custom Title</title>');
        expect(html).toContain('<h1>My Custom Title</h1>');
    });
    it('displays date from frontmatter', () => {
        writeMarkdown(contentDir, 'post', 'Body', 'title: Post\ndate: 2024-06-15');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
        expect(html).toContain('2024-06-15');
    });
    it('displays tags from frontmatter', () => {
        writeMarkdown(contentDir, 'tagged', 'Content', 'title: Tagged\ntags:\n  - javascript\n  - typescript');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'tagged.html'), 'utf-8');
        expect(html).toContain('javascript');
        expect(html).toContain('typescript');
    });
    it('escapes HTML in metadata', () => {
        writeMarkdown(contentDir, 'xss', 'Body', 'title: <script>alert("xss")</script>');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'xss.html'), 'utf-8');
        expect(html).not.toContain('<script>alert("xss")</script>');
        expect(html).toContain('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;');
    });
    it('sorts pages by date descending on the index page', () => {
        writeMarkdown(contentDir, 'old', 'Old', 'title: Old\ndate: 2023-01-01');
        writeMarkdown(contentDir, 'new', 'New', 'title: New\ndate: 2024-12-31');
        (0, build_1.build)(contentDir, outputDir);
        const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
        const newPos = indexHtml.indexOf('href="new.html"');
        const oldPos = indexHtml.indexOf('href="old.html"');
        expect(newPos).toBeLessThan(oldPos);
    });
    it('handles empty content directory gracefully', () => {
        (0, build_1.build)(contentDir, outputDir);
        const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
        expect(indexHtml).toContain('No pages found');
    });
    it('uses slug as fallback title when no frontmatter title', () => {
        writeMarkdown(contentDir, 'fallback', 'Content');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'fallback.html'), 'utf-8');
        expect(html).toContain('<title>fallback</title>');
    });
    it('produces a link back to index on each page', () => {
        writeMarkdown(contentDir, 'linked', 'Body', 'title: Linked');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'linked.html'), 'utf-8');
        expect(html).toContain('href="index.html"');
        expect(html).toContain('Home');
    });
    it('renders code blocks from markdown', () => {
        writeMarkdown(contentDir, 'code', '```\nconst x = 1;\n```', 'title: Code');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'code.html'), 'utf-8');
        expect(html).toContain('<code>');
    });
    it('handles pages without tags gracefully', () => {
        writeMarkdown(contentDir, 'notags', 'Body', 'title: No Tags');
        (0, build_1.build)(contentDir, outputDir);
        const html = fs.readFileSync(path.join(outputDir, 'notags.html'), 'utf-8');
        expect(html).toContain('<title>No Tags</title>');
        expect(html).not.toMatch(/<span class="tag">/);
    });
});
describe('ssg build with templates', () => {
    let contentDir;
    let outputDir;
    let templatesDir;
    beforeEach(() => {
        contentDir = tmpDir();
        outputDir = tmpDir();
        templatesDir = tmpDir();
        setupTemplatesDir(templatesDir);
    });
    afterEach(() => {
        fs.rmSync(contentDir, { recursive: true, force: true });
        fs.rmSync(outputDir, { recursive: true, force: true });
        fs.rmSync(templatesDir, { recursive: true, force: true });
    });
    it('renders pages using the default template', () => {
        writeMarkdown(contentDir, 'post', '# Hello World', 'title: My Post');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
        expect(html).toContain('<title>My Post</title>');
        expect(html).toContain('<h1>My Post</h1>');
        expect(html).toContain('Home');
        expect(html).toContain('<hr>');
    });
    it('renders pages using a template specified in frontmatter', () => {
        writeTemplate(templatesDir, 'custom.hbs', `<!DOCTYPE html>
<html><head><title>{{title}}</title></head>
<body><article><h1>{{title}}</h1>{{{content}}}</article></body>
</html>`);
        writeMarkdown(contentDir, 'custom-page', 'Custom content', 'title: Custom\ntemplate: custom');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const html = fs.readFileSync(path.join(outputDir, 'custom-page.html'), 'utf-8');
        expect(html).toContain('<article>');
        expect(html).toContain('<h1>Custom</h1>');
    });
    it('wraps page content in a layout with {{{body}}} placeholder', () => {
        writeTemplate(templatesDir, 'layouts/default.hbs', `<!DOCTYPE html>
<html><head><title>{{title}}</title></head>
<body>
<header>SITE HEADER</header>
{{{body}}}
<footer>SITE FOOTER</footer>
</body></html>`);
        writeTemplate(templatesDir, 'default.hbs', `<article><h1>{{title}}</h1>{{{content}}}</article>`);
        writeMarkdown(contentDir, 'layered', 'Layered content', 'title: Layered');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const html = fs.readFileSync(path.join(outputDir, 'layered.html'), 'utf-8');
        expect(html).toContain('SITE HEADER');
        expect(html).toContain('SITE FOOTER');
        expect(html).toContain('<h1>Layered</h1>');
    });
    it('includes partials in layout', () => {
        writeTemplate(templatesDir, 'layouts/default.hbs', `<!DOCTYPE html>
<html><head><title>{{title}}</title></head>
<body>
{{> header}}
{{{body}}}
{{> footer}}
</body></html>`);
        writeTemplate(templatesDir, 'partials/header.hbs', `<header class="site-header">HEADER PARTIAL</header>`);
        writeTemplate(templatesDir, 'partials/footer.hbs', `<footer class="site-footer">FOOTER PARTIAL</footer>`);
        writeTemplate(templatesDir, 'default.hbs', `<main>{{{content}}}</main>`);
        writeMarkdown(contentDir, 'partial-test', 'Content', 'title: Partial Test');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const html = fs.readFileSync(path.join(outputDir, 'partial-test.html'), 'utf-8');
        expect(html).toContain('HEADER PARTIAL');
        expect(html).toContain('FOOTER PARTIAL');
    });
    it('renders the index page using index.hbs template with pages array', () => {
        writeMarkdown(contentDir, 'page1', 'One', 'title: Page One');
        writeMarkdown(contentDir, 'page2', 'Two', 'title: Page Two');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
        expect(indexHtml).toContain('href="page1.html"');
        expect(indexHtml).toContain('Page One');
        expect(indexHtml).toContain('href="page2.html"');
        expect(indexHtml).toContain('Page Two');
    });
    it('throws when specified template file is missing', () => {
        writeMarkdown(contentDir, 'missing', 'Content', 'title: Missing\ntemplate: nonexistent');
        expect(() => (0, build_1.build)(contentDir, outputDir, templatesDir)).toThrow(/Template not found/);
    });
    it('uses layout specified in frontmatter', () => {
        writeTemplate(templatesDir, 'layouts/alt.hbs', `<!DOCTYPE html>
<html><head><title>{{title}}</title></head>
<body>
<div class="alt-layout">{{{body}}}</div>
</body></html>`);
        writeTemplate(templatesDir, 'default.hbs', `<h1>{{title}}</h1>{{{content}}}`);
        writeMarkdown(contentDir, 'alt-layout', 'Alt content', 'title: Alt Layout\nlayout: alt');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const html = fs.readFileSync(path.join(outputDir, 'alt-layout.html'), 'utf-8');
        expect(html).toContain('class="alt-layout"');
        expect(html).toContain('<h1>Alt Layout</h1>');
    });
    it('falls back to default template when no template specified in frontmatter', () => {
        writeMarkdown(contentDir, 'no-template', 'Just content');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const html = fs.readFileSync(path.join(outputDir, 'no-template.html'), 'utf-8');
        expect(html).toContain('<h1>no-template</h1>');
    });
    it('uses built-in templates when templates dir does not exist', () => {
        const nonExistentTpl = path.join(tmpDir(), 'nonexistent-templates');
        writeMarkdown(contentDir, 'fallback', 'Body', 'title: Fallback');
        (0, build_1.build)(contentDir, outputDir, nonExistentTpl);
        const html = fs.readFileSync(path.join(outputDir, 'fallback.html'), 'utf-8');
        expect(html).toContain('<title>Fallback</title>');
        expect(html).toContain('<h1>Fallback</h1>');
        fs.rmSync(path.dirname(nonExistentTpl), { recursive: true, force: true });
    });
    it('supports date and tags in template output', () => {
        writeTemplate(templatesDir, 'default.hbs', `<!DOCTYPE html>
<html><head><title>{{title}}</title></head>
<body>
<h1>{{title}}</h1>
{{#if date}}<p class="date">{{date}}</p>{{/if}}
{{#if tags}}{{#each tags}}<span class="tag">{{this}}</span>{{/each}}{{/if}}
{{{content}}}
</body></html>`);
        writeMarkdown(contentDir, 'meta-test', 'Content', 'title: Meta Test\ndate: 2025-01-15\ntags:\n  - js\n  - ts');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const html = fs.readFileSync(path.join(outputDir, 'meta-test.html'), 'utf-8');
        expect(html).toContain('2025-01-15');
        expect(html).toContain('<span class="tag">js</span>');
        expect(html).toContain('<span class="tag">ts</span>');
    });
    it('renders markdown content as HTML inside template', () => {
        writeMarkdown(contentDir, 'md-test', '# Heading\n\n**bold** and `code`', 'title: Markdown Test');
        (0, build_1.build)(contentDir, outputDir, templatesDir);
        const html = fs.readFileSync(path.join(outputDir, 'md-test.html'), 'utf-8');
        expect(html).toContain('<h1>Heading</h1>');
        expect(html).toContain('<strong>bold</strong>');
        expect(html).toContain('<code>code</code>');
    });
    it('renders template without layout when no layout exists', () => {
        const noLayoutDir = tmpDir();
        fs.mkdirSync(noLayoutDir, { recursive: true });
        writeTemplate(noLayoutDir, 'default.hbs', `<!DOCTYPE html>
<html><head><title>{{title}}</title></head>
<body><h1>{{title}}</h1>{{{content}}}</body></html>`);
        writeMarkdown(contentDir, 'no-layout', 'A plain line', 'title: No Layout');
        (0, build_1.build)(contentDir, outputDir, noLayoutDir);
        const html = fs.readFileSync(path.join(outputDir, 'no-layout.html'), 'utf-8');
        expect(html).toContain('<h1>No Layout</h1>');
        expect(html).toContain('A plain line');
        fs.rmSync(noLayoutDir, { recursive: true, force: true });
    });
});
//# sourceMappingURL=build.test.js.map