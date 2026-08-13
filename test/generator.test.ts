import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite, type BuildStats, readPages } from '../src/generator';

describe('static site generator', () => {
  let directory: string;
  let content: string;
  let output: string;
  let templates: string;

  beforeEach(async () => {
    directory = await mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    content = path.join(directory, 'content');
    output = path.join(directory, 'site');
    templates = path.join(directory, 'templates');
    await mkdir(content);
  });

  afterEach(async () => rm(directory, { recursive: true, force: true }));

  it('parses frontmatter and Markdown', async () => {
    await writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello World\ndate: 2025-01-02\ntags:\n  - news\n---\n# Welcome\n\n**Text**');

    const pages = await readPages(content);

    expect(pages).toEqual([expect.objectContaining({ slug: 'hello', title: 'Hello World', date: '2025-01-02', tags: ['news'], html: expect.stringContaining('<h1>Welcome</h1>') })]);
  });

  it('writes a page and an index to the requested output directory', async () => {
    await writeFile(path.join(content, 'first.md'), '---\ntitle: First Post\n---\nA post.');
    await writeFile(path.join(content, 'second.md'), '# Second');

    await buildSite({ contentDir: content, outputDir: output });

    await expect(readFile(path.join(output, 'first.html'), 'utf8')).resolves.toContain('<title>First Post</title>');
    await expect(readFile(path.join(output, 'second.html'), 'utf8')).resolves.toContain('<h1>Second</h1>');
    await expect(readFile(path.join(output, 'index.html'), 'utf8')).resolves.toContain('<a href="first.html">First Post</a>');
  });

  it('renders selected page templates inside layouts with partials', async () => {
    await mkdir(path.join(templates, 'layouts'), { recursive: true });
    await mkdir(path.join(templates, 'partials'));
    await writeFile(path.join(templates, 'post.hbs'), '<article><h1>{{title}}</h1>{{{body}}}</article>');
    await writeFile(path.join(templates, 'layouts', 'site.hbs'), '<!doctype html>{{> header}}<main>{{{body}}}</main>{{> footer}}');
    await writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{siteName}}</header>');
    await writeFile(path.join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');
    await writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello\ntemplate: post\nlayout: site\nsiteName: Example Site\n---\nWelcome');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    await expect(readFile(path.join(output, 'hello.html'), 'utf8')).resolves.toBe('<!doctype html><header>Example Site</header><main><article><h1>Hello</h1><p>Welcome</p>\n</article></main><footer>Footer</footer>');
  });

  it('uses default page and layout templates when no frontmatter selection is given', async () => {
    await mkdir(path.join(templates, 'layouts'), { recursive: true });
    await writeFile(path.join(templates, 'default.hbs'), '<section>{{title}}: {{{body}}}</section>');
    await writeFile(path.join(templates, 'layouts', 'default.hbs'), '<html><body>{{{body}}}</body></html>');
    await writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello\n---\nWelcome');

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    await expect(readFile(path.join(output, 'hello.html'), 'utf8')).resolves.toBe('<html><body><section>Hello: <p>Welcome</p>\n</section></body></html>');
  });

  it('only rebuilds changed pages during an incremental build and invalidates templates', async () => {
    await mkdir(path.join(templates, 'layouts'), { recursive: true });
    await writeFile(path.join(templates, 'default.hbs'), '<article>{{title}} {{{body}}}</article>');
    await writeFile(path.join(content, 'first.md'), '---\ntitle: First\n---\nOne');
    await writeFile(path.join(content, 'second.md'), '---\ntitle: Second\n---\nTwo');
    const firstStats: BuildStats[] = [];
    const secondStats: BuildStats[] = [];
    const changedStats: BuildStats[] = [];
    const templateStats: BuildStats[] = [];
    const cleanStats: BuildStats[] = [];

    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, onBuildStats: (stats) => firstStats.push(stats) });
    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, onBuildStats: (stats) => secondStats.push(stats) });
    await writeFile(path.join(content, 'first.md'), '---\ntitle: First Updated\n---\nOne');
    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, onBuildStats: (stats) => changedStats.push(stats) });
    await writeFile(path.join(templates, 'default.hbs'), '<main>{{title}} {{{body}}}</main>');
    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, onBuildStats: (stats) => templateStats.push(stats) });
    await buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, clean: true, onBuildStats: (stats) => cleanStats.push(stats) });

    expect(firstStats).toEqual([{ pagesBuilt: 2, pagesSkipped: 0, timeSaved: 0 }]);
    expect(secondStats).toEqual([{ pagesBuilt: 0, pagesSkipped: 2, timeSaved: 2 }]);
    expect(changedStats).toEqual([{ pagesBuilt: 1, pagesSkipped: 1, timeSaved: 1 }]);
    expect(templateStats).toEqual([{ pagesBuilt: 2, pagesSkipped: 0, timeSaved: 0 }]);
    expect(cleanStats).toEqual([{ pagesBuilt: 2, pagesSkipped: 0, timeSaved: 0 }]);
    await expect(readFile(path.join(output, 'first.html'), 'utf8')).resolves.toContain('First Updated');
    await expect(readFile(path.join(output, 'second.html'), 'utf8')).resolves.toContain('<main>Second');
    await expect(readFile(path.join(output, '.ssg-cache.json'), 'utf8')).resolves.toContain('first');
  });
});
