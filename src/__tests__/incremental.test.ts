import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { buildSite } from '../build';
import { BuildStats, CacheManifest, CACHE_FILE } from '../cache';
import { parseArgs, run } from '../cli';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-incr-'));
}

async function write(filePath: string, content: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content, 'utf-8');
}

async function readManifest(outputDir: string): Promise<CacheManifest> {
  const raw = await fs.readFile(path.join(outputDir, CACHE_FILE), 'utf-8');
  return JSON.parse(raw) as CacheManifest;
}

interface Fixture {
  root: string;
  contentDir: string;
  outputDir: string;
  templateDir: string;
}

async function makeFixture(): Promise<Fixture> {
  const root = await makeTempDir();
  const contentDir = path.join(root, 'content');
  const outputDir = path.join(root, 'dist');
  const templateDir = path.join(root, 'templates');

  await write(
    path.join(templateDir, 'default.hbs'),
    '<article><h1>{{title}}</h1>{{{body}}}</article>'
  );
  await write(
    path.join(templateDir, 'layouts', 'default.hbs'),
    '<html><body>{{> banner}}<main>{{{body}}}</main></body></html>'
  );
  await write(
    path.join(templateDir, 'partials', 'banner.hbs'),
    '<p class="banner">Banner</p>'
  );

  return { root, contentDir, outputDir, templateDir };
}

async function seedContent(contentDir: string): Promise<void> {
  await write(
    path.join(contentDir, 'a.md'),
    `---
title: Page A
date: 2024-01-01
tags: [one, two]
---
# A
Body **A** here.
`
  );
  await write(
    path.join(contentDir, 'posts', 'b.md'),
    `---
title: Page B
date: 2024-01-02
tags: [three]
---
# B
Body B here.
`
  );
}

async function captureStats(
  options: Parameters<typeof buildSite>[0]
): Promise<{ pages: Awaited<ReturnType<typeof buildSite>>; stats: BuildStats }> {
  let stats: BuildStats | undefined;
  const pages = await buildSite(options, (s) => {
    stats = s;
  });
  return { pages, stats: stats! };
}

describe('.ssg-cache.json manifest', () => {
  it('tracks a hash per page along with cached frontmatter', async () => {
    const fx = await makeFixture();
    await seedContent(fx.contentDir);

    await buildSite({
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templateDir: fx.templateDir,
    });

    const manifest = await readManifest(fx.outputDir);
    expect(manifest.version).toBe(1);
    expect(Object.keys(manifest.pages).sort()).toEqual(['a.md', 'posts/b.md']);

    for (const source of Object.keys(manifest.pages)) {
      const entry = manifest.pages[source];
      expect(entry.hash).toMatch(/^[a-f0-9]{64}$/);
      expect(entry.templateHash).toMatch(/^[a-f0-9]{64}$/);
      expect(entry.page.source).toBe(source);
      expect(entry.page.renderedHtml).toBeTruthy();
    }

    const a = manifest.pages['a.md'].page;
    expect(a.title).toBe('Page A');
    expect(a.tags).toEqual(['one', 'two']);
    expect(a.date).toBe('2024-01-01T00:00:00.000Z');
    expect(a.html).toContain('<strong>A</strong>');
  });
});

describe('incremental builds', () => {
  it('skips every page when nothing changed', async () => {
    const fx = await makeFixture();
    await seedContent(fx.contentDir);
    const options = {
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templateDir: fx.templateDir,
    };

    await buildSite(options);
    const before = await fs.readFile(
      path.join(fx.outputDir, 'posts', 'b.html'),
      'utf-8'
    );

    const { pages, stats } = await captureStats({ ...options, incremental: true });

    expect(pages).toHaveLength(2);
    expect(stats.built).toBe(0);
    expect(stats.skipped).toBe(2);
    expect(stats.total).toBe(2);
    expect(stats.timeSavedMs).toBeGreaterThanOrEqual(0);

    const after = await fs.readFile(
      path.join(fx.outputDir, 'posts', 'b.html'),
      'utf-8'
    );
    expect(after).toBe(before);
  });

  it('rebuilds only the page whose source changed', async () => {
    const fx = await makeFixture();
    await seedContent(fx.contentDir);
    const options = {
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templateDir: fx.templateDir,
    };

    await buildSite(options);
    const bBefore = await fs.readFile(
      path.join(fx.outputDir, 'posts', 'b.html'),
      'utf-8'
    );

    await write(
      path.join(fx.contentDir, 'a.md'),
      `---
title: Page A Updated
date: 2024-01-01
tags: [one, two]
---
# A
New **content**.
`
    );

    const { stats } = await captureStats({ ...options, incremental: true });

    expect(stats.built).toBe(1);
    expect(stats.skipped).toBe(1);

    const a = await fs.readFile(path.join(fx.outputDir, 'a.html'), 'utf-8');
    expect(a).toContain('Page A Updated');
    expect(a).toContain('<strong>content</strong>');

    const bAfter = await fs.readFile(
      path.join(fx.outputDir, 'posts', 'b.html'),
      'utf-8'
    );
    expect(bAfter).toBe(bBefore);

    const index = await fs.readFile(path.join(fx.outputDir, 'index.html'), 'utf-8');
    expect(index).toContain('Page A Updated');
    expect(index).toContain('Page B');
  });

  it('invalidates pages when a template file changes', async () => {
    const fx = await makeFixture();
    await seedContent(fx.contentDir);
    const options = {
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templateDir: fx.templateDir,
    };

    await buildSite(options);

    await write(
      path.join(fx.templateDir, 'default.hbs'),
      '<section class="new"><h1>{{title}}</h1>{{{body}}}</section>'
    );

    const { stats } = await captureStats({ ...options, incremental: true });

    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);

    const a = await fs.readFile(path.join(fx.outputDir, 'a.html'), 'utf-8');
    expect(a).toContain('<section class="new">');
  });

  it('invalidates pages when a partial changes', async () => {
    const fx = await makeFixture();
    await seedContent(fx.contentDir);
    const options = {
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templateDir: fx.templateDir,
    };

    await buildSite(options);
    const aBefore = await fs.readFile(path.join(fx.outputDir, 'a.html'), 'utf-8');
    expect(aBefore).toContain('Banner');

    await write(
      path.join(fx.templateDir, 'partials', 'banner.hbs'),
      '<p class="banner">New Banner</p>'
    );

    const { stats } = await captureStats({ ...options, incremental: true });

    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);

    const a = await fs.readFile(path.join(fx.outputDir, 'a.html'), 'utf-8');
    expect(a).toContain('New Banner');
    expect(a).not.toContain('>Banner<');
  });

  it('prunes removed sources from output and cache', async () => {
    const fx = await makeFixture();
    await seedContent(fx.contentDir);
    const options = {
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templateDir: fx.templateDir,
    };

    await buildSite(options);
    await fs.rm(path.join(fx.contentDir, 'posts', 'b.md'));

    const { pages, stats } = await captureStats({ ...options, incremental: true });

    expect(pages).toHaveLength(1);
    expect(stats.built).toBe(0);
    expect(stats.skipped).toBe(1);

    await expect(
      fs.readFile(path.join(fx.outputDir, 'posts', 'b.html'), 'utf-8')
    ).rejects.toThrow();

    const manifest = await readManifest(fx.outputDir);
    expect(Object.keys(manifest.pages)).toEqual(['a.md']);

    const index = await fs.readFile(path.join(fx.outputDir, 'index.html'), 'utf-8');
    expect(index).not.toContain('Page B');
  });

  it('builds every page when the cache is missing', async () => {
    const fx = await makeFixture();
    await seedContent(fx.contentDir);
    const options = {
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templateDir: fx.templateDir,
    };

    await buildSite(options);
    await fs.rm(path.join(fx.outputDir, CACHE_FILE));

    const { stats } = await captureStats({ ...options, incremental: true });

    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);
  });

  it('does a full rebuild when --clean is set, ignoring the cache', async () => {
    const fx = await makeFixture();
    await seedContent(fx.contentDir);
    const options = {
      contentDir: fx.contentDir,
      outputDir: fx.outputDir,
      templateDir: fx.templateDir,
    };

    await buildSite(options);

    await write(
      path.join(fx.contentDir, 'a.md'),
      '---\ntitle: Cleaned A\n---\n# A\nFresh.'
    );

    const { stats } = await captureStats({
      ...options,
      incremental: true,
      clean: true,
    });

    expect(stats.built).toBe(2);
    expect(stats.skipped).toBe(0);

    const a = await fs.readFile(path.join(fx.outputDir, 'a.html'), 'utf-8');
    expect(a).toContain('Cleaned A');
  });
});

describe('CLI flags', () => {
  it('parses --incremental and --clean', () => {
    const result = parseArgs(['node', 'ssg', 'build', '--incremental', '--clean']);
    expect(result.command).toBe('build');
    expect(result.options.incremental).toBe(true);
    expect(result.options.clean).toBe(true);
  });

  it('keeps incremental and clean off by default', () => {
    const result = parseArgs(['node', 'ssg', 'build']);
    expect(result.options.incremental).toBeFalsy();
    expect(result.options.clean).toBeFalsy();
  });

  it('reports build stats over two incremental CLI runs', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'out');
    const templateDir = path.join(root, 'templates');

    await write(
      path.join(contentDir, 'a.md'),
      '---\ntitle: A\n---\n# A\nHello.'
    );
    await write(
      path.join(contentDir, 'b.md'),
      '---\ntitle: B\n---\n# B\nWorld.'
    );
    await write(
      path.join(templateDir, 'default.hbs'),
      '<article>{{{body}}}</article>'
    );
    await write(
      path.join(templateDir, 'layouts', 'default.hbs'),
      '<html><body>{{{body}}}</body></html>'
    );

    const logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    let messages: string[] = [];
    try {
      await run([
        'node',
        'ssg',
        'build',
        '--content',
        contentDir,
        '--output',
        outputDir,
        '--templates',
        templateDir,
        '--incremental',
      ]);
      await run([
        'node',
        'ssg',
        'build',
        '--content',
        contentDir,
        '--output',
        outputDir,
        '--templates',
        templateDir,
        '--incremental',
      ]);
      messages = logSpy.mock.calls.map((c) => c.join(' '));
    } finally {
      logSpy.mockRestore();
    }
    expect(messages.some((m) => m.includes('2 built, 0 skipped'))).toBe(true);
    expect(messages.some((m) => m.includes('0 built, 2 skipped'))).toBe(true);
    expect(messages.some((m) => m.includes('time saved'))).toBe(true);

    const manifest = await readManifest(outputDir);
    expect(Object.keys(manifest.pages).sort()).toEqual(['a.md', 'b.md']);
  });
});
