import * as fs from 'fs';
import * as path from 'path';
import type { Plugin, SsgContext } from '../plugin';
import { renderIndex, renderPage, type SiteConfig } from '../template';
import type { Page } from '../types';

export class TemplatePlugin implements Plugin {
  readonly name = 'template';

  async onFile(page: Page, context: SsgContext): Promise<void> {
    const config: SiteConfig = context.siteConfig;
    const html = renderPage(page, config);
    fs.mkdirSync(path.dirname(page.outputPath), { recursive: true });
    fs.writeFileSync(page.outputPath, html, 'utf8');
  }

  async afterBuild(context: SsgContext): Promise<void> {
    const config: SiteConfig = context.siteConfig;
    fs.mkdirSync(context.outputDir, { recursive: true });
    fs.writeFileSync(
      path.join(context.outputDir, 'index.html'),
      renderIndex(context.pages, config),
      'utf8'
    );
  }
}
