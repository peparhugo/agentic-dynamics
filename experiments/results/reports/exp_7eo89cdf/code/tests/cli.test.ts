import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { execSync } from "node:child_process";
import { join } from "node:path";
import { existsSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const fixtures = join(__dirname, "fixtures");

const runner = (args: string): string =>
  execSync(`node --import tsx src/index.ts ${args}`, {
    cwd: join(__dirname, ".."),
    encoding: "utf-8",
    env: { ...process.env, NO_COLOR: "1" },
  }).trim();

describe("CLI", () => {
  it("shows help text", () => {
    const out = runner("--help");
    assert.ok(out.includes("build"), "build command listed");
    assert.ok(out.includes("serve"), "serve command listed");
    assert.ok(out.includes("--source"), "source option listed");
    assert.ok(out.includes("--templates"), "templates option listed");
    assert.ok(out.includes("--output"), "output option listed");
    assert.ok(out.includes("--title"), "title option listed");
  });

  it("build command uses default flags", () => {
    const tmpOut = join(__dirname, "fixtures/_cli-out");
    try {
      const out = runner(
        `--source ${join(fixtures, "content")} --templates ${join(fixtures, "templates")} --output ${tmpOut} build`
      );
      assert.ok(out.includes("Built"), "build output message");
      assert.ok(existsSync(join(tmpOut, "index.html")), "index.html created");
    } finally {
      if (existsSync(tmpOut)) rmSync(tmpOut, { recursive: true });
    }
  });

  it("build command respects --title and --description flags", () => {
    const tmpOut = join(__dirname, "fixtures/_cli-out2");
    try {
      runner(
        `--source ${join(fixtures, "content")} --templates ${join(fixtures, "templates")} --output ${tmpOut} --title "Custom Title" --description "Custom Desc" build`
      );
      const { readFileSync } = require("node:fs");
      const html = readFileSync(join(tmpOut, "index.html"), "utf-8");
      assert.ok(html.includes("Custom Title"), "custom title in output");
      assert.ok(html.includes("Custom Desc"), "custom description in output");
    } finally {
      if (existsSync(tmpOut)) rmSync(tmpOut, { recursive: true });
    }
  });

  it("build command generates RSS feed", () => {
    const tmpOut = join(__dirname, "fixtures/_cli-out3");
    try {
      runner(
        `--source ${join(fixtures, "content")} --templates ${join(fixtures, "templates")} --output ${tmpOut} --base-url "https://myblog.com/" build`
      );
      const { readFileSync } = require("node:fs");
      const rss = readFileSync(join(tmpOut, "rss.xml"), "utf-8");
      assert.ok(rss.includes("https://myblog.com/"), "base URL in RSS");
    } finally {
      if (existsSync(tmpOut)) rmSync(tmpOut, { recursive: true });
    }
  });

  it("serve command accepts --port flag", () => {
    const out = runner(`--source ${join(fixtures, "content")} --templates ${join(fixtures, "templates")} --output /tmp/_serve-out serve --help`);
    assert.ok(out.includes("--port"), "serve has port option");
  });

  it("rejects unknown commands gracefully", () => {
    try {
      runner("nonexistent");
      assert.fail("should have thrown");
    } catch (e: any) {
      assert.ok(e.stderr?.includes("unknown command") || e.stderr?.includes("help"), "reports unknown command");
    }
  });
});
