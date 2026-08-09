import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { execSync, spawnSync } from "child_process";

function buildProject(): void {
  execSync("npx tsc", { cwd: path.resolve(__dirname, ".."), stdio: "pipe" });
}

describe("CLI flags", () => {
  let tmpDir: string;
  let sourceDir: string;
  let templateDir: string;
  let outputDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "triton-cli-"));
    sourceDir = path.join(tmpDir, "custom-src");
    templateDir = path.join(tmpDir, "custom-tpl");
    outputDir = path.join(tmpDir, "out");
    fs.mkdirSync(sourceDir, { recursive: true });
    fs.mkdirSync(templateDir, { recursive: true });
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function writeSource(relPath: string, content: string): void {
    const fullPath = path.join(sourceDir, relPath);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content);
  }

  function writeTemplate(name: string, content: string): void {
    const fullPath = path.join(templateDir, name);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content);
  }

  it("builds with --source --templates --output flags", () => {
    writeSource("post.md", `---
title: CLI Test
---
# CLI

Works.`);
    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    buildProject();

    execSync(
      `node ${path.resolve(__dirname, "../dist/index.js")} --source ${sourceDir} --templates ${templateDir} --output ${outputDir}`,
      { stdio: "pipe" },
    );

    const outFile = path.join(outputDir, "post.html");
    expect(fs.existsSync(outFile)).toBe(true);
    expect(fs.readFileSync(outFile, "utf-8")).toContain("CLI");
  });

  it("uses -s -t -o short flags", () => {
    writeSource("post.md", `---
title: Short Flags
---
Short flags test.`);
    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    buildProject();

    execSync(
      `node ${path.resolve(__dirname, "../dist/index.js")} -s ${sourceDir} -t ${templateDir} -o ${outputDir}`,
      { stdio: "pipe" },
    );

    const outFile = path.join(outputDir, "post.html");
    expect(fs.existsSync(outFile)).toBe(true);
    expect(fs.readFileSync(outFile, "utf-8")).toContain("Short Flags");
  });

  it("sets custom site title via --title", () => {
    writeSource("post.md", `---
title: Post
---
Content.`);
    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");
    writeTemplate("index.hbs", "<title>{{site.title}}</title>");

    buildProject();

    execSync(
      `node ${path.resolve(__dirname, "../dist/index.js")} -s ${sourceDir} -t ${templateDir} -o ${outputDir} --title "My Custom Title"`,
      { stdio: "pipe" },
    );

    const html = fs.readFileSync(path.join(outputDir, "index.html"), "utf-8");
    expect(html).toContain("My Custom Title");
  });

  it("sets custom URL via --url", () => {
    writeSource("post.md", `---
title: Post
---
Content.`);
    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    buildProject();

    execSync(
      `node ${path.resolve(__dirname, "../dist/index.js")} -s ${sourceDir} -t ${templateDir} -o ${outputDir} --url "https://myblog.com"`,
      { stdio: "pipe" },
    );

    const rssPath = path.join(outputDir, "rss.xml");
    expect(fs.existsSync(rssPath)).toBe(true);
    const rss = fs.readFileSync(rssPath, "utf-8");
    expect(rss).toContain("https://myblog.com");
  });

  it("accepts -d flag for dev mode (starts server, cleans up)", () => {
    writeSource("post.md", `---
title: Dev
---
Content.`);
    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    buildProject();

    const result = spawnSync(
      "node",
      [path.resolve(__dirname, "../dist/index.js"), "-s", sourceDir, "-t", templateDir, "-o", outputDir, "--dev", "--port", "19876"],
      { stdio: "pipe", timeout: 5000, killSignal: "SIGINT" },
    );

    const stdout = result.stdout?.toString() ?? "";
    const stderr = result.stderr?.toString() ?? "";

    const combined = stdout + stderr;

    expect(combined).toContain("19876");
  });

  it("defaults source to ./source, templates to ./templates, output to ./public", () => {
    const cwd = process.cwd();

    fs.mkdirSync(path.join(tmpDir, "source"), { recursive: true });
    fs.mkdirSync(path.join(tmpDir, "templates"), { recursive: true });

    fs.writeFileSync(path.join(tmpDir, "source", "post.md"), `---
title: Default Dirs
---
Default.`);
    fs.writeFileSync(path.join(tmpDir, "templates", "default.hbs"), "{{{content}}}");
    fs.writeFileSync(path.join(tmpDir, "templates", "page.hbs"), "{{{content}}}");

    buildProject();

    try {
      process.chdir(tmpDir);
      execSync(
        `node ${path.resolve(__dirname, "../dist/index.js")}`,
        { stdio: "pipe" },
      );

      const outFile = path.join(tmpDir, "public", "post.html");
      expect(fs.existsSync(outFile)).toBe(true);
      expect(fs.readFileSync(outFile, "utf-8")).toContain("Default Dirs");
    } finally {
      process.chdir(cwd);
    }
  });

  it("exits cleanly without dev flag", () => {
    writeSource("post.md", `---
title: Clean
---
Clean.`);
    writeTemplate("default.hbs", "{{{content}}}");
    writeTemplate("page.hbs", "{{{content}}}");

    buildProject();

    const result = execSync(
      `node ${path.resolve(__dirname, "../dist/index.js")} -s ${sourceDir} -t ${templateDir} -o ${outputDir}`,
      { stdio: "pipe" },
    );

    expect(result.toString()).not.toContain("Dev server running");
  });
});
