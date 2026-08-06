import { describe, it, expect } from "vitest";
import { parseMarkdown } from "../src/markdown.js";

describe("parseMarkdown", () => {
  it("parses YAML frontmatter fields", () => {
    const raw = `---
title: My Post
date: "2025-03-10"
tags:
  - typescript
  - ssg
draft: false
---

# Content

Hello world.
`;
    const page = parseMarkdown(raw, "posts/my-post.md");

    expect(page.frontmatter.title).toBe("My Post");
    expect(page.frontmatter.date).toBe("2025-03-10");
    expect(page.frontmatter.tags).toEqual(["typescript", "ssg"]);
    expect(page.frontmatter.draft).toBe(false);
    expect(page.isPost).toBe(true);
  });

  it("defaults title to Untitled when missing", () => {
    const raw = `---
date: 2025-01-01
---

Text.
`;
    const page = parseMarkdown(raw, "posts/no-title.md");
    expect(page.frontmatter.title).toBe("Untitled");
  });

  it("parses comma-separated tags string", () => {
    const raw = `---
title: Post
tags: "js, css, html"
---

Text.
`;
    const page = parseMarkdown(raw, "posts/comma-tags.md");
    expect(page.frontmatter.tags).toEqual(["js", "css", "html"]);
  });

  it("handles draft as boolean", () => {
    const raw = `---
title: Drafty
draft: true
---

Content.
`;
    const page = parseMarkdown(raw, "posts/drafty.md");
    expect(page.frontmatter.draft).toBe(true);
  });

  it("handles draft as string", () => {
    const raw = `---
title: Drafty
draft: "true"
---

Content.
`;
    const page = parseMarkdown(raw, "posts/drafty-str.md");
    expect(page.frontmatter.draft).toBe(true);
  });

  it("produces correct URL from file path", () => {
    const raw = `---
title: A Post
---

Text.
`;
    const page = parseMarkdown(raw, "posts/nested/deep-post.md");
    expect(page.url).toBe("/posts/nested/deep-post/");
  });

  it("handles index.md specially", () => {
    const raw = `---
title: Index
---

Home.
`;
    const page = parseMarkdown(raw, "index.md");
    expect(page.url).toBe("/");
  });

  it("syntax highlights code blocks", () => {
    const raw = `---
title: Code
---

\`\`\`js
const x = 1;
\`\`\`
`;
    const page = parseMarkdown(raw, "posts/code.md");
    expect(page.html).toContain("language-js");
    expect(page.html).toContain("hljs");
  });

  it("escapes unknown languages", () => {
    const raw = `---
title: Code
---

\`\`\`fakelang
some code
\`\`\`
`;
    const page = parseMarkdown(raw, "posts/fake.md");
    expect(page.html).toContain("<pre><code");
    expect(page.html).not.toContain("language-fakelang");
  });

  it("marks non-posts paths as not posts", () => {
    const raw = `---
title: About
---

About us.
`;
    const page = parseMarkdown(raw, "about.md");
    expect(page.isPost).toBe(false);
  });

  it("preserves extra frontmatter keys", () => {
    const raw = `---
title: Extra
author: Jane Doe
custom: value
---

Text.
`;
    const page = parseMarkdown(raw, "posts/extra.md");
    expect(page.frontmatter.author).toBe("Jane Doe");
    expect(page.frontmatter.custom).toBe("value");
  });
});
