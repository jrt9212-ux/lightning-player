import urllib.request, json, subprocess, time, os, base64
import websocket

edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
html_path = os.path.abspath('client/index.html').replace('\\', '/')
profile_path = os.path.abspath('scratch/edge_prof_check')
os.makedirs(profile_path, exist_ok=True)

cmd = [
    edge_path,
    '--headless=new',
    '--remote-debugging-port=9224',
    f'--user-data-dir={profile_path}',
    '--window-size=1280,800',
    f'file:///{html_path}'
]
proc = subprocess.Popen(cmd)
time.sleep(2)

try:
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9224/json').read().decode())
    target = [t for t in tabs if 'index.html' in t.get('url', '')][0]
    ws = websocket.create_connection(target['webSocketDebuggerUrl'])
    
    js_code = """
    const bar = document.getElementById('categoryPillBar');
    bar.style.display = 'flex';
    bar.innerHTML = `
      <button class="category-pill active" data-cat="all"><span class="pill-emoji">🔥</span><span class="pill-name">All Categories</span><span class="pill-badge">125</span></button>
      <button class="category-pill" data-cat="foryou"><span class="pill-emoji">✨</span><span class="pill-name">Made For You</span><span class="pill-badge">15</span></button>
      <button class="category-pill" data-cat="chill"><span class="pill-emoji">🌙</span><span class="pill-name">Chill & Lo-Fi Beats</span><span class="pill-badge">25</span></button>
      <button class="category-pill" data-cat="rap"><span class="pill-emoji">⚡</span><span class="pill-name">Rap & Trap Anthems</span><span class="pill-badge">25</span></button>
    `;
    const rect = bar.getBoundingClientRect();
    const pill = bar.querySelector('.category-pill.active').getBoundingClientRect();
    ({
      bar: { top: rect.top, bottom: rect.bottom, height: rect.height },
      pill: { top: pill.top, bottom: pill.bottom, height: pill.height, offsetTop: pill.top - rect.top }
    })
    """
    
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'returnByValue': True}}))
    res = json.loads(ws.recv())
    print('Geometry:', json.dumps(res['result']['result']['value'], indent=2))
    
    clip_js = """
    (() => {
        const barElem = document.getElementById('categoryPillBar');
        const r = barElem.getBoundingClientRect();
        return { x: r.x, y: r.y, width: r.width, height: r.height, scale: 1 };
    })()
    """
    ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': clip_js, 'returnByValue': True}}))
    eval2 = json.loads(ws.recv())
    print('eval2 keys:', eval2.keys())
    print('eval2:', eval2)
    clip_res = eval2.get('result', {}).get('result', {}).get('value', {})
    
    ws.send(json.dumps({
        'id': 3,
        'method': 'Page.captureScreenshot',
        'params': {
            'format': 'png',
            'clip': clip_res
        }
    }))
    res2 = json.loads(ws.recv())
    with open('scratch/pill_bar_screenshot.png', 'wb') as f:
        f.write(base64.b64decode(res2['result']['data']))
    print('Saved scratch/pill_bar_screenshot.png')
    
finally:
    proc.terminate()
