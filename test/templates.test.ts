import fs from 'fs';
import os from 'os';
import path from 'path';

import { buildSite } from '../src/site';
import { TemplateEngine } from '../src/templates';

function tmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(root: string, relative: string, content: string): string {
  const full = path.join(root, relative);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
  return full;
}

const DEFAULT_LAYOUT = `<!doctype html>
<html>
<head><title>{{title}}</title></head>
<body>
{{> header}}
<main>{{{body}}}</main>
{{> footer}}
</body>
</html>
`;

function setupProject(overrides: { layoutContent?: string } = {}) {
  const root = tmpDir('ssg-project-');
  const contentDir = path.join(root, 'content');
  const templatesDir = path.join(root, 'templates');
  const outputDir = path.join(root, 'dist');

  fs.mkdirSync(contentDir, { recursive: true });

  writeFile(templatesDir, path.join('layouts', 'default.hbs'), overrides.layoutContent ?? DEFAULT_LAYOUT);
  writeFile(templatesDir, path.join('partials', 'header.hbs'), '<header>Site Header</header>');
  writeFile(templatesDir, path.join('partials', 'footer.hbs'), '<footer>Site Footer</footer>');
  writeFile(templatesDir, path.join('partials', 'nav.hbs'), '<nav>Nav</nav>');

  return { root, contentDir, templatesDir, outputDir };
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

describe('template engine', () => {
  it('renders a page through the default layout using {{{body}}}', () => {
    const { contentDir, templatesDir, outputDir } = setupProject();
    try {
      writeFile(
        contentDir,
        'hello.md',
        `---
title: Hello World
---
# Welcome

This is the **first** post.
`
      );

      buildSite({ contentDir, outputDir, templatesDir });

      const page = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
      expect(page).toContain('<title>Hello World</title>');
      expect(page).toContain('<h1>Welcome</h1>');
      expect(page).toContain('<strong>first</strong>');
      expect(page).toContain('<main>');
    } finally {
      cleanup(path.join(outputDir, '..'));
    }
  });

  it('includes partials (header, footer, nav) referenced in the layout', () => {
    const { contentDir, templatesDir, outputDir } = setupProject({
      layoutContent: `<!doctype html>
<html>
<body>
{{> header}}
{{> nav}}
<main>{{{body}}}</main>
{{> footer}}
</body>
</html>
`,
    });
    try {
      writeFile(
        contentDir,
        'page.md',
        `---
title: Partials
---
Body content.
`
      );

      buildSite({ contentDir, outputDir, templatesDir });

      const page = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
      expect(page).toContain('<header>Site Header</header>');
      expect(page).toContain('<nav>Nav</nav>');
      expect(page).toContain('<footer>Site Footer</footer>');
      expect(page).toContain('<p>Body content.</p>');
    } finally {
      cleanup(path.join(outputDir, '..'));
    }
  });

  it('uses the layout named in the frontmatter template field', () => {
    const { contentDir, templatesDir, outputDir } = setupProject();
    try {
      writeFile(
        templatesDir,
        path.join('layouts', 'post.hbs'),
        `<article class="post">{{{body}}}</article>`
      );
      writeFile(
        contentDir,
        'hello.md',
        `---
title: Hello
template: post
---
Special body.
`
      );
      writeFile(
        contentDir,
        'about.md',
        `---
title: About
---
Normal body.
`
      );

      buildSite({ contentDir, outputDir, templatesDir });

      const post = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
      expect(post).toContain('<article class="post">');
      expect(post).not.toContain('<main>');

      const about = fs.readFileSync(path.join(outputDir, 'about.html'), 'utf-8');
      expect(about).toContain('<main>');
    } finally {
      cleanup(path.join(outputDir, '..'));
    }
  });

  it('falls back to the default layout when the requested template is missing', () => {
    const { contentDir, templatesDir, outputDir } = setupProject();
    try {
      writeFile(
        contentDir,
        'hello.md',
        `---
title: Hello
template: does-not-exist
---
Body.
`
      );

      buildSite({ contentDir, outputDir, templatesDir });

      const page = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
      expect(page).toContain('<main>');
      expect(page).toContain('<title>Hello</title>');
    } finally {
      cleanup(path.join(outputDir, '..'));
    }
  });

  it('escapes {{title}} but renders {{{body}}} as raw HTML', () => {
    const { contentDir, templatesDir, outputDir } = setupProject({
      layoutContent: '<title>{{title}}</title><main>{{{body}}}</main>',
    });
    try {
      writeFile(
        contentDir,
        'hello.md',
        `---
title: A <script> title
---
Some **bold** text.
`
      );

      buildSite({ contentDir, outputDir, templatesDir });

      const page = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
      expect(page).toContain('A &lt;script&gt; title');
      expect(page).not.toContain('<script> title');
      expect(page).toContain('<strong>bold</strong>');
    } finally {
      cleanup(path.join(outputDir, '..'));
    }
  });

  it('resolves nested layout names from the frontmatter', () => {
    const { contentDir, templatesDir, outputDir } = setupProject();
    try {
      writeFile(
        templatesDir,
        path.join('layouts', 'blog', 'post.hbs'),
        '<section class="blog">{{{body}}}</section>'
      );
      writeFile(
        contentDir,
        'hello.md',
        `---
title: Hello
template: blog/post
---
Nested body.
`
      );

      buildSite({ contentDir, outputDir, templatesDir });

      const page = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
      expect(page).toContain('<section class="blog">');
    } finally {
      cleanup(path.join(outputDir, '..'));
    }
  });

  it('still uses the built-in HTML when no templates directory exists', () => {
    const contentDir = tmpDir('ssg-content-');
    const outputDir = tmpDir('ssg-dist-');
    try {
      writeFile(
        contentDir,
        'hello.md',
        `---
title: Hello
---
Plain body.
`
      );

      buildSite({ contentDir, outputDir, templatesDir: path.join(contentDir, 'missing-templates') });

      const page = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf-8');
      expect(page).toContain('← Index');
      expect(page).toContain('<h1>Hello</h1>');
    } finally {
      cleanup(contentDir);
      cleanup(outputDir);
    }
  });
});

describe('TemplateEngine', () => {
  it('discovers layouts and partials from the templates directory', () => {
    const templatesDir = tmpDir('ssg-templates-');
    try {
      writeFile(templatesDir, path.join('layouts', 'default.hbs'), '{{{body}}}');
      writeFile(templatesDir, path.join('layouts', 'post.hbs'), 'post');
      writeFile(templatesDir, path.join('partials', 'header.hbs'), 'H');

      const engine = new TemplateEngine(templatesDir);
      expect(engine.availableLayouts).toEqual(expect.arrayContaining(['default', 'post']));
      expect(engine.hasLayout('post')).toBe(true);
      expect(engine.hasLayout('missing')).toBe(false);
    } finally {
      cleanup(templatesDir);
    }
  });

  it('renders with the default layout and returns null when none matches', () => {
    const templatesDir = tmpDir('ssg-templates-');
    try {
      const engine = new TemplateEngine(templatesDir);
      expect(engine.render(undefined, makeContext())).toBeNull();
    } finally {
      cleanup(templatesDir);
    }
  });

  it('renders the default layout when no template name is given', () => {
    const templatesDir = tmpDir('ssg-templates-');
    try {
      writeFile(templatesDir, path.join('layouts', 'default.hbs'), '<b>{{title}}</b>');
      const engine = new TemplateEngine(templatesDir);
      const html = engine.render(undefined, makeContext());
      expect(html).toBe('<b>My Page</b>');
    } finally {
      cleanup(templatesDir);
    }
  });
});

function makeContext() {
  return {
    title: 'My Page',
    tags: [],
    slug: 'my-page',
    content: '',
    body: '<p>hi</p>',
  };
}
