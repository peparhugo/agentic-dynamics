import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildSite, createBuildPipeline, parsePage } from '../src/generator';

describe('parsePage', () => {
  it('merges simple YAML frontmatter and renders Markdown', () => {
    const page = parsePage('---\ntitle: Hello world\ndate: 2026-08-15\ntags: [typescript, static]\n---\n# Welcome\n\nText', 'hello.md');

    expect(page).toMatchObject({ title: 'Hello world', date: '2026-08-15', tags: ['typescript', 'static'], slug: 'hello' });
    expect(page.html).toContain('<h1>Welcome</h1>');
  });

  it('uses the filename and empty tags when frontmatter is absent', () => {
    expect(parsePage('A paragraph', 'notes.md')).toMatchObject({ title: 'notes', tags: [], slug: 'notes' });
  });
});

describe('buildSite', () => {
  let root: string;

  beforeEach(() => { root = mkdtempSync(join(tmpdir(), 'ssg-')); });
  afterEach(() => { rmSync(root, { recursive: true, force: true }); });

  it('writes each page and an index to the selected output directory', () => {
    const content = join(root, 'content');
    const output = join(root, 'site');
    mkdirSync(content);
    writeFileSync(join(content, 'first.md'), '---\ntitle: First post\ndate: 2026-01-02\n---\n# First');
    writeFileSync(join(content, 'second.md'), '# Second');

    expect(buildSite({ contentDir: content, outputDir: output })).toHaveLength(2);
    expect(readFileSync(join(output, 'first.html'), 'utf8')).toContain('<h1>First post</h1>');
    const index = readFileSync(join(output, 'index.html'), 'utf8');
    expect(index).toContain('href="first.html"');
    expect(index).toContain('First post');
  });

  it('renders a page template in the default layout with partials', () => {
    const content = join(root, 'content');
    const output = join(root, 'site');
    const templates = join(root, 'templates');
    mkdirSync(content);
    mkdirSync(join(templates, 'layouts'), { recursive: true });
    mkdirSync(join(templates, 'partials'));
    writeFileSync(join(content, 'post.md'), '---\ntitle: Templated post\n---\n# Hello');
    writeFileSync(join(templates, 'default.hbs'), '<article><h1>{{title}}</h1>{{{content}}}</article>');
    writeFileSync(join(templates, 'layouts', 'default.hbs'), '<html><body>{{> header}}{{{body}}}{{> footer}}</body></html>');
    writeFileSync(join(templates, 'partials', 'header.hbs'), '<header>Site header</header>');
    writeFileSync(join(templates, 'partials', 'footer.hbs'), '<footer>Site footer</footer>');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    const page = readFileSync(join(output, 'post.html'), 'utf8');
    expect(page).toContain('<header>Site header</header>');
    expect(page).toContain('<article><h1>Templated post</h1><h1>Hello</h1>');
    expect(page).toContain('<footer>Site footer</footer>');
  });

  it('uses frontmatter-selected templates and layouts', () => {
    const content = join(root, 'content');
    const output = join(root, 'site');
    const templates = join(root, 'templates');
    mkdirSync(content);
    mkdirSync(join(templates, 'layouts'), { recursive: true });
    writeFileSync(join(content, 'post.md'), '---\ntitle: Custom\ntemplate: card\nlayout: shell\n---\nBody');
    writeFileSync(join(templates, 'card.hbs'), '<section data-slug="{{slug}}">{{title}}: {{{content}}}</section>');
    writeFileSync(join(templates, 'layouts', 'shell.hbs'), '<main>{{{body}}}</main>');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });

    expect(readFileSync(join(output, 'post.html'), 'utf8')).toBe('<main><section data-slug="post">Custom: <p>Body</p>\n</section></main>');
  });

  it('skips unchanged pages during an incremental build', () => {
    const content = join(root, 'content');
    const output = join(root, 'site');
    mkdirSync(content);
    writeFileSync(join(content, 'first.md'), '# First');
    writeFileSync(join(content, 'second.md'), '# Second');

    buildSite({ contentDir: content, outputDir: output, incremental: true });
    const pipeline = createBuildPipeline({ contentDir: content, outputDir: output, incremental: true });
    pipeline.build();

    expect(pipeline.context.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });
    expect(readFileSync(join(output, '.ssg-cache.json'), 'utf8')).toContain('first');
  });

  it('rebuilds only a changed source page and invalidates all pages when templates change', () => {
    const content = join(root, 'content');
    const output = join(root, 'site');
    const templates = join(root, 'templates');
    mkdirSync(content);
    mkdirSync(templates);
    writeFileSync(join(content, 'first.md'), '# First');
    writeFileSync(join(content, 'second.md'), '# Second');
    writeFileSync(join(templates, 'default.hbs'), '<article>{{{content}}}</article>');

    buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    writeFileSync(join(content, 'first.md'), '# Changed');
    let pipeline = createBuildPipeline({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    pipeline.build();
    expect(pipeline.context.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(readFileSync(join(output, 'first.html'), 'utf8')).toContain('Changed');

    writeFileSync(join(templates, 'default.hbs'), '<main>{{{content}}}</main>');
    pipeline = createBuildPipeline({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true });
    pipeline.build();
    expect(pipeline.context.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(readFileSync(join(output, 'second.html'), 'utf8')).toContain('<main>');
  });

  it('performs a clean build when requested', () => {
    const content = join(root, 'content');
    const output = join(root, 'site');
    mkdirSync(content);
    writeFileSync(join(content, 'post.md'), '# Post');
    buildSite({ contentDir: content, outputDir: output, incremental: true });
    writeFileSync(join(output, 'stale.txt'), 'stale');

    const pipeline = createBuildPipeline({ contentDir: content, outputDir: output, incremental: true, clean: true });
    pipeline.build();

    expect(pipeline.context.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
    expect(existsSync(join(output, 'stale.txt'))).toBe(false);
  });
});
