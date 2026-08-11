import http from 'http';
import { ServeOptions } from './types';
import { createDevServer } from './plugins/devserver';

export function serve(options: ServeOptions): http.Server {
  return createDevServer(options);
}
