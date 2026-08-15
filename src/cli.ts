#!/usr/bin/env node
import { build } from './ssg';
import { startDevServer } from './server';

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
  incremental: boolean;
  clean: boolean;
}

export function parseArgs(argv: string[]): CliOptions {
  const args = argv.slice(2);
  let command = 'build';
  let contentDir = './content';
  let outputDir = './dist';
  let templatesDir = './templates';
  let port = 3000;
  let incremental = false;
  let clean = false;
  const positionals: string[] = [];

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--content' || arg === '-c') {
      contentDir = args[++i] ?? contentDir;
    } else if (arg === '--output' || arg === '-o') {
      outputDir = args[++i] ?? outputDir;
    } else if (arg === '--templates' || arg === '-t') {
      templatesDir = args[++i] ?? templatesDir;
    } else if (arg === '--port' || arg === '-p') {
      const value = args[++i];
      if (value !== undefined && value !== '') port = Number(value);
    } else if (arg === '--incremental') {
      incremental = true;
    } else if (arg === '--clean') {
      clean = true;
    } else if (arg.startsWith('--content=')) {
      contentDir = arg.slice('--content='.length);
    } else if (arg.startsWith('--output=')) {
      outputDir = arg.slice('--output='.length);
    } else if (arg.startsWith('--templates=')) {
      templatesDir = arg.slice('--templates='.length);
    } else if (arg.startsWith('--port=')) {
      const value = arg.slice('--port='.length);
      if (value !== '') port = Number(value);
    } else if (!arg.startsWith('-')) {
      positionals.push(arg);
    }
  }

  if (positionals.length > 0) {
    command = positionals[0];
  }

  return { command, contentDir, outputDir, templatesDir, port, incremental, clean };
}

export function run(argv: string[]): number | Promise<number> {
  const opts = parseArgs(argv);

  if (opts.command === 'build') {
    try {
      const result = build({
        contentDir: opts.contentDir,
        outputDir: opts.outputDir,
        templatesDir: opts.templatesDir,
        incremental: opts.incremental,
        clean: opts.clean,
      });
      if (opts.incremental) {
        const stats = result.stats;
        console.log(
          `Generated ${result.pages.length} page(s) in ${opts.outputDir} ` +
            `(built ${stats.pagesBuilt}, skipped ${stats.pagesSkipped}, saved ${stats.timeSavedMs}ms)`
        );
      } else {
        console.log(`Generated ${result.pages.length} page(s) in ${opts.outputDir}`);
      }
      return 0;
    } catch (err) {
      console.error((err as Error).message);
      return 1;
    }
  }

  if (opts.command === 'serve') {
    return startDevServer({
      contentDir: opts.contentDir,
      outputDir: opts.outputDir,
      templatesDir: opts.templatesDir,
      port: opts.port,
    })
      .then((server) => {
        console.log(`Serving ${opts.outputDir} at ${server.url}`);
        return new Promise<number>((resolve) => {
          const shutdown = (signal: string) => {
            console.log(`\n[ssg] ${signal} received, shutting down`);
            server.close().then(() => resolve(0));
          };
          process.once('SIGINT', () => shutdown('SIGINT'));
          process.once('SIGTERM', () => shutdown('SIGTERM'));
        });
      })
      .catch((err) => {
        console.error((err as Error).message);
        return 1;
      });
  }

  console.error(`Unknown command: ${opts.command}`);
  return 1;
}

if (require.main === module) {
  Promise.resolve(run(process.argv)).then(
    (code) => process.exit(code),
    (err) => {
      console.error((err as Error).message);
      process.exit(1);
    }
  );
}
