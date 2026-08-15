import Handlebars from 'handlebars';
import { promises as fs } from 'fs';
import path from 'path';

export interface TemplateEngine {
  registerPartial(name: string, content: string): void;
  render(templateContent: string, data: Record<string, unknown>): string;
}

let defaultTemplateDir = './templates';
let defaultLayoutName = 'default';
let engine: TemplateEngine | null = null;

export function setTemplateDir(dir: string): void {
  defaultTemplateDir = dir;
}

export function setDefaultLayout(name: string): void {
  defaultLayoutName = name;
}

export function createTemplateEngine(): TemplateEngine {
  return {
    registerPartial(name: string, content: string): void {
      Handlebars.registerPartial(name, content);
    },
    render(templateContent: string, data: Record<string, unknown>): string {
      const template = Handlebars.compile(templateContent);
      return template(data);
    }
  };
}

export function getEngine(): TemplateEngine {
  if (!engine) {
    engine = createTemplateEngine();
  }
  return engine;
}

export async function loadPartials(templateDir: string): Promise<void> {
  const partialsDir = path.join(templateDir, 'partials');
  const eng = getEngine();

  try {
    const files = await fs.readdir(partialsDir);
    for (const file of files) {
      if (file.endsWith('.hbs')) {
        const filePath = path.join(partialsDir, file);
        const content = await fs.readFile(filePath, 'utf-8');
        const partialName = file.replace(/\.hbs$/, '');
        eng.registerPartial(partialName, content);
      }
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
      throw error;
    }
  }
}

export async function loadTemplate(templateName: string, templateDir: string): Promise<string> {
  const templatePath = path.join(templateDir, `${templateName}.hbs`);
  try {
    return await fs.readFile(templatePath, 'utf-8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      // Try loading from layouts directory
      const layoutPath = path.join(templateDir, 'layouts', `${templateName}.hbs`);
      return await fs.readFile(layoutPath, 'utf-8');
    }
    throw error;
  }
}

export async function loadLayout(layoutName: string, templateDir: string): Promise<string> {
  const layoutPath = path.join(templateDir, 'layouts', `${layoutName}.hbs`);
  try {
    return await fs.readFile(layoutPath, 'utf-8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      // Return a default layout if the specified one doesn't exist
      return '{{body}}';
    }
    throw error;
  }
}

export async function renderPage(
  pageHtml: string,
  templateContent: string | null,
  layoutName: string | null,
  pageData: Record<string, unknown>,
  templateDir: string
): Promise<string> {
  const eng = getEngine();

  // Step 1: If a template is specified, render the page with the template
  let html = pageHtml;
  if (templateContent) {
    html = eng.render(templateContent, { ...pageData, body: pageHtml });
  }

  // Step 2: If a layout is specified, wrap with layout
  if (layoutName) {
    const layout = await loadLayout(layoutName, templateDir);
    html = eng.render(layout, { ...pageData, body: html });
  }

  return html;
}
