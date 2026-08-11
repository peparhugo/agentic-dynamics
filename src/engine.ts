import * as fs from 'fs';
import * as path from 'path';
import { Page } from './types';
import { Plugin, BuildContext } from './plugin';
import { loadConfig } from './config';
import { MarkdownPlugin } from '../plugins/markdown-plugin';
import { TemplatePlugin } from '../plugins/template-plugin';

function getDefaultPlugins(): Plugin[] {
  return [
    new MarkdownPlugin(),
    new TemplatePlugin(),
  ];
}

export class SsgEngine {
  private plugins: Plugin[];

  constructor(additionalPlugins?: Plugin[]) {
    const config = loadConfig();
    const configPlugins = config.plugins || [];
    if (configPlugins.length > 0) {
      this.plugins = [...configPlugins, ...(additionalPlugins || [])];
    } else {
      this.plugins = [...getDefaultPlugins(), ...(additionalPlugins || [])];
    }
  }

  build(contentDir: string, outputDir: string, templatesDir?: string): void {
    const absoluteContent = path.resolve(contentDir);

    if (!fs.existsSync(absoluteContent)) {
      throw new Error(`Content directory does not exist: ${absoluteContent}`);
    }

    const ctx: BuildContext = {
      contentDir: absoluteContent,
      outputDir,
      templatesDir,
    };

    for (const plugin of this.plugins) {
      if (plugin.setContext) plugin.setContext(ctx);
    }

    for (const plugin of this.plugins) {
      if (plugin.onStart) plugin.onStart();
    }

    const files = fs.readdirSync(absoluteContent).filter((f) => f.endsWith('.md'));

    const pages: Page[] = files.map((file) => ({
      slug: path.basename(file, '.md'),
      title: path.basename(file, '.md'),
      content: fs.readFileSync(path.join(absoluteContent, file), 'utf-8'),
      html: '',
    }));

    for (const plugin of this.plugins) {
      if (plugin.beforeBuild) plugin.beforeBuild();
    }

    for (const page of pages) {
      for (const plugin of this.plugins) {
        if (plugin.onFile) plugin.onFile(page);
      }
    }

    pages.sort((a, b) => {
      if (a.date && b.date) {
        return b.date.localeCompare(a.date);
      }
      if (a.date) return -1;
      if (b.date) return 1;
      return a.title.localeCompare(b.title);
    });

    for (const plugin of this.plugins) {
      if (plugin.afterBuild) plugin.afterBuild(pages);
    }

    for (const plugin of this.plugins) {
      if (plugin.onEnd) plugin.onEnd();
    }
  }
}
