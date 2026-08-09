declare module 'gray-matter' {
  interface GrayMatterFile {
    data: { [key: string]: any };
    content: string;
  }

  function matter(input: string): GrayMatterFile;
  export default matter;
}

declare module 'marked' {
  export class Renderer {
    code(code: string, language: string | undefined, isEscaped: boolean): string;
  }
  export const marked: {
    setOptions(options: { renderer: Renderer }): void;
    parse(markdown: string): string;
    Renderer: new () => Renderer;
  };
}
