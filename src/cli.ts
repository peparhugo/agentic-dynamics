#!/usr/bin/env node
import path from 'path';
import { Command } from 'commander';
import { build, buildIncremental } from './build';
import { startServer } from './serve';

const program = new Command();

program.name('ssg').description('A minimal static site generator');

program
  .command('build')
  .description('Generate the static site')
  .option('--content <dir>', 'content directory', './content')
  .option('--output <dir>', 'output directory', './dist')
  .option('--templates <dir>', 'templates directory', './templates')
  .option('--incremental', 'skip pages whose source and template are unchanged since the last build', false)
  .option('--clean', 'ignore the incremental cache (used with --incremental) and rebuild every page', false)
  .action((opts: { content: string; output: string; templates: string; incremental: boolean; clean: boolean }) => {
    const contentDir = path.resolve(process.cwd(), opts.content);
    const outputDir = path.resolve(process.cwd(), opts.output);
    const templatesDir = path.resolve(process.cwd(), opts.templates);

    if (opts.incremental) {
      const result = buildIncremental({ contentDir, outputDir, templatesDir, clean: opts.clean });
      const { stats } = result;
      const savedNote = stats.skipped > 0 ? `, saved ~${stats.timeSavedMs}ms` : '';
      console.log(
        `Built ${stats.built} page(s), skipped ${stats.skipped} page(s) (of ${stats.total}) into ${outputDir} ` +
          `in ${stats.timeMs}ms${savedNote}`
      );
      return;
    }

    const result = build({ contentDir, outputDir, templatesDir });
    console.log(`Built ${result.pages.length} page(s) into ${outputDir}`);
  });

program
  .command('serve')
  .description('Start a live-reload development server')
  .option('--content <dir>', 'content directory', './content')
  .option('--output <dir>', 'output directory', './dist')
  .option('--templates <dir>', 'templates directory', './templates')
  .option('--port <port>', 'port to serve on', '3000')
  .action(async (opts: { content: string; output: string; templates: string; port: string }) => {
    const contentDir = path.resolve(process.cwd(), opts.content);
    const outputDir = path.resolve(process.cwd(), opts.output);
    const templatesDir = path.resolve(process.cwd(), opts.templates);
    const port = parseInt(opts.port, 10);
    const server = await startServer({ contentDir, outputDir, templatesDir, port });
    console.log(`Dev server running at http://localhost:${server.port}`);
  });

if (require.main === module) {
  program.parse(process.argv);
}

export { program };
