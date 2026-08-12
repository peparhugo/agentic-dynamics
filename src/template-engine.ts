import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';
import * as ejs from 'ejs';

export type TemplateEngine = 'hbs' | 'ejs' | 'html';

export interface TemplateContext {
  [key: string]: unknown;
}

const TEMPLATE_EXTENSIONS = ['.hbs', '.ejs', '.html'];

export function detectEngine(filePath: string): TemplateEngine {
  const lower = filePath.toLowerCase();
  if (lower.endsWith('.ejs')) return 'ejs';
  if (lower.endsWith('.html')) return 'html';
  return 'hbs';
}

export function findTemplateFile(templatesDir: string, name: string): string | null {
  if (!templatesDir) return null;
  const base = path.isAbsolute(name) ? name : path.join(templatesDir, name);
  if (TEMPLATE_EXTENSIONS.some((ext) => base.toLowerCase().endsWith(ext))) {
    return fs.existsSync(base) && fs.statSync(base).isFile() ? base : null;
  }
  for (const ext of TEMPLATE_EXTENSIONS) {
    const candidate = `${base}${ext}`;
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
  }
  return null;
}

function registerPartials(env: typeof Handlebars, partialsDir: string): void {
  if (!fs.existsSync(partialsDir)) return;
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (
        entry.isFile() &&
        TEMPLATE_EXTENSIONS.some((ext) => entry.name.toLowerCase().endsWith(ext))
      ) {
        const relative = path.relative(partialsDir, full).replace(/\\/g, '/');
        const name = relative.replace(/\.[^/.]+$/, '');
        env.registerPartial(name, fs.readFileSync(full, 'utf8'));
      }
    }
  };
  walk(partialsDir);
}

function renderWithEngine(
  filePath: string,
  source: string,
  context: TemplateContext,
  templatesDir: string
): string {
  const engine = detectEngine(filePath);
  if (engine === 'ejs') {
    return ejs.render(source, context, {
      filename: filePath,
      root: templatesDir,
      views: [path.join(templatesDir, 'partials')],
      async: false,
    });
  }
  if (engine === 'html') {
    return source;
  }
  const env = Handlebars.create();
  registerPartials(env, path.join(templatesDir, 'partials'));
  return env.compile(source)(context);
}

export function renderNamedTemplate(
  templatesDir: string,
  name: string,
  context: TemplateContext
): { html: string; filePath: string } | null {
  const filePath = findTemplateFile(templatesDir, name);
  if (!filePath) return null;
  const source = fs.readFileSync(filePath, 'utf8');
  return { html: renderWithEngine(filePath, source, context, templatesDir), filePath };
}

export function renderLayoutTemplate(
  templatesDir: string,
  layoutName: string,
  body: string,
  context: TemplateContext
): string | null {
  if (!templatesDir) return null;
  const layoutsDir = path.join(templatesDir, 'layouts');
  const filePath = findTemplateFile(layoutsDir, layoutName);
  if (!filePath) return null;
  const source = fs.readFileSync(filePath, 'utf8');
  return renderWithEngine(filePath, source, { ...context, body }, templatesDir);
}
