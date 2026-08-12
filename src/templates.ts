import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import ejs from 'ejs';

export const DEFAULT_TEMPLATES_DIR = './templates';
export const DEFAULT_TEMPLATE = 'default';
export const DEFAULT_LAYOUT = 'default';

const TEMPLATE_EXTENSIONS: readonly string[] = ['.hbs', '.ejs'];

export type TemplateEngine = 'handlebars' | 'ejs';

export interface TemplateFile {
  /** Filename-derived identifier (e.g. `page` for `page.hbs`). */
  name: string;
  /** Which engine renders this file, based on its extension. */
  engine: TemplateEngine;
  /** Raw template source. */
  source: string;
  /** Absolute path, used to resolve EJS includes. */
  absPath: string;
}

export interface TemplateSet {
  /** The root templates directory. */
  dir: string;
  /** Page templates found directly under the templates directory. */
  templates: Map<string, TemplateFile>;
  /** Layout templates found under `templates/layouts/`. */
  layouts: Map<string, TemplateFile>;
  /** Partials found under `templates/partials/`. */
  partials: Map<string, TemplateFile>;
}

/** Pick the engine for a template file based on its extension. */
export function detectEngine(fileName: string): TemplateEngine {
  return path.extname(fileName).toLowerCase() === '.ejs' ? 'ejs' : 'handlebars';
}

function readTemplateFiles(dir: string): TemplateFile[] {
  if (!fs.existsSync(dir)) return [];

  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter(
      (entry) =>
        entry.isFile() &&
        TEMPLATE_EXTENSIONS.includes(path.extname(entry.name).toLowerCase())
    )
    .map((entry) => {
      const absPath = path.join(dir, entry.name);
      return {
        name: path.basename(entry.name, path.extname(entry.name)),
        engine: detectEngine(entry.name),
        source: fs.readFileSync(absPath, 'utf8'),
        absPath,
      };
    });
}

function toMap(files: TemplateFile[]): Map<string, TemplateFile> {
  return new Map(files.map((file) => [file.name, file]));
}

/**
 * Load every template, layout, and partial from the given directory. A missing
 * directory simply yields an empty set so callers can fall back gracefully.
 */
export function loadTemplates(dir: string = DEFAULT_TEMPLATES_DIR): TemplateSet {
  return {
    dir,
    templates: toMap(readTemplateFiles(dir)),
    layouts: toMap(readTemplateFiles(path.join(dir, 'layouts'))),
    partials: toMap(readTemplateFiles(path.join(dir, 'partials'))),
  };
}

/** EJS layouts written per the spec use `{{{body}}}`; map it to EJS output syntax. */
function normalizeEjsBody(source: string): string {
  return source.replace(/\{\{\{body\}\}\}/g, '<%- body %>');
}

/**
 * Render a single template file against a context object. Handlebars partials
 * are registered per-render (on a fresh instance) to avoid global state leaks;
 * EJS resolves `include()` calls relative to the template's own file.
 */
export function renderTemplateFile(
  file: TemplateFile,
  context: Record<string, unknown>,
  partials: TemplateFile[] = []
): string {
  if (file.engine === 'ejs') {
    return ejs.render(normalizeEjsBody(file.source), context, {
      filename: file.absPath,
      cache: false,
    });
  }

  const handlebars = Handlebars.create();
  for (const partial of partials) {
    handlebars.registerPartial(partial.name, partial.source);
  }
  return handlebars.compile(file.source)(context);
}
