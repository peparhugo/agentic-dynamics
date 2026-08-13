#!/usr/bin/env node
import { Command } from 'commander';
import * as path from 'path';
import { loadConfig } from './config';
import { startDevServer } from './devServer';
import { SSGEngine } from './engine';
import { buildSite } from './generator';
import { createMarkdownPlugin } from './plugins/markdownPlugin';
import { createTemplatePlugin } from './plugins/templatePlugin';

export function run(argv: string[]): void {
  const program = new Command();

  program.name('ssg').description('A static site generator').version('1.0.0');

  program
    .command('build')
    .description('Generate the site from Markdown content')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .option('--templates <dir>', 'templates directory', './templates')
    .option('--config <path>', 'plugin config file (e.g. ssg.config.ts); enables the custom plugin pipeline')
    .action((opts: { content: string; output: string; templates: string; config?: string }) => {
      const contentDir = path.resolve(process.cwd(), opts.content);
      const outputDir = path.resolve(process.cwd(), opts.output);
      const templatesDir = path.resolve(process.cwd(), opts.templates);

      if (opts.config) {
        const configPath = path.resolve(process.cwd(), opts.config);
        const config = loadConfig(configPath);
        const plugins = config.plugins.length > 0 ? config.plugins : [createMarkdownPlugin(), createTemplatePlugin()];
        const engine = new SSGEngine(plugins);
        engine
          .run({
            contentDir: config.contentDir ? path.resolve(process.cwd(), config.contentDir) : contentDir,
            outputDir: config.outputDir ? path.resolve(process.cwd(), config.outputDir) : outputDir,
            templatesDir: config.templatesDir ? path.resolve(process.cwd(), config.templatesDir) : templatesDir,
          })
          .then((result) => {
            // eslint-disable-next-line no-console
            console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
          })
          .catch((err) => {
            // eslint-disable-next-line no-console
            console.error('Build failed:', err instanceof Error ? err.message : err);
            process.exitCode = 1;
          });
        return;
      }

      const result = buildSite({ contentDir, outputDir, templatesDir });
      // eslint-disable-next-line no-console
      console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);
    });

  program
    .command('serve')
    .description('Build the site and serve it with live reload')
    .option('--content <dir>', 'content directory', './content')
    .option('--output <dir>', 'output directory', './dist')
    .option('--templates <dir>', 'templates directory', './templates')
    .option('--port <port>', 'port to serve on', '3000')
    .action(async (opts: { content: string; output: string; templates: string; port: string }) => {
      const contentDir = path.resolve(process.cwd(), opts.content);
      const outputDir = path.resolve(process.cwd(), opts.output);
      const templatesDir = path.resolve(process.cwd(), opts.templates);
      const port = parseInt(opts.port, 10);
      const server = await startDevServer({ contentDir, outputDir, templatesDir, port });
      // eslint-disable-next-line no-console
      console.log(`Serving ${outputDir} at http://localhost:${server.port} (watching ${opts.content}, ${opts.templates})`);
    });

  program.parse(argv);
}

if (require.main === module) {
  run(process.argv);
}
