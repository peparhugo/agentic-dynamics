#!/usr/bin/env node
import { Command } from "commander";
import { resolve } from "node:path";
import { generate } from "./generator.js";
import { serve } from "./server.js";
import type { SiteConfig } from "./types.js";

const program = new Command();

program
  .name("static-site-gen")
  .description("Static site generator from Markdown + Handlebars");

program
  .command("build")
  .description("Build the static site")
  .requiredOption("--src <dir>", "Source directory of markdown files", "content")
  .requiredOption("--tmpl <dir>", "Template directory of handlebars files", "templates")
  .requiredOption("--out <dir>", "Output directory for generated HTML", "public")
  .option("--base-url <url>", "Base URL for RSS feed", "http://localhost:3000")
  .option("--title <title>", "Site title", "My Site")
  .option("--description <desc>", "Site description", "A static site")
  .action(async (opts) => {
    const config: SiteConfig = {
      src: resolve(opts.src),
      tmpl: resolve(opts.tmpl),
      out: resolve(opts.out),
      port: 3000,
      baseUrl: opts.baseUrl,
      title: opts.title,
      description: opts.description,
    };
    await generate(config);
    console.log(`Site built to ${config.out}`);
  });

program
  .command("dev")
  .description("Start dev server with live reload")
  .requiredOption("--src <dir>", "Source directory of markdown files", "content")
  .requiredOption("--tmpl <dir>", "Template directory of handlebars files", "templates")
  .requiredOption("--out <dir>", "Output directory for generated HTML", "public")
  .option("--port <number>", "Port for dev server", "3000")
  .option("--base-url <url>", "Base URL for RSS feed", "http://localhost:3000")
  .option("--title <title>", "Site title", "My Site")
  .option("--description <desc>", "Site description", "A static site")
  .action(async (opts) => {
    const config: SiteConfig = {
      src: resolve(opts.src),
      tmpl: resolve(opts.tmpl),
      out: resolve(opts.out),
      port: parseInt(opts.port, 10),
      baseUrl: opts.baseUrl,
      title: opts.title,
      description: opts.description,
    };
    await generate(config);
    console.log(`Initial build complete. Starting dev server...`);
    await serve(config, true);
  });

program
  .command("serve")
  .description("Serve the output directory")
  .requiredOption("--out <dir>", "Output directory to serve", "public")
  .option("--port <number>", "Port for server", "3000")
  .action(async (opts) => {
    const config: SiteConfig = {
      src: "",
      tmpl: "",
      out: resolve(opts.out),
      port: parseInt(opts.port, 10),
      baseUrl: `http://localhost:${opts.port}`,
      title: "",
      description: "",
    };
    await serve(config, false);
  });

program.parse();
