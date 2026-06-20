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
  'BMO':       {'name':'BMO Field',                'city':'Toronto, Canada',                   'tz':'America/Toronto',     'off':-4},
  'BC':        {'name':'BC Place',                 'city':'Vancouver, Canada',                'tz':'America/Vancouver',    'off':-7},
  'SoFi':      {'name':'SoFi Stadium',             'city':'Inglewood, California, USA',       'tz':'America/Los_Angeles', 'off':-7},
  'Levis':     {'name':"Levi's Stadium",           'city':'Santa Clara, California, USA',     'tz':'America/Los_Angeles', 'off':-7},
  'MetLife':   {'name':'MetLife Stadium',          'cty':'East Rutherford, New Jersey, USA', 'tz':'America/New_York',    'off':-4},
  'Gillette':  {'name':'Gillette Stadium',         'city':'Foxborough, Massachusetts, USA',   'tz':'America/New_York',    'off':-4},
  'LFF':       {'name':'Lincoln Financial Field',  '