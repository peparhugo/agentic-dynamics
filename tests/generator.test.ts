import { mkdtemp, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite, parseYamlFrontmatter } from '../src/generator';

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
});
