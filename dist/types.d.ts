import http from 'http';
import { FSWatcher } from 'chokidar';
export interface Frontmatter {
    title?: string;
    date?: string;
    tags?: string[];
    template?: string;
    layout?: string | false;
    [key: string]: unknown;
}
export interface Page {
    slug: string;
    title: string;
    date?: string;
    tags: string[];
    html: string;
    sourcePath: string;
    frontmatter: Frontmatter;
    template?: string;
    layout?: string | false;
}
export interface BuildOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    defaultTemplate?: string;
    defaultLayout?: string;
}
export interface Site {
    pages: Page[];
    outputDir: string;
}
export interface ServeOptions {
    contentDir?: string;
    outputDir?: string;
    templatesDir?: string;
    port?: number;
    host?: string;
    debounce?: number;
}
export interface DevServer {
    server: http.Server;
    port: number;
    contentDir: string;
    outputDir: string;
    templatesDir: string;
    watcher: FSWatcher;
    close(): Promise<void>;
}
