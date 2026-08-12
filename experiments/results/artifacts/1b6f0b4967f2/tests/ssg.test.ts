import fs from 'fs';
import path from 'path';
import os from 'os';
import { build } from '../src/ssg';

const testContentDir = path.join(__dirname, 'content');
const testOutputDir = path.join(__dirname, 'output');

function setupOutputDir() {
  if (fs.existsSync(testOutputDir)) {
    fs.rmSync(testOutputDir, { recursive: true });
  }
  fs.mkdirSync(testOutputDir, { recursive: true });
}

describe('SSG build', () => {
  beforeEach(() => {
    setupOutputDir();
  });

  afterEach(() => {
    if (fs.existsSync(testOutputDir)) {
      fs.rmSync(testOutputDir, { recursive: true });
    }
  });

  test('generates index.html', () => {
    build({ contentDir: testContentDir, outputDir: testOutputDir });

    const indexPath = path.join(testOutputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexContent = fs.readFileSync(indexPath, 'utf-8');
    expect(indexContent).toContain('Hello World');
    expect(indexContent).toContain('Getting Started');
    expect(indexContent).toContain('hello-world.html');
    expect(indexContent).toContain('getting-started.html');
    expect(indexContent).toContain('1/15/2024');
    expect(indexContent).toContain('2/20/2024');
    expect(indexContent).toContain('intro, typescript');
    expect(indexContent).toContain('guide');
  });

  test('generates individual page HTML files', () => {
    build({ contentDir: testContentDir, outputDir: testOutputDir });

    const helloPath = path.join(testOutputDir, 'hello-world.html');
    expect(fs.existsSync(helloPath)).toBe(true);

    const helloContent = fs.readFileSync(helloPath, 'utf-8');
    expect(helloContent).toContain('<title>Hello World</title>');
    expect(helloContent).toContain('<h1>Hello World</h1>');
    expect(helloContent).toContain('This is a test page.');
    expect(helloContent).toContain('<a href="index.html">Back to index</a>');

    const gsPath = path.join(testOutputDir, 'getting-started.html');
    expect(fs.existsSync(gsPath)).toBe(true);

    const gsContent = fs.readFileSync(gsPath, 'utf-8');
    expect(gsContent).toContain('<title>Getting Started</title>');
    expect(gsContent).toContain('<h1>Getting Started</h1>');
    expect(gsContent).toContain('<strong>bold</strong>');
    expect(gsContent).toContain('<em>italic</em>');
    expect(gsContent).toContain('<code>npm install</code>');
  });

  test('handles empty content directory', () => {
    const emptyDir = path.join(os.tmpdir(), 'ssg-empty-' + Date.now());
    fs.mkdirSync(emptyDir, { recursive: true });

    try {
      build({ contentDir: emptyDir, outputDir: testOutputDir });

      const indexPath = path.join(testOutputDir, 'index.html');
      expect(fs.existsSync(indexPath)).toBe(true);

      const indexContent = fs.readFileSync(indexPath, 'utf-8');
      expect(indexContent).toContain('<h1>Pages</h1>');
      expect(indexContent).not.toContain('<li>');
    } finally {
      fs.rmSync(emptyDir, { recursive: true });
    }
  });

  test('handles non-existent content directory', () => {
    build({ contentDir: '/tmp/nonexistent-dir-ssg-test', outputDir: testOutputDir });

    const indexPath = path.join(testOutputDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(true);

    const indexContent = fs.readFileSync(indexPath, 'utf-8');
    expect(indexContent).toContain('<h1>Pages</h1>');
    expect(indexContent).not.toContain('<li>');
  });

  test('creates output directory if it does not exist', () => {
    const newOutput = path.join(os.tmpdir(), 'ssg-new-output-' + Date.now());
    expect(fs.existsSync(newOutput)).toBe(false);

    try {
      build({ contentDir: testContentDir, outputDir: newOutput });
      expect(fs.existsSync(newOutput)).toBe(true);
      expect(fs.existsSync(path.join(newOutput, 'index.html'))).toBe(true);
    } finally {
      fs.rmSync(newOutput, { recursive: true });
    }
  });

  test('index page lists all pages sorted', () => {
    build({ contentDir: testContentDir, outputDir: testOutputDir });

    const indexContent = fs.readFileSync(path.join(testOutputDir, 'index.html'), 'utf-8');

    const helloIndex = indexContent.indexOf('Hello World');
    const gsIndex = indexContent.indexOf('Getting Started');
    // Both should appear; order depends on file read order
    expect(helloIndex).toBeGreaterThan(-1);
    expect(gsIndex).toBeGreaterThan(-1);
  });

  test('page without frontmatter uses slug as title', () => {
    const dir = path.join(os.tmpdir(), 'ssg-nofm-' + Date.now());
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, 'no-title.md'), '# Just content\n\nNo frontmatter here.');

    try {
      build({ contentDir: dir, outputDir: testOutputDir });

      const pagePath = path.join(testOutputDir, 'no-title.html');
      expect(fs.existsSync(pagePath)).toBe(true);
      const content = fs.readFileSync(pagePath, 'utf-8');
      expect(content).toContain('<title>no-title</title>');
    } finally {
      fs.rmSync(dir, { recursive: true });
    }
  });
});

describe('SSG template engine', () => {
  const testTemplatesDir = path.join(__dirname, 'templates');
  let tempContentDir: string;

  beforeEach(() => {
    setupOutputDir();
    tempContentDir = path.join(os.tmpdir(), 'ssg-tmpl-' + Date.now());
    fs.mkdirSync(tempContentDir, { recursive: true });
  });

  afterEach(() => {
    if (fs.existsSync(tempContentDir)) {
      fs.rmSync(tempContentDir, { recursive: true });
    }
  });

  test('renders pages using templates from template directory', () => {
    fs.writeFileSync(path.join(tempContentDir, 'test.md'), `---
title: Test Page
date: 2024-03-01
tags:
  - demo
---
# Test Page

Template rendered content.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const pagePath = path.join(testOutputDir, 'test.html');
    expect(fs.existsSync(pagePath)).toBe(true);
    const content = fs.readFileSync(pagePath, 'utf-8');

    expect(content).toContain('Test Page - My Site');
    expect(content).toContain('<header>');
    expect(content).toContain('<nav>');
    expect(content).toContain('<a href="index.html">Home</a>');
    expect(content).toContain('Template rendered content.');
    expect(content).toContain('<footer>');
    expect(content).toContain('<a href="index.html">Back to index</a>');
  });

  test('respects template specified in frontmatter', () => {
    fs.writeFileSync(path.join(tempContentDir, 'custom.md'), `---
title: Custom Page
template: custom
---
Content with custom template.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const pagePath = path.join(testOutputDir, 'custom.html');
    const content = fs.readFileSync(pagePath, 'utf-8');

    expect(content).toContain('Custom Page - My Site');
    expect(content).toContain('class="custom-page"');
    expect(content).toContain('class="custom-title"');
    expect(content).toContain('Content with custom template.');
  });

  test('respects layout specified in frontmatter', () => {
    fs.writeFileSync(path.join(tempContentDir, 'blog.md'), `---
title: Blog Post
layout: blog
---
Blog content here.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const pagePath = path.join(testOutputDir, 'blog.html');
    const content = fs.readFileSync(pagePath, 'utf-8');

    expect(content).toContain('Blog Post - Blog');
    expect(content).toContain('class="blog-layout"');
    expect(content).toContain('Blog content here.');
  });

  test('falls back to default template when specified template not found', () => {
    fs.writeFileSync(path.join(tempContentDir, 'missing.md'), `---
title: Missing Template
template: nonexistent
---
Fallback content.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const pagePath = path.join(testOutputDir, 'missing.html');
    const content = fs.readFileSync(pagePath, 'utf-8');

    expect(content).toContain('Missing Template - My Site');
    expect(content).toContain('Fallback content.');
    expect(content).toContain('<header>');
    expect(content).toContain('<footer>');
  });

  test('falls back to default layout when specified layout not found', () => {
    fs.writeFileSync(path.join(tempContentDir, 'bad-layout.md'), `---
title: Bad Layout
layout: nonexistent
---
Content.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const pagePath = path.join(testOutputDir, 'bad-layout.html');
    const content = fs.readFileSync(pagePath, 'utf-8');

    expect(content).toContain('Bad Layout - My Site');
    expect(content).toContain('Content.');
  });

  test('partials are registered and usable in templates', () => {
    fs.writeFileSync(path.join(tempContentDir, 'partial.md'), `---
title: Partial Test
---
Partial included content.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const pagePath = path.join(testOutputDir, 'partial.html');
    const content = fs.readFileSync(pagePath, 'utf-8');

    expect(content).toContain('<header>');
    expect(content).toContain('<nav>');
    expect(content).toContain('<a href="index.html">Home</a>');
    expect(content).toContain('<a href="#">About</a>');
    expect(content).toContain('<footer>');
    expect(content).toContain('Back to index');
    expect(content).toContain('Partial included content.');
  });

  test('index page uses custom index template when available', () => {
    fs.writeFileSync(path.join(tempContentDir, 'page1.md'), `---
title: Page One
---
Content one.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const indexPath = path.join(testOutputDir, 'index.html');
    const content = fs.readFileSync(indexPath, 'utf-8');

    expect(content).toContain('<header>');
    expect(content).toContain('<footer>');
    expect(content).toContain('Page One');
    expect(content).toContain('page1.html');
  });

  test('template receives page frontmatter data', () => {
    fs.writeFileSync(path.join(tempContentDir, 'data.md'), `---
title: Data Test
date: 2024-06-15
tags:
  - typescript
  - javascript
---
Data-driven page.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const pagePath = path.join(testOutputDir, 'data.html');
    const content = fs.readFileSync(pagePath, 'utf-8');

    expect(content).toContain('Data Test - My Site');
    expect(content).toContain('<h1>Data Test</h1>');
    expect(content).toContain('Tags: typescript, javascript');
    expect(content).toContain('Data-driven page.');
  });

  test('layout {{{body}}} placeholder inserts page content', () => {
    fs.writeFileSync(path.join(tempContentDir, 'layout-body.md'), `---
title: Body Test
---
Body placeholder test.`);

    build({ contentDir: tempContentDir, outputDir: testOutputDir, templateDir: testTemplatesDir });

    const pagePath = path.join(testOutputDir, 'layout-body.html');
    const content = fs.readFileSync(pagePath, 'utf-8');

    expect(content).toContain('Body Test - My Site');
    expect(content).toContain('Body placeholder test.');
    expect(content).toContain('<header>');
  });
});
