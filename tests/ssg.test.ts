import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src';

describe('buildSite', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  test('converts Markdown and frontmatter into a page', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello World
date: 2024-06-01
tags: [news, launch]
---
## Welcome

This is **important**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const html = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');

    expect(pages).toEqual([{
      title: 'Hello World',
      date: '2024-06-01',
      tags: ['news', 'launch'],
      outputPath: 'hello.html'
    }]);
    expect(html).toContain('<h1>Hello World</h1>');
    expect(html).toContain('<h2>Welcome</h2>');
    expect(html).toContain('<strong>important</strong>');
    expect(html).toContain('<li>news</li>');
  });

  test('generates an index ordered by newest dated page first', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'old.md'), '---\ntitle: Old\ndate: 2020-01-01\n---\nOld');
    await fs.writeFile(path.join(contentDir, 'new.md'), '---\ntitle: New\ndate: 2025-01-01\n---\nNew');

    await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(index).toContain('<a href="new.html">New</a>');
    expect(index.indexOf('New</a>')).toBeLessThan(index.indexOf('Old</a>'));
  });

  test('uses the filename as a title and supports comma-separated tags', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'about.md'), '---\ntags: company, team\n---\nAbout us');

    const [page] = await buildSite({ contentDir, outputDir });

    expect(page).toMatchObject({ title: 'about', tags: ['company', 'team'] });
  });

  test('preserves nested paths and ignores non-Markdown files', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(path.join(contentDir, 'posts'), { recursive: true });
    await fs.writeFile(path.join(contentDir, 'posts', 'entry.md'), '# Entry');
    await fs.writeFile(path.join(contentDir, 'notes.txt'), 'Not a page');

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(1);
    await expect(fs.readFile(path.join(outputDir, 'posts', 'entry.html'), 'utf8')).resolves.toContain('<h1>Entry</h1>');
    await expect(fs.stat(path.join(outputDir, 'notes.html'))).rejects.toThrow();
  });

  test('escapes frontmatter rendered into HTML', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'safe.md'), '---\ntitle: "<script>alert(1)</script>"\n---\nSafe');

    await buildSite({ contentDir, outputDir });
    const html = await fs.readFile(path.join(outputDir, 'safe.html'), 'utf8');

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).not.toContain('<script>');
  });

  test('renders a frontmatter-selected Handlebars template and layout', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'post.md'), `---
title: Template Post
author: Sam
template: post
layout: main
---
This is **rendered**.
`);
    await fs.writeFile(
      path.join(templatesDir, 'post.hbs'),
      '<article><h1>{{title}}</h1><p>{{author}}</p>{{{content}}}</article>'
    );
    await fs.writeFile(
      path.join(templatesDir, 'layouts', 'main.hbs'),
      '<!doctype html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'post.html'), 'utf8');

    expect(html).toContain('<title>Template Post</title>');
    expect(html).toContain('<article><h1>Template Post</h1><p>Sam</p>');
    expect(html).toContain('<p>This is <strong>rendered</strong>.</p>');
    expect(html).not.toContain('&lt;article&gt;');
  });

  test('uses default templates and renders partials', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templatesDir, 'partials'), { recursive: true });
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'about.md'), '---\ntitle: About\n---\nOur story');
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '{{> nav}}<main>{{{body}}}</main>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<html><body>{{{body}}}{{> footer}}</body></html>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'nav.hbs'), '<nav>{{title}}</nav>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>Site footer</footer>');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'about.html'), 'utf8');

    expect(html).toBe('<html><body><nav>About</nav><main><p>Our story</p>\n</main><footer>Site footer</footer></body></html>');
  });

  test('escapes template values unless triple braces are used', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(contentDir, 'safe.md'), '---\ntitle: "<b>Safe</b>"\n---\nText');
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<h1>{{title}}</h1>{{{content}}}');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'safe.html'), 'utf8');

    expect(html).toContain('<h1>&lt;b&gt;Safe&lt;/b&gt;</h1>');
    expect(html).toContain('<p>Text</p>');
  });

  test('reports a missing selected template', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'bad.md'), '---\ntemplate: missing\n---\nText');

    await expect(buildSite({ contentDir, outputDir, templatesDir })).rejects.toThrow('Template not found');
  });
});
