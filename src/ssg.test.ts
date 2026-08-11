import fs from 'fs';
import path from 'path';
import http from 'http';
import { WebSocket } from 'ws';
import { parseFiles } from './parser';
import { generateSite } from './generator';
import { TemplateEngine } from './templates';
import { PageData } from './types';
import { startDevServer } from './server';
import { parseArgs } from './index';

const tmpDir = path.join(__dirname, '..', '.test-tmp');

function setupContentDir(files: Record<string, string>): string {
  const contentDir = path.join(tmpDir, 'content');
  if (fs.existsSync(contentDir)) {
    fs.rmSync(contentDir, { recursive: true });
  }
  fs.mkdirSync(contentDir, { recursive: true });
  for (const [name, body] of Object.entries(files)) {
    fs.writeFileSync(path.join(contentDir, name), body);
  }
  return contentDir;
}

function outputDir(): string {
  const dir = path.join(tmpDir, 'dist');
  if (fs.existsSync(dir)) {
    fs.rmSync(dir, { recursive: true });
  }
  return dir;
}

function setupTemplatesDir(files: Record<string, string>): string {
  const templatesDir = path.join(tmpDir, 'templates');
  if (fs.existsSync(templatesDir)) {
    fs.rmSync(templatesDir, { recursive: true });
  }
  fs.mkdirSync(templatesDir, { recursive: true });
  for (const [name, body] of Object.entries(files)) {
    const fullPath = path.join(templatesDir, name);
    const dir = path.dirname(fullPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(fullPath, body);
  }
  return templatesDir;
}

function getFreePort(): Promise<number> {
  return new Promise((resolve) => {
    const srv = http.createServer();
    srv.listen(0, () => {
      const address = srv.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      srv.close(() => resolve(port));
    });
  });
}

function httpGet(url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => resolve({ status: res.statusCode || 0, body }));
    }).on('error', reject);
  });
}

beforeEach(() => {
  if (fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true });
  }
});

describe('parseFiles', () => {
  it('parses a single markdown file with frontmatter', () => {
    const contentDir = setupContentDir({
      'hello.md': `---
title: Hello World
date: 2024-01-15
tags:
  - typescript
  - cli
---
# Hello

This is a test post.`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages).toHaveLength(1);
    expect(result.pages[0].slug).toBe('hello');
    expect(result.pages[0].frontmatter.title).toBe('Hello World');
    expect(result.pages[0].frontmatter.date).toBe('2024-01-15');
    expect(result.pages[0].frontmatter.tags).toEqual(['typescript', 'cli']);
    expect(result.pages[0].html).toContain('<h1>Hello</h1>');
    expect(result.pages[0].html).toContain('<p>This is a test post.</p>');
  });

  it('uses filename as title when no title in frontmatter', () => {
    const contentDir = setupContentDir({
      'no-title.md': `---
date: 2024-02-01
---
# Content`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages[0].frontmatter.title).toBe('no-title');
  });

  it('handles missing date and tags gracefully', () => {
    const contentDir = setupContentDir({
      'minimal.md': `---
title: Minimal
---
Just content.`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages[0].frontmatter.date).toBe('');
    expect(result.pages[0].frontmatter.tags).toEqual([]);
  });

  it('parses multiple files', () => {
    const contentDir = setupContentDir({
      'a.md': `---
title: Post A
date: 2024-01-01
---
# A`,
      'b.md': `---
title: Post B
date: 2024-02-01
---
# B`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages).toHaveLength(2);
  });

  it('ignores non-markdown files', () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: Post
date: 2024-01-01
---
# Post`,
      'readme.txt': 'not markdown',
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages).toHaveLength(1);
    expect(result.pages[0].slug).toBe('post');
  });

  it('throws when content directory does not exist', () => {
    expect(() =>
      parseFiles({ contentDir: '/nonexistent/dir', outputDir: outputDir() })
    ).toThrow('Content directory not found');
  });

  it('parses template and layout from frontmatter', () => {
    const contentDir = setupContentDir({
      'custom.md': `---
title: Custom Page
date: 2024-01-01
template: fancy
layout: wide
---
# Custom`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages[0].frontmatter.template).toBe('fancy');
    expect(result.pages[0].frontmatter.layout).toBe('wide');
  });

  it('template and layout are undefined when not specified', () => {
    const contentDir = setupContentDir({
      'plain.md': `---
title: Plain
date: 2024-01-01
---
# Plain`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    expect(result.pages[0].frontmatter.template).toBeUndefined();
    expect(result.pages[0].frontmatter.layout).toBeUndefined();
  });
});

describe('generateSite', () => {
  it('generates index.html and individual pages', () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: My Post
date: 2024-03-10
tags:
  - blog
---
# My Post

Content here.`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    const dist = outputDir();
    generateSite(result, dist);

    const indexHtml = fs.readFileSync(path.join(dist, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('<!DOCTYPE html>');
    expect(indexHtml).toContain('My Post');
    expect(indexHtml).toContain('post.html');
    expect(indexHtml).toContain('2024-03-10');
    expect(indexHtml).toContain('blog');

    const postHtml = fs.readFileSync(path.join(dist, 'post.html'), 'utf-8');
    expect(postHtml).toContain('<!DOCTYPE html>');
    expect(postHtml).toContain('<h1>My Post</h1>');
    expect(postHtml).toContain('<h1>My Post</h1>');
  });

  it('sorts index by date descending', () => {
    const contentDir = setupContentDir({
      'old.md': `---
title: Old Post
date: 2024-01-01
---
# Old`,
      'new.md': `---
title: New Post
date: 2024-06-01
---
# New`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    const dist = outputDir();
    generateSite(result, dist);

    const indexHtml = fs.readFileSync(path.join(dist, 'index.html'), 'utf-8');
    const newIdx = indexHtml.indexOf('New Post');
    const oldIdx = indexHtml.indexOf('Old Post');
    expect(newIdx).toBeLessThan(oldIdx);
  });

  it('creates output directory if it does not exist', () => {
    const contentDir = setupContentDir({
      'p.md': `---
title: P
date: 2024-01-01
---
# P`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    const dist = outputDir();
    generateSite(result, dist);
    expect(fs.existsSync(dist)).toBe(true);
    expect(fs.existsSync(path.join(dist, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(dist, 'p.html'))).toBe(true);
  });
});

describe('TemplateEngine', () => {
  it('renders a page with default templates when no templates dir exists', () => {
    const nonExistentDir = path.join(tmpDir, 'nonexistent-templates');
    const engine = new TemplateEngine({ templatesDir: nonExistentDir });

    const page: PageData = {
      slug: 'hello',
      frontmatter: {
        title: 'Hello World',
        date: '2024-01-15',
        tags: ['typescript', 'cli'],
      },
      content: '# Hello',
      html: '<h1>Hello</h1>',
    };

    const html = engine.renderPage(page);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<h1>Hello World</h1>');
    expect(html).toContain('<time>2024-01-15</time>');
    expect(html).toContain('Tags: typescript, cli');
    expect(html).toContain('<h1>Hello</h1>');
    expect(html).toContain('<a href="index.html">&larr; Back to index</a>');
  });

  it('renders the index with default templates', () => {
    const nonExistentDir = path.join(tmpDir, 'nonexistent-templates');
    const engine = new TemplateEngine({ templatesDir: nonExistentDir });

    const pages: PageData[] = [
      {
        slug: 'post-a',
        frontmatter: { title: 'Post A', date: '2024-02-01', tags: ['blog'] },
        content: '# A',
        html: '<h1>A</h1>',
      },
      {
        slug: 'post-b',
        frontmatter: { title: 'Post B', date: '2024-01-01', tags: [] },
        content: '# B',
        html: '<h1>B</h1>',
      },
    ];

    const html = engine.renderIndex(pages);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<h1>Blog</h1>');
    expect(html).toContain('Post A');
    expect(html).toContain('Post B');
    const idxA = html.indexOf('Post A');
    const idxB = html.indexOf('Post B');
    expect(idxA).toBeLessThan(idxB);
  });

  it('renders a page using custom template and layout from frontmatter', () => {
    const templatesDir = setupTemplatesDir({
      'layouts/custom.hbs': `<!DOCTYPE html><html><head><title>{{title}}</title></head><body><main>{{{body}}}</main></body></html>`,
      'post.hbs': `<article><h2>{{title}}</h2><div>{{{content}}}</div></article>`,
    });

    const engine = new TemplateEngine({ templatesDir });

    const page: PageData = {
      slug: 'my-post',
      frontmatter: {
        title: 'My Post',
        date: '2024-01-01',
        tags: [],
        template: 'post',
        layout: 'custom',
      },
      content: '# Hello',
      html: '<h1>Hello</h1>',
    };

    const html = engine.renderPage(page);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('<title>My Post</title>');
    expect(html).toContain('<article><h2>My Post</h2><div><h1>Hello</h1></div></article>');
  });

  it('uses default template when frontmatter does not specify one', () => {
    const templatesDir = setupTemplatesDir({
      'layouts/default.hbs': `<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>`,
      'default.hbs': `<main>{{{content}}}</main>`,
    });

    const engine = new TemplateEngine({ templatesDir });

    const page: PageData = {
      slug: 'test',
      frontmatter: { title: 'Test', date: '', tags: [] },
      content: 'Body',
      html: '<p>Body</p>',
    };

    const html = engine.renderPage(page);
    expect(html).toContain('<main><p>Body</p></main>');
    expect(html).toContain('<title>Test</title>');
  });

  it('supports partials from the partials directory', () => {
    const templatesDir = setupTemplatesDir({
      'layouts/default.hbs': `<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{> header}}{{{body}}}{{> footer}}</body></html>`,
      'default.hbs': `<main>{{{content}}}</main>`,
      'partials/header.hbs': `<header><nav>Site Header</nav></header>`,
      'partials/footer.hbs': `<footer>Site Footer</footer>`,
    });

    const engine = new TemplateEngine({ templatesDir });

    const page: PageData = {
      slug: 'test',
      frontmatter: { title: 'Test', date: '', tags: [] },
      content: 'Body',
      html: '<p>Body</p>',
    };

    const html = engine.renderPage(page);
    expect(html).toContain('<header><nav>Site Header</nav></header>');
    expect(html).toContain('<footer>Site Footer</footer>');
    expect(html).toContain('<p>Body</p>');
  });

  it('escapes HTML in title via Handlebars', () => {
    const nonExistentDir = path.join(tmpDir, 'nonexistent-templates');
    const engine = new TemplateEngine({ templatesDir: nonExistentDir });

    const page: PageData = {
      slug: 'test',
      frontmatter: { title: '<script>alert("xss")</script>', date: '', tags: [] },
      content: 'Body',
      html: '<p>Body</p>',
    };

    const html = engine.renderPage(page);
    expect(html).not.toContain('<script>alert');
    expect(html).toContain('&lt;script&gt;alert');
  });

  it('renders index with custom layout from file', () => {
    const templatesDir = setupTemplatesDir({
      'layouts/custom-index.hbs': `<!DOCTYPE html><html><head><title>{{title}}</title></head><body><div class="wrap">{{{body}}}</div></body></html>`,
      'index.hbs': `<ul>{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>`,
    });

    const engine = new TemplateEngine({ templatesDir });

    const pages: PageData[] = [
      {
        slug: 'a',
        frontmatter: { title: 'A', date: '2024-01-01', tags: [] },
        content: '',
        html: '<p>A</p>',
      },
    ];

    const html = engine.renderIndex(pages, 'custom-index');
    expect(html).toContain('<div class="wrap">');
    expect(html).toContain('<a href="a.html">A</a>');
  });

  it('generates site using custom templates from a directory', () => {
    const contentDir = setupContentDir({
      'post.md': `---
title: Custom Template Post
date: 2024-05-01
template: fancy
layout: fancy-layout
---
# Fancy

Custom template content.`,
    });

    const templatesDir = setupTemplatesDir({
      'layouts/fancy-layout.hbs': `<!DOCTYPE html><html><head><title>{{title}}</title></head><body><section>{{{body}}}</section></body></html>`,
      'fancy.hbs': `<div class="fancy-post"><h2>{{title}}</h2><time>{{date}}</time><div class="content">{{{content}}}</div></div>`,
      'index.hbs': `<ul>{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>`,
    });

    const result = parseFiles({ contentDir, outputDir: outputDir() });
    const dist = outputDir();
    generateSite(result, dist, templatesDir);

    const postHtml = fs.readFileSync(path.join(dist, 'post.html'), 'utf-8');
    expect(postHtml).toContain('<div class="fancy-post">');
    expect(postHtml).toContain('<h2>Custom Template Post</h2>');
    expect(postHtml).toContain('<time>2024-05-01</time>');
    expect(postHtml).toContain('<section>');

    const indexHtml = fs.readFileSync(path.join(dist, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('<a href="post.html">Custom Template Post</a>');
  });
});

describe('dev server', () => {
  let server: http.Server;
  let port: number;
  let contentDir: string;
  let templatesDir: string;
  let dist: string;

  beforeEach(async () => {
    contentDir = setupContentDir({
      'post.md': `---
title: My Post
date: 2024-03-10
tags:
  - blog
---
# My Post

Content here.`,
    });
    templatesDir = setupTemplatesDir({});
    dist = outputDir();
    port = await getFreePort();
    server = undefined as unknown as http.Server;
  });

  afterEach(async () => {
    if (server) {
      let timer: NodeJS.Timeout;
      const closePromise = new Promise<void>((resolve) => {
        server.close(() => resolve());
      });
      const timeoutPromise = new Promise<void>((resolve) => {
        timer = setTimeout(resolve, 2000);
      });
      await Promise.race([closePromise, timeoutPromise]);
      clearTimeout(timer!);
      server = undefined as unknown as http.Server;
    }
  });

  it('serves HTML files from the dist directory', async () => {
    server = startDevServer({ contentDir, outputDir: dist, templatesDir, port });
    await new Promise((r) => server.on('listening', r));

    const { status, body } = await httpGet(`http://localhost:${port}/post.html`);
    expect(status).toBe(200);
    expect(body).toContain('<!DOCTYPE html>');
    expect(body).toContain('My Post');
  });

  it('injects live-reload WebSocket script into HTML responses', async () => {
    server = startDevServer({ contentDir, outputDir: dist, templatesDir, port });
    await new Promise((r) => server.on('listening', r));

    const { body } = await httpGet(`http://localhost:${port}/post.html`);
    expect(body).toContain("WebSocket('ws://' + location.host)");
    expect(body).toContain("msg.data === 'reload'");
    expect(body).toContain('location.reload()');
  });

  it('serves index.html for the root path', async () => {
    server = startDevServer({ contentDir, outputDir: dist, templatesDir, port });
    await new Promise((r) => server.on('listening', r));

    const { status, body } = await httpGet(`http://localhost:${port}/`);
    expect(status).toBe(200);
    expect(body).toContain('<h1>Blog</h1>');
    expect(body).toContain("WebSocket('ws://' + location.host)");
  });

  it('falls back to index.html for unknown paths', async () => {
    server = startDevServer({ contentDir, outputDir: dist, templatesDir, port });
    await new Promise((r) => server.on('listening', r));

    const { status, body } = await httpGet(`http://localhost:${port}/nonexistent`);
    expect(status).toBe(200);
    expect(body).toContain('<h1>Blog</h1>');
  });

  it('does not inject script into non-HTML responses', async () => {
    const cssContent = 'body { color: red; }';
    fs.mkdirSync(dist, { recursive: true });
    fs.writeFileSync(path.join(dist, 'style.css'), cssContent);

    server = startDevServer({ contentDir, outputDir: dist, templatesDir, port });
    await new Promise((r) => server.on('listening', r));

    const { body } = await httpGet(`http://localhost:${port}/style.css`);
    expect(body).toBe(cssContent);
    expect(body).not.toContain('WebSocket');
  });

  it('returns 404 when no matching file and no index.html', async () => {
    const emptyContent = path.join(tmpDir, 'empty-content');
    fs.mkdirSync(emptyContent, { recursive: true });
    const emptyDist = path.join(tmpDir, 'empty-dist');
    fs.mkdirSync(emptyDist, { recursive: true });
    const emptyTemplates = path.join(tmpDir, 'empty-templates');
    fs.mkdirSync(emptyTemplates, { recursive: true });

    server = startDevServer({
      contentDir: emptyContent,
      outputDir: emptyDist,
      templatesDir: emptyTemplates,
      port,
    });
    await new Promise((r) => server.on('listening', r));

    const indexPath = path.join(emptyDist, 'index.html');
    if (fs.existsSync(indexPath)) {
      fs.unlinkSync(indexPath);
    }

    const { status } = await httpGet(`http://localhost:${port}/nonexistent`);
    expect(status).toBe(404);
  });

  it('rebuilds on content change and notifies WebSocket clients', async () => {
    server = startDevServer({ contentDir, outputDir: dist, templatesDir, port });
    await new Promise((r) => server.on('listening', r));

    const ws = new WebSocket(`ws://localhost:${port}`);
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('WebSocket connection timeout')), 3000);
      ws.on('open', () => { clearTimeout(timeout); resolve(); });
      ws.on('error', (err) => { clearTimeout(timeout); reject(err); });
    });

    const msgPromise = new Promise<string>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('No reload message received')), 5000);
      ws.on('message', (data) => {
        clearTimeout(timeout);
        resolve(data.toString());
      });
      ws.on('error', (err) => {
        clearTimeout(timeout);
        reject(err);
      });
    });

    await new Promise((r) => setTimeout(r, 100));

    fs.writeFileSync(path.join(contentDir, 'new-post.md'), `---
title: New Post
date: 2024-08-01
---
# New Content`);

    const msg = await msgPromise;
    expect(msg).toBe('reload');

    ws.close();

    const distFile = path.join(dist, 'new-post.html');
    expect(fs.existsSync(distFile)).toBe(true);
    const html = fs.readFileSync(distFile, 'utf-8');
    expect(html).toContain('New Post');
  }, 15000);

  it('parseArgs handles --port flag', () => {
    const result = parseArgs(['serve', '--port', '8080']);
    expect(result.command).toBe('serve');
    expect(result.port).toBe(8080);
  });

  it('parseArgs uses default port 3000', () => {
    const result = parseArgs(['serve']);
    expect(result.port).toBe(3000);
  });
});
