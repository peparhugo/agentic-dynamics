import { buildWithStats } from './generator';
import { startDevServer } from './serve';
import { BuildOptions } from './types';

const DEFAULT_CONTENT_DIR = 'content';
const DEFAULT_OUTPUT_DIR = 'dist';
const DEFAULT_TEMPLATES_DIR = 'templates';
const DEFAULT_PORT = 3000;

export interface CliArgs {
  command: string;
  options: BuildOptions;
  port?: number;
}

function usage(): string {
  return `Usage: ssg <command> [options]

Commands:
  build   Build a static site from Markdown files
  serve   Run a live-reload development server

Options:
  --content <dir>   Content directory containing Markdown files (default: ./content)
  --output <dir>    Output directory for generated HTML (default: ./dist)
  --templates <dir> Templates directory with .hbs templates, layouts/, and partials/ (default: ./templates)
  --incremental     Only rebuild pages whose source or template changed (build)
  --clean           Ignore any existing cache and force a full rebuild (build)
  --port <number>   Port for the dev server (default: 3000)
  --help            Show this help message`;
}

export function parseArgs(argv: string[]): CliArgs {
  const options: BuildOptions = {
    contentDir: DEFAULT_CONTENT_DIR,
    outputDir: DEFAULT_OUTPUT_DIR,
    templatesDir: DEFAULT_TEMPLATES_DIR,
  };
  let command = 'build';
  let port: number | undefined;
  let seenPositional = false;

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];

    if (arg === '--help' || arg === '-h') {
      throw new HelpError(usage());
    }

    const equalsIndex = arg.indexOf('=');
    const flag = equalsIndex === -1 ? arg : arg.slice(0, equalsIndex);
    const inlineValue = equalsIndex === -1 ? undefined : arg.slice(equalsIndex + 1);

    if (flag === '--content') {
      options.contentDir = inlineValue ?? argv[++i];
      if (!options.contentDir) {
        throw new Error('--content requires a directory argument');
      }
    } else if (flag === '--output') {
      options.outputDir = inlineValue ?? argv[++i];
      if (!options.outputDir) {
        throw new Error('--output requires a directory argument');
      }
    } else if (flag === '--templates') {
      options.templatesDir = inlineValue ?? argv[++i];
      if (!options.templatesDir) {
        throw new Error('--templates requires a directory argument');
      }
    } else if (flag === '--incremental') {
      options.incremental = true;
    } else if (flag === '--clean') {
      options.clean = true;
    } else if (flag === '--port') {
      const raw = inlineValue ?? argv[++i];
      if (!raw) {
        throw new Error('--port requires a number argument');
      }
      const parsed = Number(raw);
      if (!Number.isInteger(parsed) || parsed < 0 || parsed > 65535) {
        throw new Error('--port must be an integer between 0 and 65535');
      }
      port = parsed;
    } else if (arg.startsWith('-')) {
      throw new Error(`unknown argument: ${arg}`);
    } else {
      if (seenPositional) {
        throw new Error(`unknown argument: ${arg}`);
      }
      seenPositional = true;
      command = arg;
    }
  }

  if (command !== 'build' && command !== 'serve') {
    throw new Error(`unknown command: ${command}`);
  }

  return { command, options, port };
}

export class HelpError extends Error {}

export async function main(argv: string[]): Promise<void> {
  const { command, options, port } = parseArgs(argv);

  if (command === 'serve') {
    const dev = await startDevServer({ ...options, port });
    process.stdout.write(`Dev server running at http://localhost:${dev.port}\n`);
    process.stdout.write(
      `Watching ${options.contentDir} and ${options.templatesDir} for changes\n`
    );
    return new Promise<void>(() => {});
  }

  const { pages, stats } = await buildWithStats(options);
  process.stdout.write(
    `Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${options.outputDir}\n`
  );
  if (options.incremental) {
    process.stdout.write(
      `Incremental: ${stats.built} built, ${stats.skipped} skipped, ` +
        `saved ${Math.round(stats.timeSavedMs)}ms\n`
    );
  }
}
