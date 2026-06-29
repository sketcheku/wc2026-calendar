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
  '墨西哥':'Mexico','南非':'South Africa',
  '南韓':'South Korea','韓國':'South Korea',          # worldcups.tw/Fifa世界杯.tw 兩種寫法
  '捷克':'Czechia','加拿大':'Canada',
  '波士尼亞':'Bosnia','波士尼亞與赫塞哥維納':'Bosnia', # Fifa世界杯.tw 全名
  '美國':'USA','巴拉圭':'Paraguay',
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
  '英格蘭':'England','克羅埃西亞':'Croatia',
  '迦納':'Ghana','加納':'Ghana',                      # 兩種繁中寫法
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
# 時間均為 UTC，台灣時間 = UTC+8
MATCHES = [
  [1,'20260611T190000Z',120,'Azteca','Mexico','South Africa','GA'],      # TW 06/12 03:00
  [2,'20260612T020000Z',120,'Akron','South Korea','Czechia','GA'],       # TW 06/12 10:00
  [3,'20260612T190000Z',120,'BMO','Canada','Bosnia','GB'],               # TW 06/13 03:00
  [4,'20260613T010000Z',120,'SoFi','USA','Paraguay','GD'],               # TW 06/13 09:00
  [5,'20260613T190000Z',120,'Levis','Qatar','Switzerland','GB'],         # TW 06/14 03:00
  [6,'20260613T220000Z',120,'MetLife','Brazil','Morocco','GC'],          # TW 06/14 06:00
  [7,'20260614T010000Z',120,'Gillette','Haiti','Scotland','GC'],         # TW 06/14 09:00
  [8,'20260614T040000Z',120,'BC','Australia','Turkey','GD'],             # TW 06/14 12:00
  [9,'20260614T170000Z',120,'NRG','Germany','Curacao','GE'],             # TW 06/15 01:00
  [10,'20260614T200000Z',120,'ATT','Netherlands','Japan','GF'],          # TW 06/15 04:00
  [11,'20260614T230000Z',120,'LFF','IvoryCoast','Ecuador','GE'],         # TW 06/15 07:00
  [12,'20260615T020000Z',120,'BBVA','Sweden','Tunisia','GF'],            # TW 06/15 10:00
  [13,'20260615T160000Z',120,'MBZ','Spain','CapeVerde','GH'],            # TW 06/16 00:00
  [14,'20260615T190000Z',120,'Lumen','Belgium','Egypt','GG'],            # TW 06/16 03:00
  [15,'20260615T220000Z',120,'HardRock','SaudiArabia','Uruguay','GH'],   # TW 06/16 06:00
  [16,'20260616T010000Z',120,'SoFi','Iran','NewZealand','GG'],           # TW 06/16 09:00
  [17,'20260616T190000Z',120,'MetLife','France','Senegal','GI'],         # TW 06/17 03:00
  [18,'20260616T220000Z',120,'Gillette','Iraq','Norway','GI'],           # TW 06/17 06:00
  [19,'20260617T010000Z',120,'Arrowhead','Argentina','Algeria','GJ'],    # TW 06/17 09:00
  [20,'20260617T040000Z',120,'Levis','Austria','Jordan','GJ'],           # TW 06/17 12:00
  [21,'20260617T170000Z',120,'NRG','Portugal','DRCongo','GK'],           # TW 06/18 01:00
  [22,'20260617T200000Z',120,'ATT','England','Croatia','GL'],            # TW 06/18 04:00
  [23,'20260617T230000Z',120,'BMO','Ghana','Panama','GL'],               # TW 06/18 07:00
  [24,'20260618T020000Z',120,'Azteca','Colombia','Uzbekistan','GK'],     # TW 06/18 10:00
  [25,'20260618T160000Z',120,'MBZ','Czechia','South Africa','GA'],       # TW 06/19 00:00
  [26,'20260618T190000Z',120,'SoFi','Switzerland','Bosnia','GB'],        # TW 06/19 03:00
  [27,'20260618T220000Z',120,'BC','Canada','Qatar','GB'],                # TW 06/19 06:00
  [28,'20260619T010000Z',120,'Akron','Mexico','South Korea','GA'],       # TW 06/19 09:00
  [29,'20260619T190000Z',120,'Lumen','USA','Australia','GD'],            # TW 06/20 03:00
  [30,'20260619T220000Z',120,'Gillette','Scotland','Morocco','GC'],      # TW 06/20 06:00
  [31,'20260620T003000Z',120,'LFF','Brazil','Haiti','GC'],               # TW 06/20 08:30
  [32,'20260620T030000Z',120,'Levis','Turkey','Paraguay','GD'],          # TW 06/20 11:00
  [33,'20260620T170000Z',120,'NRG','Netherlands','Sweden','GF'],         # TW 06/21 01:00
  [34,'20260620T200000Z',120,'BMO','Germany','IvoryCoast','GE'],         # TW 06/21 04:00
  [35,'20260621T000000Z',120,'Arrowhead','Ecuador','Curacao','GE'],      # TW 06/21 08:00
  [36,'20260621T040000Z',120,'BBVA','Tunisia','Japan','GF'],             # TW 06/21 12:00
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
  # ── 32強（來源：worldcups.tw 確認真實對陣，2026/06/29 更新） ────────────────
  [73,'20260628T190000Z',150,'SoFi','South Africa','Canada','R32'],     # TW 06/29 03:00 FT 0-1 ✅
  [74,'20260629T170000Z',150,'NRG','Brazil','Japan','R32'],             # TW 06/30 01:00 ✅
  [75,'20260629T203000Z',150,'Gillette','Germany','Paraguay','R32'],    # TW 06/30 04:30 ✅
  [76,'20260630T010000Z',150,'BBVA','Netherlands','Morocco','R32'],     # TW 06/30 09:00 ✅
  [77,'20260630T170000Z',150,'ATT','IvoryCoast','Norway','R32'],        # TW 07/01 01:00 ✅
  [78,'20260630T210000Z',150,'MetLife','France','Sweden','R32'],        # TW 07/01 05:00 ✅
  [79,'20260701T010000Z',150,'Azteca','Mexico','Ecuador','R32'],        # TW 07/01 09:00 ✅
  [80,'20260701T160000Z',150,'MBZ','England','DRCongo','R32'],          # TW 07/02 00:00 ✅
  [81,'20260701T200000Z',150,'Lumen','Belgium','Senegal','R32'],        # TW 07/02 04:00 ✅
  [82,'20260702T000000Z',150,'Levis','USA','Bosnia','R32'],             # TW 07/02 08:00 ✅
  [83,'20260702T190000Z',150,'SoFi','Spain','Austria','R32'],           # TW 07/03 03:00 ✅
  [84,'20260702T230000Z',150,'BMO','Portugal','Croatia','R32'],         # TW 07/03 07:00 ✅
  [85,'20260703T030000Z',150,'BC','Switzerland','Algeria','R32'],       # TW 07/03 11:00 ✅
  [88,'20260703T180000Z',150,'ATT','Australia','Egypt','R32'],          # TW 07/04 02:00 ✅
  [86,'20260703T220000Z',150,'HardRock','Argentina','CapeVerde','R32'], # TW 07/04 06:00 ✅
  [87,'20260704T013000Z',150,'Arrowhead','Colombia','Ghana','R32'],     # TW 07/04 09:30 ✅
  # ── 16強 ──────────────────────────────────────────────────────────────────────
  [90,'20260704T170000Z',150,'NRG','M73勝者','M75勝者','R16'],    # TW 07/05 01:00 FIFA ✅
  [89,'20260704T210000Z',150,'LFF','M74勝者','M77勝者','R16'],    # TW 07/05 05:00 FIFA ✅
  [91,'20260705T200000Z',150,'MetLife','M76勝者','M78勝者','R16'],# TW 07/06 04:00 FIFA ✅
  [92,'20260706T000000Z',150,'Azteca','M79勝者','M80勝者','R16'], # TW 07/06 08:00 FIFA ✅
  [93,'20260706T190000Z',150,'ATT','M83勝者','M84勝者','R16'],    # TW 07/07 03:00 FIFA ✅
  [94,'20260707T000000Z',150,'Lumen','M81勝者','M82勝者','R16'],  # TW 07/07 08:00 FIFA ✅
  [95,'20260707T160000Z',150,'MBZ','M86勝者','M88勝者','R16'],    # TW 07/08 00:00 FIFA ✅
  [96,'20260707T200000Z',150,'BC','M85勝者','M87勝者','R16'],     # TW 07/08 04:00 FIFA ✅
  # ── 8強 ───────────────────────────────────────────────────────────────────────
  [97,'20260709T200000Z',150,'Gillette','M89勝者','M90勝者','QF'],# TW 07/10 04:00 FIFA ✅
  [98,'20260710T190000Z',150,'SoFi','M93勝者','M94勝者','QF'],    # TW 07/11 03:00 FIFA ✅
  [99,'20260711T210000Z',150,'HardRock','M91勝者','M92勝者','QF'],# TW 07/12 05:00 FIFA ✅
  [100,'20260712T010000Z',150,'Arrowhead','M95勝者','M96勝者','QF'],# TW 07/12 09:00 FIFA ✅
  # ── 4強、季軍、決賽 ────────────────────────────────────────────────────────────
  [101,'20260714T190000Z',150,'ATT','M97勝者','M98勝者','SF'],    # TW 07/15 03:00 FIFA ✅
  [102,'20260715T190000Z',150,'MBZ','M99勝者','M100勝者','SF'],   # TW 07/16 03:00 FIFA ✅
  [103,'20260718T210000Z',150,'HardRock','四強負者①','四強負者②','3P'],# TW 07/19 05:00 FIFA ✅
  [104,'20260719T190000Z',180,'MetLife','M101勝者','M102勝者','FIN'],  # TW 07/20 03:00 FIFA ✅
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

# ── 淘汰賽自動解析（核心新功能） ─────────────────────────────────────────────────

def compute_group_standings(scores_dict):
    """從已完成的小組賽比分計算各組積分表
    只有當一個組的所有6場比賽都完成時，才計入 standings。
    返回: {'A': [('Mexico', pts, gd, gf), ...], ...} (降序)
    """
    # 建立各組隊伍清單（從 MATCHES 動態推導）
    groups = {}
    group_matches_list = {}
    for entry in MATCHES:
        no, dtstart, dur, vkey, t1, t2, stage = entry
        if stage.startswith('G') and len(stage) == 2:
            g = stage[1]   # 'GA' → 'A'
            groups.setdefault(g, set())
            groups[g].add(t1)
            groups[g].add(t2)
            group_matches_list.setdefault(g, []).append((t1, t2))

    standings = {}
    for g in sorted(groups.keys()):
        teams = groups[g]
        team_stats = {t: {'pts': 0, 'gd': 0, 'gf': 0} for t in teams}
        all_done = True

        for t1, t2 in group_matches_list[g]:
            k = f'{t1}|{t2}'
            if k not in scores_dict:
                all_done = False
                continue
            mo = re.match(r'(\d+)-(\d+)', scores_dict[k])
            if not mo:
                all_done = False
                continue
            s1, s2 = int(mo.group(1)), int(mo.group(2))
            team_stats[t1]['gf'] += s1
            team_stats[t2]['gf'] += s2
            team_stats[t1]['gd'] += s1 - s2
            team_stats[t2]['gd'] += s2 - s1
            if s1 > s2:
                team_stats[t1]['pts'] += 3
            elif s2 > s1:
                team_stats[t2]['pts'] += 3
            else:
                team_stats[t1]['pts'] += 1
                team_stats[t2]['pts'] += 1

        if not all_done:
            continue  # 此組尚未完賽，不計入

        sorted_teams = sorted(
            team_stats.items(),
            key=lambda x: (x[1]['pts'], x[1]['gd'], x[1]['gf']),
            reverse=True
        )
        standings[g] = [(t, s['pts'], s['gd'], s['gf']) for t, s in sorted_teams]

    return standings


def assign_group_slots(standings):
    """積分表 → 組別佔位符映射
    返回: {'A組冠軍': 'Mexico', 'A組亞軍': 'SouthAfrica', 'A組第三': 'SouthKorea', ...}
    """
    slots = {}
    for g, ranked in standings.items():
        if len(ranked) >= 1: slots[f'{g}組冠軍'] = ranked[0][0]
        if len(ranked) >= 2: slots[f'{g}組亞軍'] = ranked[1][0]
        if len(ranked) >= 3: slots[f'{g}組第三'] = ranked[2][0]
    return slots


def _tw_time_key(dtstart_utc):
    """UTC 時間字串 → 台灣時間 key，格式 'MM/DD HH:MM'"""
    dt = _parse_dt(dtstart_utc)
    tw = dt + timedelta(hours=8)
    return tw.strftime('%m/%d %H:%M')

def build_knockout_bracket(time_results):
    """依台灣時間比對 time_results 與淘汰賽場次（允許 ±30 分鐘誤差）
    返回 {match_no: {'t1', 't2', 'score', 'scorers'}}
    """
    bracket = {}
    if not time_results:
        return bracket

    knockout = [(entry[0], _tw_time_key(entry[1]))
                for entry in MATCHES if not entry[6].startswith('G')]

    def _to_mins(key):
        mo = re.match(r'(\d{2})/(\d{2}) (\d{2}):(\d{2})', key)
        if not mo: return -1
        mm, dd, hh, mi = map(int, mo.groups())
        return (mm * 31 + dd) * 1440 + hh * 60 + mi

    for result_key, result_data in time_results.items():
        rm = _to_mins(result_key)
        if rm < 0: continue
        best_no, best_diff = None, 31   # 最多允許 30 分鐘誤差
        for no, our_key in knockout:
            diff = abs(rm - _to_mins(our_key))
            if diff <= 30 and diff < best_diff:
                best_diff = diff
                best_no = no
        if best_no is not None and best_no not in bracket:
            bracket[best_no] = result_data.copy()

    return bracket

def resolve_matches(bracket, group_slots=None):
    """根據 bracket 與 group_slots 解析 MATCHES 中的佔位符，回傳含真實隊名的 MATCHES copy

    解析優先順序：
    1. group_slots（小組積分表）→ 解析 'A組冠軍', 'H組亞軍' 等
    2. bracket（已完成淘汰賽比賽資料）→ 取代步驟1結果（最準確）
    3. winner_map（已完成比賽的勝者）→ 解析 'M73勝者' 等前向引用
    """
    if group_slots is None:
        group_slots = {}

    # 建立勝者對照表（比賽場次 → 勝隊 key）
    winner_map = {}
    for no, info in bracket.items():
        if info.get('score'):
            mo = re.match(r'(\d+)-(\d+)', info['score'])
            if mo:
                s1, s2 = int(mo.group(1)), int(mo.group(2))
                if s1 > s2:
                    winner_map[no] = info['t1']
                elif s2 > s1:
                    winner_map[no] = info['t2']
                # 平局 → 延長賽/PK 決定，等後續更新

    def resolve_ref(name):
        """解析 'MXX勝者' 前向引用"""
        mo = re.match(r'M(\d+)勝者', name)
        if mo:
            ref_no = int(mo.group(1))
            return winner_map.get(ref_no, name)
        return name

    resolved = []
    for entry in MATCHES:
        no, dtstart, dur, vkey, t1, t2, stage = entry

        if not stage.startswith('G'):
            # 步驟 1：先用小組積分表解析組別佔位符（如 'A組亞軍'）
            t1 = group_slots.get(t1, t1)
            t2 = group_slots.get(t2, t2)

            # 步驟 2：若此場比賽已打完（在 bracket 中），以實際比賽隊名覆蓋（最準確）
            if no in bracket:
                bkt = bracket[no]
                if bkt.get('t1'): t1 = bkt['t1']
                if bkt.get('t2'): t2 = bkt['t2']

        # 步驟 3：解析 'MXX勝者' 等前向引用（鏈式推算）
        t1 = resolve_ref(t1)
        t2 = resolve_ref(t2)
        resolved.append([no, dtstart, dur, vkey, t1, t2, stage])

    return resolved

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
def generate_ics(scores_map, scorers_map=None, matches=None):
    """生成 ICS 檔案。matches 預設使用 MATCHES，傳入 resolve_matches() 的結果可自動更新淘汰賽隊名"""
    if scorers_map is None:
        scorers_map = {}
    if matches is None:
        matches = MATCHES
    # DTSTAMP 是 RFC 5545 必填欄位，同時作為 Apple Calendar 判斷版本新舊的依據
    now_stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//2026 FIFA World Cup//ZH-TW//',
        'X-WR-CALNAME:2026世界盃足球賽',
        'X-WR-CALDESC:2026年FIFA世界盃足球賽完整賽程（含台灣時間，比分自動更新）',
        'X-WR-TIMEZONE:Asia/Taipei',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'REFRESH-INTERVAL;VALUE=DURATION:PT2H',
        'X-PUBLISHED-TTL:PT2H',
        f'LAST-MODIFIED:{now_stamp}',
    ]

    for no, dtstart, dur_min, vkey, t1, t2, stage in matches:
        v = VENUES[vkey]
        stage_zh = STAGE_ZH[stage]
        stage_en = STAGE_EN[stage]
        t1zh = NAMES_ZH.get(t1, t1)
        t2zh = NAMES_ZH.get(t2, t2)
        match_key = f'{t1}|{t2}'
        score = scores_map.get(match_key)
        scorers = scorers_map.get(match_key, '')

        summary = f'{stage_zh}｜{t1zh} vs {t2zh}（{score}）' if score else f'{stage_zh}｜{t1zh} vs {t2zh}'
        location = f'{v["name"]}\\, {v["city"]}'
        tw_time = utc_to_tw(dtstart)
        local_time = utc_to_local(dtstart, v['off'])
        desc_parts = [
            f'對戰：{t1zh} vs {t2zh}',
            f'階段：{stage_zh} / {stage_en}',
            f'台灣時間：{tw_time}（UTC+8）',
            f'當地時間：{local_time}（{v["tz"]}）',
            f'地點：{v["name"]}\\, {v["city"]}',
        ]
        if scorers:
            desc_parts.append(f'進球：{scorers}')
        desc_parts.append('提醒：賽程可能因 FIFA 公告更新而調整。')
        desc = '\\n'.join(desc_parts)

        lines += [
            '',
            'BEGIN:VEVENT',
            f'UID:wc2026-match-{str(no).zfill(3)}@calendar',
            f'DTSTAMP:{now_stamp}',
            'SEQUENCE:0',
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
    # 繁體中文（用於中文來源，含兩網站不同寫法）
    **ZH_ALIAS,
    # Fifa世界杯.tw 額外變體（ZH_ALIAS 裡已含，這裡確保 TEAM_ALIAS 也有）
    '韓國':'South Korea',
    '加納':'Ghana',
    '波士尼亞與赫塞哥維納':'Bosnia',
}

def _norm(name):
    """將隊名正規化為 MATCHES 中使用的 key"""
    return TEAM_ALIAS.get(name) or TEAM_ALIAS.get(name.strip())

def _add_score(scores, h_key, a_key, hs, as_):
    """雙向儲存比分（小組賽 + 淘汰賽皆適用）"""
    scores[f'{h_key}|{a_key}'] = f'{hs}-{as_}'
    scores[f'{a_key}|{h_key}'] = f'{as_}-{hs}'

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

# ── 共用：解析含比分與進球資訊的 HTML 表格 ──────────────────────────────────
def _parse_score_table(html):
    """解析 worldcups.tw / Fifa世界杯.tw 格式的賽程表
    回傳 (scores, scorers, time_results)
    time_results: {'MM/DD HH:MM': {'t1':..., 't2':..., 'score':..., 'scorers':...}}
    """
    scores = {}
    scorers = {}
    time_results = {}
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
    last_key = None
    last_tw = None
    for row in rows:
        cells = [
            re.sub(r'<[^>]+>', '', c).replace('\xa0', ' ').strip()
            for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        ]
        # 進球資訊列：第一格含 ⚽ 或「分」且其餘格為空
        if cells and ('⚽' in cells[0] or ('分' in cells[0] and len(cells[0]) > 5)) \
                and all(c == '' for c in cells[1:]):
            scorer_txt = re.sub(r'\s+', ' ', cells[0]).strip()
            if last_key:
                scorers[last_key] = scorer_txt
            if last_tw and last_tw in time_results:
                time_results[last_tw]['scorers'] = scorer_txt
            last_key = None
            last_tw = None
            continue
        # 比賽主列：[日期, 主隊, 比分/VS, 客隊, 狀態, 場地, 輪次]
        if len(cells) < 5:
            last_key = None
            last_tw = None
            continue
        hk = _norm(cells[1])
        ak = _norm(cells[3])
        if not hk or not ak:
            last_key = None
            last_tw = None
            continue

        is_finished = '比賽結束' in cells[4]
        m = re.search(r'(\d+)\s*[:\-]\s*(\d+)', cells[2])

        # 提取台灣時間 key（格式 'MM/DD HH:MM'）
        # 先把 cells[0] 中的換行/多餘空白折疊成一個空格，避免 re.search 的 . 不匹配 \n
        cell0_norm = re.sub(r'\s+', ' ', cells[0]).strip()
        tm = re.search(r'(\d{2}/\d{2}).*?(\d{2}:\d{2})', cell0_norm)
        tw_key = f"{tm.group(1)} {tm.group(2)}" if tm else None

        score_str = ''
        if is_finished and m:
            # 完賽：儲存比分（雙向）
            _add_score(scores, hk, ak, m.group(1), m.group(2))
            score_str = f'{m.group(1)}-{m.group(2)}'

        # 所有有效比賽（含未開賽）都記錄隊名到 time_results，供淘汰賽隊名解析用
        # 若已有完賽資料則不覆蓋（完賽 > 未開賽）
        if tw_key and (tw_key not in time_results or (is_finished and m)):
            time_results[tw_key] = {
                't1': hk, 't2': ak,
                'score': score_str,
                'scorers': ''
            }

        # 小組賽進球追蹤（VALID_KEYS），僅完賽有效
        if is_finished and m:
            k1, k2 = f'{hk}|{ak}', f'{ak}|{hk}'
            last_key = k1 if k1 in VALID_KEYS else (k2 if k2 in VALID_KEYS else None)
            last_tw = tw_key
        else:
            last_key = None
            last_tw = tw_key  # 仍更新 tw_key，方便後續比賽行覆蓋
    return scores, scorers, time_results

# ── 比分來源：worldcups.tw ────────────────────────────────────────────────────
def fetch_worldcups_tw_scores():
    """從 worldcups.tw 抓取比分與進球資訊，回傳 (scores_map, scorers_map, time_results)"""
    try:
        html = fetch_html('https://worldcups.tw/livescore/')
        return _parse_score_table(html)
    except Exception as e:
        print(f'    ⚠️  worldcups.tw 失敗：{e}')
        return {}, {}, {}

def fetch_fifatw_scores():
    """從 Fifa世界杯.tw 抓取比分與進球資訊（備用來源），回傳 (scores_map, scorers_map, time_results)"""
    try:
        html = fetch_html('https://xn--fifa-tc5fq65k1ju.tw/world-cup-2026-schedule/')
        return _parse_score_table(html)
    except Exception as e:
        print(f'    ⚠️  Fifa世界杯.tw 失敗：{e}')
        return {}, {}, {}

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
    print('📡  抓取 worldcups.tw 比分與進球資訊...')
    scores, scorers, time_r1 = fetch_worldcups_tw_scores()
    print(f'    ✅ {len(scores)//2} 筆比分，{len(scorers)} 場有進球資訊，'
          f'{len(time_r1)} 筆時間索引')

    print('📡  抓取 Fifa世界杯.tw（補充來源）...')
    scores2, scorers2, time_r2 = fetch_fifatw_scores()
    print(f'    ✅ {len(scores2)//2} 筆比分，{len(scorers2)} 場有進球資訊，'
          f'{len(time_r2)} 筆時間索引')

    # 合併：以 worldcups.tw 為主，Fifa世界杯.tw 補缺漏
    for k, v in scores2.items():
        if k not in scores:
            scores[k] = v
    for k, v in scorers2.items():
        if k not in scorers:
            scorers[k] = v
    time_results = {**time_r2, **time_r1}   # time_r1 優先
    total_matches = len(scores) // 2
    print(f'    合計 {total_matches} 筆比分，{len(scorers)} 場有進球資訊')

    # ── 小組積分計算 ─────────────────────────────────────────────────────────────
    print('\n📊  計算小組積分表，解析組別佔位符...')
    standings = compute_group_standings(scores)
    group_slots = assign_group_slots(standings)
    if standings:
        completed = sorted(standings.keys())
        print(f'    ✅ {len(standings)}/12 組完賽：{"、".join(completed)}組')
        for g in completed:
            ranked = standings[g]
            names = [NAMES_ZH.get(t, t) for t, *_ in ranked]
            print(f'    {g}組：① {names[0]}  ② {names[1]}  ③ {names[2]}  ④ {names[3]}')
    else:
        print('    ℹ️  小組賽尚未全部結束，組別佔位符暫時保留')

    # ── 淘汰賽自動解析 ───────────────────────────────────────────────────────────
    print('\n🏆  解析淘汰賽對戰與勝者推算...')
    bracket = build_knockout_bracket(time_results)
    if bracket:
        for no, info in bracket.items():
            t1zh = NAMES_ZH.get(info['t1'], info['t1'])
            t2zh = NAMES_ZH.get(info['t2'], info['t2'])
            score = info.get('score', '未知')
            print(f'    M{no}: {t1zh} vs {t2zh}（{score}）')
    else:
        print('    ℹ️  淘汰賽尚未開始，佔位符將保留原樣')

    resolved_matches = resolve_matches(bracket, group_slots)

    # 將淘汰賽比分/進球注入 scores/scorers（依解析後的真實隊名）
    for no, info in bracket.items():
        if not info.get('score'):
            continue
        for entry in resolved_matches:
            if entry[0] == no:
                rt1, rt2 = entry[4], entry[5]
                s1, s2 = info['score'].split('-')
                scores.setdefault(f'{rt1}|{rt2}', info['score'])
                scores.setdefault(f'{rt2}|{rt1}', f'{s2}-{s1}')
                if info.get('scorers'):
                    scorers.setdefault(f'{rt1}|{rt2}', info['scorers'])
                    scorers.setdefault(f'{rt2}|{rt1}', info['scorers'])
                break

    if not scores:
        print('\n⚠️  無比分資料（賽事未開始或來源暫時不可用），將寫入無比分的賽程。')
    else:
        print(f'\n✅  比分明細（小組賽 + 淘汰賽）：')
        # 僅顯示 MATCHES 順序方向，避免重複印出
        match_keys = {f'{t1}|{t2}' for _, _, _, _, t1, t2, _ in resolved_matches}
        for k in sorted(match_keys):
            if k in scores:
                t1, t2 = k.split('|')
                t1zh = NAMES_ZH.get(t1, t1)
                t2zh = NAMES_ZH.get(t2, t2)
                scorer_info = scorers.get(k, '')
                print(f'    {t1zh} vs {t2zh}：{scores[k]}'
                      + (f'  {scorer_info}' if scorer_info else ''))

    print('\n🏗️   在本機生成 ICS（含淘汰賽解析結果）...')
    ics = generate_ics(scores, scorers, resolved_matches)
    score_count = sum(1 for line in ics.splitlines() if '（' in line and '）' in line and 'SUMMARY' in line)
    print(f'    ✅ 生成完成（{len(ics):,} bytes，{score_count} 場有比分）')

    # 本機驗證：印出前幾筆有比分的行事曆標題
    print('\n    驗證比分格式（前3筆）：')
    shown = 0
    for line in ics.splitlines():
        if line.startswith('SUMMARY:') and '（' in line and '）' in line:
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
