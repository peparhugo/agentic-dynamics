import fs from 'fs';
import path from 'path';
import {
  parseMarkdownFile,
  readContentDirectory,
  generateSite,
} from '../src/generator';
import { TemplateEngine } from '../src/templates';

const tmpDir = path.join(__dirname, '..', '.test-tmp');

beforeEach(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

afterAll(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

function createContentDir(name: string): string {
  const dir = path.join(tmpDir, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.writeFileSync(filePath, content);
  return filePath;
}

describe('parseMarkdownFile', () => {
  it('parses markdown with frontmatter', () => {
    const contentDir = createContentDir('parse-test');
    const filePath = writeFile(
      contentDir,
      'hello.md',
      `---
title: Hello World
date: 2024-01-15
tags:
  - typescript
  - ssg
---

# Hello

This is a paragraph.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('Hello World');
    expect(page!.date).toBe('2024-01-15');
    expect(page!.tags).toEqual(['typescript', 'ssg']);
    expect(page!.slug).toBe('hello');
    expect(page!.content).toContain('<h1');
    expect(page!.content).toContain('Hello');
    expect(page!.content).toContain('This is a paragraph.');
  });

  it('uses filename as title when no title in frontmatter', () => {
    const contentDir = createContentDir('no-title');
    const filePath = writeFile(
      contentDir,
      'about.md',
      `# About

Some content.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('about');
    expect(page!.slug).toBe('about');
    expect(page!.date).toBe('');
    expect(page!.tags).toEqual([]);
  });

  it('parses markdown with only frontmatter title', () => {
    const contentDir = createContentDir('title-only');
    const filePath = writeFile(
      contentDir,
      'test.md',
      `---
title: Just Title
---

Content here.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('Just Title');
    expect(page!.date).toBe('');
    expect(page!.tags).toEqual([]);
  });

  it('handles code blocks in markdown', () => {
    const contentDir = createContentDir('code-block');
    const filePath = writeFile(
      contentDir,
      'code.md',
      `---
title: Code Post
---

\`\`\`typescript
const x = 1;
\`\`\``
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.content).toContain('class="language-typescript"');
  });

  it('extracts layout and template from frontmatter', () => {
    const contentDir = createContentDir('layout-tmpl');
    const filePath = writeFile(
      contentDir,
      'custom.md',
      `---
title: Custom Page
layout: blog
template: post
---

# Custom

Content.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('Custom Page');
    expect(page!.layout).toBe('blog');
    expect(page!.template).toBe('post');
  });

  it('handles empty frontmatter gracefully', () => {
    const contentDir = createContentDir('empty-fm');
    const filePath = writeFile(
      contentDir,
      'empty.md',
      `---
---

Just content.`
    );

    const page = parseMarkdownFile(filePath);
    expect(page).not.toBeNull();
    expect(page!.title).toBe('empty');
    expect(page!.date).toBe('');
    expect(page!.tags).toEqual([]);
  });
});

describe('readContentDirectory', () => {
  it('returns empty array for non-existent directory', () => {
    const pages = readContentDirectory('/nonexistent/path');
    expect(pages).toEqual([]);
  });

  it('returns empty array for empty directory', () => {
    const contentDir = createContentDir('empty-dir');
    const pages = readContentDirectory(contentDir);
    expect(pages).toEqual([]);
  });

  it('reads all .md files in directory', () => {
    const contentDir = createContentDir('multi-file');
    writeFile(
      contentDir,
      'post1.md',
      `---
title: Post One
---

# One`
    );
    writeFile(
      contentDir,
      'post2.md',
      `---
title: Post Two
---

# Two`
    );
    writeFile(contentDir, 'not-a-post.txt', 'hello');

    const pages = readContentDirectory(contentDir);
    expect(pages).toHaveLength(2);
    expect(pages.map((p) => p.title)).toContain('Post One');
    expect(pages.map((p) => p.title)).toContain('Post Two');
  });

  it('skips non-markdown files', () => {
    const contentDir = createContentDir('skip-non-md');
    writeFile(contentDir, 'data.json', '{}');
    writeFile(contentDir, 'readme.md', `---
title: Readme
---

# Readme`);

    const pages = readContentDirectory(contentDir);
    expect(pages).toHaveLength(1);
    expect(pages[0].title).toBe('Readme');
  });
});

describe('generateSite', () => {
  it('generates html files in output directory', () => {
    const contentDir = createContentDir('gen-site');
    const outputDir = path.join(tmpDir, 'gen-output');

    writeFile(
      contentDir,
      'post1.md',
      `---
title: First Post
date: 2024-01-01
tags:
  - blog
  - tech
---

# Hello

World content.`
    );

    writeFile(
      contentDir,
      'post2.md',
      `---
title: Second Post
date: 2024-02-01
tags:
  - tutorial
---

# Second

More content.`
    );

    const count = generateSite(contentDir, outputDir);
    expect(count).toBe(3);

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'post1.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'post2.html'))).toBe(true);

    const post1Html = fs.readFileSync(path.join(outputDir, 'post1.html'), 'utf-8');
    expect(post1Html).toContain('<!DOCTYPE html>');
    expect(post1Html).toContain('<title>First Post</title>');
    expect(post1Html).toContain('>Hello</h1>');
    expect(post1Html).toContain('World content.');
    expect(post1Html).toContain('2024-01-01');
    expect(post1Html).toContain('blog, tech');

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('First Post');
    expect(indexHtml).toContain('Second Post');
    expect(indexHtml).toContain('post1.html');
    expect(indexHtml).toContain('post2.html');
  });

  it('handles empty content directory', () => {
    const contentDir = createContentDir('empty-gen');
    const outputDir = path.join(tmpDir, 'empty-output');

    const count = generateSite(contentDir, outputDir);
    expect(count).toBe(0);
  });

  it('creates output directory if it does not exist', () => {
    const contentDir = createContentDir('create-dir-test');
    const outputDir = path.join(tmpDir, 'new-output-dir');

    writeFile(
      contentDir,
      'hello.md',
      `---
title: Hello
---

Hello world.`
    );

    expect(fs.existsSync(outputDir)).toBe(false);
    generateSite(contentDir, outputDir);
    expect(fs.existsSync(outputDir)).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
  });

  it('generates page with no tags', () => {
    const contentDir = createContentDir('no-tags');
    const outputDir = path.join(tmpDir, 'no-tags-output');

    writeFile(
      contentDir,
      'simple.md',
      `---
title: Simple Page
---

Simple content.`
    );

    const count = generateSite(contentDir, outputDir);
    expect(count).toBe(2);

    const simpleHtml = fs.readFileSync(path.join(outputDir, 'simple.html'), 'utf-8');
    expect(simpleHtml).toContain('<title>Simple Page</title>');
    expect(simpleHtml).toContain('<h1>Simple Page</h1>');
    expect(simpleHtml).toContain('<p>Simple content.</p>');
  });
});

describe('index.html generation', () => {
  it('includes links to all pages', () => {
    const contentDir = createContentDir('index-test');
    const outputDir = path.join(tmpDir, 'index-output');

    writeFile(
      contentDir,
      'a.md',
      `---
title: Page A
date: 2024-03-01
tags:
  - alpha
---

Content A.`
    );

    writeFile(
      contentDir,
      'b.md',
      `---
title: Page B
---

Content B.`
    );

    generateSite(contentDir, outputDir);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('<a href="a.html">Page A</a>');
    expect(indexHtml).toContain('<a href="b.html">Page B</a>');
  });
});

function createTemplatesDir(name: string): string {
  const dir = path.join(tmpDir, name);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

describe('TemplateEngine', () => {
  it('renders with default layout', () => {
    const templatesDir = createTemplatesDir('tpl-test');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });
    writeFile(
      layoutsDir,
      'default.hbs',
      `<!DOCTYPE html><title>{{title}}</title><body>{{{body}}}</body>`
    );

    const engine = new TemplateEngine(templatesDir);
    expect(engine.initialized).toBe(true);

    const html = engine.render({
      title: 'Test',
      date: '',
      tags: [],
      content: '<p>Hello</p>',
      slug: 'test',
    });

    expect(html).not.toBeNull();
    expect(html!).toContain('<p>Hello</p>');
    expect(html!).toContain('<title>Test</title>');
  });

  it('renders with partials', () => {
    const templatesDir = createTemplatesDir('tpl-partials');
    const layoutsDir = path.join(templatesDir, 'layouts');
    const partialsDir = path.join(templatesDir, 'partials');
    fs.mkdirSync(layoutsDir, { recursive: true });
    fs.mkdirSync(partialsDir, { recursive: true });

    writeFile(partialsDir, 'header.hbs', `<header>{{title}}</header>`);
    writeFile(
      layoutsDir,
      'default.hbs',
      `<!DOCTYPE html><body>{{> header}}{{{body}}}</body>`
    );

    const engine = new TemplateEngine(templatesDir);

    const html = engine.render({
      title: 'Partials',
      date: '',
      tags: [],
      content: '<p>Body</p>',
      slug: 'partials',
    });

    expect(html).not.toBeNull();
    expect(html!).toContain('<header>Partials</header>');
    expect(html!).toContain('<p>Body</p>');
  });

  it('uses custom layout from frontmatter', () => {
    const templatesDir = createTemplatesDir('tpl-custom');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      layoutsDir,
      'default.hbs',
      `<!DOCTYPE html><title>{{title}}</title><body>{{{body}}}</body>`
    );
    writeFile(
      layoutsDir,
      'blog.hbs',
      `<html><title>Blog: {{title}}</title><article>{{{body}}}</article></html>`
    );

    const engine = new TemplateEngine(templatesDir);

    const html = engine.render({
      title: 'Post',
      date: '',
      tags: [],
      content: '<p>Content</p>',
      slug: 'post',
      layout: 'blog',
    });

    expect(html).not.toBeNull();
    expect(html!).toContain('Blog: Post');
    expect(html!).toContain('<article><p>Content</p></article>');
  });

  it('uses custom page template', () => {
    const templatesDir = createTemplatesDir('tpl-pagetpl');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      templatesDir,
      'post.hbs',
      `<article><h1>{{title}}</h1>{{{content}}}</article>`
    );
    writeFile(
      layoutsDir,
      'default.hbs',
      `<!DOCTYPE html><title>{{title}}</title><body>{{{body}}}</body>`
    );

    const engine = new TemplateEngine(templatesDir);

    const html = engine.render({
      title: 'Templated',
      date: '',
      tags: [],
      content: '<p>Body</p>',
      slug: 'templated',
      template: 'post',
    });

    expect(html).not.toBeNull();
    expect(html!).toContain('<article><h1>Templated</h1><p>Body</p></article>');
  });

  it('falls back to content when no template found', () => {
    const templatesDir = createTemplatesDir('tpl-nofound');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      layoutsDir,
      'default.hbs',
      `<!DOCTYPE html><title>{{title}}</title><body>{{{body}}}</body>`
    );

    const engine = new TemplateEngine(templatesDir);

    const html = engine.render({
      title: 'Fallback',
      date: '',
      tags: [],
      content: '<p>Raw</p>',
      slug: 'fallback',
      template: 'nonexistent',
    });

    expect(html).not.toBeNull();
    expect(html!).toContain('<p>Raw</p>');
  });

  it('renders index with default layout', () => {
    const templatesDir = createTemplatesDir('tpl-index');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      layoutsDir,
      'default.hbs',
      `<html><body><h1>Site</h1>{{{body}}}</body></html>`
    );

    const engine = new TemplateEngine(templatesDir);

    const indexHtml = engine.renderIndex([
      { title: 'A', date: '', tags: [], content: '', slug: 'a' },
      { title: 'B', date: '', tags: [], content: '', slug: 'b' },
    ]);

    expect(indexHtml).not.toBeNull();
    expect(indexHtml!).toContain('All Pages');
    expect(indexHtml!).toContain('<a href="a.html">A</a>');
    expect(indexHtml!).toContain('<a href="b.html">B</a>');
    expect(indexHtml!).toContain('<h1>Site</h1>');
  });

  it('renders index with dedicated index layout', () => {
    const templatesDir = createTemplatesDir('tpl-idx-layout');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      layoutsDir,
      'default.hbs',
      `<html><body>Default{{{body}}}</body></html>`
    );
    writeFile(
      layoutsDir,
      'index.hbs',
      `<html><body>IndexLayout{{{body}}}</body></html>`
    );

    const engine = new TemplateEngine(templatesDir);

    const indexHtml = engine.renderIndex([
      { title: 'A', date: '', tags: [], content: '', slug: 'a' },
    ]);

    expect(indexHtml).not.toBeNull();
    expect(indexHtml!).toContain('IndexLayout');
  });

  it('returns null when no templates dir exists', () => {
    const engine = new TemplateEngine('/nonexistent/templates/dir');
    expect(engine.initialized).toBe(false);

    const result = engine.render({
      title: 'Test',
      date: '',
      tags: [],
      content: '<p>Hi</p>',
      slug: 'test',
    });

    expect(result).toBeNull();
  });
});

describe('generateSite with templates', () => {
  it('generates pages using template engine', () => {
    const contentDir = createContentDir('gen-tpl-content');
    const outputDir = path.join(tmpDir, 'gen-tpl-output');
    const templatesDir = createTemplatesDir('gen-tpl-templates');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      layoutsDir,
      'default.hbs',
      `<!DOCTYPE html><title>{{title}}</title><body>{{{body}}}</body>`
    );

    writeFile(
      contentDir,
      'page.md',
      `---
title: Template Page
date: 2024-06-01
tags:
  - ssg
---

# Template

Generated with templates.`
    );

    const count = generateSite(contentDir, outputDir, templatesDir);
    expect(count).toBe(2);

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>Template Page</title>');
    expect(html).toContain('<h1');
    expect(html).toContain('Template');
    expect(html).toContain('Generated with templates.');
  });

  it('uses layout specified in frontmatter', () => {
    const contentDir = createContentDir('gen-layout-content');
    const outputDir = path.join(tmpDir, 'gen-layout-output');
    const templatesDir = createTemplatesDir('gen-layout-templates');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      layoutsDir,
      'default.hbs',
      `<html><body>Default{{{body}}}</body></html>`
    );
    writeFile(
      layoutsDir,
      'minimal.hbs',
      `<html><body>Minimal{{{body}}}</body></html>`
    );

    writeFile(
      contentDir,
      'post.md',
      `---
title: Minimal Post
layout: minimal
---

Content.`
    );

    generateSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'post.html'), 'utf-8');
    expect(html).toContain('<body>Minimal');
    expect(html).not.toContain('<body>Default');
  });

  it('uses template specified in frontmatter', () => {
    const contentDir = createContentDir('gen-tmpl-content');
    const outputDir = path.join(tmpDir, 'gen-tmpl-output');
    const templatesDir = createTemplatesDir('gen-tmpl-templates');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      templatesDir,
      'post.hbs',
      `<article class="post"><h1>{{title}}</h1>{{{content}}}</article>`
    );
    writeFile(
      layoutsDir,
      'default.hbs',
      `<!DOCTYPE html><title>{{title}}</title><body>{{{body}}}</body>`
    );

    writeFile(
      contentDir,
      'entry.md',
      `---
title: Entry
template: post
---

# Entry

Body.`
    );

    generateSite(contentDir, outputDir, templatesDir);

    const html = fs.readFileSync(path.join(outputDir, 'entry.html'), 'utf-8');
    expect(html).toContain('<article class="post">');
  });

  it('generates index with template engine', () => {
    const contentDir = createContentDir('gen-idx-tpl-content');
    const outputDir = path.join(tmpDir, 'gen-idx-tpl-output');
    const templatesDir = createTemplatesDir('gen-idx-tpl-templates');
    const layoutsDir = path.join(templatesDir, 'layouts');
    fs.mkdirSync(layoutsDir, { recursive: true });

    writeFile(
      layoutsDir,
      'default.hbs',
      `<!DOCTYPE html><title>{{title}}</title><body><nav>Nav</nav>{{{body}}}</body>`
    );

    writeFile(
      contentDir,
      'p1.md',
      `---
title: P1
---

Content 1.`
    );

    generateSite(contentDir, outputDir, templatesDir);

    const indexHtml = fs.readFileSync(path.join(outputDir, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('Nav');
    expect(indexHtml).toContain('All Pages');
    expect(indexHtml).toContain('<a href="p1.html">P1</a>');
  });

  it('falls back to hardcoded render when no template dir', () => {
    const contentDir = createContentDir('gen-fallback-content');
    const outputDir = path.join(tmpDir, 'gen-fallback-output');

    writeFile(
      contentDir,
      'test.md',
      `---
title: Fallback
---

Fallback content.`
    );

    const count = generateSite(contentDir, outputDir);
    expect(count).toBe(2);

    const html = fs.readFileSync(path.join(outputDir, 'test.html'), 'utf-8');
    expect(html).toContain('<h1>Fallback</h1>');
    expect(html).toContain('Fallback content.');
  });
});
