'use strict';
// Custom CAP server — serves the mass-balance UI at the root path /
const cds = require('@sap/cds');
const path = require('path');
const fs   = require('fs');

cds.on('bootstrap', (app) => {
    const indexFile = path.join(__dirname, 'app', 'index.html');
    // Serve our custom SPA at /
    app.get('/', (req, res) => res.sendFile(indexFile));
    // Also mount the app/ directory for any future static assets (css, images, etc.)
    const express = require('express');
    app.use('/app', express.static(path.join(__dirname, 'app')));
});

module.exports = cds.server;
