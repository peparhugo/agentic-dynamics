import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { runCli } from '../src/cli';
import { buildSite } from '../src';

describe('static site generator', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'public');
    templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  test('renders Markdown and frontmatter into a page', async () => {
    await fs.writeFile(path.join(contentDir, 'hello.md'), `---
title: A <Great> Post
date: 2026-08-13
tags: [typescript, static sites]
---

## Welcome

This is **important**.
`);

    const pages = await buildSite({ contentDir, outputDir });
    const html = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(html).toContain('<title>A &lt;Great&gt; Post</title>');
    expect(html).toContain('<h2>Welcome</h2>');
    expect(html).toContain('<strong>important</strong>');
    expect(html).toContain('<time datetime="2026-08-13">2026-08-13</time>');
    expect(html).toContain('<li>typescript</li>');
  });

  test('generates an index sorted by date and links nested pages', async () => {
    await fs.mkdir(path.join(contentDir, 'notes'));
    await fs.writeFile(path.join(contentDir, 'older.md'), '---\ntitle: Older\ndate: 2025-01-01\n---\nOld');
    await fs.writeFile(path.join(contentDir, 'notes', 'new post.md'), '---\ntitle: Newer\ndate: 2026-01-01\n---\nNew');

    await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');
    const nested = await fs.readFile(path.join(outputDir, 'notes', 'new post.html'), 'utf8');

    expect(index).toContain('href="notes/new%20post.html"');
    expect(index.indexOf('Newer')).toBeLessThan(index.indexOf('Older'));
    expect(nested).toContain('<p>New</p>');
  });

  test('uses the filename as a title when frontmatter has no title', async () => {
    await fs.writeFile(path.join(contentDir, 'about-us.md'), 'About us');

    await buildSite({ contentDir, outputDir });
    const html = await fs.readFile(path.join(outputDir, 'about-us.html'), 'utf8');

    expect(html).toContain('<h1>About Us</h1>');
  });

  test('generates an empty index when there are no pages', async () => {
    const pages = await buildSite({ contentDir, outputDir });
    const index = await fs.readFile(path.join(outputDir, 'index.html'), 'utf8');

    expect(pages).toEqual([]);
    expect(index).toContain('<h1>Pages</h1>');
  });

  test('reports a missing content directory', async () => {
    await expect(buildSite({
      contentDir: path.join(root, 'missing'),
      outputDir
    })).rejects.toThrow('Content directory does not exist');
  });

  test('uses a default Handlebars template and default layout', async () => {
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'),
      '<article data-kind="{{kind}}"><h1>{{title}}</h1>{{{content}}}</article>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'),
      '<!doctype html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>');
    await fs.writeFile(path.join(contentDir, 'welcome.md'),
      '---\ntitle: Welcome\nkind: guide\n---\nText with **markup**.');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'welcome.html'), 'utf8');

    expect(html).toContain('<title>Welcome</title>');
    expect(html).toContain('<article data-kind="guide">');
    expect(html).toContain('<p>Text with <strong>markup</strong>.</p>');
  });

  test('selects page templates and layouts from frontmatter', async () => {
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<p>default</p>');
    await fs.writeFile(path.join(templatesDir, 'post.hbs'), '<article>{{title}}: {{{content}}}</article>');
    await fs.writeFile(path.join(templatesDir, 'layouts', 'site.hbs'), '<main class="site">{{{body}}}</main>');
    await fs.writeFile(path.join(contentDir, 'post.md'),
      '---\ntitle: Selected\ntemplate: post.hbs\nlayout: site.hbs\n---\nBody');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'post.html'), 'utf8');

    expect(html).toBe('<main class="site"><article>Selected: <p>Body</p>\n</article></main>');
  });

  test('supports a layout without requiring a page template', async () => {
    await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'layouts', 'default.hbs'),
      '<!doctype html><body class="layout">{{{body}}}</body>');
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntitle: Layout only\n---\nBody');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'page.html'), 'utf8');

    expect(html).toContain('<body class="layout"><main>');
    expect(html).not.toContain('<body class="layout"><!doctype html>');
  });

  test('registers reusable Handlebars partials', async () => {
    await fs.mkdir(path.join(templatesDir, 'partials'), { recursive: true });
    await fs.writeFile(path.join(templatesDir, 'default.hbs'),
      '{{> header}}<main>{{{content}}}</main>{{> footer}}');
    await fs.writeFile(path.join(templatesDir, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(templatesDir, 'partials', 'footer.hbs'), '<footer>End</footer>');
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntitle: Partials\n---\nPage');

    await buildSite({ contentDir, outputDir, templatesDir });
    const html = await fs.readFile(path.join(outputDir, 'page.html'), 'utf8');

    expect(html).toBe('<header>Partials</header><main><p>Page</p>\n</main><footer>End</footer>');
  });

  test('fails clearly when a selected template does not exist', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\ntemplate: missing\n---\nPage');

    await expect(buildSite({ contentDir, outputDir, templatesDir }))
      .rejects.toThrow('Template not found: missing.hbs');
  });

  test('fails clearly when a selected layout does not exist', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '---\nlayout: missing\n---\nPage');

    await expect(buildSite({ contentDir, outputDir, templatesDir }))
      .rejects.toThrow('Layout not found: missing.hbs');
  });

  test('runs build with custom CLI directories', async () => {
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page');
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    const exitCode = await runCli(
      ['build', '--content', contentDir, '--output', outputDir],
      { stdout, stderr }
    );

    expect(exitCode).toBe(0);
    expect(stdout.write).toHaveBeenCalledWith('Generated 1 page.\n');
    expect(stderr.write).not.toHaveBeenCalled();
    await expect(fs.stat(path.join(outputDir, 'page.html'))).resolves.toBeDefined();
  });

  test('runs build with a custom CLI templates directory', async () => {
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<section>{{title}}</section>');
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page');
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    const exitCode = await runCli(
      ['build', '--content', contentDir, '--output', outputDir, '--templates', templatesDir],
      { stdout, stderr }
    );

    expect(exitCode).toBe(0);
    await expect(fs.readFile(path.join(outputDir, 'page.html'), 'utf8'))
      .resolves.toBe('<section>Page</section>');
  });

  test('rejects invalid CLI input', async () => {
    const stdout = { write: jest.fn(() => true) };
    const stderr = { write: jest.fn(() => true) };

    await expect(runCli([], { stdout, stderr })).resolves.toBe(1);
    await expect(runCli(['build', '--other'], { stdout, stderr })).resolves.toBe(1);
    expect(stderr.write).toHaveBeenCalledTimes(2);
  });
});
