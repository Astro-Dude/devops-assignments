// Minimal Node.js HTTP server - no external dependencies needed.
const http = require('http');

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(`<!doctype html>
<html>
  <head><title>Node.js on Docker</title></head>
  <body style="font-family: system-ui, sans-serif; text-align:center; padding-top:80px; background:#f6f8fa;">
    <h1>Hello World</h1>
    <p>Served by <strong>Node.js ${process.version}</strong> inside Docker</p>
    <p>Hostname (container ID): <code>${require('os').hostname()}</code></p>
  </body>
</html>`);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Node.js server listening on port ${PORT}`);
});
