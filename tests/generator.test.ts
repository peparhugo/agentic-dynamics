import { mkdir, mkdtemp, readFile, stat, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite, buildSiteWithStats } from '../src/generator.js';

describe('buildSite', () => {
  it('renders markdown pages and an index from frontmatter', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'public');
    await mkdir(content);
    await writeFile(path.join(content, 'hello.md'), `---
title: Hello <World>
date: 2025-01-02
  - news
  - updates
---
# Welcome

This is **markdown**.`);
    await writeFile(path.join(content, 'about.md'), '# About');

    const pages = await buildSite({ contentDir: content, outputDir: output });

    expect(pages.map((page) => page.slug)).toEqual(['hello', 'about']);
    const hello = await readFile(path.join(output, 'hello.html'), 'utf8');
    expect(hello).toContain('<title>Hello &lt;World&gt;</title>');
    expect(hello).toContain('<h1>Welcome</h1>');
    expect(hello).toContain('<strong>markdown</strong>');
    expect(hello).toContain('<li>news</li>');
    const index = await readFile(path.join(output, 'index.html'), 'utf8');
    expect(index).toContain('<a href="hello.html">Hello &lt;World&gt;</a>');
    expect(index).toContain('<a href="about.html">about</a>');
  });

  it('renders pages with default and selected Handlebars templates, layouts, and partials', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const layouts = path.join(templates, 'layouts');
    const partials = path.join(templates, 'partials');
    const output = path.join(root, 'public');
    await Promise.all([mkdir(content), mkdir(layouts, { recursive: true }), mkdir(partials, { recursive: true })]);
    await writeFile(path.join(content, 'hello.md'), `---
title: Hello
---
# Welcome

This is **markdown**.`);
    await writeFile(path.join(content, 'about.md'), `---
title: About
template: feature
layout: article
description: A template value
---
About us.`);
    await writeFile(path.join(templates, 'default.hbs'), '<article><h1>{{title}}</h1>{{{html}}}</article>');
    await writeFile(path.join(templates, 'feature.hbs'), '<section class="feature">{{> header}}<p>{{title}}</p><p>{{description}}</p>{{{html}}}</section>');
    await writeFile(path.join(layouts, 'default.hbs'), '<!doctype html><body>{{> nav}}<main>{{{body}}}</main></body>');
    await writeFile(path.join(layouts, 'article.hbs'), '<!doctype html><body><aside>{{> nav}}</aside>{{{body}}}{{> footer}}</body>');
    await writeFile(path.join(partials, 'header.hbs'), '<header>Featured</header>');
    await writeFile(path.join(partials, 'nav.hbs'), '<nav>Navigation</nav>');
    await writeFile(path.join(partials, 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite({ contentDir: content, templatesDir: templates, outputDir: output });

    const hello = await readFile(path.join(output, 'hello.html'), 'utf8');
    expect(hello).toContain('<nav>Navigation</nav>');
    expect(hello).toContain('<article><h1>Hello</h1><h1>Welcome</h1>');
    expect(hello).toContain('<strong>markdown</strong>');
    const about = await readFile(path.join(output, 'about.html'), 'utf8');
    expect(about).toContain('<section class="feature"><header>Featured</header><p>About</p><p>A template value</p><p>About us.</p>');
    expect(about).toContain('<footer>Footer</footer>');
  });

  it('skips unchanged pages and invalidates cached pages when source or templates change', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'ssg-incremental-'));
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    const output = path.join(root, 'public');
    await Promise.all([mkdir(content), mkdir(path.join(templates, 'layouts'), { recursive: true })]);
    await writeFile(path.join(content, 'one.md'), '# One');
    await writeFile(path.join(content, 'two.md'), '# Two');
    await writeFile(path.join(templates, 'default.hbs'), '<article>{{{html}}}</article>');
    await writeFile(path.join(templates, 'layouts', 'default.hbs'), '<body>{{{body}}}</body>');

    const first = await buildSiteWithStats({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true });
    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(stat(path.join(root, '.ssg-cache.json'))).resolves.toBeDefined();

    const unchanged = await buildSiteWithStats({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true });
    expect(unchanged.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });

    await writeFile(path.join(content, 'one.md'), '# Updated one');
    const sourceChanged = await buildSiteWithStats({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true });
    expect(sourceChanged.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    await expect(readFile(path.join(output, 'one.html'), 'utf8')).resolves.toContain('Updated one');

    await writeFile(path.join(templates, 'default.hbs'), '<section>{{{html}}}</section>');
    const templateChanged = await buildSiteWithStats({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true });
    expect(templateChanged.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    await expect(readFile(path.join(output, 'two.html'), 'utf8')).resolves.toContain('<section><h1>Two</h1>');

    const clean = await buildSiteWithStats({ contentDir: content, templatesDir: templates, outputDir: output, incremental: true, clean: true });
    expect(clean.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
  });
});
