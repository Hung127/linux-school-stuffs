const http = require('http');
const port = process.argv[2] || 3000;
http.createServer((req, res) => {
res.setHeader('Content-Type', 'application/json');
res.end(JSON.stringify({
instance: `node-${port}`,
path: req.url,
pid: process.pid,
time: new Date().toISOString()
}));
}).listen(port, '127.0.0.1', () => console.log(`API on 127.0.0.1:${port}`));
