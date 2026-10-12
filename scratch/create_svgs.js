const fs = require('fs');
const path = require('path');

const targetDir = path.join(__dirname, '..', 'assets', 'providers');

// 1. Groq - Crisp orange squircle with sharp white lightning bolt
fs.writeFileSync(
  path.join(targetDir, 'groq.svg'),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><rect width="128" height="128" rx="28" fill="#F04E23"/><polygon points="74,16 34,70 66,70 54,112 94,56 64,56" fill="#FFFFFF"/></svg>`
);

// 2. Mistral - Crisp orange/red gradient with geometric M pixel blocks
fs.writeFileSync(
  path.join(targetDir, 'mistral.svg'),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><defs><linearGradient id="mg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#FFCE00"/><stop offset="50%" stop-color="#FF5A00"/><stop offset="100%" stop-color="#EE0000"/></linearGradient></defs><rect width="128" height="128" rx="28" fill="url(#mg)"/><g fill="#FFFFFF"><rect x="28" y="38" width="14" height="52" rx="2"/><rect x="44" y="54" width="12" height="36" rx="2"/><rect x="58" y="68" width="12" height="22" rx="2"/><rect x="72" y="54" width="12" height="36" rx="2"/><rect x="86" y="38" width="14" height="52" rx="2"/></g></svg>`
);

// 3. Cerebras - Clean wafer dots grid
fs.writeFileSync(
  path.join(targetDir, 'cerebras.svg'),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><rect width="128" height="128" rx="28" fill="#FFF1F2"/><g fill="#E51943"><rect x="30" y="30" width="18" height="18" rx="3"/><rect x="55" y="30" width="18" height="18" rx="3"/><rect x="80" y="30" width="18" height="18" rx="3"/><rect x="30" y="55" width="18" height="18" rx="3"/><rect x="55" y="55" width="18" height="18" rx="3"/><rect x="80" y="55" width="18" height="18" rx="3"/><rect x="30" y="80" width="18" height="18" rx="3"/><rect x="55" y="80" width="18" height="18" rx="3"/><rect x="80" y="80" width="18" height="18" rx="3"/></g></svg>`
);

console.log('Crisp SVGs generated successfully!');
