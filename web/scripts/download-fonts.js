#!/usr/bin/env node

/**
 * Download IBM Plex fonts and convert to woff2 format
 * 
 * This script downloads IBM Plex Sans and IBM Plex Mono fonts from Google Fonts
 * and saves them in the public/fonts directory.
 * 
 * Prerequisites:
 * - Node.js with fs and https modules
 * - woff2 tools (optional, for conversion)
 * 
 * Usage: node scripts/download-fonts.js
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const fontsDir = path.join(__dirname, '../public/fonts');
const fontWeights = [400, 500, 600, 700];

// Ensure fonts directory exists
if (!fs.existsSync(fontsDir)) {
  fs.mkdirSync(fontsDir, { recursive: true });
}

// IBM Plex Sans font URLs from Google Fonts CDN
const ibmPlexSansUrls = {
  400: 'https://fonts.gstatic.com/s/ibmplexsans/v19/zYXgKVElMYYaJe8bpLHnCwDKhdHeFaxOedfTDw.woff2',
  500: 'https://fonts.gstatic.com/s/ibmplexsans/v19/zYX9KVElMYYaJe8bpLHnCwDKhdHeFaxOedfTDw.woff2',
  600: 'https://fonts.gstatic.com/s/ibmplexsans/v19/zYX9KVElMYYaJe8bpLHnCwDKhdHeFaxOedfTDw.woff2',
  700: 'https://fonts.gstatic.com/s/ibmplexsans/v19/zYX9KVElMYYaJe8bpLHnCwDKhdHeFaxOedfTDw.woff2',
};

// IBM Plex Mono font URLs from Google Fonts CDN
const ibmPlexMonoUrls = {
  400: 'https://fonts.gstatic.com/s/ibmplexmono/v19/-F63fjptAgt5VM-kVkqdyU8n1iIq129k.woff2',
  500: 'https://fonts.gstatic.com/s/ibmplexmono/v19/-F6qfjptAgt5VM-kVkqdyU8n3vAL2d0f7oBtd.woff2',
  600: 'https://fonts.gstatic.com/s/ibmplexmono/v19/-F6qfjptAgt5VM-kVkqdyU8n3vAL2d0f7oBtd.woff2',
  700: 'https://fonts.gstatic.com/s/ibmplexmono/v19/-F6qfjptAgt5VM-kVkqdyU8n3vAL2d0f7oBtd.woff2',
};

function downloadFile(url, filepath) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(filepath);
    https.get(url, (response) => {
      if (response.statusCode === 200) {
        response.pipe(file);
        file.on('finish', () => {
          file.close();
          console.log(`Downloaded: ${path.basename(filepath)}`);
          resolve();
        });
      } else if (response.statusCode === 301 || response.statusCode === 302) {
        // Handle redirects
        file.close();
        fs.unlinkSync(filepath);
        downloadFile(response.headers.location, filepath).then(resolve).catch(reject);
      } else {
        file.close();
        fs.unlinkSync(filepath);
        reject(new Error(`Failed to download ${url}: ${response.statusCode}`));
      }
    }).on('error', (err) => {
      file.close();
      if (fs.existsSync(filepath)) {
        fs.unlinkSync(filepath);
      }
      reject(err);
    });
  });
}

async function downloadFonts() {
  console.log('Downloading IBM Plex fonts...\n');

  try {
    // Download IBM Plex Sans
    for (const weight of fontWeights) {
      const url = ibmPlexSansUrls[weight];
      const filename = `IBMPlexSans-${weight === 400 ? 'Regular' : weight === 500 ? 'Medium' : weight === 600 ? 'SemiBold' : 'Bold'}.woff2`;
      const filepath = path.join(fontsDir, filename);
      await downloadFile(url, filepath);
    }

    // Download IBM Plex Mono
    for (const weight of fontWeights) {
      const url = ibmPlexMonoUrls[weight];
      const filename = `IBMPlexMono-${weight === 400 ? 'Regular' : weight === 500 ? 'Medium' : weight === 600 ? 'SemiBold' : 'Bold'}.woff2`;
      const filepath = path.join(fontsDir, filename);
      await downloadFile(url, filepath);
    }

    console.log('\nAll fonts downloaded successfully!');
  } catch (error) {
    console.error('Error downloading fonts:', error.message);
    process.exit(1);
  }
}

downloadFonts();

