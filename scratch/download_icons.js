const fs = require('fs');
const path = require('path');

const targetDir = path.join(__dirname, '..', 'assets', 'providers');
if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

async function run() {
  console.log('Fetching provider file list from GitHub API...');
  const res = await fetch('https://api.github.com/repos/decolua/9router/contents/public/providers?ref=master', {
    headers: { 'User-Agent': 'AntiHalu-Downloader' }
  });
  const files = await res.json();
  if (!Array.isArray(files)) {
    console.error('API response is not an array:', files);
    return;
  }

  console.log(`Found ${files.length} icon files. Starting download...`);
  let downloaded = 0;
  let skipped = 0;

  // Concurrency pool of 5
  const queue = [...files];
  const workers = Array(6).fill(null).map(async () => {
    while (queue.length > 0) {
      const file = queue.shift();
      const destPath = path.join(targetDir, file.name);
      if (fs.existsSync(destPath) && fs.statSync(destPath).size > 100) {
        skipped++;
        continue;
      }
      try {
        const r = await fetch(file.download_url);
        if (r.ok) {
          const buf = await r.arrayBuffer();
          fs.writeFileSync(destPath, Buffer.from(buf));
          downloaded++;
        } else {
          console.warn(`Failed to fetch ${file.name}: ${r.status}`);
        }
      } catch (err) {
        console.error(`Error downloading ${file.name}:`, err.message);
      }
    }
  });

  await Promise.all(workers);
  console.log(`Finished! Downloaded: ${downloaded}, Skipped: ${skipped}, Total local: ${fs.readdirSync(targetDir).length}`);
}

run();
