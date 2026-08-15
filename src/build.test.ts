import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite, buildSiteWithStats } from './build';
import { Plugin } from './types';

describe('buildSite', () => {
  let root: string;

  beforeEach(async () => { root = await mkdtemp(join(tmpdir(), 'ssg-')); });
  afterEach(async () => { await rm(root, { recursive: true, force: true }); });

  it('writes a page per markdown file and an index', async () => {
    const content = join(root, 'content');
    const output = join(root, 'dist');
    await mkdir(join(content, 'guides'), { recursive: true });
    await writeFile(join(content, 'first.md'), '---\ntitle: First\ndate: 2026-01-02\ntags: alpha, beta\n---\n# First body');
    await writeFile(join(content, 'guides', 'second.md'), '# Second body');

    const pages = await buildSite(content, output);

    expect(pages).toHaveLength(2);
    expect(await readFile(join(output, 'first.html'), 'utf8')).toContain('<h1>First</h1>');
    expect(await readFile(join(output, 'guides', 'second.html'), 'utf8')).toContain('<h1>second</h1>');
    const index = await readFile(join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="first.html"');
    expect(index).toContain('href="guides/second.html"');
  });

  it('renders a selected Handlebars template inside a layout with partials', async () => {
    const content = join(root, 'content');
    const output = join(root, 'dist');
    const templates = join(root, 'templates');
    await mkdir(content, { recursive: true });
    await mkdir(join(templates, 'layouts'), { recursive: true });
    await mkdir(join(templates, 'partials'), { recursive: true });
    await writeFile(join(content, 'welcome.md'), '---\ntitle: Welcome & friends\ntemplate: article\nlayout: site\n---\nHello **world**');
    await writeFile(join(templates, 'article.hbs'), '{{> header}}<section>{{{body}}}</section>{{> footer}}');
    await writeFile(join(templates, 'layouts', 'site.hbs'), '<!doctype html><html><head><title>{{title}}</title></head><body><nav>Navigation</nav>{{{body}}}</body></html>');
    await writeFile(join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await writeFile(join(templates, 'partials', 'footer.hbs'), '<footer>Footer</footer>');

    await buildSite(content, output, templates);

    const page = await readFile(join(output, 'welcome.html'), 'utf8');
    expect(page).toContain('<title>Welcome &amp; friends</title>');
    expect(page).toContain('<nav>Navigation</nav>');
    expect(page).toContain('<header>Welcome &amp; friends</header>');
    expect(page).toContain('<section><p>Hello <strong>world</strong></p>');
    expect(page).toContain('<footer>Footer</footer>');
  });

  it('skips unchanged pages during an incremental build and keeps their rendered output', async () => {
    const content = join(root, 'content');
    const output = join(root, 'dist');
    const processed: string[] = [];
    const plugin: Plugin = {
      onFile(page) {
        processed.push(page.sourceFile);
        page.metadata = { title: page.outputPath, tags: [] };
        page.renderedHtml = `<html>${page.source}</html>`;
      },
    };
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'first.md'), 'first');
    await writeFile(join(content, 'second.md'), 'second');

    await buildSiteWithStats(content, output, join(root, 'templates'), [plugin]);
    processed.length = 0;
    const result = await buildSiteWithStats(content, output, join(root, 'templates'), [plugin], { incremental: true });

    expect(processed).toEqual([]);
    expect(result.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });
    expect(await readFile(join(output, 'first.html'), 'utf8')).toBe('<html>first</html>');
    expect(await readFile(join(output, '.ssg-cache.json'), 'utf8')).toContain('first.md');
  });

  it('rebuilds changed sources and invalidates all pages when templates change', async () => {
    const content = join(root, 'content');
    const output = join(root, 'dist');
    const templates = join(root, 'templates');
    await mkdir(content, { recursive: true });
    await mkdir(templates, { recursive: true });
    await writeFile(join(content, 'first.md'), '# First');
    await writeFile(join(content, 'second.md'), '# Second');
    await buildSiteWithStats(content, output, templates);

    await writeFile(join(content, 'first.md'), '# Updated');
    const changedSource = await buildSiteWithStats(content, output, templates, undefined, { incremental: true });
    expect(changedSource.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(await readFile(join(output, 'first.html'), 'utf8')).toContain('Updated');

    await writeFile(join(templates, 'page.hbs'), '<main>{{{body}}}</main>');
    const changedTemplate = await buildSiteWithStats(content, output, templates, undefined, { incremental: true });
    expect(changedTemplate.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(await readFile(join(output, 'second.html'), 'utf8')).toContain('<main><h1>Second</h1>');
  });
});
