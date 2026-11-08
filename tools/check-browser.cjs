// Browser smoke test for the local wiki. No external network is used.
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const browser = 'C:\\Users\\24790\\AppData\\Local\\ms-playwright\\chromium-1237\\chrome-win64\\chrome.exe';
const output = path.join(root, 'build', 'screenshots');
fs.mkdirSync(output, { recursive: true });
const pages = [
  ['home', '首页'],
  ['warfare', '机制:战争基础'],
  ['character', '人物/破军使徒:菲奥伦扎·斯科桑蒂'],
  ['routes', '坚毅使徒/战区路线图'],
  ['card', '蔑世使徒:可悲的疯人'],
];
for (const [name, title] of pages) {
  const url = 'http://localhost:8090/index.php?title=' + encodeURIComponent(title);
  const args = [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
    '--window-size=1440,1100', '--virtual-time-budget=10000',
    '--screenshot=' + path.join(output, name + '.png'), url,
  ];
  execFileSync(browser, args, { stdio: 'pipe', timeout: 30000 });
  const dump = execFileSync(browser, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--virtual-time-budget=8000',
    '--dump-dom', url,
  ], { encoding: 'utf8', maxBuffer: 20 * 1024 * 1024, timeout: 30000 });
  fs.writeFileSync(path.join(output, name + '.html'), dump, 'utf8');
  const images = [...dump.matchAll(/<img\b[^>]*>/g)].map(m => m[0]);
  const badModLinks = (dump.match(/title="[^"]*Mod[/:][^"]*（页面不存在）/g) || []).length;
  const headings = [...dump.matchAll(/<h[12][^>]*>(.*?)<\/h[12]>/g)].map(m => m[1].replace(/<[^>]+>/g, ''));
  console.log(JSON.stringify({ name, url, images: images.length, badModLinks, headings }));
}
