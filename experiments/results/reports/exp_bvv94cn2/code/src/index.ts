#!/usr/bin/env node
import { Command } from "commander";
import { resolve } from "node:path";
import type { SiteConfig } from "./types.js";
import { build } from "./build.js";
import { startServer } from "./server.js";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator")
  .version("1.0.0");

program
  .command("build")
  .description("Build the static site")
  .requiredOption("-s, --source <dir>", "Source directory of markdown files")
  .requiredOption("-t, --templates <dir>", "Template directory of Handlebars files")
  .requiredOption("-o, --output <dir>", "Output directory for generated HTML")
  .option("--site-title <title>", "Site title", "My Site")
  .option("--site-url <url>", "Site URL for RSS", "http://localhost:3000")
  .action(async (opts) => {
    const config: SiteConfig = {
      sourceDir: resolve(opts.source),
      templateDir: resolve(opts.templates),
      outputDir: resolve(opts.output),
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
    };

    console.log(`Building site from ${config.sourceDir}...`);
    const result = await build(config);
    console.log(`Built ${result.pages.length} pages, ${result.tags.length} tag indexes.`);
    if (result.errors.length > 0) {
      console.error("Errors:");
      for (const err of result.errors) {
        console.error(`  - ${err}`);
      }
    }
  });

program
  .command("serve")
  .description("Start dev server with live reload")
  .requiredOption("-s, --source <dir>", "Source directory of markdown files")
  .requiredOption("-t, --templates <dir>", "Template directory of Handlebars files")
  .requiredOption("-o, --output <dir>", "Output directory for generated HTML")
  .option("-p, --port <port>", "Port to listen on", "3000")
  .option("--site-title <title>", "Site title", "My Site")
  .option("--site-url <url>", "Site URL for RSS", "http://localhost:3000")
  .action(async (opts) => {
    const config: SiteConfig = {
      sourceDir: resolve(opts.source),
      templateDir: resolve(opts.templates),
      outputDir: resolve(opts.output),
      siteTitle: opts.siteTitle,
      siteUrl: opts.siteUrl,
    };

    // Initial build
    console.log("Building site...");
    await build(config);

    const port = parseInt(opts.port, 10);
    await startServer(config, port, opts.source, opts.templates);
  });

program.parse();
