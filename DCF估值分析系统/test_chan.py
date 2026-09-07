import re

with open('上市公司K线/澜起科技_688008_日线_20251113_20260515.txt', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

klines = []
for line in lines[1:]:
    parts = re.split(r'\s+', line.strip())
    parts = [p for p in parts if p]
    if len(parts) >= 6:
        try:
            o, h, l, c = float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])
            klines.append({'o': o, 'h': h, 'l': l, 'c': c})
        except:
            pass

print(f'K线数量: {len(klines)}')

rawTops, rawBottoms = [], []
for i in range(1, len(klines) - 1):
    p, c, n = klines[i-1], klines[i], klines[i+1]
    if c['h'] >= p['h'] and c['h'] >= n['h'] and c['l'] >= p['l'] and c['l'] >= n['l'] and (c['h'] > p['h'] or c['h'] > n['h']):
        rawTops.append({'index': i, 'price': c['h']})
    if c['l'] <= p['l'] and c['l'] <= n['l'] and c['h'] <= p['h'] and c['h'] <= n['h'] and (c['l'] < p['l'] or c['l'] < n['l']):
        rawBottoms.append({'index': i, 'price': c['l']})

print(f'原始顶分型: {len(rawTops)}, 原始底分型: {len(rawBottoms)}')

tops, bottoms = [], []
for t in rawTops:
    if tops and t['index'] - tops[-1]['index'] <= 2:
        if t['price'] > tops[-1]['price']:
            tops[-1]['price'] = t['price']
            tops[-1]['index'] = t['index']
    else:
        tops.append({**t, 'type': 'top'})

for b in rawBottoms:
    if bottoms and b['index'] - bottoms[-1]['index'] <= 2:
        if b['price'] < bottoms[-1]['price']:
            bottoms[-1]['price'] = b['price']
            bottoms[-1]['index'] = b['index']
    else:
        bottoms.append({**b, 'type': 'bottom'})

print(f'过滤后顶分型: {len(tops)}, 底分型: {len(bottoms)}')

pts = sorted(tops + bottoms, key=lambda x: x['index'])
bi = []
for i in range(len(pts) - 1):
    dist = pts[i+1]['index'] - pts[i]['index']
    if pts[i]['type'] != pts[i+1]['type'] and dist >= 3:
        bi.append({
            'from': pts[i]['index'], 'to': pts[i+1]['index'],
            'fromPrice': pts[i]['price'], 'toPrice': pts[i+1]['price'],
            'direction': 'down' if pts[i]['type'] == 'top' else 'up'
        })

print(f'笔数量: {len(bi)}')
for i, b in enumerate(bi):
    print(f'  笔{i}: {b["direction"]} K{b["from"]}->K{b["to"]} {b["fromPrice"]:.1f}->{b["toPrice"]:.1f}')

zs = []
for i in range(len(bi) - 2):
    d1, d2, d3 = bi[i]['direction'], bi[i+1]['direction'], bi[i+2]['direction']
    if not (d1 != d2 and d2 != d3):
        continue
    highs = [max(bi[i]['fromPrice'], bi[i]['toPrice']), max(bi[i+1]['fromPrice'], bi[i+1]['toPrice']), max(bi[i+2]['fromPrice'], bi[i+2]['toPrice'])]
    lows = [min(bi[i]['fromPrice'], bi[i]['toPrice']), min(bi[i+1]['fromPrice'], bi[i+1]['toPrice']), min(bi[i+2]['fromPrice'], bi[i+2]['toPrice'])]
    upper = min(highs)
    lower = max(lows)
    if upper > lower:
        zs.append({'fromIdx': bi[i]['from'], 'toIdx': bi[i+2]['to'], 'upper': upper, 'lower': lower})

print(f'原始中枢: {len(zs)}')
for i, z in enumerate(zs):
    print(f'  中枢{i}: [{z["lower"]:.1f}, {z["upper"]:.1f}] K{z["fromIdx"]}~{z["toIdx"]}')

merged = []
for z in zs:
    if merged and z['fromIdx'] <= merged[-1]['toIdx'] + 2:
        overlap = min(merged[-1]['upper'], z['upper']) - max(merged[-1]['lower'], z['lower'])
        minRange = min(merged[-1]['upper'] - merged[-1]['lower'], z['upper'] - z['lower'])
        if overlap > 0 and overlap > minRange * 0.2:
            merged[-1]['toIdx'] = max(merged[-1]['toIdx'], z['toIdx'])
            merged[-1]['upper'] = min(merged[-1]['upper'], z['upper'])
            merged[-1]['lower'] = max(merged[-1]['lower'], z['lower'])
            continue
    merged.append({**z})

print(f'合并后中枢: {len(merged)}')
for i, z in enumerate(merged):
    print(f'  中枢{i+1}: [{z["lower"]:.1f}, {z["upper"]:.1f}] K{z["fromIdx"]}~{z["toIdx"]}')
