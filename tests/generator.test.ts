import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite, buildSiteWithStats, parseYamlFrontmatter } from '../src/generator';
import { Plugin } from '../src/plugin';

describe('static site generator', () => {
  let directory: string;

  beforeEach(async () => { directory = await mkdtemp(join(tmpdir(), 'ssg-')); });
  afterEach(async () => { await rm(directory, { recursive: true, force: true }); });

  it('extracts a simple YAML frontmatter block', () => {
    expect(parseYamlFrontmatter('---\ntitle: Hello\ntags: [news, typescript]\n---\n# Body')).toEqual({ data: { title: 'Hello', tags: ['news', 'typescript'] }, content: '# Body' });
  });

  it('builds page files and an index from Markdown content', async () => {
    const content = join(directory, 'content');
    const output = join(directory, 'public');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'welcome.md'), '---\ntitle: Welcome\ndate: 2026-08-15\ntags: [news, updates]\n---\n# Hello\n\nThis is **Markdown**.');
    await writeFile(join(content, 'guides', 'start.md'), '---\ntitle: Getting Started\n---\nA guide.');

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await readFile(join(output, 'welcome.html'), 'utf8');
    const index = await readFile(join(output, 'index.html'), 'utf8');

    expect(pages).toHaveLength(2);
    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('<strong>Markdown</strong>');
    expect(page).toContain('Tags: news, updates');
    expect(await readFile(join(output, 'guides', 'start.html'), 'utf8')).toContain('<h1>Getting Started</h1>');
    expect(index).toContain('href="welcome.html"');
    expect(index).toContain('href="guides/start.html"');
  });

  it('renders a selected Handlebars template inside its layout and partials', async () => {
    const content = join(directory, 'content');
    const output = join(directory, 'public');
    const templates = join(directory, 'templates');
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(join(templates, 'partials'), { recursive: true });
    await writeFile(join(content, 'post.md'), '---\ntitle: Fish & Chips\ntemplate: post\nlayout: site\n---\nBody');
    await writeFile(join(templates, 'post.hbs'), '<main>{{title}} {{{html}}}</main>');
    await writeFile(join(templates, 'layouts', 'site.hbs'), '<!doctype html><body>{{> header}}{{{body}}}{{> footer}}</body>');
    await writeFile(join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await writeFile(join(templates, 'partials', 'footer.hbs'), '<footer>Copyright</footer>');

    await buildSite({ contentDir: content, outputDir: output, templateDir: templates });

    const page = await readFile(join(output, 'post.html'), 'utf8');
    expect(page).toBe('<!doctype html><body><header>Fish &amp; Chips</header><main>Fish &amp; Chips <p>Body</p>\n</main><footer>Copyright</footer></body>');
  });

  it('uses the default template and layout when a page does not specify them', async () => {
    const content = join(directory, 'content');
    const output = join(directory, 'public');
    const templates = join(directory, 'templates');
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await writeFile(join(content, 'page.md'), '---\ntitle: Defaulted\n---\nContent');
    await writeFile(join(templates, 'default.hbs'), '<main>{{title}} {{{body}}}</main>');
    await writeFile(join(templates, 'layouts', 'default.hbs'), '<shell>{{{body}}}</shell>');

    await buildSite({ contentDir: content, outputDir: output, templateDir: templates });

    expect(await readFile(join(output, 'page.html'), 'utf8')).toContain('<shell><main>Defaulted <article>');
  });

  it('runs plugin hooks in order around every page', async () => {
    const content = join(directory, 'content');
    const output = join(directory, 'public');
    const calls: string[] = [];
    const plugin: Plugin = {
      onStart: () => calls.push('start'),
      beforeBuild: () => calls.push('before'),
      onFile: (page) => { calls.push(`file:${page.title}`); page.title = 'Changed'; },
      afterBuild: () => calls.push('after'),
      onEnd: () => calls.push('end'),
    };
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'page.md'), '---\ntitle: Original\n---\nBody');

    await buildSite({ contentDir: content, outputDir: output, plugins: [plugin] });

    expect(calls).toEqual(['start', 'before', 'file:Original', 'after', 'end']);
    expect(await readFile(join(output, 'page.html'), 'utf8')).toContain('<h1>Changed</h1>');
  });

  it('loads plugins from a TypeScript config file', async () => {
    const content = join(directory, 'content');
    const output = join(directory, 'public');
    const config = join(directory, 'ssg.config.ts');
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'page.md'), '---\ntitle: Original\n---\nBody');
    await writeFile(config, 'export default { plugins: [{ onFile(page: { title: string }) { page.title = "Configured"; } }] };');

    await buildSite({ contentDir: content, outputDir: output, configFile: config });

    expect(await readFile(join(output, 'page.html'), 'utf8')).toContain('<h1>Configured</h1>');
  });

  it('incrementally reuses unchanged rendered pages and invalidates source or template changes', async () => {
    const content = join(directory, 'content');
    const output = join(directory, 'public');
    const templates = join(directory, 'templates');
    const rendered: string[] = [];
    const plugin: Plugin = { onFile: (page) => { rendered.push(page.sourcePath); page.title = `${page.title}!`; } };
    await mkdir(content, { recursive: true });
    await mkdir(templates, { recursive: true });
    await writeFile(join(content, 'one.md'), '---\ntitle: One\n---\nFirst');
    await writeFile(join(content, 'two.md'), '---\ntitle: Two\n---\nSecond');
    await writeFile(join(templates, 'default.hbs'), '<main>{{title}}</main>');

    const first = await buildSiteWithStats({ contentDir: content, outputDir: output, templateDir: templates, plugins: [plugin], incremental: true });
    expect(first.stats).toEqual({ pagesBuilt: 2, pagesSkipped: 0, timeSavedMs: expect.any(Number) });
    expect(rendered).toHaveLength(2);
    expect(await readFile(join(output, '.ssg-cache.json'), 'utf8')).toContain('renderedHtml');

    rendered.length = 0;
    const unchanged = await buildSiteWithStats({ contentDir: content, outputDir: output, templateDir: templates, plugins: [plugin], incremental: true });
    expect(unchanged.stats.pagesBuilt).toBe(0);
    expect(unchanged.stats.pagesSkipped).toBe(2);
    expect(rendered).toEqual([]);

    await writeFile(join(content, 'one.md'), '---\ntitle: One Updated\n---\nFirst');
    const sourceChanged = await buildSiteWithStats({ contentDir: content, outputDir: output, templateDir: templates, plugins: [plugin], incremental: true });
    expect(sourceChanged.stats.pagesBuilt).toBe(1);
    expect(sourceChanged.stats.pagesSkipped).toBe(1);
    expect(await readFile(join(output, 'one.html'), 'utf8')).toContain('One Updated!');

    await writeFile(join(templates, 'default.hbs'), '<article>{{title}}</article>');
    const templateChanged = await buildSiteWithStats({ contentDir: content, outputDir: output, templateDir: templates, plugins: [plugin], incremental: true });
    expect(templateChanged.stats.pagesBuilt).toBe(2);
    expect(templateChanged.stats.pagesSkipped).toBe(0);
    expect(await readFile(join(output, 'two.html'), 'utf8')).toContain('<article>Two!</article>');
  });

  it('performs a clean incremental build when requested', async () => {
    const content = join(directory, 'content');
    const output = join(directory, 'public');
    await mkdir(content, { recursive: true });
    await mkdir(output, { recursive: true });
    await writeFile(join(content, 'page.md'), '# Page');
    await writeFile(join(output, 'obsolete.txt'), 'remove me');

    const result = await buildSiteWithStats({ contentDir: content, outputDir: output, incremental: true, clean: true });

    expect(result.stats.pagesBuilt).toBe(1);
    await expect(readFile(join(output, 'obsolete.txt'), 'utf8')).rejects.toMatchObject({ code: 'ENOENT' });
  });
});
