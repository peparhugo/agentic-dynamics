#!/usr/bin/env node

import { build, buildWithStats } from './generator';
import { DevServer } from './dev-server';
import { loadPluginsFromConfig } from './plugin-loader';
import { DevServerPlugin } from './plugins/dev-server-plugin';
import { createBuildCache } from './cache';

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('Usage: ssg <command> [options]');
    console.error('Commands:');
    console.error('  build    Build the site');
    console.error('  serve    Start development server with live reload');
    console.error('Options:');
    console.error('  --incremental   Use incremental builds (only rebuild changed pages)');
    console.error('  --clean         Clean cache before building');
    process.exit(1);
  }

  const command = args[0];
  let contentDir = './content';
  let outputDir = './dist';
  let templatesDir = './templates';
  let port = 3000;
  let incremental = false;
  let clean = false;

  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--content' && args[i + 1]) {
      contentDir = args[i + 1];
      i++;
    } else if (args[i] === '--output' && args[i + 1]) {
      outputDir = args[i + 1];
      i++;
    } else if (args[i] === '--templates' && args[i + 1]) {
      templatesDir = args[i + 1];
      i++;
    } else if (args[i] === '--port' && args[i + 1]) {
      port = parseInt(args[i + 1], 10);
      i++;
    } else if (args[i] === '--incremental') {
      incremental = true;
    } else if (args[i] === '--clean') {
      clean = true;
    }
  }

  try {
    if (command === 'build') {
      if (incremental) {
        const cache = createBuildCache('.');
        const stats = await buildWithStats(contentDir, outputDir, templatesDir, undefined, {
          incremental: true,
          clean,
          cache,
        });
        console.log(`✓ Site built successfully to ${outputDir}`);
        console.log(`  Pages built: ${stats.pagesBuilt}`);
        console.log(`  Pages skipped: ${stats.pagesSkipped}`);
        if (stats.timeSaved > 0) {
          console.log(`  Time saved: ${stats.timeSaved}ms`);
        }
      } else {
        await build(contentDir, outputDir, templatesDir);
        console.log(`✓ Site built successfully to ${outputDir}`);
      }
    } else if (command === 'serve') {
      await build(contentDir, outputDir, templatesDir);
      console.log(`✓ Initial build complete`);
      const devServer = new DevServer({ contentDir, outputDir, templatesDir, port });
      devServer.start();
    } else {
      console.error(`✗ Unknown command: ${command}`);
      console.error('Usage: ssg <command> [options]');
      console.error('Commands:');
      console.error('  build    Build the site');
      console.error('  serve    Start development server with live reload');
      process.exit(1);
    }
  } catch (error) {
    if (error instanceof Error) {
      console.error(`✗ Error: ${error.message}`);
    } else {
      console.error('✗ Unknown error occurred');
    }
    process.exit(1);
  }
}

main();
