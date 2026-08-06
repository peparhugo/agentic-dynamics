import { describe, it, expect, afterAll } from "vitest";
import { execSync } from "node:child_process";
import { existsSync, rmSync, mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { join } from "node:path";

const TMP = join(import.meta.dirname ?? __dirname, "..", "test_fixtures", "..", "test-cli-tmp");

function runSsg(args: string): string {
  return execSync(`node dist/index.js ${args}`, {
    cwd: TMP,
    encoding: "utf-8",
    stdio: "pipe",
  });
}

function setup(minimal = false) {
  rmSync(TMP, { recursive: true, force: true });
  mkdirSync(join(TMP, "content"), { recursive: true });
  mkdirSync(join(TMP, "templates", "partials"), { recursive: true });

  if (!minimal) {
    writeFileSync(
      join(TMP, "content", "post.md"),
      `---
title: CLI Post
date: 2025-04-01
tags:
  - cli
---
# CLI Post

Testing the CLI.
`,
    );
  }

  writeFileSync(
    join(TMP, "templates", "layout.hbs"),
    "<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>",
  );
  writeFileSync(
    join(TMP, "templates", "post.hbs"),
    "<article><h1>{{title}}</h1>{{{content}}}</article>",
  );
  writeFileSync(join(TMP, "templates", "index.hbs"), "<h1>Index</h1>");
  writeFileSync(join(TMP, "templates", "tag.hbs"), "<h1>Tag {{tag}}</h1>");
}

afterAll(() => {
  rmSync(TMP, { recursive: true, force: true });
});

describe("CLI flags", () => {
  it("uses default directories when no flags are given", () => {
    setup();
    mkdirSync(join(TMP, "content"), { recursive: true });
    writeFileSync(
      join(TMP, "content", "hello.md"),
      `---
title: Hello
---
Content
`,
    );

    const out = runSsg("");
    expect(out).toContain("Built");
    expect(existsSync(join(TMP, "public", "hello.html"))).toBe(true);
  });

  it("respects --source, --templates, and --output flags", () => {
    setup();
    mkdirSync(join(TMP, "mycontent"), { recursive: true });
    writeFileSync(
      join(TMP, "mycontent", "custom.md"),
      `---
title: Custom
---
Custom body
`,
    );

    const out = runSsg("-s mycontent -t templates -o dist");
    expect(out).toContain("Built");
    expect(existsSync(join(TMP, "dist", "custom.html"))).toBe(true);
    expect(existsSync(join(TMP, "public", "custom.html"))).toBe(false);
  });

  it("builds with --serve (but exits without error on smoke)", () => {
    setup();
    // We can't actually serve in tests, but verify the build portion works
    // and that --serve doesn't crash on flag parse
    const out = runSsg("--serve --port 9999");
    // Build ran (the output just contains "Dev server listening" if serve launched)
    expect(out).toContain("Dev server listening at http://localhost:9999");
  });

  it("skips draft posts in published count", () => {
    setup();
    writeFileSync(
      join(TMP, "content", "visible.md"),
      `---
title: Visible
---
`,
    );
    writeFileSync(
      join(TMP, "content", "hidden.md"),
      `---
title: Hidden
draft: true
---
`,
    );

    const out = runSsg("");
    expect(out).toContain("1 drafts");
    expect(existsSync(join(TMP, "public", "visible.html"))).toBe(true);
    expect(existsSync(join(TMP, "public", "hidden.html"))).toBe(false);
  });

  it("generates tag pages", () => {
    setup();
    writeFileSync(
      join(TMP, "content", "a.md"),
      `---
title: A
tags:
  - x
---
`,
    );
    writeFileSync(
      join(TMP, "content", "b.md"),
      `---
title: B
tags:
  - x
  - y
---
`,
    );

    runSsg("");
    expect(existsSync(join(TMP, "public", "tags", "x.html"))).toBe(true);
    expect(existsSync(join(TMP, "public", "tags", "y.html"))).toBe(true);
  });

  it("generates RSS feed", () => {
    setup();
    writeFileSync(
      join(TMP, "content", "rss-post.md"),
      `---
title: RSS Post
date: 2025-08-01
---
`,
    );

    runSsg("");
    const feed = readFileSync(join(TMP, "public", "feed.xml"), "utf-8");
    expect(feed).toContain("<rss version=\"2.0\">");
    expect(feed).toContain("<title>RSS Post</title>");
  });

  it("rejects invalid port with error", () => {
    setup();
    expect(() => runSsg("--serve --port abc")).toThrow();
  });
});
