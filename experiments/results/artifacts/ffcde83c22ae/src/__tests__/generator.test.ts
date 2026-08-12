import fs from 'fs';
import path from 'path';
import os from 'os';
import { buildSite } from '../generator';

function setupContentDir(files: Record<string, string>): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
  for (const [name, content] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), content, 'utf-8');
  }
  return dir;
}

function setupTemplateDir(files: Record<string, string>): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-tmpl-'));
  for (const [name, content] of Object.entries(files)) {
    const fullPath = path.join(dir, name);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content, 'utf-8');
  }
  return dir;
}

describe('buildSite', () => {
  let outputDir: string;

  beforeEach(() => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-output-'));
  });

  afterEach(() => {
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  test('throws if content directory does not exist', () => {
    expect(() => buildSite('/nonexistent/path', outputDir)).toThrow(
      'Content directory does not exist'
    );
  });

  test('creates output directory if it does not exist', () => {
    const contentDir = setupContentDir({
      'hello.md': `---
title: Hello World
date: 2024-01-01
---

# Hello

This is a test.
`,
    });

    const outDir = path.join(outputDir, 'nested', 'sub');
    buildSite(contentDir, outDir);
    expect(fs.existsSync(outDir)).toBe(true);
    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('parses frontmatter and generates HTML page', () => {
    const contentDir = setupContentDir({
      'hello.md': `---
title: Hello World
date: 2024-01-15
tags:
  - test
  - ssg
---

# Hello

This is a **test**.
`,
    });

    buildSite(contentDir, outputDir);

    const pagePath = path.join(outputDir, 'hello.html');
    expect(fs.existsSync(pagePath)).toBe(true);

    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<title>Hello World</title>');
    expect(html).toContain('<h1>Hello World</h1>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<strong>test</strong>');
    expect(html).toContain('2024-01-15');
    expect(html).toContain('<span class="tag">test</span>');
    expect(html).toContain('<span class="tag">ssg</span>');
    expect(html).toContain('<article>');
    expect(html).toContain('</article>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('generates index.html listing all pages', () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Alpha
date: 2024-03-01
---

# Alpha
`,
      'b.md': `---
title: Beta
date: 2024-01-01
---

# Beta
`,
    });

    buildSite(contentDir, outputDir);

    const indexPath = path.join(outputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const html = fs.readFileSync(indexPath, 'utf-8');
    expect(html).toContain('<title>Site Index</title>');
    expect(html).toContain('<a href="a.html">Alpha</a>');
    expect(html).toContain('<a href="b.html">Beta</a>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('uses Untitled as fallback title', () => {
    const contentDir = setupContentDir({
      'nometa.md': `# Just Content

No frontmatter here.
`,
    });

    buildSite(contentDir, outputDir);

    const pagePath = path.join(outputDir, 'nometa.html');
    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<title>Untitled</title>');
    expect(html).toContain('<h1>Untitled</h1>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('only processes .md files', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
      'readme.txt': 'not a markdown file',
    });

    buildSite(contentDir, outputDir);

    const files = fs.readdirSync(outputDir).filter((f) => f.endsWith('.html'));
    expect(files).toHaveLength(2);
    expect(files).toContain('page.html');
    expect(files).toContain('index.html');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('handles empty tags gracefully', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
    });

    buildSite(contentDir, outputDir);

    const pagePath = path.join(outputDir, 'page.html');
    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<div class="tags">');
    expect(html).not.toContain('<span class="tag">');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('handles empty date gracefully', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
---

# Page
`,
    });

    buildSite(contentDir, outputDir);

    const pagePath = path.join(outputDir, 'page.html');
    const html = fs.readFileSync(pagePath, 'utf-8');
    expect(html).toContain('<p class="date"></p>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('sorts pages by date descending in index', () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Alpha
date: 2024-01-01
---

# Alpha
`,
      'b.md': `---
title: Beta
date: 2024-06-01
---

# Beta
`,
      'c.md': `---
title: Gamma
date: 2024-03-01
---

# Gamma
`,
    });

    buildSite(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');

    const aIdx = html.indexOf('Alpha');
    const bIdx = html.indexOf('Beta');
    const cIdx = html.indexOf('Gamma');

    expect(bIdx).toBeLessThan(cIdx);
    expect(cIdx).toBeLessThan(aIdx);

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('escapes HTML in frontmatter values', () => {
    const contentDir = setupContentDir({
      'xss.md': `---
title: <script>alert("xss")</script>
date: 2024-01-01
---

# Content
`,
    });

    buildSite(contentDir, outputDir);

    const html = fs.readFileSync(path.join(outputDir, 'xss.html'), 'utf-8');
    expect(html).not.toContain('<script>alert');
    expect(html).toContain('&lt;script&gt;alert');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('empty content directory produces only index.html', () => {
    const contentDir = setupContentDir({});
    buildSite(contentDir, outputDir);

    const files = fs.readdirSync(outputDir).filter((f) => f.endsWith('.html'));
    expect(files).toHaveLength(1);
    expect(files).toContain('index.html');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('handles content directory with nested paths gracefully (only top-level)', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
    });

    const nestedDir = path.join(contentDir, 'subdir');
    fs.mkdirSync(nestedDir);
    fs.writeFileSync(
      path.join(nestedDir, 'nested.md'),
      `---
title: Nested
date: 2024-02-01
---

# Nested
`
    );

    buildSite(contentDir, outputDir);

    const files = fs.readdirSync(outputDir).filter((f) => f.endsWith('.html'));
    expect(files).toContain('page.html');
    expect(files).toContain('index.html');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });
});

describe('buildSite with templates', () => {
  let outputDir: string;

  beforeEach(() => {
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-output-'));
  });

  afterEach(() => {
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  test('renders pages using default layout template', () => {
    const contentDir = setupContentDir({
      'hello.md': `---
title: Hello World
date: 2024-01-15
tags:
  - test
---

# Hello

This is a **test**.
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<!DOCTYPE html>
<html>
<head><title>{{title}}</title></head>
<body>
  {{> header}}
  <main>{{{body}}}</main>
  {{> footer}}
</body>
</html>`,
      'partials/header.hbs': `<header><h1>{{title}}</h1></header>`,
      'partials/footer.hbs': `<footer>&copy; {{year}}</footer>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
    expect(html).toContain('<title>Hello World</title>');
    expect(html).toContain('<header><h1>Hello World</h1></header>');
    expect(html).toContain('<footer>');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<strong>test</strong>');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('uses custom template specified in frontmatter', () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: My Post
date: 2024-01-01
template: post
---

# Content
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<html><body><h1>Default</h1>{{{body}}}</body></html>`,
      'layouts/post.hbs': `<html><body><h1>Post Layout</h1>{{{body}}}</body></html>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
    expect(html).toContain('Post Layout');
    expect(html).not.toContain('Default');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('falls back to default layout when specified template not found', () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: My Post
date: 2024-01-01
template: nonextistent
---

# Content
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<html><body><h1>Default Layout</h1>{{{body}}}</body></html>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
    expect(html).toContain('Default Layout');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('uses default layout when no template specified in frontmatter', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<html><body><h1>Default</h1>{{{body}}}</body></html>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('Default');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('{{{body}}} placeholder contains page content', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Test
date: 2024-01-01
tags:
  - demo
---

## Section

Some **bold** text.
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<html><body><div class="wrap">{{{body}}}</div></body></html>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('<div class="wrap">');
    expect(html).toContain('<h1>Test</h1>');
    expect(html).toContain('<h2>Section</h2>');
    expect(html).toContain('<strong>bold</strong>');
    expect(html).toContain('<span class="tag">demo</span>');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('partials are included in the output', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Test
date: 2024-01-01
---

# Content
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<html><body>{{> header}}{{> nav}}{{{body}}}{{> footer}}</body></html>`,
      'partials/header.hbs': `<header>Site Header</header>`,
      'partials/nav.hbs': `<nav><a href="index.html">Home</a></nav>`,
      'partials/footer.hbs': `<footer>Site Footer</footer>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('<header>Site Header</header>');
    expect(html).toContain('<nav><a href="index.html">Home</a></nav>');
    expect(html).toContain('<footer>Site Footer</footer>');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('template data includes title, date, and tags', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Data Test
date: 2024-06-15
tags:
  - typescript
  - ssg
---

# Content
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<html><head><title>{{title}}</title></head><body><p class="date">{{date}}</p><ul>{{#each tags}}<li>{{this}}</li>{{/each}}</ul>{{{body}}}</body></html>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('<title>Data Test</title>');
    expect(html).toContain('<p class="date">2024-06-15</p>');
    expect(html).toContain('<li>typescript</li>');
    expect(html).toContain('<li>ssg</li>');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('index page uses template when available', () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Alpha
date: 2024-03-01
---

# Alpha
`,
      'b.md': `---
title: Beta
date: 2024-01-01
---

# Beta
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<html><body>{{> nav}}{{{body}}}</body></html>`,
      'partials/nav.hbs': `<nav>Template Nav</nav>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('Template Nav');
    expect(indexHtml).toContain('<a href="a.html">Alpha</a>');
    expect(indexHtml).toContain('<a href="b.html">Beta</a>');
    expect(indexHtml).toContain('All Pages');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('empty templates directory falls back to inline HTML', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
    });

    const templatesDir = setupTemplateDir({});

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('<title>Page</title>');
    expect(html).toContain('<style>');
    expect(html).toContain('<article>');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  test('nonexistent templates directory falls back to inline HTML', () => {
    const contentDir = setupContentDir({
      'page.md': `---
title: Page
date: 2024-01-01
---

# Page
`,
    });

    buildSite(contentDir, outputDir, '/nonexistent/templates');

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('<title>Page</title>');
    expect(html).toContain('<style>');
    expect(html).toContain('<article>');

    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  test('escapes HTML in frontmatter values within template output', () => {
    const contentDir = setupContentDir({
      'xss.md': `---
title: <script>alert("xss")</script>
date: 2024-01-01
---

# Content
`,
    });

    const templatesDir = setupTemplateDir({
      'layouts/default.hbs': `<html><head><title>{{title}}</title></head><body><h1>{{title}}</h1>{{{body}}}</body></html>`,
    });

    buildSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'xss.html'), 'utf-8');
    expect(html).toContain('&lt;script&gt;alert');
    expect(html).not.toContain('<script>alert');

    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });
});
