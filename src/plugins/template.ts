import fs from 'fs';
import path from 'path';
import { Plugin, BuildContext } from '../plugin';
import { TemplateEngine } from '../templates';

export class TemplatePlugin implements Plugin {
  name = 'template';

  async afterBuild(ctx: BuildContext): Promise<void> {
    if (!fs.existsSync(ctx.outputDir)) {
      fs.mkdirSync(ctx.outputDir, { recursive: true });
    }

    const engine = new TemplateEngine({ templatesDir: ctx.templatesDir });
    engine.init();

    for (const page of ctx.pages) {
      const html = engine.renderPage(page);
      fs.writeFileSync(path.join(ctx.outputDir, `${page.slug}.html`), html);
    }

    const indexHtml = engine.renderIndex(ctx.pages);
    fs.writeFileSync(path.join(ctx.outputDir, 'index.html'), indexHtml);
  }
}
