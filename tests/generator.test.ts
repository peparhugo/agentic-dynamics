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
