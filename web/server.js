const express = require('express');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

// Serve static assets from the current directory
app.use(express.static(__dirname));

// Serve indexx.html for the root route (handles the naming typo indexx.html)
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'indexx.html'));
});

// Fallback to indexx.html for any other unhandled GET requests
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'indexx.html'));
});

// Start server
app.listen(PORT, () => {
    console.log('==================================================');
    console.log(`🚀 Server is running on http://localhost:${PORT}`);
    console.log(`📂 Serving dating app mockup from: ${__dirname}`);
    console.log('==================================================');
});
