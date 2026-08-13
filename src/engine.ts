import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { BuildOptions, BuildStats, Page, Plugin, PluginContext, PluginPage } from './plugin';

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  buildTimeMs: number;
  page: PluginPage;
}

interface CacheManifest {
  version: 1;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Record<string, CacheEntry>;
}

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

async function dependencyHash(directory: string): Promise<string> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return hash('');
    throw error;
  }
  const values = await Promise.all(entries.sort((left, right) => left.name.localeCompare(right.name)).map(async (entry) => {
    const location = path.join(directory, entry.name);
    if (entry.isDirectory()) return `${entry.name}/${await dependencyHash(location)}`;
    return `${entry.name}:${hash(await fs.readFile(location, 'utf8'))}`;
  }));
  return hash(values.join('\n'));
}

async function readManifest(file: string): Promise<CacheManifest | undefined> {
  try {
    const parsed = JSON.parse(await fs.readFile(file, 'utf8')) as CacheManifest;
    const validPages = parsed.pages && typeof parsed.pages === 'object'
      && Object.values(parsed.pages).every((entry) => entry
        && typeof entry.sourceHash === 'string'
        && typeof entry.templateHash === 'string'
        && typeof entry.buildTimeMs === 'number'
        && typeof entry.page?.outputPath === 'string');
    return parsed.version === 1 && validPages ? parsed : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const location = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(location);
    return /\.md$/i.test(entry.name) ? [location] : [];
  }));
  return files.flat().sort();
}

export class SsgEngine {
  readonly options: PluginContext['options'];
  stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, durationMs: 0, timeSavedMs: 0 };
  private plugins: Plugin[] = [];
  private pages: PluginPage[] = [];
  private started = false;

  constructor(private readonly buildOptions: BuildOptions = {}, private readonly additionalPlugins: Plugin[] = []) {
    this.options = {
      contentDir: path.resolve(buildOptions.contentDir ?? './content'),
      outputDir: path.resolve(buildOptions.outputDir ?? './dist'),
      templatesDir: path.resolve(buildOptions.templatesDir ?? './templates')
    };
  }

  private context(): PluginContext {
    return { options: this.options, pages: this.pages, build: () => this.build() };
  }

  async start(): Promise<void> {
    if (this.started) return;
    const configured = await loadPlugins(this.buildOptions);
    this.plugins = [new MarkdownPlugin(), ...configured, new TemplatePlugin(), ...this.additionalPlugins];
    this.started = true;
    for (const plugin of this.plugins) await plugin.onStart?.(this.context());
  }

  async build(): Promise<Page[]> {
    const buildStarted = performance.now();
    await this.start();
    this.pages = [];
    for (const plugin of this.plugins) await plugin.beforeBuild?.(this.context());
    const files = await markdownFiles(this.options.contentDir);
    const cacheFile = path.join(path.dirname(this.options.outputDir), '.ssg-cache.json');
    const templateHash = await dependencyHash(this.options.templatesDir);
    const cached = this.buildOptions.incremental && !this.buildOptions.clean
      ? await readManifest(cacheFile)
      : undefined;
    const manifestMatches = cached
      && cached.contentDir === this.options.contentDir
      && cached.outputDir === this.options.outputDir
      && cached.templatesDir === this.options.templatesDir;
    const previous = manifestMatches ? cached.pages : {};
    const cleanBuild = !this.buildOptions.incremental || this.buildOptions.clean || !manifestMatches;
    if (cleanBuild) await fs.rm(this.options.outputDir, { recursive: true, force: true });
    await fs.mkdir(this.options.outputDir, { recursive: true });

    const next: CacheManifest = {
      version: 1,
      contentDir: this.options.contentDir,
      outputDir: this.options.outputDir,
      templatesDir: this.options.templatesDir,
      pages: {}
    };
    let pagesBuilt = 0;
    let pagesSkipped = 0;
    let timeSavedMs = 0;

    for (const file of files) {
      const sourceRelative = path.relative(this.options.contentDir, file);
      const relative = sourceRelative.replace(/\.md$/i, '.html');
      const source = await fs.readFile(file, 'utf8');
      const sourceHash = hash(source);
      const entry = previous[sourceRelative];
      if (entry && entry.sourceHash === sourceHash && entry.templateHash === templateHash) {
        try {
          if ((await fs.stat(entry.page.outputPath)).isFile()) {
            const page = { ...entry.page, filePath: file, source };
            this.pages.push(page);
            next.pages[sourceRelative] = { ...entry, page };
            pagesSkipped += 1;
            timeSavedMs += entry.buildTimeMs;
            continue;
          }
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
        }
      }
      const pageStarted = performance.now();
      const page: PluginPage = {
        title: path.basename(file, path.extname(file)),
        tags: [],
        outputPath: path.join(this.options.outputDir, relative),
        url: relative.split(path.sep).map(encodeURIComponent).join('/'),
        filePath: file,
        source,
        data: {},
        content: '',
        output: ''
      };
      for (const plugin of this.plugins) await plugin.onFile?.(page);
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      await fs.writeFile(page.outputPath, page.output);
      if (entry && entry.page.outputPath !== page.outputPath) await fs.rm(entry.page.outputPath, { force: true });
      this.pages.push(page);
      next.pages[sourceRelative] = {
        sourceHash,
        templateHash,
        buildTimeMs: performance.now() - pageStarted,
        page
      };
      pagesBuilt += 1;
    }

    for (const [sourceRelative, entry] of Object.entries(previous)) {
      if (!next.pages[sourceRelative]) await fs.rm(entry.page.outputPath, { force: true });
    }

    this.pages.sort((left, right) => {
      if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
      return left.title.localeCompare(right.title);
    });
    for (const plugin of this.plugins) await plugin.afterBuild?.(this.context());
    if (this.buildOptions.incremental) {
      const temporary = `${cacheFile}.${process.pid}.tmp`;
      await fs.writeFile(temporary, `${JSON.stringify(next, null, 2)}\n`);
      await fs.rename(temporary, cacheFile);
    } else {
      await fs.rm(cacheFile, { force: true });
    }
    this.stats = {
      pagesBuilt,
      pagesSkipped,
      durationMs: performance.now() - buildStarted,
      timeSavedMs
    };
    return this.pages.map(({ title, date, tags, outputPath, url }) => ({ title, date, tags, outputPath, url }));
  }

  async stop(): Promise<void> {
    if (!this.started) return;
    for (const plugin of this.plugins) await plugin.onEnd?.(this.context());
    this.started = false;
  }
}
