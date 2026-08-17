import * as fs from 'fs';
import * as path from 'path';
import { Page, Plugin, BuildResult } from './plugin';
import { renderIndex } from './render';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
}

type LifecycleHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

function collectMarkdownFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) {
    return results;
  }
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMarkdownFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      results.push(full);
    }
  }
  return results;
}

function toSlug(contentDir: string, filePath: string): string {
  const rel = path.relative(contentDir, filePath);
  const ext = path.extname(rel);
  const withoutExt = ext ? rel.slice(0, -ext.length) : rel;
  return withoutExt.split(path.sep).join('/');
}

export class Engine {
  private readonly options: EngineOptions;
  private readonly plugins: Plugin[];

  constructor(options: EngineOptions, plugins: Plugin[]) {
    this.options = options;
    this.plugins = plugins;
  }

  build(): BuildResult {
    const { contentDir, outputDir } = this.options;

    this.emit('onStart');
    this.emit('beforeBuild');

    const files = collectMarkdownFiles(contentDir);
    const pages: Page[] = files.map((file) => {
      const slug = toSlug(contentDir, file);
      const page: Page = {
        slug,
        title: '',
        date: null,
        tags: [],
        html: '',
        rendered: '',
        template: null,
        layout: null,
        frontmatter: {},
        sourcePath: file,
        outputPath: `${slug}.html`,
      };
      for (const plugin of this.plugins) {
        plugin.onFile?.(page);
      }
      return page;
    });

    pages.sort((a, b) => {
      const aDate = a.date;
      const bDate = b.date;
      if (!aDate && !bDate) {
        return a.title.localeCompare(b.title);
      }
      if (!aDate) {
        return 1;
      }
      if (!bDate) {
        return -1;
      }
      return bDate.localeCompare(aDate);
    });

    fs.mkdirSync(outputDir, { recursive: true });

    for (const page of pages) {
      const outFile = path.join(outputDir, page.outputPath);
      fs.mkdirSync(path.dirname(outFile), { recursive: true });
      fs.writeFileSync(outFile, page.rendered);
    }

    const indexPath = path.join(outputDir, 'index.html');
    fs.writeFileSync(indexPath, renderIndex(pages));

    this.emit('afterBuild');
    this.emit('onEnd');

    return { pages, outputDir, indexPath };
  }

  private emit(hook: LifecycleHook): void {
    for (const plugin of this.plugins) {
      plugin[hook]?.();
    }
  }
}
