import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import { build } from '../src';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-tpl-'));
}

async function writeFile(filePath: string, contents: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, contents, 'utf8');
}

describe('template engine', () => {
  it('renders a page using a custom template, layout and partials', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    const templatesDir = await makeTempDir();

    await writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      `<!DOCTYPE html>
<html>
<body>
{{> header}}
{{{body}}}
{{> footer}}
</body>
</html>
`
    );
    await writeFile(
      path.join(templatesDir, 'partials', 'header.hbs'),
      `<header>Site header</header>`
    );
    await writeFile(
      path.join(templatesDir, 'partials', 'footer.hbs'),
      `<footer>Site footer</footer>`
    );
    await writeFile(
      path.join(templatesDir, 'post.hbs'),
      `<article class="post"><h2>{{title}}</h2>{{{contentHtml}}}</article>`
    );

    await writeFile(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello Template
template: post
---
# Welcome
Body text.`
    );

    const pages = await build({
      content: contentDir,
      output: outputDir,
      templates: templatesDir,
    });

    expect(pages).toHaveLength(1);

    const html = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');
    expect(html).toContain('<header>Site header</header>');
    expect(html).toContain('<footer>Site footer</footer>');
    expect(html).toContain('<article class="post">');
    expect(html).toContain('<h2>Hello Template</h2>');
    expect(html).toContain('<h1>Welcome</h1>');
    expect(html).not.toContain('{{{body}}}');
  });

  it('falls back to the default page template when none is specified', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    const templatesDir = await makeTempDir();

    await writeFile(path.join(contentDir, 'post.md'), '---\ntitle: Defaulted\n---\n# Hi');

    await build({ content: contentDir, output: outputDir, templates: templatesDir });

    const html = await fs.readFile(path.join(outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<article>');
    expect(html).toContain('<h1>Defaulted</h1>');
    expect(html).toContain('<h1>Hi</h1>');
  });

  it('uses a custom default layout for pages without an explicit layout', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    const templatesDir = await makeTempDir();

    await writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      `<!DOCTYPE html>
<html>
<body>{{> nav}}{{{body}}}</body>
</html>
`
    );
    await writeFile(
      path.join(templatesDir, 'partials', 'nav.hbs'),
      `<nav>Home | About</nav>`
    );
    await writeFile(path.join(contentDir, 'about.md'), '---\ntitle: About Us\n---\n# About');

    await build({ content: contentDir, output: outputDir, templates: templatesDir });

    const html = await fs.readFile(path.join(outputDir, 'about.html'), 'utf8');
    expect(html).toContain('<nav>Home | About</nav>');
    expect(html).toContain('<h1>About Us</h1>');
    expect(html).toContain('<h1>About</h1>');
  });

  it('exposes custom frontmatter fields to templates', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    const templatesDir = await makeTempDir();

    await writeFile(
      path.join(templatesDir, 'page.hbs'),
      `<p>By {{author}}</p>{{{contentHtml}}}`
    );
    await writeFile(
      path.join(contentDir, 'note.md'),
      `---
title: Note
template: page
author: Jane Doe
---
# Note body`
    );

    await build({ content: contentDir, output: outputDir, templates: templatesDir });

    const html = await fs.readFile(path.join(outputDir, 'note.html'), 'utf8');
    expect(html).toContain('<p>By Jane Doe</p>');
  });

  it('lets a page select a specific layout via frontmatter', async () => {
    const contentDir = await makeTempDir();
    const outputDir = await makeTempDir();
    const templatesDir = await makeTempDir();

    await writeFile(
      path.join(templatesDir, 'layouts', 'post.hbs'),
      `<html><body><div class="post-layout">{{{body}}}</div></body></html>`
    );
    await writeFile(path.join(contentDir, 'post.md'), '---\ntitle: Laid Out\nlayout: post\n---\n# Body');

    await build({ content: contentDir, output: outputDir, templates: templatesDir });

    const html = await fs.readFile(path.join(outputDir, 'post.html'), 'utf8');
    expect(html).toContain('<div class="post-layout">');
    expect(html).toContain('<h1>Body</h1>');
  });
});
