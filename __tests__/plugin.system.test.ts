import fs from 'fs';
import os from 'os';
import path from 'path';
import { SiteEngine } from '../src/engine';
import { Plugin, PluginContext, loadConfig, toPlugin } from '../src/plugin';
import { buildSite } from '../src/site';
import { Page, BuildResult } from '../src/types';

interface TempDir {
  dir: string;
  cleanup: () => void;
}

function makeTempDir(): TempDir {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-plugin-'));
  return { dir, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

describe('plugin system sanity', () => {
  it('runs all hooks in order', () => {
    const calls: string[] = [];
    class Tracking implements Plugin {
      name = 'tracking';
      onStart = (): void => { calls.push('onStart'); };
      beforeBuild = (): void => { calls.push('beforeBuild'); };
      afterBuild = (): void => { calls.push('afterBuild'); };
      onFile = (): void => { calls.push('onFile'); };
      onEnd = (): void => { calls.push('onEnd'); };
    }

    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    fs.mkdirSync(contentDir, { recursive: true });
    fs.writeFileSync(path.join(contentDir, 'a.md'), '# Hi');
    const engine = new SiteEngine({
      contentDir,
      outputDir: path.join(dir, 'dist'),
      cwd: dir,
      extraPlugins: [new Tracking()],
    });
    engine.build();
    cleanup();
    expect(calls).toEqual(['onStart', 'beforeBuild', 'onFile', 'afterBuild', 'onEnd']);
  });

  it('lets an onFile plugin modify pages', () => {
    class Upper implements Plugin {
      name = 'upper';
      onFile = (page: Page): Page => ({ ...page, title: page.title.toUpperCase() });
    }
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    fs.mkdirSync(contentDir, { recursive: true });
    fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: hello\n---\nBody');
    buildSite(contentDir, outDir, undefined);
    expect(
      fs.readFileSync(path.join(outDir, 'hello.html'), 'utf8')
    ).toContain('hello');
    const engine = new SiteEngine({ contentDir, outputDir: outDir, extraPlugins: [new Upper()] });
    engine.build();
    const page = fs.readFileSync(path.join(outDir, 'hello.html'), 'utf8');
    expect(page).toContain('HELLO');
    cleanup();
  });

  it('lets an afterBuild plugin write extra files', () => {
    class Sitemap implements Plugin {
      name = 'sitemap';
      afterBuild = (ctx: PluginContext): void => {
        fs.writeFileSync(path.join(ctx.outputDir, 'sitemap.xml'), '<urlset/>');
        ctx.files.push('sitemap.xml');
      };
    }
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    fs.mkdirSync(contentDir, { recursive: true });
    fs.writeFileSync(path.join(contentDir, 'a.md'), '# Hi');
    const engine = new SiteEngine({
      contentDir,
      outputDir: path.join(dir, 'dist'),
      extraPlugins: [new Sitemap()],
    });
    const result = engine.build();
    expect(result.files).toContain('sitemap.xml');
    expect(fs.existsSync(path.join(result.outputDir, 'sitemap.xml'))).toBe(true);
    cleanup();
  });

  it('loads plugins from ssg.config.ts in cwd', () => {
    const { dir, cleanup } = makeTempDir();
    fs.writeFileSync(
      path.join(dir, 'ssg.config.ts'),
      "import { Plugin } from '" +
        path.resolve(__dirname, '../src/plugin') +
        "';\nclass Cfg implements Plugin { name = 'cfg'; }\nexport default { plugins: [new Cfg()] };"
    );
    const config = loadConfig(dir, 'ssg.config.ts');
    expect(Array.isArray(config.plugins)).toBe(true);
    expect((config.plugins as unknown[]).length).toBe(1);
    cleanup();
  });

  it('normalizes a plugin class via toPlugin', () => {
    class P implements Plugin {
      name = 'p';
    }
    const plugin = toPlugin(P);
    expect(plugin).not.toBeNull();
    expect(plugin!.name).toBe('p');
  });

  it('does not break the public buildSite API', () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    fs.mkdirSync(contentDir, { recursive: true });
    fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: One\n---\nBody');
    const result = buildSite(contentDir, path.join(dir, 'dist'));
    expect(result.pages).toBe(1);
    cleanup();
  });
});
