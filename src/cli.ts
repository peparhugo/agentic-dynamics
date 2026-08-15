#!/usr/bin/env node
import { Command } from 'commander';
import { buildSite } from './site';
import { startDevServer } from './serve';

export function run(argv: string[]): void {
  const program = new Command();

  program.name('ssg').description('A static site generator CLI');

  program
    .command('build')
    .description('Generate the site from Markdown content')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .option('--templates <dir>', 'templates directory', './templates')
    .option('--incremental', 'skip rebuilding pages whose source and templates are unchanged', false)
    .option('--clean', 'ignore the existing build cache and rebuild every page', false)
    .action((opts: { content: string; output: string; templates: string; incremental: boolean; clean: boolean }) => {
      const result = buildSite({
        contentDir: opts.content,
        outputDir: opts.output,
        templatesDir: opts.templates,
        incremental: opts.incremental,
        clean: opts.clean,
      });
      // eslint-disable-next-line no-console
      console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
      if (result.stats) {
        const { built, skipped, timeSavedMs } = result.stats;
        // eslint-disable-next-line no-console
        console.log(`Incremental build: ${built} built, ${skipped} skipped (~${timeSavedMs}ms saved)`);
      }
    });

  program
    .command('serve')
    .description('Build the site and start a live-reload development server')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .option('--templates <dir>', 'templates directory', './templates')
    .option('--port <port>', 'port to serve on', '3000')
    .action(async (opts: { content: string; output: string; templates: string; port: string }) => {
      const port = Number.parseInt(opts.port, 10);
      const server = await startDevServer({
        contentDir: opts.content,
        outputDir: opts.output,
        templatesDir: opts.templates,
        port,
      });
      // eslint-disable-next-line no-console
      console.log(`Dev server running at ${server.url}`);
      // eslint-disable-next-line no-console
      console.log(`Watching ${opts.content} and ${opts.templates} for changes...`);
    });

  program.parse(argv);
}

if (require.main === module) {
  run(process.argv);
}
