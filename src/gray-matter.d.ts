declare module 'gray-matter' {
  interface GrayMatterFile {
    data: Record<string, unknown>;
    content: string;
    excerpt?: string;
    orig: Buffer | string;
    language: string;
    matter: string;
    stringify(lang?: string): string;
  }

  interface GrayMatterOptions {
    excerpt?: boolean | string;
    excerpt_separator?: string;
    engines?: Record<string, unknown>;
    language?: string;
    delimiters?: string | [string, string];
  }

  function matter(
    input: string | Buffer,
    options?: GrayMatterOptions
  ): GrayMatterFile;

  namespace matter {
    function read(
      filepath: string,
      options?: GrayMatterOptions
    ): GrayMatterFile;
    function stringify(file: string, data: object, options?: GrayMatterOptions): string;
  }

  export = matter;
}
