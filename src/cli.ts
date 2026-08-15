#!/usr/bin/env node
import { buildSite } from './generator';
import { startDevServer } from './dev-server';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_TEMPLATE_DIR = './templates';
const DEFAULT_PORT = 3000;

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  port: number;
}

export function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    command: '',
    contentDir: DEFAULT_CONTENT_DIR,
    outputDir: DEFAULT_OUTPUT_DIR,
    port: DEFAULT_PORT,
  };
  const args = argv.slice();
  if (args.length === 0) {
    return opts;
  }
  if (args.includes('--help') || args.includes('-h')) {
    opts.command = 'help';
    return opts;
  }
  opts.command = args[0] ?? '';
  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--content') {
      opts.contentDir = args[i + 1] ?? DEFAULT_CONTENT_DIR;
      i += 1;
    } else if (arg === '--output') {
      opts.outputDir = args[i + 1] ?? DEFAULT_OUTPUT_DIR;
      i += 1;
    } else if (arg === '--templates') {
      opts.templateDir = args[i + 1] ?? DEFAULT_TEMPLATE_DIR;
      i += 1;
    } else if (arg === '--port') {
      const parsed = Number(args[i + 1]);
      opts.port = Number.isInteger(parsed) && parsed > 0 ? parsed : DEFAULT_PORT;
      i += 1;
    }
  }
  return opts;
}

export function printHelp(): void {
  console.log(
    [
      'Static Site Generator',
      '',
      'Usage:',
      '  npx ssg build [options]',
      '  npx ssg serve [options]',
      '',
      'Commands:',
      '  build    Build the site into the output directory',
      '  serve    Start a live-reload development server',
      '',
      'Options:',
      '  --content <dir>    Markdown content directory (default: ./content)',
      '  --output <dir>     Output directory (default: ./dist)',
      '  --templates <dir>  Template directory (default: ./templates)',
      '  --port <number>    Port for the dev server (default: 3000)',
      '  -h, --help         Show this help',
      '',
    ].join('\n')
  );
}

export function serveSite(opts: CliOptions): number {
  try {
    const pages = buildSite({
      contentDir: opts.contentDir,
      outputDir: opts.outputDir,
      templateDir: opts.templateDir,
    });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${opts.outputDir}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`Serve failed: ${message}`);
    return 1;
  }

  startDevServer({
    contentDir: opts.contentDir,
    outputDir: opts.outputDir,
    templateDir: opts.templateDir,
    port: opts.port,
  })
    .then((devServer) => {
      console.log(`Serving ${opts.outputDir} at http://localhost:${devServer.port}`);
      console.log('Watching content/ and templates/ for changes...');
    })
    .catch((error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`Serve failed: ${message}`);
      process.exitCode = 1;
    });

  return 0;
}

export function main(argv: string[]): number {
  const opts = parseArgs(argv);

  if (opts.command === 'help') {
    printHelp();
    return 0;
  }
  if (opts.command === 'serve') {
    return serveSite(opts);
  }
  if (opts.command !== 'build') {
    console.error(
      `Unknown command: "${opts.command}". Run "npx ssg build" or "npx ssg serve".`
    );
    return 1;
  }

  try {
    const pages = buildSite({
      contentDir: opts.contentDir,
      outputDir: opts.outputDir,
      templateDir: opts.templateDir,
    });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${opts.outputDir}`);
    return 0;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`Build failed: ${message}`);
    return 1;
  }
}

if (require.main === module) {
  process.exitCode = main(process.argv.slice(2));
}
