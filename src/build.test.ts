import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite } from './build';

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
});
