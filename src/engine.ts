import fs from 'fs';
import path from 'path';
import { Page, BuildOptions } from './types';
import { Plugin, PluginContext, PluginPipeline } from './plugin';
import { collectMarkdownFiles } from './collect';
import { slugify } from './parse';

export interface SSGOptions {
  options: BuildOptions;
  plugins: Plugin[];
}

export class SSG {
  readonly options: BuildOptions;
  private pipeline: PluginPipeline;
  private ctx: PluginContext;
  private started = false;

  constructor(opts: SSGOptions) {
    this.options = opts.options;
    this.pipeline = new PluginPipeline(opts.plugins);
    this.ctx = {
      engine: this,
      options: this.options,
      pages: [],
      writeFile: (relPath, content) => {
        const out = path.join(this.options.outputDir, relPath);
        fs.mkdirSync(path.dirname(out), { recursive: true });
        fs.writeFileSync(out, content, 'utf-8');
      },
    };
  }

  get plugins(): Plugin[] {
    return this.pipeline.plugins;
  }

  start(): this {
    if (this.started) return this;
    this.started = true;
    this.pipeline.run('onStart', this.ctx);
    return this;
  }

  build(): Page[] {
    fs.rmSync(this.options.outputDir, { recursive: true, force: true });
    fs.mkdirSync(this.options.outputDir, { recursive: true });

    this.ctx.pages = [];
    this.pipeline.run('beforeBuild', this.ctx);

    for (const file of collectMarkdownFiles(this.options.contentDir)) {
      this.ctx.currentFile = file;
      const raw = fs.readFileSync(file, 'utf-8');
      const page: Page = { slug: slugify(file), content: raw, html: '', data: {} };
      const result = this.pipeline.runFile(page, this.ctx);
      this.ctx.pages.push(result);
      this.ctx.writeFile(`${result.slug}.html`, result.html);
    }

    this.pipeline.run('afterBuild', this.ctx);
    this.pipeline.run('onEnd', this.ctx);
    return this.ctx.pages;
  }
}

export function createSSG(options: SSGOptions): SSG {
  return new SSG(options);
}
