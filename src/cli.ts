#!/usr/bin/env node
import { Command } from 'commander';
import * as path from 'path';
import { build, defaultBuildPlugins } from './generator';
import { serve } from './serve';
import { SsgEngine } from './engine';
import { loadConfig } from './config';
import { DevServerPlugin } from '../plugins/dev-server';
import type { Plugin } from './plugin';

const DEFAULT_SERVE_DEBOUNCE_MS = 100;

/** Resolves the plugin pipeline for a build: the configured plugins when --config is given and non-empty, otherwise the built-ins. */
function resolvePlugins(configOpt: string | undefined): Plugin[] {
  if (!configOpt) return defaultBuildPlugins();
  const config = loadConfig(path.resolve(process.cwd(), configOpt));
  return config.plugins && config.plugins.length > 0 ? config.plugins : defaultBuildPlugins();
}

export function createCli(): Command {
  const program = new Command();

  program
    .name('ssg')
    .description('A static site generator for Markdown content');

  program
    .command('build')
    .description('Generate the static site')
    .option('--content <dir>', 'content directory to read Markdown files from', './content')
    .option('--output <dir>', 'output directory to write the generated site to', './dist')
    .option('--templates <dir>', 'templates directory containing layouts/ and partials/', './templates')
    .option('--config <file>', 'path to a ssg.config.ts plugin config file (defaults to the built-in plugins)')
    .option('--incremental', 'only rebuild pages whose source or templates changed since the last build', false)
    .option('--clean', 'discard any existing build cache and force a full rebuild', false)
    .action(
      (opts: {
        content: string;
        output: string;
        templates: string;
        config?: string;
        incremental: boolean;
        clean: boolean;
      }) => {
        const contentDir = path.resolve(process.cwd(), opts.content);
        const outputDir = path.resolve(process.cwd(), opts.output);
        const templatesDir = path.resolve(process.cwd(), opts.templates);

        const result = opts.config
          ? new SsgEngine({
              contentDir,
              outputDir,
              templatesDir,
              plugins: resolvePlugins(opts.config),
              incremental: opts.incremental,
              clean: opts.clean,
            }).build()
          : build({
              contentDir,
              outputDir,
              templatesDir,
              incremental: opts.incremental,
              clean: opts.clean,
            });

        // eslint-disable-next-line no-console
        console.log(`Built ${result.pages.length} page(s) into ${result.outputDir}`);

        if (opts.incremental) {
          const { pagesBuilt, pagesSkipped, totalPages, durationMs, timeSavedMs } = result.stats;
          // eslint-disable-next-line no-console
          console.log(
            `Incremental build: ${pagesBuilt} built, ${pagesSkipped} skipped (${totalPages} total) in ${durationMs}ms, ~${timeSavedMs}ms saved`
          );
        }
      }
    );

  program
    .command('serve')
    .description('Build the site, then serve it with live reload while watching for changes')
    .option('--content <dir>', 'content directory to read Markdown files from', './content')
    .option('--output <dir>', 'output directory to write the generated site to', './dist')
    .option('--templates <dir>', 'templates directory containing layouts/ and partials/', './templates')
    .option('--port <port>', 'port to serve the dev server on', '3000')
    .option('--config <file>', 'path to a ssg.config.ts plugin config file (defaults to the built-in plugins)')
    .action(
      async (opts: {
        content: string;
        output: string;
        templates: string;
        port: string;
        config?: string;
      }) => {
        const contentDir = path.resolve(process.cwd(), opts.content);
        const outputDir = path.resolve(process.cwd(), opts.output);
        const templatesDir = path.resolve(process.cwd(), opts.templates);
        const port = Number(opts.port);

        const handle = opts.config
          ? await serveWithConfig(opts.config, { contentDir, outputDir, templatesDir, port })
          : await serve({ contentDir, outputDir, templatesDir, port });

        // eslint-disable-next-line no-console
        console.log(`Dev server running at ${handle.url}`);
        // eslint-disable-next-line no-console
        console.log(`Watching ${opts.content} and ${opts.templates} for changes...`);
      }
    );

  return program;
}

async function serveWithConfig(
  configOpt: string,
  dirs: { contentDir: string; outputDir: string; templatesDir: string; port: number }
) {
  const plugins = resolvePlugins(configOpt);
  let devServer = plugins.find(
    (plugin): plugin is DevServerPlugin => plugin instanceof DevServerPlugin
  );
  if (!devServer) {
    devServer = new DevServerPlugin();
    plugins.push(devServer);
  }

  const engine = new SsgEngine({
    contentDir: dirs.contentDir,
    outputDir: dirs.outputDir,
    templatesDir: dirs.templatesDir,
    plugins,
  });
  engine.build();

  return devServer.start({
    outputDir: dirs.outputDir,
    watchPaths: [dirs.contentDir, dirs.templatesDir],
    port: dirs.port,
    debounceMs: DEFAULT_SERVE_DEBOUNCE_MS,
    rebuild: () => {
      engine.build();
    },
  });
}

export function run(argv: string[]): void {
  createCli().parse(argv);
}

if (require.main === module) {
  run(process.argv);
}
