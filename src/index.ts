#!/usr/bin/env node
import { runCli } from './cli';

export { parseMarkdown, Frontmatter, ParsedDocument } from './markdown';
export {
  build,
  escapeHtml,
  Page,
  BuildOptions,
  BuildResult,
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

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}
