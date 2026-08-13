import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'public');
    await fs.mkdir(contentDir);
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  it('renders Markdown and frontmatter into page and index files', async () => {
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Hello World
date: 2024-05-01
tags:
  - news
  - typescript
---
# Welcome

This is **generated**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toMatchObject([{ title: 'Hello World', date: '2024-05-01', tags: ['news', 'typescript'] }]);
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>generated</strong>');
    expect(page).toContain('news, typescript');
    expect(index).toContain('<a href="hello.html">Hello World</a>');
  });

  it('preserves nested paths, ignores non-Markdown files, and uses filename titles', async () => {
    await fs.mkdir(path.join(contentDir, 'guides'));
    await fs.writeFile(path.join(contentDir, 'guides', 'start.md'), 'Start here.');
    await fs.writeFile(path.join(contentDir, 'ignored.txt'), 'Not content.');

    const pages = await buildSite({ contentDir, outputDir });

    expect(pages).toHaveLength(1);
    expect(pages[0]).toMatchObject({ title: 'start', url: 'guides/start.html' });
    await expect(fs.readFile(path.join(outputDir, 'guides', 'start.html'), 'utf8')).resolves.toContain('<p>Start here.</p>');
    await expect(fs.access(path.join(outputDir, 'ignored.html'))).rejects.toThrow();
  });

  it('creates an index when the content directory is empty', async () => {
    await buildSite({ contentDir, outputDir });
    await expect(fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).resolves.toContain('No pages found.');
  });

  it('uses default page and layout templates with partials', async () => {
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templatesDir, 'partials'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article><h1>{{title}}</h1>{{{content}}}</article>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), '<html>{{> header}}<main>{{{body}}}</main>{{> footer}}</html>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>{{tags}}</footer>');
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: Templates & Layouts
tags: [one, two]
---
Hello **world**.
`);

    await buildSite({ contentDir, outputDir, templatesDir });
    const page = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');

    expect(page).toBe('<html><header>Templates &amp; Layouts</header><main><article><h1>Templates &amp; Layouts</h1><p>Hello <strong>world</strong>.</p>\n</article></main><footer>one,two</footer></html>');
  });

  it('selects page and layout templates from frontmatter', async () => {
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), 'wrong');
    await fs.writeFile(path.join(templatesDir, 'feature.hbs'), '<section data-kind="{{kind}}">{{{body}}}</section>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'), 'wrong {{{body}}}');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'bare.hbs'), '<!doctype html><title>{{title}}</title>{{{body}}}');
    await fs.writeFile(path.join(contentDir, 'chosen.md'), `---
title: Chosen
kind: guide
template: feature.hbs
layout: bare
---
# Content
`);

    await buildSite({ contentDir, outputDir, templatesDir });

    await expect(fs.readFile(path.join(outputDir, 'chosen.html'), 'utf8')).resolves.toBe(
      '<!doctype html><title>Chosen</title><section data-kind="guide"><h1>Content</h1>\n</section>'
    );
  });

  it('reports a missing explicitly requested template', async () => {
    const templatesDir = path.join(root, 'templates');
    await fs.writeFile(path.join(contentDir, 'broken.md'), '---\ntemplate: missing\n---\nContent');

    await expect(buildSite({ contentDir, outputDir, templatesDir })).rejects.toThrow('Template not found:');
  });
});
