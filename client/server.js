const express = require('express');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

// Serve static assets from the current directory
app.use(express.static(__dirname));

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
