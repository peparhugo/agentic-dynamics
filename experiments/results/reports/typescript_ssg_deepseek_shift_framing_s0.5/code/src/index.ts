#!/usr/bin/env node
import { Command } from "commander";
import path from "path";
import { buildSite } from "./generator";
import { startDevServer } from "./server";
import { GeneratorOptions, SiteConfig } from "./types";

const program = new Command();

program
  .name("staticsmith")
  .description("Static site generator from Markdown + Handlebars")
  .version("1.0.0");

program
  .command("build")
  .description("Build the static site")
  .option("-s, --source <dir>", "Source directory of Markdown files", "content")
  .option("-t, --templates <dir>", "Template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "Output directory for generated site", "_site")
  .option("--site-name <name>", "Site name", "My Site")
  .option("--site-url <url>", "Site URL", "http://localhost:3456")
  .option("--author <name>", "Site author")
  .action((opts) => {
    const config: SiteConfig = {
      siteName: opts.siteName,
      siteUrl: opts.siteUrl,
      author: opts.author,
    };
    const options: GeneratorOptions = {
      sourceDir: path.resolve(opts.source),
      templateDir: path.resolve(opts.templates),
      outputDir: path.resolve(opts.output),
      config,
    };
    buildSite(options);
    console.log(`Site built to ${options.outputDir}`);
  });

program
  .command("dev")
  .description("Start dev server with live reload")
  .option("-s, --source <dir>", "Source directory of Markdown files", "content")
  .option("-t, --templates <dir>", "Template directory of Handlebars files", "templates")
  .option("-o, --output <dir>", "Output directory for generated site", "_site")
  .option("--site-name <name>", "Site name", "My Site")
  .option("--site-url <url>", "Site URL", "http://localhost:3456")
  .option("--author <name>", "Site author")
  .action((opts) => {
    const config: SiteConfig = {
      siteName: opts.siteName,
      siteUrl: opts.siteUrl,
      author: opts.author,
    };
    const options: GeneratorOptions = {
      sourceDir: path.resolve(opts.source),
      templateDir: path.resolve(opts.templates),
      outputDir: path.resolve(opts.output),
      config,
    };
    startDevServer(options);
  });

program.parse();
