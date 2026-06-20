#!/usr/bin/env python3
"""
2026 世界盃比分更新腳本 v4
執行方式：python3 update_scores.py
功能：從 fifacom.tw 抓取比分 → 在本機生成完整 ICS → 透過 Cloudflare REST API 寫入 KV
"""

import re, json, ssl, urllib.request, urllib.parse, sys, os
from datetime import datetime, timezone, timedelta

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

ACCOUNT_ID     = "89d786906d13196a7a9f7f43eb70922a"
KV_NAMESPACE_ID = "2bd8237a6b864195a66d83b522ff439f"

# ── 場地資料 ──────────────────────────────────────────────────────────────────
VENUES = {
  'Azteca':    {'name':'Estadio Azteca',           'city':'Mexico City, Mexico',              'tz':'America/Mexico_City', 'off':-5},
  'Akron':     {'name':'Estadio Akron',            'city':'Zapopan, Mexico',                  'tz':'America/Mexico_City', 'off':-5},
  'BMO':       {'name':'BMO Field',                'city':'Toronto, Canada',                  'tz':'America/Toronto',     'off':-4},
  'BC':        {'name':'BC Place',                 'city':'Vancouver, Canada',                'tz':'America/Vancouver',   'off':-7},
  'SoFi':      {'name':'SoFi Stadium',             'city':'Inglewood, California, USA',       'tz':'America/Los_Angeles', 'off':-7},
  'Levis':     {'name':"Levi's Stadium",           'city':'Santa Clara, California, USA',     'tz':'America/Los_Angeles', 'off':-7},
  'MetLife':   {'name':'MetLife Stadium',          'city':'East Rutherford, New Jersey, USA', 'tz':'America/New_York',    'off':-4},
  'Gillette':  {'name':'Gillette Stadium',         'city':'Foxborough, Massachusetts, USA',   'tz':'America/New_York',    'off':-4},
  'LFF':       {'name':'Lincoln Financial Field',  'city':'Philadelphia, Pennsylvania, USA',  'tz':'America/New_York',    'off':-4},
  'NRG':       {'name':'NRG Stadium',              'city':'Houston, Texas, USA',              'tz':'America/Chicago',     'off':-5},
  'ATT':       {'name':'AT&T Stadium',             'city':'Arlington, Texas, USA',            'tz':'America/Chicago',     'off':-5},
  'Arrowhead': {'name':'Arrowhead Stadium',        'city':'Kansas City, Missouri, USA',       'tz':'America/Chicago',     'off':-5},
  'MBZ':       {'name':'Mercedes-Benz Stadium',    'city':'Atlanta, Georgia, USA',            'tz':'America/New_York',    'off':-4},
  'Lumen':     {'name':'Lumen Field',              'city':'Seattle, Washington, USA',         'tz':'America/Los_Angeles', 'off':-7},
  'HardRock':  {'name':'Hard Rock Stadium',        'city':'Miami Gardens, Florida, USA',      'tz':'America/New_York',    'off':-4},
  'BBVA':      {'name':'Estadio BBVA',             'city':'Monterrey, Mexico',                'tz':'America/Monterrey',   'off':-5},
}

# ── 繁體中文隊名 ──────────────────────────────────────────────────────────────
NAMES_ZH = {
  'Mexico':'墨西哥','South Africa':'南非','South Korea':'南韓','Czechia':'捷克',
  'Canada':'加拿大','Bosnia':'波士尼亞','USA':'美國','Paraguay':'巴拉圭',
  'Qatar':'卡達','Switzerland':'瑞士','Brazil':'巴西','Morocco':'摩洛哥',
  'Haiti':'海地','Scotland':'蘇格蘭','Australia':'澳洲','Turkey':'土耳其',
  'Germany':'德國','Curacao':'庫拉索','Netherlands':'荷蘭','Japan':'日本',
  'IvoryCoast':'象牙海岸','Ecuador':'厄瓜多','Sweden':'瑞典','Tunisia':'突尼西亞',
  'Spain':'西班牙','CapeVerde':'維德角','Belgium':'比利時','Egypt':'埃及',
  'SaudiArabia':'沙烏地阿拉伯','Uruguay':'烏拉圭','Iran':'伊朗','NewZealand':'紐西蘭',
  'France':'法國','Senegal':'塞內加爾','Iraq':'伊拉克','Norway':'挪威',
  'Argentina':'阿根廷','Algeria':'阿爾及利亞','Austria':'奧地利','Jordan':'約旦',
  'Portugal':'葡萄牙','DRCongo':'剛果民主共和國','England':'英格蘭','Croatia':'克羅埃西亞',
  'Ghana':'迦納','Panama':'巴拿馬','Colombia':'哥倫比亞','Uzbekistan':'烏茲別克',
}

ZH_ALIAS = {
  '墨西哥':'Mexico','南非':'South Africa','南韓':'South Korea','捷克':'Czechia',
  '加拿大':'Canada','波士尼亞':'Bosnia','美國':'USA','巴拉圭':'Paraguay',
  '卡達':'Qatar','瑞士':'Switzerland','巴西':'Brazil','摩洛哥':'Morocco',
  '海地':'Haiti','蘇格蘭':'Scotland',
  '澳大利亞':'Australia','澳洲':'Australia',
  '土耳其':'Turkey','德國':'Germany','庫拉索':'Curacao',
  '荷蘭':'Netherlands','日本':'Japan','象牙海岸':'IvoryCoast',
  '厄瓜多':'Ecuador','瑞典':'Sweden','突尼西亞':'Tunisia',
  '西班牙':'Spain','維德角':'CapeVerde','比利時':'Belgium','埃及':'Egypt',
  '沙烏地阿拉伯':'SaudiArabia','烏拉圭':'Uruguay','伊朗':'Iran',
  '紐西蘭':'NewZealand','法國':'France','塞內加爾':'Senegal',
  '伊拉克':'Iraq','挪威':'Norway','阿根廷':'Argentina',
  '阿爾及利亞':'Algeria','奧地利':'Austria','約旦':'Jordan',
  '葡萄牙':'Portugal','剛果民主共和國':'DRCongo',
  '英格蘭':'England','克羅埃西亞':'Croatia','迦納':'Ghana',
  '巴拿馬':'Panama','哥倫比亞':'Colombia','烏茲別克':'Uzbekistan',
}

STAGE_ZH = {
  'GA':'小組賽：A組','GB':'小組賽：B組','GC':'小組賽：C組','GD':'小組賽：D組',
  'GE':'小組賽：E組','GF':'小組賽：F組','GG':'小組賽：G組','GH':'小組賽：H組',
  'GI':'小組賽：I組','GJ':'小組賽：J組','GK':'小組賽：K組','GL':'小組賽：L組',
  'R32':'三十二強','R16':'十六強','QF':'八強','SF':'四強','3P':'季軍賽','FIN':'決賽',
}
STAGE_EN = {
  'GA':'Group A','GB':'Group B','GC':'Group C','GD':'Group D',
  'GE':'Group E','GF':'Group F','GG':'Group G','GH':'Group H',
  'GI':'Group I','GJ':'Group J','GK':'Group K','GL':'Group L',
  'R32':'Round of 32','R16':'Round of 16','QF':'Quarterfinals',
  'SF':'Semifinals','3P':'Third-Place Match','FIN':'Final',
}

# ── 104 場賽事 [no, dtstart_utc, dur_min, venue, t1, t2, stage] ──────────────
MATCHES = [
  [1,'20260611T190000Z',120,'Azteca','Mexico','South Africa','GA'],
  [2,'20260612T020000Z',120,'Akron','South Korea','Czechia','GA'],
  [3,'20260612T190000Z',120,'BMO','Canada','Bosnia','GB'],
  [4,'20260613T010000Z',120,'SoFi','USA','Paraguay','GD'],
  [5,'20260613T160000Z',120,'Levis','Qatar','Switzerland','GB'],
  [6,'20260613T200000Z',120,'MetLife','Brazil','Morocco','GC'],
  [7,'20260613T230000Z',120,'Gillette','Haiti','Scotland','GC'],
  [8,'20260614T170000Z',120,'BC','Australia','Turkey','GD'],
  [9,'20260614T200000Z',120,'NRG','Germany','Curacao','GE'],
  [10,'20260614T230000Z',120,'ATT','Netherlands','Japan','GF'],
  [11,'20260615T020000Z',120,'LFF','IvoryCoast','Ecuador','GE'],
  [12,'20260615T040000Z',120,'BBVA','Sweden','Tunisia','GF'],
  [13,'20260615T160000Z',120,'MBZ','Spain','CapeVerde','GH'],
  [14,'20260615T190000Z',120,'Lumen','Belgium','Egypt','GG'],
  [15,'20260615T230000Z',120,'HardRock','SaudiArabia','Uruguay','GH'],
  [16,'20260616T020000Z',120,'SoFi','Iran','NewZealand','GG'],
  [17,'20260616T190000Z',120,'MetLife','France','Senegal','GI'],
  [18,'20260616T220000Z',120,'Gillette','Iraq','Norway','GI'],
  [19,'20260617T010000Z',120,'Arrowhead','Argentina','Algeria','GJ'],
  [20,'20260617T170000Z',120,'Levis','Austria','Jordan','GJ'],
  [21,'20260617T200000Z',120,'NRG','Portugal','DRCongo','GK'],
  [22,'20260617T230000Z',120,'ATT','England','Croatia','GL'],
  [23,'20260618T020000Z',120,'BMO','Ghana','Panama','GL'],
  [24,'20260618T040000Z',120,'Azteca','Colombia','Uzbekistan','GK'],
  [25,'20260618T190000Z',120,'MBZ','Czechia','South Africa','GA'],
  [26,'20260618T220000Z',120,'SoFi','Switzerland','Bosnia','GB'],
  [27,'20260619T010000Z',120,'BC','Canada','Qatar','GB'],
  [28,'20260619T040000Z',120,'Akron','Mexico','South Korea','GA'],
  [29,'20260619T190000Z',120,'Lumen','USA','Australia','GD'],
  [30,'20260619T220000Z',120,'Gillette','Scotland','Morocco','GC'],
  [31,'20260620T003000Z',120,'LFF','Brazil','Haiti','GC'],
  [32,'20260620T030000Z',120,'Levis','Turkey','Paraguay','GD'],
  [33,'20260620T040000Z',120,'BBVA','Tunisia','Japan','GF'],
  [34,'20260620T170000Z',120,'NRG','Netherlands','Sweden','GF'],
  [35,'20260620T200000Z',120,'BMO','Germany','IvoryCoast','GE'],
  [36,'20260621T000000Z',120,'Arrowhead','Ecuador','Curacao','GE'],
  [37,'20260621T160000Z',120,'MBZ','Spain','SaudiArabia','GH'],
  [38,'20260621T190000Z',120,'SoFi','Belgium','Iran','GG'],
  [39,'20260621T220000Z',120,'HardRock','Uruguay','CapeVerde','GH'],
  [40,'20260622T010000Z',120,'BC','NewZealand','Egypt','GG'],
  [41,'20260622T170000Z',120,'ATT','Argentina','Austria','GJ'],
  [42,'20260622T210000Z',120,'LFF','France','Iraq','GI'],
  [43,'20260623T000000Z',120,'MetLife','Norway','Senegal','GI'],
  [44,'20260623T030000Z',120,'Levis','Jordan','Algeria','GJ'],
  [45,'20260623T170000Z',120,'NRG','Portugal','Uzbekistan','GK'],
  [46,'20260623T200000Z',120,'Gillette','England','Ghana','GL'],
  [47,'20260623T230000Z',120,'BMO','Panama','Croatia','GL'],
  [48,'20260624T020000Z',120,'Akron','Colombia','DRCongo','GK'],
  [49,'20260624T190000Z',120,'BC','Switzerland','Canada','GB'],
  [50,'20260624T190000Z',120,'Lumen','Bosnia','Qatar','GB'],
  [51,'20260624T220000Z',120,'HardRock','Scotland','Brazil','GC'],
  [52,'20260624T220000Z',120,'MBZ','Morocco','Haiti','GC'],
  [53,'20260625T010000Z',120,'Azteca','Czechia','Mexico','GA'],
  [54,'20260625T010000Z',120,'BBVA','South Africa','South Korea','GA'],
  [55,'20260625T200000Z',120,'LFF','Curacao','IvoryCoast','GE'],
  [56,'20260625T200000Z',120,'MetLife','Ecuador','Germany','GE'],
  [57,'20260625T230000Z',120,'ATT','Japan','Sweden','GF'],
  [58,'20260625T230000Z',120,'Arrowhead','Tunisia','Netherlands','GF'],
  [59,'20260626T020000Z',120,'SoFi','Turkey','USA','GD'],
  [60,'20260626T020000Z',120,'Levis','Paraguay','Australia','GD'],
  [61,'20260626T190000Z',120,'Gillette','Norway','France','GI'],
  [62,'20260626T190000Z',120,'BMO','Senegal','Iraq','GI'],
  [63,'20260627T000000Z',120,'NRG','CapeVerde','SaudiArabia','GH'],
  [64,'20260627T000000Z',120,'Akron','Uruguay','Spain','GH'],
  [65,'20260627T030000Z',120,'Lumen','Egypt','Iran','GG'],
  [66,'20260627T030000Z',120,'BC','NewZealand','Belgium','GG'],
  [67,'20260627T210000Z',120,'MetLife','Panama','England','GL'],
  [68,'20260627T210000Z',120,'LFF','Croatia','Ghana','GL'],
  [69,'20260627T233000Z',120,'HardRock','Colombia','Portugal','GK'],
  [70,'20260627T233000Z',120,'MBZ','DRCongo','Uzbekistan','GK'],
  [71,'20260628T020000Z',120,'Arrowhead','Algeria','Austria','GJ'],
  [72,'20260628T020000Z',120,'ATT','Jordan','Argentina','GJ'],
  [73,'20260628T190000Z',150,'SoFi','A組亞軍','B組亞軍','R32'],
  [74,'20260629T170000Z',150,'Gillette','E組冠軍','最佳第三名①','R32'],
  [75,'20260629T200000Z',150,'BBVA','F組冠軍','C組亞軍','R32'],
  [76,'20260629T210000Z',150,'NRG','C組冠軍','F組亞軍','R32'],
  [77,'20260630T170000Z',150,'MetLife','I組冠軍','最佳第三名②','R32'],
  [78,'20260630T210000Z',150,'ATT','E組亞軍','I組亞軍','R32'],
  [79,'20260630T230000Z',150,'Azteca','墨西哥','最佳第三名③','R32'],
  [80,'20260701T160000Z',150,'MBZ','L組冠軍','最佳第三名④','R32'],
  [81,'20260701T200000Z',150,'Levis','D組冠軍','最佳第三名⑤','R32'],
  [82,'20260701T210000Z',150,'Lumen','G組冠軍','最佳第三名⑥','R32'],
  [83,'20260702T190000Z',150,'BMO','K組亞軍','L組亞軍','R32'],
  [84,'20260702T190000Z',150,'SoFi','H組冠軍','J組亞軍','R32'],
  [85,'20260703T030000Z',150,'BC','B組冠軍','最佳第三名⑦','R32'],
  [86,'20260703T220000Z',150,'HardRock','J組冠軍','H組亞軍','R32'],
  [87,'20260704T013000Z',150,'Arrowhead','K組冠軍','最佳第三名⑧','R32'],
  [88,'20260703T180000Z',150,'ATT','D組亞軍','G組亞軍','R32'],
  [89,'20260704T210000Z',150,'LFF','M74勝者','M77勝者','R16'],
  [90,'20260704T170000Z',150,'NRG','M73勝者','M75勝者','R16'],
  [91,'20260705T200000Z',150,'MetLife','M76勝者','M78勝者','R16'],
  [92,'20260705T210000Z',150,'Azteca','M79勝者','M80勝者','R16'],
  [93,'20260706T190000Z',150,'ATT','M83勝者','M84勝者','R16'],
  [94,'20260706T200000Z',150,'Lumen','M81勝者','M82勝者','R16'],
  [95,'20260707T160000Z',150,'MBZ','M86勝者','M88勝者','R16'],
  [96,'20260707T200000Z',150,'BC','M85勝者','M87勝者','R16'],
  [97,'20260709T200000Z',150,'Gillette','M89勝者','M90勝者','QF'],
  [98,'20260710T190000Z',150,'SoFi','M93勝者','M94勝者','QF'],
  [99,'20260711T210000Z',150,'HardRock','M91勝者','M92勝者','QF'],
  [100,'20260712T010000Z',150,'Arrowhead','M95勝者','M96勝者','QF'],
  [101,'20260714T190000Z',150,'ATT','M97勝者','M98勝者','SF'],
  [102,'20260715T190000Z',150,'MBZ','M99勝者','M100勝者','SF'],
  [103,'20260718T210000Z',150,'HardRock','四強負者①','四強負者②','3P'],
  [104,'20260719T190000Z',180,'MetLife','M101勝者','M102勝者','FIN'],
]

# 有效的小組賽配對 key（用於比分對應）
VALID_KEYS = set()
for no, dtstart, dur, vkey, t1, t2, stage in MATCHES:
    if stage.startswith('G'):
        VALID_KEYS.add(f'{t1}|{t2}')

# ── 時間工具 ──────────────────────────────────────────────────────────────────
def _parse_dt(dtstart):
    s = dtstart  # e.g. '20260611T190000Z'
    return datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]),
                    int(s[9:11]), int(s[11:13]), tzinfo=timezone.utc)

def utc_to_tw(dtstart):
    return (_parse_dt(dtstart) + timedelta(hours=8)).strftime('%Y/%m/%d %H:%M')

def utc_to_local(dtstart, offset_h):
    return (_parse_dt(dtstart) + timedelta(hours=offset_h)).strftime('%Y/%m/%d %H:%M')

def calc_dtend(dtstart, dur_min):
    return (_parse_dt(dtstart) + timedelta(minutes=dur_min)).strftime('%Y%m%dT%H%M%SZ')

# ── ICS 折行（RFC 5545，以 UTF-8 bytes 計算） ──────────────────────────────────
def fold_line(line):
    encoded = line.encode('utf-8')
    if len(encoded) <= 75:
        return line + '\r\n'
    parts = []
    current = b''
    for ch in line:
        cb = ch.encode('utf-8')
        if len(current) + len(cb) > 75:
            parts.append(current.decode('utf-8'))
            current = b' ' + cb
        else:
            current += cb
    if current:
        parts.append(current.decode('utf-8'))
    return '\r\n'.join(parts) + '\r\n'

# ── ICS 生成 ──────────────────────────────────────────────────────────────────
def generate_ics(scores_map):
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//2026 FIFA World Cup//ZH-TW//',
        'X-WR-CALNAME:2026世界盃足球賽',
        'X-WR-CALDESC:2026年FIFA世界盃足球賽完整賽程（含台灣時間，比分自動更新）',
        'X-WR-TIMEZONE:Asia/Taipei',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
    ]

    for no, dtstart, dur_min, vkey, t1, t2, stage in MATCHES:
        v = VENUES[vkey]
        stage_zh = STAGE_ZH[stage]
        stage_en = STAGE_EN[stage]
        t1zh = NAMES_ZH.get(t1, t1)
        t2zh = NAMES_ZH.get(t2, t2)
        score = scores_map.get(f'{t1}|{t2}')

        summary = f'{stage_zh}｜{t1zh} vs {t2zh}（{score}）' if score else f'{stage_zh}｜{t1zh} vs {t2zh}'
        location = f'{v["name"]}\\, {v["city"]}'
        tw_time = utc_to_tw(dtstart)
        local_time = utc_to_local(dtstart, v['off'])
        desc = '\\n'.join([
            f'對戰：{t1zh} vs {t2zh}',
            f'階段：{stage_zh} / {stage_en}',
            f'台灣時間：{tw_time}（UTC+8）',
            f'當地時間：{local_time}（{v["tz"]}）',
            f'地點：{v["name"]}\\, {v["city"]}',
            '提醒：賽程可能因 FIFA 公告更新而調整。',
        ])

        lines += [
            '',
            'BEGIN:VEVENT',
            f'UID:wc2026-match-{str(no).zfill(3)}@calendar',
            f'DTSTART:{dtstart}',
            f'DTEND:{calc_dtend(dtstart, dur_min)}',
            f'SUMMARY:{summary}',
            f'LOCATION:{location}',
            f'DESCRIPTION:{desc}',
            'END:VEVENT',
        ]

    lines += ['', 'END:VCALENDAR']
    return ''.join(fold_line(l) for l in lines)

# ── 隊名別名對應（統一映射到 MATCHES 中使用的英文 key）──────────────────────
TEAM_ALIAS = {
    # 英文變體
    'Mexico':'Mexico','South Africa':'South Africa',
    'Korea Republic':'South Korea','Republic of Korea':'South Korea','South Korea':'South Korea',
    'Czech Republic':'Czechia','Czechia':'Czechia',
    'Canada':'Canada',
    'Bosnia and Herzegovina':'Bosnia','Bosnia & Herzegovina':'Bosnia','Bosnia':'Bosnia',
    'USA':'USA','United States':'USA','United States of America':'USA',
    'Paraguay':'Paraguay','Qatar':'Qatar','Switzerland':'Switzerland',
    'Brazil':'Brazil','Morocco':'Morocco','Haiti':'Haiti','Scotland':'Scotland',
    'Australia':'Australia',
    'Turkey':'Turkey','Türkiye':'Turkey','Turkiye':'Turkey',
    'Germany':'Germany',
    'Curaçao':'Curacao','Curacao':'Curacao',
    'Netherlands':'Netherlands','Japan':'Japan',
    "Côte d'Ivoire":'IvoryCoast',"Cote d'Ivoire":'IvoryCoast','Ivory Coast':'IvoryCoast',
    'Ecuador':'Ecuador','Sweden':'Sweden','Tunisia':'Tunisia',
    'Spain':'Spain','Cape Verde':'CapeVerde','Cabo Verde':'CapeVerde',
    'Belgium':'Belgium','Egypt':'Egypt',
    'Saudi Arabia':'SaudiArabia','KSA':'SaudiArabia',
    'Uruguay':'Uruguay','Iran':'Iran','New Zealand':'NewZealand',
    'France':'France','Senegal':'Senegal','Iraq':'Iraq','Norway':'Norway',
    'Argentina':'Argentina','Algeria':'Algeria','Austria':'Austria','Jordan':'Jordan',
    'Portugal':'Portugal',
    'DR Congo':'DRCongo','Congo DR':'DRCongo','D.R. Congo':'DRCongo',
    'Democratic Republic of the Congo':'DRCongo','Congo, DR':'DRCongo',
    'England':'England','Croatia':'Croatia','Ghana':'Ghana',
    'Panama':'Panama','Colombia':'Colombia','Uzbekistan':'Uzbekistan',
    # 繁體中文（用於中文來源）
    **ZH_ALIAS,
}

def _norm(name):
    """將隊名正規化為 MATCHES 中使用的 key"""
    return TEAM_ALIAS.get(name) or TEAM_ALIAS.get(name.strip())

def _add_score(scores, h_key, a_key, hs, as_):
    """嘗試兩種方向加入比分"""
    k1, k2 = f'{h_key}|{a_key}', f'{a_key}|{h_key}'
    if k1 in VALID_KEYS:
        scores[k1] = f'{hs}-{as_}'
    elif k2 in VALID_KEYS:
        scores[k2] = f'{as_}-{hs}'

# ── 抓取工具 ──────────────────────────────────────────────────────────────────
def fetch_html(url, extra_headers=None):
    headers = {
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
        'Accept': 'text/html,application/xhtml+xml,*/*',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as r:
        raw = r.read()
        enc = r.getheader('Content-Encoding', '')
        if 'gzip' in enc:
            import gzip; raw = gzip.decompress(raw)
        elif 'br' in enc:
            pass  # 忽略 brotli，讓 decode 盡力處理
        return raw.decode('utf-8', errors='replace')

def fetch_json(url, extra_headers=None):
    headers = {
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
        'Accept': 'application/json',
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as r:
        return json.loads(r.read())

# ── 來源 1：ESPN API ──────────────────────────────────────────────────────────
def fetch_espn_scores():
    """ESPN scoreboard API，逐日掃描已完成場次"""
    from datetime import date as date_cls, timedelta
    scores = {}
    start = date_cls(2026, 6, 11)
    today = datetime.now(timezone.utc).date()
    slugs = ['fifa.world', 'fifa.worldcup', 'fifa.world.2026']
    for slug in slugs:
        slug_events = []
        d = start
        while d <= today:
            ds = d.strftime('%Y%m%d')
            try:
                day_data = fetch_json(
                    f'https://site.api.espn.com/apis/v2/sports/soccer/{slug}/scoreboard?dates={ds}')
                day_events = day_data.get('events', [])
                slug_events += day_events
            except Exception:
                pass
            d += timedelta(days=1)
        print(f'      [ESPN/{slug}] {len(slug_events)} events')
        for ev in slug_events:
            comp = (ev.get('competitions') or [{}])[0]
            status = comp.get('status', {}).get('type', {})
            completed = status.get('completed') or status.get('name') in ('STATUS_FINAL', 'STATUS_FULL_TIME')
            if not completed:
                continue
            comps = comp.get('competitors', [])
            home = next((c for c in comps if c.get('homeAway') == 'home'), None)
            away = next((c for c in comps if c.get('homeAway') == 'away'), None)
            if not home or not away: continue
            hk = _norm(home.get('team', {}).get('displayName', ''))
            ak = _norm(away.get('team', {}).get('displayName', ''))
            hs = str(home.get('score', ''))
            as_ = str(away.get('score', ''))
            if not hk or not ak or not hs or not as_: continue
            _add_score(scores, hk, ak, hs, as_)
        if scores:
            break
    return scores

# ── 來源 2：FIFA 官方 API ─────────────────────────────────────────────────────
def fetch_fifa_scores():
    """FIFA 官方賽果 API"""
    scores = {}
    # FIFA API v3
    urls = [
        'https://api.fifa.com/api/v3/calendar/matches?from=2026-06-11&to=2026-07-20&language=EN&count=200&IdCompetition=&IdSeason=&IdStage=',
        'https://www.fifa.com/fifaplus/en/tournaments/mens/worldcup/canadamexicousa2026/news',
    ]
    try:
        data = fetch_json(urls[0], extra_headers={'Origin': 'https://www.fifa.com'})
        results = data.get('Results', [])
        print(f'      [FIFA] {len(results)} matches')
        for m in results:
            if m.get('MatchStatus') not in (0, 3):  # 0=upcoming 3=completed
                continue
            if m.get('MatchStatus') != 3:
                continue
            home = m.get('Home', {}).get('TeamName', [{}])
            away = m.get('Away', {}).get('TeamName', [{}])
            hname = (home[0].get('Description', '') if home else '')
            aname = (away[0].get('Description', '') if away else '')
            hs = str(m.get('Home', {}).get('Score', ''))
            as_ = str(m.get('Away', {}).get('Score', ''))
            hk = _norm(hname)
            ak = _norm(aname)
            if not hk or not ak or not hs or not as_: continue
            _add_score(scores, hk, ak, hs, as_)
    except Exception as e:
        print(f'      [FIFA] err: {e}')
    return scores

# ── 來源 3：TheSportsDB（免費，無需 API key）──────────────────────────────────
def fetch_thesportsdb_scores():
    """TheSportsDB - league 4335 = FIFA World Cup"""
    scores = {}
    # 嘗試多個可能的 league ID
    for lid in ['4335', '4480', '4396']:
        try:
            data = fetch_json(f'https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id={lid}&s=2026')
            events = data.get('events') or []
            print(f'      [TheSportsDB/league{lid}] {len(events)} events')
            for ev in events:
                status = ev.get('strStatus', '')
                if status not in ('FT', 'AET', 'PEN', 'Match Finished', '90'):
                    continue
                hk = _norm(ev.get('strHomeTeam', ''))
                ak = _norm(ev.get('strAwayTeam', ''))
                hs = ev.get('intHomeScore')
                as_ = ev.get('intAwayScore')
                if not hk or not ak or hs is None or as_ is None: continue
                _add_score(scores, hk, ak, str(hs), str(as_))
            if scores:
                break
        except Exception as e:
            print(f'      [TheSportsDB/league{lid}] err: {e}')
    return scores

# ── 來源 4：SofaScore 非官方 API ──────────────────────────────────────────────
def fetch_sofascore_scores():
    """SofaScore - 先查詢正確的 season ID 再抓比分"""
    scores = {}
    headers = {
        'Referer': 'https://www.sofascore.com/',
        'Origin': 'https://www.sofascore.com',
    }
    # 先查詢 tournament 16 的 seasons 列表
    season_id = None
    try:
        meta = fetch_json('https://api.sofascore.com/api/v1/unique-tournament/16/seasons',
                          extra_headers=headers)
        seasons = meta.get('seasons', [])
        print(f'      [SofaScore] seasons: {[(s.get("id"),s.get("name")) for s in seasons[:5]]}')
        for s in seasons:
            if '2026' in str(s.get('name', '')):
                season_id = s['id']
                break
        if not season_id and seasons:
            season_id = seasons[0]['id']  # 最新的
    except Exception as e:
        print(f'      [SofaScore seasons] err: {e}')

    if not season_id:
        return scores

    try:
        for page in range(0, 15):
            url = (f'https://api.sofascore.com/api/v1/unique-tournament/16'
                   f'/season/{season_id}/events/last/{page}')
            data = fetch_json(url, extra_headers=headers)
            events = data.get('events', [])
            if not events:
                break
            for ev in events:
                if ev.get('status', {}).get('type') != 'finished':
                    continue
                home = ev.get('homeTeam', {}).get('name', '')
                away = ev.get('awayTeam', {}).get('name', '')
                hs = ev.get('homeScore', {}).get('current')
                as_ = ev.get('awayScore', {}).get('current')
                hk = _norm(home)
                ak = _norm(away)
                if not hk or not ak or hs is None or as_ is None: continue
                _add_score(scores, hk, ak, str(hs), str(as_))
    except Exception as e:
        print(f'      [SofaScore events] err: {e}')
    return scores

# ── 來源 5：worldfootball.net HTML 爬取 ──────────────────────────────────────
def fetch_worldfootball_scores():
    """worldfootball.net 爬取 2026 世界盃比分"""
    scores = {}
    urls = [
        'https://www.worldfootball.net/schedule/wm-2026/1/',
        'https://www.worldfootball.net/schedule/wm-2026/2/',
        'https://www.worldfootball.net/schedule/wm-2026/3/',
        'https://www.worldfootball.net/all_matches/wm-2026/',
    ]
    found_html = False
    for url in urls:
        try:
            html = fetch_html(url)
            if len(html) < 500:
                continue
            found_html = True
            # 找比分行：隊名 - N:N - 隊名
            for m in re.finditer(
                r'class="[^"]*">\s*([A-Za-zÀ-ÿ\s\-\.\']+?)\s*</[^>]+>\s*'
                r'[^<]*?(\d+)\s*:\s*(\d+)[^<]*?'
                r'[^<]*?([A-Za-zÀ-ÿ\s\-\.\']+?)\s*</[^>]+>',
                html
            ):
                hk = _norm(m.group(1).strip())
                ak = _norm(m.group(4).strip())
                if not hk or not ak: continue
                _add_score(scores, hk, ak, m.group(2), m.group(3))
        except Exception as e:
            print(f'      [worldfootball] {url}: err={e}')
    if not found_html:
        print('      [worldfootball] 無法取得頁面')
    return scores

# ── 來源 6：worldcups.tw（繁中，格式穩定）────────────────────────────────────
def fetch_worldcups_tw_scores():
    """worldcups.tw 完整賽程表（含比分），繁體中文隊名"""
    scores = {}
    try:
        html = fetch_html('https://worldcups.tw/livescore/')
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
        print(f'      [worldcups.tw] {len(rows)} rows')
        found = 0
        for row in rows:
            cells = [
                re.sub(r'<[^>]+>', '', c).replace('\xa0', ' ').strip()
                for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
            ]
            # 格式：[日期, 主隊, 比分, 客隊, 狀態, 場地, 輪次]
            if len(cells) < 5: continue
            if '比賽結束' not in cells[4]: continue
            m = re.search(r'(\d+)\s*:\s*(\d+)', cells[2])
            if not m: continue
            hk = _norm(cells[1])
            ak = _norm(cells[3])
            if not hk or not ak: continue
            _add_score(scores, hk, ak, m.group(1), m.group(2))
            found += 1
        print(f'      [worldcups.tw] {found} 場已結束')
    except Exception as e:
        print(f'      [worldcups.tw] err: {e}')
    return scores

# ── 來源 7：fifacom.tw（繁中，若未封鎖則使用）────────────────────────────────
def fetch_fifacom_scores():
    scores = {}
    try:
        html = fetch_html('https://fifacom.tw/schedule/')
        rows = re.findall(r'<tr[\s\S]*?</tr>', html, re.IGNORECASE)
        print(f'      [fifacom.tw] {len(rows)} rows')
        for row in rows:
            cells = [
                re.sub(r'<[^>]+>', '', t).replace('\xa0', ' ').replace('&amp;', '&').strip()
                for t in re.findall(r'<td[^>]*>([\s\S]*?)</td>', row, re.IGNORECASE)
            ]
            if len(cells) < 5: continue
            m = re.search(r'(\d+)\s*:\s*(\d+)', cells[2])
            if not m: continue
            if '比賽結束' not in cells[4]: continue
            hk = _norm(cells[1])
            ak = _norm(cells[3])
            if not hk or not ak: continue
            _add_score(scores, hk, ak, m.group(1), m.group(2))
    except Exception as e:
        print(f'      [fifacom.tw] err: {e}')
    return scores

# ── 寫入 KV（透過 Cloudflare REST API） ──────────────────────────────────────
def get_cf_token():
    """取得 Cloudflare API token（環境變數 > wrangler 設定檔）"""
    # 優先使用環境變數
    if os.environ.get('CF_API_TOKEN'):
        return os.environ['CF_API_TOKEN']

    # 嘗試多個 wrangler 設定檔位置
    possible = [
        '~/Library/Preferences/.wrangler/config/default.toml',  # macOS
        '~/.wrangler/config/default.toml',
        '~/.config/wrangler/default.toml',
        '~/.config/.wrangler/config/default.toml',
    ]
    for p in possible:
        path = os.path.expanduser(p)
        if os.path.exists(path):
            with open(path, 'r') as f:
                content = f.read()
            m = re.search(r'oauth_token\s*=\s*"([^"]+)"', content)
            if m:
                return m.group(1)

    raise Exception(
        '找不到 Cloudflare token。\n'
        '請用以下方式執行：\n'
        '  CF_API_TOKEN="你的token" python3 update_scores.py\n\n'
        'Token 建立方式：\n'
        '  https://dash.cloudflare.com/profile/api-tokens\n'
        '  → Create Custom Token\n'
        '  → Workers KV Storage: Edit'
    )

def kv_put(key, value_str):
    """透過 Cloudflare REST API 直接寫入 KV，不依賴 wrangler CLI"""
    token = get_cf_token()
    url = (f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}'
           f'/storage/kv/namespaces/{KV_NAMESPACE_ID}/values/{urllib.parse.quote(key)}')
    data = value_str.encode('utf-8')
    req = urllib.request.Request(url, data=data, method='PUT')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'text/plain; charset=utf-8')
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as r:
        result = json.loads(r.read())
    if not result.get('success'):
        raise Exception(str(result.get('errors', [])))

# ── 主程式 ────────────────────────────────────────────────────────────────────
def main():
    scores = {}

    sources = [
        ('worldcups.tw',    fetch_worldcups_tw_scores),   # 主要：繁中，格式穩定
        ('ESPN API',        fetch_espn_scores),
        ('FIFA 官方 API',   fetch_fifa_scores),
        ('TheSportsDB',     fetch_thesportsdb_scores),
        ('SofaScore',       fetch_sofascore_scores),
        ('worldfootball',   fetch_worldfootball_scores),
        ('fifacom.tw',      fetch_fifacom_scores),
    ]

    for i, (name, fn) in enumerate(sources, 1):
        print(f'📡  [{i}/{len(sources)}] 抓取 {name}...')
        try:
            s = fn()
            new = {k: v for k, v in s.items() if k not in scores}
            print(f'    ✅ {len(s)} 筆（新增 {len(new)} 筆）')
            scores.update(s)
        except Exception as e:
            print(f'    ⚠️  失敗：{e}')

    if not scores:
        print('⚠️  無比分資料（賽事未開始或來源暫時不可用），將寫入無比分的賽程。')
    else:
        print(f'\n✅  合計 {len(scores)} 筆比分：')
        for k, v in sorted(scores.items()):
            t1, t2 = k.split('|')
            print(f'    {t1} vs {t2}：{v}')

    print('\n🏗️   在本機生成 ICS...')
    ics = generate_ics(scores)
    score_count = sum(1 for line in ics.splitlines() if '（' in line and '）' in line and 'SUMMARY' in line)
    print(f'    ✅ 生成完成（{len(ics):,} bytes，{score_count} 場有比分）')

    # 本機驗證：印出前幾筆有比分的行事曆標題
    print('\n    驗證比分格式：')
    shown = 0
    for line in ics.splitlines():
        if 'SUMMARY:小組賽' in line and '（' in line:
            print(f'    ✓ {line[8:]}')
            shown += 1
            if shown >= 3: break

    print('\n📦  透過 Cloudflare REST API 寫入 KV...')
    try:
        kv_put('ics', ics)
        print('    ✅ ics 寫入成功')
    except Exception as e:
        print(f'❌  ics 寫入失敗：{e}'); sys.exit(1)

    try:
        kv_put('scores_json', json.dumps(scores, ensure_ascii=False))
        kv_put('last_updated', datetime.now(timezone.utc).isoformat())
        print('    ✅ scores_json / last_updated 寫入成功')
    except Exception as e:
        print(f'    ⚠️  metadata 寫入失敗（不影響 ICS）：{e}')

    # 立刻讀回驗證
    print('\n🔍  驗證：從 KV 讀回 ics key...')
    try:
        token = get_cf_token()
        url = (f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}'
               f'/storage/kv/namespaces/{KV_NAMESPACE_ID}/values/ics')
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'Bearer {token}')
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            readback = r.read().decode('utf-8', errors='replace')
        scored = len(re.findall(r'SUMMARY:.*（\d+-\d+）', readback))
        print(f'    讀回大小：{len(readback):,} bytes，有比分場次：{scored}')
        if scored > 0:
            print('    ✅ 驗證成功！')
        else:
            print('    ⚠️  讀回的 ICS 沒有比分，請回報此問題')
    except Exception as e:
        print(f'    ⚠️  驗證失敗：{e}')

    print('\n✅  全部完成！')
    print('    在 Apple Calendar 對訂閱行事曆按右鍵 → 重新整理，即可看到最新比分。')

if __name__ == '__main__':
    main()
