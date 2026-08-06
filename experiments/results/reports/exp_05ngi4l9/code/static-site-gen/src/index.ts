#!/usr/bin/env node
import { Command } from "commander";
import { build } from "./build.js";
import { startDevServer } from "./server.js";
import type { BuildOptions, ServerOptions } from "./types.js";

const program = new Command();

program
  .name("staticsmith")
  .description("Static site generator: Markdown + Handlebars → HTML")
  .version("1.0.0");

program
  .command("build")
  .description("Build the static site")
  .option("-s, --source <dir>", "Source directory of Markdown files", "content")
  .option("-t, --templates <dir>", "Template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "Output directory for generated HTML", "public")
  .option("--drafts", "Include draft posts", false)
  .option("--site-title <title>", "Site title", "My Site")
  .option("--site-description <desc>", "Site description", "A static site")
  .option("--site-url <url>", "Site base URL", "http://localhost:3000")
  .action(async (opts) => {
    const options: BuildOptions = {
      source: opts.source,
      templates: opts.templates,
      output: opts.output,
      drafts: opts.drafts,
      siteTitle: opts.siteTitle,
      siteDescription: opts.siteDescription,
      siteUrl: opts.siteUrl,
    };
    await build(options);
  });

program
  .command("serve")
  .description("Start dev server with live reload")
  .option("-s, --source <dir>", "Source directory of Markdown files", "content")
  .option("-t, --templates <dir>", "Template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "Output directory for generated HTML", "public")
  .option("-p, --port <number>", "Port to listen on", "3000")
  .option("--drafts", "Include draft posts", false)
  .option("--site-title <title>", "Site title", "My Site")
  .option("--site-description <desc>", "Site description", "A static site")
  .option("--site-url <url>", "Site base URL", "http://localhost:3000")
  .action(async (opts) => {
    const buildOptions: BuildOptions = {
      source: opts.source,
      templates: opts.templates,
      output: opts.output,
      drafts: opts.drafts,
      siteTitle: opts.siteTitle,
      siteDescription: opts.siteDescription,
      siteUrl: opts.siteUrl,
    };

    // Build first, then serve
    await build(buildOptions);

    const serverOptions: ServerOptions = {
      port: parseInt(opts.port, 10),
      output: opts.output,
    };

    startDevServer(serverOptions, buildOptions);
  });

program.parse();
