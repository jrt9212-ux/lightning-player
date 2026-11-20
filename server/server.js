// server/server.js - Lightweight Dual-Source Music Server (Node.js runtime)
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

const PORT = process.env.PORT || 3000;
const CLIENT_DIR = path.join(__dirname, '..', 'client');

// Preset featured tracks for immediate out-of-the-box playback
const FEATURED_TRACKS = [
  {
    id: 'jfKfPfyJRdk',
    source: 'youtube',
    title: 'Lofi Hip Hop Radio - Beats to Relax/Study to',
    artist: 'Lofi Girl',
    duration: 'Live',
    thumbnail: 'https://i.ytimg.com/vi/jfKfPfyJRdk/hqdefault.jpg'
  },
  {
    id: '5yx6BWlEVcY',
    source: 'youtube',
    title: 'Chillhop Essentials Summer 2024',
    artist: 'Chillhop Music',
    duration: '2:15:40',
    thumbnail: 'https://i.ytimg.com/vi/5yx6BWlEVcY/hqdefault.jpg'
  },
  {
    id: '4xDzrJKXOOY',
    source: 'youtube',
    title: 'Synthwave Radio - Chill synth / retro beats',
    artist: 'Lofi Girl Synthwave',
    duration: 'Live',
    thumbnail: 'https://i.ytimg.com/vi/4xDzrJKXOOY/hqdefault.jpg'
  },
  {
    id: 'spotify-demo-1',
    source: 'spotify',
    title: 'Starboy',
    artist: 'The Weeknd, Daft Punk',
    duration: '3:50',
    thumbnail: 'https://i.scdn.co/image/ab67616d0000b2734718e2b124f79258be7bc452',
    fallbackQuery: 'The Weeknd Starboy official audio'
  },
  {
    id: 'spotify-demo-2',
    source: 'spotify',
    title: 'Midnight City',
    artist: 'M83',
    duration: '4:03',
    thumbnail: 'https://i.scdn.co/image/ab67616d0000b273f6b450702d7e63ef01ebec5e',
    fallbackQuery: 'M83 Midnight City official audio'
  }
];

// Helper: HTTP GET request returning a promise
function fetchHttps(targetUrl, headers = {}) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(targetUrl);
    const options = {
      hostname: parsed.hostname,
      path: parsed.pathname + parsed.search,
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        ...headers
      }
    };

    const req = https.request(options, (res) => {
      // Handle redirects
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        let redirectUrl = res.headers.location;
        if (!redirectUrl.startsWith('http')) {
          redirectUrl = new URL(redirectUrl, targetUrl).toString();
        }
        return resolve(fetchHttps(redirectUrl, headers));
      }

      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        resolve({ status: res.statusCode, data });
      });
    });

    req.on('error', reject);
    req.setTimeout(8000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    req.end();
  });
}

// Extract YouTube video results by scraping public search results page
async function searchYouTube(query) {
  try {
    const encoded = encodeURIComponent(query);
    const searchUrl = `https://www.youtube.com/results?search_query=${encoded}&sp=EgIQAQ%253D%253D`; // filter for videos only
    const response = await fetchHttps(searchUrl);

    if (response.status !== 200) {
      throw new Error(`YouTube responded with status ${response.status}`);
    }

    const html = response.data;
    const marker = 'var ytInitialData = ';
    const startIndex = html.indexOf(marker);
    if (startIndex === -1) {
      throw new Error('ytInitialData marker not found');
    }

    const jsonStart = startIndex + marker.length;
    let jsonEnd = html.indexOf(';</script>', jsonStart);
    if (jsonEnd === -1) {
      jsonEnd = html.indexOf('};', jsonStart) + 1;
    }

    const jsonRaw = html.substring(jsonStart, jsonEnd);
    const parsedData = JSON.parse(jsonRaw);

    const items = [];
    const contents = parsedData?.contents?.twoColumnSearchResultsRenderer?.primaryContents?.sectionListRenderer?.contents;
    if (contents && Array.isArray(contents)) {
      for (const section of contents) {
        const itemSection = section?.itemSectionRenderer?.contents;
        if (!itemSection || !Array.isArray(itemSection)) continue;

        for (const item of itemSection) {
          const video = item.videoRenderer;
          if (!video || !video.videoId) continue;

          const title = video.title?.runs?.map(r => r.text).join('') || 'Unknown Title';
          const artist = video.ownerText?.runs?.map(r => r.text).join('') || 'Unknown Artist';
          const duration = video.lengthText?.simpleText || 'Live';
          const thumbnail = video.thumbnail?.thumbnails?.[0]?.url || `https://i.ytimg.com/vi/${video.videoId}/hqdefault.jpg`;

          items.push({
            id: video.videoId,
            source: 'youtube',
            title,
            artist,
            duration,
            thumbnail
          });

          if (items.length >= 15) break;
        }
        if (items.length >= 15) break;
      }
    }

    return items;
  } catch (err) {
    console.error('YouTube search scraper failed, using fallback filter:', err.message);
    // Fallback: filter featured tracks by keyword
    const q = query.toLowerCase();
    return FEATURED_TRACKS.filter(t => 
      t.title.toLowerCase().includes(q) || t.artist.toLowerCase().includes(q)
    );
  }
}

// Search Spotify or resolve metadata
async function searchSpotify(query) {
  // If user pasted a Spotify track URL
  const trackUrlMatch = query.match(/open\.spotify\.com\/track\/([a-zA-Z0-9]+)/);
  if (trackUrlMatch) {
    try {
      const oembedUrl = `https://open.spotify.com/oembed?url=${encodeURIComponent(query)}`;
      const res = await fetchHttps(oembedUrl);
      if (res.status === 200) {
        const json = JSON.parse(res.data);
        return [{
          id: trackUrlMatch[1],
          source: 'spotify',
          title: json.title || 'Spotify Track',
          artist: json.author_name || 'Spotify Artist',
          duration: '3:30',
          thumbnail: json.thumbnail_url || '',
          fallbackQuery: `${json.title} ${json.author_name} official audio`
        }];
      }
    } catch (e) {
      console.error('Spotify oEmbed lookup failed:', e.message);
    }
  }

  // Spotify catalog query fallback: search YouTube for track audio while labeling as Spotify source
  try {
    const ytResults = await searchYouTube(`${query} official audio`);
    return ytResults.map(item => ({
      ...item,
      source: 'spotify',
      spotifyMatchId: item.id,
      fallbackQuery: `${item.title} ${item.artist}`
    }));
  } catch (err) {
    const q = query.toLowerCase();
    return FEATURED_TRACKS.filter(t => t.source === 'spotify' && (
      t.title.toLowerCase().includes(q) || t.artist.toLowerCase().includes(q)
    ));
  }
}

// Serve MIME types
const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon'
};

const server = http.createServer(async (req, res) => {
  const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = parsedUrl.pathname;

  // API Routes
  if (pathname === '/api/popular') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify({ tracks: FEATURED_TRACKS }));
    return;
  }

  if (pathname === '/api/search') {
    const query = parsedUrl.searchParams.get('q') || '';
    const source = parsedUrl.searchParams.get('source') || 'youtube';

    if (!query.trim()) {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ tracks: FEATURED_TRACKS }));
      return;
    }

    try {
      let results = [];
      if (source === 'spotify') {
        results = await searchSpotify(query);
      } else {
        results = await searchYouTube(query);
      }

      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ tracks: results }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ error: err.message, tracks: [] }));
    }
    return;
  }

  if (pathname === '/api/resolve') {
    const title = parsedUrl.searchParams.get('title') || '';
    const artist = parsedUrl.searchParams.get('artist') || '';
    const resolveQuery = `${title} ${artist} audio`.trim();

    try {
      const results = await searchYouTube(resolveQuery);
      const topMatch = results[0] || null;
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ match: topMatch }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ error: err.message, match: null }));
    }
    return;
  }

  // Static File Serving
  let relativePath = pathname === '/' ? 'index.html' : pathname.replace(/^\//, '');
  let filePath = path.join(CLIENT_DIR, relativePath);

  // Security check: prevent directory traversal
  if (!filePath.startsWith(CLIENT_DIR)) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('Access Denied');
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      // Fallback to index.html for SPA routing
      const fallbackIndex = path.join(CLIENT_DIR, 'index.html');
      fs.readFile(fallbackIndex, (errIndex, data) => {
        if (errIndex) {
          res.writeHead(404, { 'Content-Type': 'text/plain' });
          res.end('Not Found');
          return;
        }
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(data);
      });
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';

    fs.readFile(filePath, (readErr, content) => {
      if (readErr) {
        res.writeHead(500, { 'Content-Type': 'text/plain' });
        res.end('Server Error');
        return;
      }
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(content);
    });
  });
});

server.listen(PORT, () => {
  console.log(`[TubeFast Web Player] Server online at http://localhost:${PORT}`);
});
