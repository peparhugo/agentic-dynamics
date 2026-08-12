import { access, mkdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import Module from 'node:module';
import ts from 'typescript';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { Plugin, PluginConfig, PluginContext } from './plugin';

export interface PageMetadata { title?: string; date?: string; tags: string[]; [key: string]: unknown; }
export interface Page { sourcePath: string; outputPath: string; url: string; metadata: PageMetadata; content: string; }
export interface BuildOptions {
  contentDir?: string; outputDir?: string; templatesDir?: string; defaultTemplate?: string; defaultLayout?: string;
  plugins?: PluginConfig[]; configFile?: string;
}
export { Plugin, PluginConfig, PluginContext } from './plugin';

type Config = Partial<BuildOptions> & { plugins?: PluginConfig[] };
let tsLoaderInstalled = false;

function installTsLoader(): void {
  if (tsLoaderInstalled) return;
  tsLoaderInstalled = true;
  require.extensions['.ts'] = (module: NodeModule, filename: string) => {
    const source = require('node:fs').readFileSync(filename, 'utf8');
    (module as Module & { _compile: (code: string, file: string) => void })._compile(
      ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText,
      filename
    );
  };
}

async function loadConfig(file: string): Promise<Config> {
  try { await access(file); } catch { return {}; }
  installTsLoader();
  const loaded = require(file) as { default?: Config } & Config;
  return loaded.default || loaded;
}

async function resolvePlugins(configured: PluginConfig[], baseDirectory: string): Promise<Plugin[]> {
  const plugins: Plugin[] = [];
  for (const configuredPlugin of configured) {
    let plugin: Plugin | (() => Plugin | Promise<Plugin>) = configuredPlugin as Plugin;
    if (typeof configuredPlugin === 'string') {
      installTsLoader();
      const loaded = require(path.resolve(baseDirectory, configuredPlugin)) as { default?: Plugin };
      plugin = loaded.default || loaded;
    }
    if (typeof plugin === 'function') plugin = await plugin();
    plugins.push(plugin as Plugin);
  }
  return plugins;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const configPath = path.resolve(options.configFile || './ssg.config.ts');
  const config = await loadConfig(configPath);
  const merged: BuildOptions = {
    ...config,
    ...options,
    plugins: [...(config.plugins || []), ...(options.plugins || [])]
  };
  const context: PluginContext = {
    options: merged,
    contentDir: path.resolve(merged.contentDir || './content'),
    outputDir: path.resolve(merged.outputDir || './dist'),
    templatesDir: path.resolve(merged.templatesDir || './templates'),
    pages: [], files: new Map(), emitFile(filePath, contents) { this.files.set(filePath, contents); }
  };
  const plugins = [new MarkdownPlugin(), ...await resolvePlugins(merged.plugins || [], path.dirname(configPath)), new TemplatePlugin()];
  for (const plugin of plugins) await plugin.onStart?.(context);
  for (const plugin of plugins) await plugin.beforeBuild?.(context);
  for (let index = 0; index < context.pages.length; index += 1) {
    const originalPage = context.pages[index];
    let page = originalPage;
    for (const plugin of plugins) page = (await plugin.onFile?.(page, context)) || page;
    context.pages[index] = page;
  }
  await rm(context.outputDir, { recursive: true, force: true });
  await mkdir(context.outputDir, { recursive: true });
  for (const plugin of plugins) await plugin.afterBuild?.(context);
  for (const [filePath, contents] of context.files) {
    await mkdir(path.dirname(filePath), { recursive: true });
    await writeFile(filePath, contents);
  }
  for (const plugin of plugins) await plugin.onEnd?.(context);
  return context.pages;
}
