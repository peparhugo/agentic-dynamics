#!/usr/bin/env node

import path from 'path';
import { SSGEngine } from './engine';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { DevServerPlugin } from './plugins/devserver';
import { Plugin, SSGOptions } from './plugin';

function getDefaultPlugins(): Plugin[] {
  return [
    new MarkdownPlugin(),
    new TemplatePlugin(),
    new DevServerPlugin(),
  ];
}

function loadConfigPlugins(cwd: string): Plugin[] {
  try {
    const configPath = path.resolve(cwd, 'ssg.config.js');
    const config = require(configPath);
    if (config && Array.isArray(config.plugins)) {
      return config.plugins;
    }
    if (config && config.default && Array.isArray(config.default.plugins)) {
      return config.default.plugins;
    }
  } catch {
    // config file not found or invalid, use defaults
  }
  return getDefaultPlugins();
}

function parseArgs(args: string[]): {
  content: string;
  output: string;
  templates: string;
  port: number;
  incremental: boolean;
  clean: boolean;
} {
  let content = 'content';
  let output = 'dist';
  let templates = 'templates';
  let port = 3000;
  let incremental = false;
  let clean = false;
  let i = 0;

  while (i < args.length) {
    if (args[i] === '--content' && i + 1 < args.length) {
      content = args[i + 1];
      i += 2;
    } else if (args[i] === '--output' && i + 1 < args.length) {
      output = args[i + 1];
      i += 2;
    } else if (args[i] === '--templates' && i + 1 < args.length) {
      templates = args[i + 1];
      i += 2;
    } else if (args[i] === '--port' && i + 1 < args.length) {
      port = parseInt(args[i + 1], 10);
      i += 2;
    } else if (args[i] === '--incremental') {
      incremental = true;
      i++;
    } else if (args[i] === '--clean') {
      clean = true;
      i++;
    } else {
      i++;
    }
  }

  return { content, output, templates, port, incremental, clean };
}

const command = process.argv[2];

async function main(): Promise<void> {
  if (command === 'build') {
    const {
      content,
      output,
      templates,
      incremental,
      clean,
    } = parseArgs(process.argv.slice(3));
    const plugins = loadConfigPlugins(process.cwd());

    const options: SSGOptions = {
      content,
      output,
      templates,
      port: 3000,
      incremental,
      clean,
    };

    const engine = new SSGEngine(options);
    for (const plugin of plugins) {
      engine.register(plugin);
    }

    await engine.build();
    if (!incremental) {
      console.log(`Site generated in ${output} (${engine.pages.length} pages)`);
    }
  } else if (command === 'serve') {
    const { content, output, templates, port } = parseArgs(
      process.argv.slice(3)
    );
    const plugins = loadConfigPlugins(process.cwd());

    const options: SSGOptions = { content, output, templates, port };

    const engine = new SSGEngine(options);
    for (const plugin of plugins) {
      engine.register(plugin);
    }

    const pages = engine.pages;
    await engine.build();
    console.log(`Site generated in ${output} (${pages.length} pages)`);

    await engine.serve();
  } else {
    console.log(
      'Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]\n' +
        '       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]'
    );
    process.exit(command ? 1 : 0);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
