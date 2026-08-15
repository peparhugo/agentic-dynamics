import fs from 'fs';
import path from 'path';
import { TemplateEngine } from '../templates';
import { renderIndex, renderPage } from '../render';
import type { Plugin, PluginContext } from './types';

/**
 * Resolve the template directory. An explicitly requested directory that does
 * not exist is an error; the default `./templates` directory is only used when
 * present so sites without templates keep the built-in rendering.
 */
export function resolveTemplateDir(
  templateDir: string | undefined
): string | null {
  if (templateDir !== undefined) {
    const dir = path.resolve(templateDir);
    if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) {
      throw new Error(`Template directory does not exist: ${dir}`);
    }
    return dir;
  }
  const dir = path.resolve('templates');
  return fs.existsSync(dir) && fs.statSync(dir).isDirectory() ? dir : null;
}

/**
 * Built-in template plugin: renders every collected page (and the site index)
 * through Handlebars templates, layouts and partials when a template
 * directory is present, otherwise through the built-in rendering. Writes the
 * finished HTML files into the output directory.
 */
export class TemplatePlugin implements Plugin {
  readonly name = 'template';

  private engine: TemplateEngine | null = null;

  beforeBuild(context: PluginContext): void {
    const templateDir = resolveTemplateDir(context.templateDir);
    this.engine =
      templateDir === null
        ? null
        : new TemplateEngine({
            templateDir,
            defaultTemplate: context.defaultTemplate,
            defaultLayout: context.defaultLayout,
          });
  }

  afterBuild(context: PluginContext): void {
    const engine = this.engine;
    for (const page of context.pages) {
      let html =
        typeof page.renderedHtml === 'string' && page.renderedHtml.length > 0
          ? page.renderedHtml
          : engine && engine.hasContent()
            ? engine.renderPage(page)
            : renderPage(page);
      if (page.renderedHtml === undefined || page.renderedHtml.length === 0) {
        page.renderedHtml = html;
      }
      fs.writeFileSync(path.join(context.outputDir, `${page.slug}.html`), html);
    }
    const indexHtml =
      engine && engine.hasContent() ? engine.renderIndex(context.pages) : renderIndex(context.pages);
    fs.writeFileSync(path.join(context.outputDir, 'index.html'), indexHtml);
  }

  /** Access to the underlying template engine (may be null). */
  getEngine(): TemplateEngine | null {
    return this.engine;
  }
}
