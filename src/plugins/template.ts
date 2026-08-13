import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { BuildContext, Plugin } from '../plugin.js';
import { renderIndex, renderPage, type Page } from '../site.js';

type TemplateEngine = ReturnType<typeof Handlebars.create>;

async function filesIn(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  return (await Promise.all(entries.map((entry) => {
    const fullPath = path.join(directory, entry.name);
    return entry.isDirectory() ? filesIn(fullPath) : [fullPath];
  }))).flat();
}

async function readTemplate(filePath: string): Promise<string | undefined> {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function registerPartials(engine: TemplateEngine, templatesDir: string): Promise<void> {
  try {
    const partialsDir = path.join(templatesDir, 'partials');
    await Promise.all((await filesIn(partialsDir)).map(async (partialPath) => {
      if (path.extname(partialPath) !== '.hbs') return;
      const name = path.relative(partialsDir, partialPath).slice(0, -4).split(path.sep).join('/');
      engine.registerPartial(name, await fs.readFile(partialPath, 'utf8'));
    }));
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
}

export class TemplatePlugin implements Plugin {
  private engine = Handlebars.create();

  async onStart(context: BuildContext): Promise<void> {
    this.engine = Handlebars.create();
    await registerPartials(this.engine, context.templatesDir);
  }

  async onFile(page: Page, context: BuildContext): Promise<void> {
    const templateName = page.template ?? 'default';
    const template = await readTemplate(path.join(context.templatesDir, `${templateName}.hbs`));
    const content = template === undefined ? renderPage(page) : this.engine.compile(template)({ ...page, body: page.html });
    const layout = await readTemplate(path.join(context.templatesDir, 'layouts', `${templateName}.hbs`))
      ?? await readTemplate(path.join(context.templatesDir, 'layouts', 'default.hbs'));
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, layout === undefined ? content : this.engine.compile(layout)({ ...page, body: content }), 'utf8');
  }

  async afterBuild(context: BuildContext): Promise<void> {
    await fs.writeFile(path.join(context.outputDir, 'index.html'), renderIndex(context.pages), 'utf8');
  }
}
