import fs from 'fs';
import path from 'path';
import { build } from '../src/build';

const FIXTURES = path.resolve(__dirname, '..', 'content');
const OUT = path.resolve(__dirname, '..', 'test-dist');

beforeEach(() => {
  if (fs.existsSync(OUT)) {
    fs.rmSync(OUT, { recursive: true, force: true });
  }
});

afterAll(() => {
  if (fs.existsSync(OUT)) {
    fs.rmSync(OUT, { recursive: true, force: true });
  }
});

describe('build', () => {
  test('generates index.html and page html files', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    expect(fs.existsSync(path.join(OUT, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(OUT, 'first-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(OUT, 'another-post.html'))).toBe(true);
    expect(fs.existsSync(path.join(OUT, 'no-date.html'))).toBe(true);
  });

  test('index.html lists all pages', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    const indexHtml = fs.readFileSync(path.join(OUT, 'index.html'), 'utf-8');
    expect(indexHtml).toContain('My First Post');
    expect(indexHtml).toContain('Another Post');
    expect(indexHtml).toContain('No Date Post');
    expect(indexHtml).toContain('<li><a href="first-post.html">My First Post</a>');
    expect(indexHtml).toContain('<li><a href="another-post.html">Another Post</a>');
    expect(indexHtml).toContain('<li><a href="no-date.html">No Date Post</a>');
  });

  test('page html contains frontmatter data', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    const firstPost = fs.readFileSync(path.join(OUT, 'first-post.html'), 'utf-8');
    expect(firstPost).toContain('<title>My First Post</title>');
    expect(firstPost).toContain('<h1>My First Post</h1>');
    expect(firstPost).toContain('2025-06-01');
    expect(firstPost).toContain('hello, world');

    const anotherPost = fs.readFileSync(path.join(OUT, 'another-post.html'), 'utf-8');
    expect(anotherPost).toContain('<title>Another Post</title>');
  });

  test('markdown content is converted to HTML', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    const firstPost = fs.readFileSync(path.join(OUT, 'first-post.html'), 'utf-8');
    expect(firstPost).toContain('<h1>Hello World</h1>');
    expect(firstPost).toContain('<p>This is the first post.</p>');

    const anotherPost = fs.readFileSync(path.join(OUT, 'another-post.html'), 'utf-8');
    expect(anotherPost).toContain('<h2>Getting Started</h2>');
    expect(anotherPost).toContain('<p>Some content here.</p>');
  });

  test('page with no date or tags does not crash', () => {
    build({ contentDir: FIXTURES, outputDir: OUT });

    const noDate = fs.readFileSync(path.join(OUT, 'no-date.html'), 'utf-8');
    expect(noDate).toContain('<title>No Date Post</title>');
    expect(noDate).not.toContain('class="date"');
    expect(noDate).not.toContain('class="tags"');
  });

  test('pages are ordered correctly (with dates first, then title)', () => {
    const tempContent = path.resolve(__dirname, '..', 'temp-content');
    const tempOut = path.resolve(__dirname, '..', 'temp-dist');

    try {
      fs.mkdirSync(tempContent, { recursive: true });
      fs.writeFileSync(
        path.join(tempContent, 'a.md'),
        `---\ntitle: Alpha\ndate: 2025-01-01\n---\nContent`
      );
      fs.writeFileSync(
        path.join(tempContent, 'b.md'),
        `---\ntitle: Beta\ndate: 2025-06-01\n---\nContent`
      );
      fs.writeFileSync(
        path.join(tempContent, 'c.md'),
        `---\ntitle: Gamma\n---\nContent`
      );

      build({ contentDir: tempContent, outputDir: tempOut });

      const indexHtml = fs.readFileSync(path.join(tempOut, 'index.html'), 'utf-8');
      const betaIdx = indexHtml.indexOf('Beta');
      const alphaIdx = indexHtml.indexOf('Alpha');
      const gammaIdx = indexHtml.indexOf('Gamma');

      expect(betaIdx).toBeLessThan(alphaIdx);
      expect(alphaIdx).toBeLessThan(gammaIdx);
    } finally {
      if (fs.existsSync(tempContent)) fs.rmSync(tempContent, { recursive: true, force: true });
      if (fs.existsSync(tempOut)) fs.rmSync(tempOut, { recursive: true, force: true });
    }
  });

  test('throws on missing content directory', () => {
    expect(() => {
      build({ contentDir: '/nonexistent/path', outputDir: OUT });
    }).toThrow('Content directory not found');
  });

  test('throws on missing title in frontmatter', () => {
    const tempContent = path.resolve(__dirname, '..', 'bad-content');
    const tempOut = path.resolve(__dirname, '..', 'bad-dist');
    try {
      fs.mkdirSync(tempContent, { recursive: true });
      fs.writeFileSync(path.join(tempContent, 'bad.md'), 'No frontmatter here');

      expect(() => {
        build({ contentDir: tempContent, outputDir: tempOut });
      }).toThrow('Missing title in frontmatter');
    } finally {
      if (fs.existsSync(tempContent)) fs.rmSync(tempContent, { recursive: true, force: true });
      if (fs.existsSync(tempOut)) fs.rmSync(tempOut, { recursive: true, force: true });
    }
  });
});

describe('templates', () => {
  function createTempDir(prefix: string): string {
    const dir = path.resolve(__dirname, '..', `${prefix}-${Date.now()}`);
    fs.mkdirSync(dir, { recursive: true });
    return dir;
  }

  function cleanupDir(dir: string): void {
    if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
  }

  test('uses default template and layout when none specified', () => {
    const tempContent = createTempDir('tmpl-content-default');
    const tempOut = createTempDir('tmpl-out-default');
    try {
      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: Default Test\ndate: 2025-01-15\n---\n# Hello`
      );

      build({ contentDir: tempContent, outputDir: tempOut });

      const html = fs.readFileSync(path.join(tempOut, 'test.html'), 'utf-8');
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>Default Test</title>');
      expect(html).toContain('<nav><a href="index.html">Home</a></nav>');
      expect(html).toContain('<h1>Default Test</h1>');
      expect(html).toContain('<p class="date">2025-01-15</p>');
    } finally {
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('supports custom template specified in frontmatter', () => {
    const tempTemplates = createTempDir('tmpl-custom-tmpl');
    const tempContent = createTempDir('tmpl-content-custom-tmpl');
    const tempOut = createTempDir('tmpl-out-custom-tmpl');
    try {
      fs.mkdirSync(path.join(tempTemplates, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tempTemplates, 'partials'), { recursive: true });

      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'special.hbs'),
        '<div class="custom">SPECIAL: {{title}} - {{{content}}}</div>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'index.hbs'),
        '<h1>Index</h1><ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
      );

      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: Custom Template Test\ntemplate: special\n---\n## Content`
      );

      build({ contentDir: tempContent, outputDir: tempOut, templatesDir: tempTemplates });

      const html = fs.readFileSync(path.join(tempOut, 'test.html'), 'utf-8');
      expect(html).toContain('<div class="custom">SPECIAL: Custom Template Test - <h2>Content</h2>');
      expect(html).toContain('<!DOCTYPE html>');
    } finally {
      cleanupDir(tempTemplates);
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('supports custom layout specified in frontmatter', () => {
    const tempTemplates = createTempDir('tmpl-custom-layout');
    const tempContent = createTempDir('tmpl-content-custom-layout');
    const tempOut = createTempDir('tmpl-out-custom-layout');
    try {
      fs.mkdirSync(path.join(tempTemplates, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tempTemplates, 'partials'), { recursive: true });

      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'blog.hbs'),
        '<!DOCTYPE html><html><head><title>BLOG: {{title}}</title></head><body><header>Blog Layout</header>{{{body}}}</body></html>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'page.hbs'),
        '<article><h1>{{title}}</h1><div>{{{content}}}</div></article>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'index.hbs'),
        '<h1>Index</h1><ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
      );

      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: Blog Post\nlayout: blog\n---\n## Body`
      );

      build({ contentDir: tempContent, outputDir: tempOut, templatesDir: tempTemplates });

      const html = fs.readFileSync(path.join(tempOut, 'test.html'), 'utf-8');
      expect(html).toContain('<title>BLOG: Blog Post</title>');
      expect(html).toContain('<header>Blog Layout</header>');
      expect(html).toContain('<h1>Blog Post</h1>');
      expect(html).toContain('<h2>Body</h2>');
    } finally {
      cleanupDir(tempTemplates);
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('supports partials/includes in templates', () => {
    const tempTemplates = createTempDir('tmpl-partials');
    const tempContent = createTempDir('tmpl-content-partials');
    const tempOut = createTempDir('tmpl-out-partials');
    try {
      fs.mkdirSync(path.join(tempTemplates, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tempTemplates, 'partials'), { recursive: true });

      fs.writeFileSync(
        path.join(tempTemplates, 'partials', 'header.hbs'),
        '<header>Site Header</header>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'partials', 'footer.hbs'),
        '<footer>Site Footer</footer>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{> header}}{{{body}}}{{> footer}}</body></html>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'page.hbs'),
        '<article><h1>{{title}}</h1><div>{{{content}}}</div></article>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'index.hbs'),
        '<h1>Index</h1><ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
      );

      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: Partial Test\n---\n## Content`
      );

      build({ contentDir: tempContent, outputDir: tempOut, templatesDir: tempTemplates });

      const html = fs.readFileSync(path.join(tempOut, 'test.html'), 'utf-8');
      expect(html).toContain('<header>Site Header</header>');
      expect(html).toContain('<footer>Site Footer</footer>');
      expect(html).toContain('<h1>Partial Test</h1>');
    } finally {
      cleanupDir(tempTemplates);
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('throws when specified template does not exist', () => {
    const tempTemplates = createTempDir('tmpl-missing');
    const tempContent = createTempDir('tmpl-content-missing');
    const tempOut = createTempDir('tmpl-out-missing');
    try {
      fs.mkdirSync(path.join(tempTemplates, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tempTemplates, 'partials'), { recursive: true });

      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'index.hbs'),
        '<h1>Index</h1>'
      );

      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: Missing Template\ntemplate: nonexistent\n---\n# Content`
      );

      expect(() => {
        build({ contentDir: tempContent, outputDir: tempOut, templatesDir: tempTemplates });
      }).toThrow('Template not found: nonexistent');
    } finally {
      cleanupDir(tempTemplates);
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('throws when specified layout does not exist', () => {
    const tempTemplates = createTempDir('tmpl-layout-missing');
    const tempContent = createTempDir('tmpl-content-layout-missing');
    const tempOut = createTempDir('tmpl-out-layout-missing');
    try {
      fs.mkdirSync(path.join(tempTemplates, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tempTemplates, 'partials'), { recursive: true });

      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'page.hbs'),
        '<article><h1>{{title}}</h1><div>{{{content}}}</div></article>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'index.hbs'),
        '<h1>Index</h1>'
      );

      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: Bad Layout\nlayout: nonexistent\n---\n# Content`
      );

      expect(() => {
        build({ contentDir: tempContent, outputDir: tempOut, templatesDir: tempTemplates });
      }).toThrow('Layout not found: nonexistent');
    } finally {
      cleanupDir(tempTemplates);
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('renders with default layout when no layout specified', () => {
    const tempTemplates = createTempDir('tmpl-no-layout');
    const tempContent = createTempDir('tmpl-content-no-layout');
    const tempOut = createTempDir('tmpl-out-no-layout');
    try {
      fs.mkdirSync(path.join(tempTemplates, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tempTemplates, 'partials'), { recursive: true });

      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
      );

      fs.writeFileSync(
        path.join(tempTemplates, 'page.hbs'),
        '<article><h1>{{title}}</h1><div>{{{content}}}</div></article>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'index.hbs'),
        '<h1>Index</h1><ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
      );

      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: No Layout\n---\n# Content`
      );

      build({ contentDir: tempContent, outputDir: tempOut, templatesDir: tempTemplates });

      const html = fs.readFileSync(path.join(tempOut, 'test.html'), 'utf-8');
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<title>No Layout</title>');
      expect(html).toContain('<h1>No Layout</h1>');
    } finally {
      cleanupDir(tempTemplates);
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('layout: false disables layout rendering', () => {
    const tempTemplates = createTempDir('tmpl-nolay-false');
    const tempContent = createTempDir('tmpl-content-nolay-false');
    const tempOut = createTempDir('tmpl-out-nolay-false');
    try {
      fs.mkdirSync(path.join(tempTemplates, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tempTemplates, 'partials'), { recursive: true });

      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'page.hbs'),
        '<article><h1>{{title}}</h1><div>{{{content}}}</div></article>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'index.hbs'),
        '<h1>Index</h1><ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
      );

      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: False Layout\nlayout: false\n---\n# Raw`
      );

      build({ contentDir: tempContent, outputDir: tempOut, templatesDir: tempTemplates });

      const html = fs.readFileSync(path.join(tempOut, 'test.html'), 'utf-8');
      expect(html).not.toContain('<!DOCTYPE html>');
      expect(html).toContain('<h1>False Layout</h1>');
      expect(html).toContain('<article>');
    } finally {
      cleanupDir(tempTemplates);
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('supports custom templatesDir option', () => {
    const tempTemplates = createTempDir('tmpl-customdir');
    const tempContent = createTempDir('tmpl-content-customdir');
    const tempOut = createTempDir('tmpl-out-customdir');
    try {
      fs.mkdirSync(path.join(tempTemplates, 'layouts'), { recursive: true });
      fs.mkdirSync(path.join(tempTemplates, 'partials'), { recursive: true });

      fs.writeFileSync(
        path.join(tempTemplates, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>CUSTOM: {{title}}</title></head><body>{{{body}}}</body></html>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'page.hbs'),
        '<article><h1>{{title}}</h1><div>{{{content}}}</div></article>'
      );
      fs.writeFileSync(
        path.join(tempTemplates, 'index.hbs'),
        '<h1>Custom Index</h1><ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>'
      );

      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: Custom Dir Test\n---\n# Content`
      );

      build({ contentDir: tempContent, outputDir: tempOut, templatesDir: tempTemplates });

      const pageHtml = fs.readFileSync(path.join(tempOut, 'test.html'), 'utf-8');
      expect(pageHtml).toContain('<title>CUSTOM: Custom Dir Test</title>');
      expect(pageHtml).toContain('<h1>Custom Dir Test</h1>');

      const indexHtml = fs.readFileSync(path.join(tempOut, 'index.html'), 'utf-8');
      expect(indexHtml).toContain('<h1>Custom Index</h1>');
      expect(indexHtml).toContain('<li>Custom Dir Test</li>');
    } finally {
      cleanupDir(tempTemplates);
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('template data includes tags as array for iteration', () => {
    const tempContent = createTempDir('tmpl-content-tags');
    const tempOut = createTempDir('tmpl-out-tags');
    try {
      fs.writeFileSync(
        path.join(tempContent, 'test.md'),
        `---\ntitle: Tags Test\ntags:\n  - red\n  - green\n  - blue\n---\n# Content`
      );

      build({ contentDir: tempContent, outputDir: tempOut });

      const html = fs.readFileSync(path.join(tempOut, 'test.html'), 'utf-8');
      expect(html).toContain('Tags: red, green, blue');
    } finally {
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('index template receives sorted pages array', () => {
    const tempContent = createTempDir('tmpl-content-sorted');
    const tempOut = createTempDir('tmpl-out-sorted');
    try {
      fs.writeFileSync(
        path.join(tempContent, 'z.md'),
        `---\ntitle: Zulu\ndate: 2025-03-01\n---\nContent`
      );
      fs.writeFileSync(
        path.join(tempContent, 'a.md'),
        `---\ntitle: Alpha\ndate: 2025-09-01\n---\nContent`
      );

      build({ contentDir: tempContent, outputDir: tempOut });

      const indexHtml = fs.readFileSync(path.join(tempOut, 'index.html'), 'utf-8');
      const alphaIdx = indexHtml.indexOf('Alpha');
      const zuluIdx = indexHtml.indexOf('Zulu');
      expect(alphaIdx).toBeLessThan(zuluIdx);
    } finally {
      cleanupDir(tempContent);
      cleanupDir(tempOut);
    }
  });

  test('throws on missing templates directory', () => {
    expect(() => {
      build({ contentDir: FIXTURES, outputDir: OUT, templatesDir: '/nonexistent/templates' });
    }).toThrow('Templates directory not found');
  });
});
