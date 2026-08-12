import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

async function fixture(): Promise<{ root: string; content: string; templates: string; output: string }> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
  const content = path.join(root, 'content');
  const templates = path.join(root, 'templates');
  const output = path.join(root, 'dist');
  await fs.mkdir(content, { recursive: true });
  await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
  await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
  return { root, content, templates, output };
}

describe('buildSite templates', () => {
  it('keeps the built-in output when no templates exist', async () => {
    const paths = await fixture();
    await fs.writeFile(path.join(paths.content, 'hello.md'), '# Hello');

    const [page] = await buildSite(paths);

    expect(page.html).toContain('<h1>Hello</h1>');
    expect(page.html).toContain('<!doctype html>');
  });

  it('renders a selected template inside a layout and expands partials', async () => {
    const paths = await fixture();
    await fs.writeFile(path.join(paths.content, 'post.md'), '---\ntitle: A <post>\ntemplate: article\nlayout: shell\n---\nHello **world**');
    await fs.writeFile(path.join(paths.templates, 'article.hbs'), '{{> header}}<article>{{title}} {{{content}}}</article>{{> footer}}');
    await fs.writeFile(path.join(paths.templates, 'layouts', 'shell.hbs'), '<html><body>{{{body}}}</body></html>');
    await fs.writeFile(path.join(paths.templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');
    await fs.writeFile(path.join(paths.templates, 'partials', 'footer.hbs'), '<footer>footer</footer>');

    const [page] = await buildSite(paths);
    const output = await fs.readFile(path.join(paths.output, 'post.html'), 'utf8');

    expect(output).toBe('<html><body><header>A &lt;post&gt;</header><article>A &lt;post&gt; <p>Hello <strong>world</strong></p>\n</article><footer>footer</footer></body></html>');
    expect(page.template).toBe('article');
    expect(page.layout).toBe('shell');
  });

  it('uses default templates for pages without a template in frontmatter', async () => {
    const paths = await fixture();
    await fs.writeFile(path.join(paths.content, 'hello.md'), '---\ntitle: Hello\n---\nWelcome');
    await fs.writeFile(path.join(paths.templates, 'default.hbs'), '<section>{{title}} {{{content}}}</section>');
    await fs.writeFile(path.join(paths.templates, 'layouts', 'default.hbs'), '<html>{{{body}}}</html>');

    const [page] = await buildSite(paths);

    expect(page.html).toBe('<html><section>Hello <p>Welcome</p>\n</section></html>');
  });
});

describe('incremental builds', () => {
  it('builds once, skips unchanged pages, and invalidates changed sources', async () => {
    const paths = await fixture();
    await fs.writeFile(path.join(paths.content, 'one.md'), '# One');
    await fs.writeFile(path.join(paths.content, 'two.md'), '# Two');

    const first = await buildSite({ ...paths, incremental: true });
    expect(first.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0, incremental: true });
    expect(JSON.parse(await fs.readFile(path.join(paths.output, '.ssg-cache.json'), 'utf8')).entries['one.md'].sourceHash).toBeDefined();

    const second = await buildSite({ ...paths, incremental: true });
    expect(second.stats).toMatchObject({ pagesBuilt: 0, pagesSkipped: 2 });

    await fs.writeFile(path.join(paths.content, 'one.md'), '# Updated');
    const third = await buildSite({ ...paths, incremental: true });
    expect(third.stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(await fs.readFile(path.join(paths.output, 'one.html'), 'utf8')).toContain('Updated');
    expect(await fs.readFile(path.join(paths.output, 'two.html'), 'utf8')).toContain('Two');
  });

  it('invalidates every page when a template changes', async () => {
    const paths = await fixture();
    await fs.writeFile(path.join(paths.content, 'one.md'), '# One');
    await fs.writeFile(path.join(paths.content, 'two.md'), '# Two');
    await fs.writeFile(path.join(paths.templates, 'default.hbs'), '<div>{{{content}}}</div>');

    await buildSite({ ...paths, incremental: true });
    await fs.writeFile(path.join(paths.templates, 'default.hbs'), '<section>{{{content}}}</section>');
    const result = await buildSite({ ...paths, incremental: true });

    expect(result.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
    expect(await fs.readFile(path.join(paths.output, 'one.html'), 'utf8')).toContain('<section>');
  });

  it('performs a clean rebuild when requested', async () => {
    const paths = await fixture();
    await fs.writeFile(path.join(paths.content, 'one.md'), '# One');
    await buildSite({ ...paths, incremental: true });
    await fs.writeFile(path.join(paths.content, 'two.md'), '# Two');
    const result = await buildSite({ ...paths, incremental: true, clean: true });

    expect(result.stats).toMatchObject({ pagesBuilt: 2, pagesSkipped: 0 });
  });
});
