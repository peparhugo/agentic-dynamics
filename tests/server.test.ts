import { injectLiveReload } from '../src/server';

describe('injectLiveReload', () => {
  it('adds the client before a closing body tag', () => {
    const html = injectLiveReload('<html><body><h1>Page</h1></body></html>');

    expect(html).toContain("new WebSocket(");
    expect(html).toMatch(/<script>[\s\S]*<\/script><\/body>/);
  });

  it('adds the client when a document has no body tag', () => {
    expect(injectLiveReload('<main>Page</main>')).toBe('<main>Page</main><script>(() => { const socket = new WebSocket((location.protocol === \'https:\' ? \'wss://\' : \'ws://\') + location.host + \'/__ssg_live_reload\'); socket.addEventListener(\'message\', () => location.reload()); })();</script>');
  });
});
