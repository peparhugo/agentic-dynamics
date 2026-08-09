#!/usr/bin/env node
import { Command } from "commander";
import path from "path";
import { build } from "./generators/build";
import { serve } from "./server/dev";
import { loadConfig } from "./commands/config";
import type { SiteConfig } from "./types";

const program = new Command();

program
  .name("staticsmith")
  .description("Static site generator from Markdown + Handlebars")
  .version("1.0.0");

program
  .command("build")
  .description("Build the static site")
  .option("-s, --source <dir>", "Source directory of Markdown files")
  .option("-o, --output <dir>", "Output directory for generated HTML")
  .option("-t, --templates <dir>", "Templates directory (Handlebars)")
  .option(
    "-c, --config <path>",
    "Path to staticsmith.json config file"
  )
  .option("-v, --verbose", "Verbose output")
  .action((opts) => {
    const config = loadConfig(opts.config);
    const sourceDir = path.resolve(
      opts.source || config.sourceDir || "content"
    );
    const outputDir = path.resolve(
      opts.output || config.outputDir || "public"
    );
    const templatesDir = path.resolve(
      opts.templates || config.templatesDir || "templates"
    );
    const site: SiteConfig = {
      title: config.site.title,
      description: config.site.description,
      url: config.site.url,
      author: config.site.author,
      language: config.site.language || "en",
    };

    const result = build({
      sourceDir,
      outputDir,
      templatesDir,
      site,
      verbose: opts.verbose,
    });
    process.exit(result);
  });

program
  .command("serve")
  .description("Start dev server with live reload")
  .option("-s, --source <dir>", "Source directory of Markdown files")
  .option("-o, --output <dir>", "Output directory for generated HTML")
  .option("-t, --templates <dir>", "Templates directory (Handlebars)")
  .option("-c, --config <path>", "Path to staticsmith.json config file")
  .option("-p, --port <number>", "Dev server port", "3000")
  .option("-v, --verbose", "Verbose output")
  .action((opts) => {
    const config = loadConfig(opts.config);
    const sourceDir = path.resolve(
      opts.source || config.sourceDir || "content"
    );
    const outputDir = path.resolve(
      opts.output || config.outputDir || "public"
    );
    const templatesDir = path.resolve(
      opts.templates || config.templatesDir || "templates"
    );
    const site: SiteConfig = {
      title: config.site.title,
      description: config.site.description,
      url: config.site.url,
      author: config.site.author,
      language: config.site.language || "en",
    };

    serve({
      sourceDir,
      outputDir,
      templatesDir,
      site,
      port: parseInt(opts.port, 10),
      verbose: opts.verbose,
    });
  });

program.parse(process.argv);
