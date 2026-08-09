// injected live reload client
(function(){
  var wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
  var url = wsProtocol + '://' + location.host + '/_livereload';
  function connect(){
    var ws = new WebSocket(url);
    ws.onmessage = function(ev){
      if (ev.data === 'reload') { location.reload(); }
    };
    ws.onclose = function(){ setTimeout(connect, 1000); };
  }
  connect();
})();
