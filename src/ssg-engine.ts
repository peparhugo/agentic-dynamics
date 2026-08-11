import fs from 'fs';
import path from 'path';
import { Plugin, BuildContext } from './plugin';
import { PageData } from './types';

export class SsgEngine {
  plugins: Plugin[];

  constructor(plugins: Plugin[]) {
    this.plugins = plugins;
  }

  async build(options: {
    contentDir: string;
    outputDir: string;
    templatesDir: string;
  }): Promise<void> {
    const ctx: BuildContext = {
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
      pages: [],
    };

    await this.runHook('onStart', ctx);
    await this.runHook('beforeBuild', ctx);

    if (!fs.existsSync(ctx.contentDir)) {
      throw new Error(`Content directory not found: ${ctx.contentDir}`);
    }

    const files = fs.readdirSync(ctx.contentDir).filter((f) => f.endsWith('.md'));

    for (const file of files) {
      const slug = file.replace(/\.md$/, '');
      const rawContent = fs.readFileSync(path.join(ctx.contentDir, file), 'utf-8');

      let page: PageData = {
        slug,
        frontmatter: { title: slug, date: '', tags: [] },
        content: rawContent,
        html: '',
      };

      for (const plugin of this.plugins) {
        if (plugin.onFile) {
          const result = await plugin.onFile(page, ctx);
          if (result !== undefined) {
            page = result;
          }
        }
      }

      ctx.pages.push(page);
    }

    await this.runHook('afterBuild', ctx);
    await this.runHook('onEnd', ctx);
  }

  private async runHook(
    hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd',
    ctx: BuildContext
  ): Promise<void> {
    for (const plugin of this.plugins) {
      const fn = plugin[hook];
      if (fn) {
        await fn.call(plugin, ctx);
      }
    }
  }
}
