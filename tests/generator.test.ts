import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, type Plugin } from '../src/generator.js';
import { parseArguments } from '../src/cli.js';

describe('static site generator', () => {
  let workspace: string;

  beforeEach(async () => {
    workspace = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    await fs.mkdir(path.join(workspace, 'content'));
  });

  afterEach(async () => {
    await fs.rm(workspace, { recursive: true, force: true });
  });

  it('renders markdown pages and an index with frontmatter', async () => {
    await fs.writeFile(path.join(workspace, 'content', 'hello.md'), '---\ntitle: Hello World\ndate: 2026-08-13\ntags:\n  - news\n  - update\n---\n\n# Welcome\n\nThis is **important**.');
    const pages = await buildSite({ contentDir: path.join(workspace, 'content'), outputDir: path.join(workspace, 'output') });

    expect(pages).toEqual([expect.objectContaining({ title: 'Hello World', date: '2026-08-13', tags: ['news', 'update'], slug: 'hello' })]);
    await expect(fs.readFile(path.join(workspace, 'output', 'hello.html'), 'utf8')).resolves.toContain('<strong>important</strong>');
    await expect(fs.readFile(path.join(workspace, 'output', 'index.html'), 'utf8')).resolves.toContain('Hello World');
  });

  it('parses build CLI options and rejects invalid commands', () => {
    expect(parseArguments(['build', '--content', 'posts', '--output', 'public', '--templates', 'theme'])).toEqual({ contentDir: 'posts', outputDir: 'public', templatesDir: 'theme' });
    expect(parseArguments(['build', '--incremental', '--clean'])).toEqual({ incremental: true, clean: true });
    expect(parseArguments(['serve', '--content', 'posts', '--templates', 'theme', '--port', '4000'])).toEqual({ contentDir: 'posts', templatesDir: 'theme', port: 4000 });
    expect(() => parseArguments(['invalid'])).toThrow('Usage:');
  });

  it('renders a page template within the default layout and includes partials', async () => {
    await fs.mkdir(path.join(workspace, 'templates', 'layouts'), { recursive: true });
    await fs.mkdir(path.join(workspace, 'templates', 'partials'));
    await fs.writeFile(path.join(workspace, 'templates', 'default.hbs'), '<main><h1>{{title}}</h1>{{{content}}}</main>');
    await fs.writeFile(path.join(workspace, 'templates', 'layouts', 'default.hbs'), '<!doctype html><body>{{> header}}{{{body}}}{{> footer}}</body>');
    await fs.writeFile(path.join(workspace, 'templates', 'partials', 'header.hbs'), '<header>Site</header>');
    await fs.writeFile(path.join(workspace, 'templates', 'partials', 'footer.hbs'), '<footer>{{slug}}</footer>');
    await fs.writeFile(path.join(workspace, 'content', 'hello.md'), '---\ntitle: Template Page\n---\n\nHello **there**');

    await buildSite({ contentDir: path.join(workspace, 'content'), outputDir: path.join(workspace, 'output'), templatesDir: path.join(workspace, 'templates') });

    await expect(fs.readFile(path.join(workspace, 'output', 'hello.html'), 'utf8')).resolves.toBe('<!doctype html><body><header>Site</header><main><h1>Template Page</h1><p>Hello <strong>there</strong></p>\n</main><footer>hello</footer></body>');
  });

  it('uses the frontmatter template and its matching layout', async () => {
    await fs.mkdir(path.join(workspace, 'templates', 'layouts'), { recursive: true });
    await fs.writeFile(path.join(workspace, 'templates', 'article.hbs'), '<article data-kind="{{kind}}">{{{content}}}</article>');
    await fs.writeFile(path.join(workspace, 'templates', 'layouts', 'article.hbs'), '<section>{{{body}}}</section>');
    await fs.writeFile(path.join(workspace, 'content', 'post.md'), '---\ntitle: Post\ntemplate: article\nkind: note\n---\n\nBody');

    await buildSite({ contentDir: path.join(workspace, 'content'), outputDir: path.join(workspace, 'output'), templatesDir: path.join(workspace, 'templates') });

    await expect(fs.readFile(path.join(workspace, 'output', 'post.html'), 'utf8')).resolves.toBe('<section><article data-kind="note"><p>Body</p>\n</article></section>');
  });

  it('runs plugin lifecycle hooks in order', async () => {
    await fs.writeFile(path.join(workspace, 'content', 'page.md'), '# Page');
    const events: string[] = [];
    const plugin: Plugin = {
      onStart: () => events.push('start'),
      beforeBuild: (context) => events.push(`before:${context.pages[0].slug}`),
      onFile: (page) => events.push(`file:${page.slug}`),
      afterBuild: () => events.push('after'),
      onEnd: () => events.push('end'),
    };

    await buildSite({ contentDir: path.join(workspace, 'content'), outputDir: path.join(workspace, 'output'), plugins: [plugin] });

    expect(events).toEqual(['start', 'before:page', 'file:page', 'after', 'end']);
  });

  it('skips unchanged pages during an incremental build', async () => {
    await fs.writeFile(path.join(workspace, 'content', 'first.md'), '---\ntitle: First\n---\n\nFirst');
    await fs.writeFile(path.join(workspace, 'content', 'second.md'), '---\ntitle: Second\n---\n\nSecond');
    const outputDir = path.join(workspace, 'output');
    const rendered: string[] = [];
    const plugin: Plugin = { onFile: (page) => rendered.push(page.slug) };

    await buildSite({ contentDir: path.join(workspace, 'content'), outputDir, plugins: [plugin] });
    rendered.length = 0;
    let stats;
    await buildSite({ contentDir: path.join(workspace, 'content'), outputDir, plugins: [plugin], incremental: true, onBuildComplete: (result) => { stats = result; } });

    expect(rendered).toEqual([]);
    expect(stats).toEqual(expect.objectContaining({ pagesBuilt: 0, pagesSkipped: 2 }));
    await expect(fs.readFile(path.join(outputDir, 'first.html'), 'utf8')).resolves.toContain('First');
    await expect(fs.readFile(path.join(outputDir, 'index.html'), 'utf8')).resolves.toContain('Second');
  });

  it('rebuilds changed pages and all pages when templates change', async () => {
    await fs.mkdir(path.join(workspace, 'templates'));
    await fs.writeFile(path.join(workspace, 'templates', 'default.hbs'), '<p>{{title}}</p>');
    await fs.writeFile(path.join(workspace, 'content', 'first.md'), '---\ntitle: First\n---\n\nFirst');
    await fs.writeFile(path.join(workspace, 'content', 'second.md'), '---\ntitle: Second\n---\n\nSecond');
    const outputDir = path.join(workspace, 'output');
    const templatesDir = path.join(workspace, 'templates');
    const rendered: string[] = [];
    const plugin: Plugin = { onFile: (page) => rendered.push(page.slug) };

    await buildSite({ contentDir: path.join(workspace, 'content'), outputDir, templatesDir, plugins: [plugin] });
    rendered.length = 0;
    await fs.writeFile(path.join(workspace, 'content', 'first.md'), '---\ntitle: Updated\n---\n\nFirst');
    await buildSite({ contentDir: path.join(workspace, 'content'), outputDir, templatesDir, plugins: [plugin], incremental: true });
    expect(rendered).toEqual(['first']);
    await expect(fs.readFile(path.join(outputDir, 'first.html'), 'utf8')).resolves.toContain('Updated');

    rendered.length = 0;
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article>{{title}}</article>');
    await buildSite({ contentDir: path.join(workspace, 'content'), outputDir, templatesDir, plugins: [plugin], incremental: true });
    expect(rendered).toEqual(['first', 'second']);
    await expect(fs.readFile(path.join(outputDir, 'second.html'), 'utf8')).resolves.toBe('<article>Second</article>');
  });
});
