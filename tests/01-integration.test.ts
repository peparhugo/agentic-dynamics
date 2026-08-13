import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/index';

describe('site generation', () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('builds pages and an index with metadata and embedded HTML', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello World
date: 2026-08-13
tags:
  - news
  - typescript
---
# Welcome

<aside class="note">Raw HTML</aside>
`);

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(page).toContain('<h1>Hello World</h1>');
    expect(page).toContain('<aside class="note">Raw HTML</aside>');
    expect(page).not.toContain('&lt;aside');
    expect(page).toContain('August 13, 2026');
    expect(page).toContain('news, typescript');
    expect(index).toContain('<a href="hello.html">Hello World</a>');
  });

  it('keeps the generated index separate from an index Markdown page', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'index.md'), '---\ntitle: Home article\n---\nHome');

    await buildSite({ contentDir, outputDir });

    await expect(fs.readFile(path.join(outputDir, 'index-page.html'), 'utf8')).resolves.toContain('Home article');
    await expect(fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).resolves.toContain('index-page.html');
  });

  it('renders default and selected templates inside layouts with partials', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templatesDir, 'partials'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article>{{> header}} {{{content}}}</article>');
    await fs.writeFile(path.join(templatesDir, 'feature.hbs'), '<section class="feature">{{subtitle}} {{{content}}}</section>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<html><body>{{{body}}}{{> footer}}</body></html>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'wide.hbs'), '<main class="wide">{{{body}}}</main>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>Footer</footer>');
    await fs.writeFile(path.join(contentDir, 'default.md'), '---\ntitle: Default Page\n---\n# Default body');
    await fs.writeFile(path.join(contentDir, 'custom.md'), `---
title: Custom Page
subtitle: A custom subtitle
template: feature
layout: wide
---
**Custom body**`);

    await buildSite({ contentDir, outputDir, templatesDir });
    const defaultPage = await fs.readFile(path.join(outputDir, 'default.html'), 'utf8');
    const customPage = await fs.readFile(path.join(outputDir, 'custom.html'), 'utf8');

    expect(defaultPage).toBe('<html><body><article><header>Default Page</header> <h1>Default body</h1>\n</article><footer>Footer</footer></body></html>');
    expect(customPage).toBe('<main class="wide"><section class="feature">A custom subtitle <p><strong>Custom body</strong></p>\n</section></main>');
  });

  it('can disable layouts for an individual page', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article>{{{content}}}</article>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');
    await fs.writeFile(path.join(contentDir, 'plain.md'), '---\nlayout: false\n---\nPlain');

    await buildSite({ contentDir, outputDir, templatesDir });

    await expect(fs.readFile(path.join(outputDir, 'plain.html'), 'utf8')).resolves.toBe('<article><p>Plain</p>\n</article>');
  });

  it('reports an explicitly selected missing template', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'site');
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(contentDir, 'broken.md'), '---\ntemplate: missing\n---\nBody');

    await expect(buildSite({ contentDir, outputDir, templatesDir })).rejects.toThrow('Template not found: missing');
  });
});
