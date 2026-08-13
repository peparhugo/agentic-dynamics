import fs from 'fs';
import path from 'path';
import { Plugin, PluginContext } from '../plugin';
import { TemplateEngine } from '../templates';

export interface TemplatePluginOptions {
  templatesDir?: string;
  layoutsDir?: string;
  partialsDir?: string;
}

export class TemplatePlugin implements Plugin {
  name = 'template-plugin';
  private templateEngine: TemplateEngine | undefined;
  private options: TemplatePluginOptions = {};

  constructor(options?: TemplatePluginOptions) {
    this.options = options || {};
  }

  async onStart(context: PluginContext): Promise<void> {
    const templatesDir = this.options.templatesDir || (context.templatesDir as string) || './templates';

    if (fs.existsSync(templatesDir)) {
      this.templateEngine = new TemplateEngine({
        templatesDir,
        layoutsDir: this.options.layoutsDir || path.join(templatesDir, 'layouts'),
        partialsDir: this.options.partialsDir || path.join(templatesDir, 'partials'),
      });
    }
  }

  getTemplateEngine(): TemplateEngine | undefined {
    return this.templateEngine;
  }
}
