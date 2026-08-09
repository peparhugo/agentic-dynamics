import { Command } from "commander";
import chokidar from "chokidar";
import path from "node:path";
import { build, BuildOptions } from "./build";
import { startDevServer, reloadClients } from "./server";

export function runCli(args: string[]): void {
  const program = new Command();

  program
    .name("statik")
    .description("Static site generator")
    .option("-s, --source <dir>", "Source directory of Markdown files", "content")
    .option("-t, --templates <dir>", "Template directory of Handlebars files", "templates")
    .option("-o, --output <dir>", "Output directory for generated HTML", "dist")
    .option("--title <title>", "Site title", "My Site")
    .option("--description <desc>", "Site description", "")
    .option("--url <url>", "Site URL", "http://localhost:3000")
    .option("--author <author>", "Site author", "")
    .option("--serve", "Start dev server", false)
    .option("-p, --port <port>", "Dev server port", "3000")
    .action((opts) => {
      const options: BuildOptions = {
        sourceDir: path.resolve(opts.source),
        templateDir: path.resolve(opts.templates),
        outputDir: path.resolve(opts.output),
        config: {
          title: opts.title,
          description: opts.description,
          url: opts.url,
          author: opts.author,
        },
      };

      const count = build(options);
      console.log(`Built ${count} pages.`);

      if (opts.serve) {
        const port = parseInt(opts.port, 10);
        const { wss } = startDevServer(options.outputDir, port, () => {});

        const watcher = chokidar.watch(
          [options.sourceDir, options.templateDir],
          { ignoreInitial: true }
        );
        watcher.on("all", () => {
          console.log("Change detected, rebuilding...");
          build(options);
          reloadClients(wss);
        });

        process.on("SIGINT", () => {
          watcher.close();
          wss.close();
          process.exit(0);
        });
      }
    });

  program.parse(args);
}
