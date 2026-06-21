const express = require('express');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

// Serve static assets from the current directory
app.use(express.static(__dirname));

const http = require('http');

const proxyRequest = (req, res, targetPort) => {
    // Override host header to prevent target server issues
    const headers = { ...req.headers };
    headers.host = `localhost:${targetPort}`;

    const options = {
        hostname: 'localhost',
        port: targetPort,
        path: req.originalUrl,
        method: req.method,
        headers: headers
    };

    const proxyReq = http.request(options, (proxyRes) => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res, { end: true });
    });

    proxyReq.on('error', (err) => {
        console.error('Proxy error:', err);
        res.status(502).send('Bad Gateway');
    });

    req.pipe(proxyReq, { end: true });
};

// Route API prefixes to port 8765 (matchmaking server)
const API_PREFIXES = ['/submit', '/result', '/chat', '/admin', '/stats'];
API_PREFIXES.forEach(prefix => {
    app.all(prefix, (req, res) => proxyRequest(req, res, 8765));
    app.all(prefix + '/*', (req, res) => proxyRequest(req, res, 8765));
});

// Serve index.html for the root route
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// Fallback to index.html for any other unhandled GET requests
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// Start server
app.listen(PORT, () => {
    console.log('==================================================');
    console.log(`🚀 Server is running on http://localhost:${PORT}`);
    console.log(`📂 Serving dating app mockup from: ${__dirname}`);
    console.log('==================================================');
});
