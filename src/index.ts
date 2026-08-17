#!/usr/bin/env node
import { runCli } from './cli';

export { parseMarkdown, Frontmatter, ParsedDocument } from './markdown';
export {
  build,
  escapeHtml,
  Page,
  BuildOptions,
  BuildResult,
  BuildStats,
} from './builder';
export {
  TemplateEngine,
  RenderContext,
  DEFAULT_TEMPLATE_NAME,
  DEFAULT_LAYOUT_NAME,
} from './templates';
export { parseArgs, runCli, CliOptions } from './cli';
export {
  startServer,
  injectLiveReloadScript,
  ServeOptions,
  DevServer,
  LIVE_RELOAD_PATH,
} from './server';
export { Plugin } from './plugin';
export { Engine, EngineOptions } from './engine';
export { loadConfig, SsgConfig } from './config';
export {
  sha256,
  hashTemplates,
  defaultCacheFile,
  loadManifest,
  saveManifest,
  CacheEntry,
  CacheManifest,
  CACHE_FILE_NAME,
  CACHE_VERSION,
} from './cache';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/templates';
export { DevServerPlugin } from './plugins/server';

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}
