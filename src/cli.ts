#!/usr/bin/env node
import { Command } from "commander";
import { build } from "./index";

const program = new Command();

program
  .name("ssg")
  .description("Static site generator");

program
  .command("build")
  .description("Generate the static site")
  .option("--content <dir>", "Content directory", "./content")
  .option("--output <dir>", "Output directory", "./dist")
  .action(async (options: { content: string; output: string }) => {
    try {
      await build({ contentDir: options.content, outputDir: options.output });
      console.log("Build complete");
    } catch (err) {
      console.error("Error:", (err as Error).message);
      process.exit(1);
    }
  });

program.parse();
