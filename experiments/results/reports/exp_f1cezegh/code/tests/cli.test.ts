import { describe, it, expect } from "vitest";
import { SiteConfig } from "../src/types";

describe("CLI configuration", () => {
  it("SiteConfig type has all required fields", () => {
    const config: SiteConfig = {
      sourceDir: "./content",
      outputDir: "./public",
      templateDir: "./templates",
      siteTitle: "My Blog",
      siteUrl: "https://blog.example.com",
      siteDescription: "A blog about things",
      port: 3000,
    };

    expect(config.sourceDir).toBe("./content");
    expect(config.outputDir).toBe("./public");
    expect(config.templateDir).toBe("./templates");
    expect(config.siteTitle).toBe("My Blog");
    expect(config.siteUrl).toBe("https://blog.example.com");
    expect(config.port).toBe(3000);
  });

  it("SiteConfig defaults work correctly", () => {
    const config: SiteConfig = {
      sourceDir: ".",
      outputDir: ".",
      templateDir: ".",
      siteTitle: "My Site",
      siteUrl: "http://localhost:8080",
      siteDescription: "",
      port: 8080,
    };

    expect(config.siteDescription).toBe("");
    expect(config.port).toBe(8080);
  });
});
