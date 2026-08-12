#!/usr/bin/env node

import { parseMarkdownFiles, generateSite, generateSiteIncremental } from './index';
import { serve } from './server';

interface CliOptions {
  content: string;
  output: string;
  templates: string;
  port: number;
  config?: string;
  incremental: boolean;
  clean: boolean;
}

function parseArgs(args: string[]): CliOptions {
  const options: CliOptions = {
    content: './content',
    output: './dist',
    templates: './templates',
    port: 3000,
    incremental: false,
    clean: false,
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--content' && i + 1 < args.length) {
      options.content = args[i + 1];
      i++;
    } else if (args[i] === '--output' && i + 1 < args.length) {
      options.output = args[i + 1];
      i++;
    } else if (args[i] === '--templates' && i + 1 < args.length) {
      options.templates = args[i + 1];
      i++;
    } else if (args[i] === '--port' && i + 1 < args.length) {
      options.port = parseInt(args[i + 1], 10) || 3000;
      i++;
    } else if (args[i] === '--config' && i + 1 < args.length) {
      options.config = args[i + 1];
      i++;
    } else if (args[i] === '--incremental') {
      options.incremental = true;
    } else if (args[i] === '--clean') {
      options.clean = true;
    }
  }

  return options;
}

function loadCliConfig(options: CliOptions): CliOptions {
  if (!options.config) return options;

  try {
    const configPath = require('path').resolve(options.config);
    const mod = require(configPath);
    const cfg = mod.default || mod;
    return {
      content: cfg.contentDir || options.content,
      output: cfg.outputDir || options.output,
      templates: cfg.templatesDir || options.templates,
      port: cfg.port || options.port,
      incremental: options.incremental,
      clean: options.clean,
    };
  } catch {
    return options;
  }
}

const args = process.argv.slice(2);

if (args.length === 0 || (args[0] !== 'build' && args[0] !== 'serve')) {
  console.error('Usage: ssg build|serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>] [--config <file>] [--incremental] [--clean]');
  process.exit(1);
}

const cliOptions = parseArgs(args.slice(1));
const options = loadCliConfig(cliOptions);

if (args[0] === 'build') {
  const pages = parseMarkdownFiles(options.content);

  if (options.incremental) {
    const stats = generateSiteIncremental(pages, options.output, options.content, options.templates, options.clean);
    console.log(`Incremental build complete: ${stats.pagesBuilt} page(s) built, ${stats.pagesSkipped} skipped. Output: ${options.output}`);
  } else {
    generateSite(pages, options.output, options.templates);
    console.log(`Generated ${pages.length} page(s) in ${options.output}`);
  }
} else if (args[0] === 'serve') {
  serve(options);
}
