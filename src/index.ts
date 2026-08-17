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
export { parseArgs, runCli, CliOptions } from './cli';

if (require.main === module) {
  process.exitCode = runCli(process.argv.slice(2));
}
