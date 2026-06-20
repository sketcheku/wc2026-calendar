/**
 * 2026 FIFA World Cup Calendar Worker - v2
 * 主要比分來源：worldcupwiki.com HTML 解析（不需 API Key，不受封鎖）
 * 今日補充：Sofascore / ESPN（如可取得）
 * GET /          → ICS 行事曆訂閱
 * GET /refresh   → 強制重新抓取比分
 * GET /debug     → 查看目前比分狀況
 */

// ─────────────────────────────────────────────
// 場地資料
// ─────────────────────────────────────────────
const VENUES = {
  Azteca:    { name: 'Estadio Azteca',          city: 'Mexico City, Mexico',               tz: 'America/Mexico_City', off: -5 },
  Akron:     { name: 'Estadio Akron',           city: 'Zapopan, Mexico',                   tz: 'America/Mexico_City', off: -5 },
  BMO:       { name: 'BMO Field',               city: 'Toronto, Canada',                   tz: 'America/Toronto',     off: -4 },
  BC:        { name: 'BC Place',                city: 'Vancouver, Canada',                 tz: 'America/Vancouver',   off: -7 },
  SoFi:      { name: 'SoFi Stadium',            city: 'Inglewood, California, USA',        tz: 'America/Los_Angeles', off: -7 },
  Levis:     { name: "Levi's Stadium",          city: 'Santa Clara, California, USA',      tz: 'America/Los_Angeles', off: -7 },
  MetLife:   { name: 'MetLife Stadium',         city: 'East Rutherford, New Jersey, USA',  tz: 'America/New_York',    off: -4 },
  Gillette:  { name: 'Gillette Stadium',        city: 'Foxborough, Massachusetts, USA',    tz: 'America/New_York',    off: -4 },
  LFF:       { name: 'Lincoln Financial Field', city: 'Philadelphia, Pennsylvania, USA',   tz: 'America/New_York',    off: -4 },
  NRG:       { name: 'NRG Stadium',             city: 'Houston, Texas, USA',               tz: 'America/Chicago',     off: -5 },
  ATT:       { name: 'AT&T Stadium',            city: 'Arlington, Texas, USA',             tz: 'America/Chicago',     off: -5 },
  Arrowhead: { name: 'Arrowhead Stadium',       city: 'Kansas City, Missouri, USA',        tz: 'America/Chicago',     off: -5 },
  MBZ:       { name: 'Mercedes-Benz Stadium',   city: 'Atlanta, Georgia, USA',             tz: 'America/New_York',    off: -4 },
  Lumen:     { name: 'Lumen Field',             city: 'Seattle, Washington, USA',          tz: 'America/Los_Angeles', off: -7 },
  HardRock:  { name: 'Hard Rock Stadium',       city: 'Miami Gardens, Florida, USA',       tz: 'America/New_York',    off: -4 },
  BBVA:      { name: 'Estadio BBVA',            city: 'Monterrey, Mexico',                 tz: 'America/Monterrey',   off: -5 },
};

// ─────────────────────────────────────────────
// 國家繁體中文名稱
// ─────────────────────────────────────────────
const NAMES_ZH = {
  Mexico:'墨西哥','South Africa':'南非','South Korea':'南韓',Czechia:'捷克',
  Canada:'加拿大',Bosnia:'波士尼亞',USA:'美國',Paraguay:'巴拉圭',
  Qatar:'卡達',Switzerland:'瑞士',Brazil:'巴西',Morocco:'摩洛哥',
  Haiti:'海地',Scotland:'蘇格蘭',Australia:'澳洲',Turkey:'土耳其',
  Germany:'德國',Curacao:'庫拉索',Netherlands:'荷蘭',Japan:'日本',
  IvoryCoast:'象牙海岸',Ecuador:'厄瓜多',Sweden:'瑞典',Tunisia:'突尼西亞',
  Spain:'西班牙',CapeVerde:'維德角',Belgium:'比利時',Egypt:'埃及',
  SaudiArabia:'沙烏地阿拉伯',Uruguay:'烏拉圭',Iran:'伊朗',NewZealand:'紐西蘭',
  France:'法國',Senegal:'塞內加爾',Iraq:'伊拉克',Norway:'挪威',
  Argentina:'阿根廷',Algeria:'阿爾及利亞',Austria:'奧地利',Jordan:'約旦',
  Portugal:'葡萄牙',DRCongo:'剛果民主共和國',England:'英格蘭',Croatia:'克羅埃西亞',
  Ghana:'迦納',Panama:'巴拿馬',Colombia:'哥倫比亞',Uzbekistan:'烏茲別克',
};

// 各種可能的英文名 → 內部 key（涵蓋 worldcupwiki / Sofascore / ESPN 的不同拼法）
const TEAM_ALIAS = {
  'Mexico':'Mexico','South Africa':'South Africa',
  'Korea Republic':'South Korea','South Korea':'South Korea','Republic of Korea':'South Korea',
  'Czech Republic':'Czechia','Czechia':'Czechia','Czechs':'Czechia',
  'Canada':'Canada',
  'Bosnia and Herzegovina':'Bosnia','Bosnia & Herzegovina':'Bosnia','Bosnia':'Bosnia',
  'USA':'USA','United States':'USA','United States of America':'USA',
  'Paraguay':'Paraguay','Qatar':'Qatar','Switzerland':'Switzerland',
  'Brazil':'Brazil','Morocco':'Morocco','Haiti':'Haiti','Scotland':'Scotland',
  'Australia':'Australia',
  'Turkey':'Turkey','Türkiye':'Turkey','Turkiye':'Turkey',
  'Germany':'Germany',
  'Curaçao':'Curacao','Curacao':'Curacao','Curaçao':'Curacao',
  'Netherlands':'Netherlands','Japan':'Japan',
  "Côte d'Ivoire":'IvoryCoast',"Cote d'Ivoire":'IvoryCoast',
  'Ivory Coast':'IvoryCoast',
  'Ecuador':'Ecuador','Sweden':'Sweden','Tunisia':'Tunisia',
  'Spain':'Spain','Cape Verde':'CapeVerde','Cabo Verde':'CapeVerde',
  'Belgium':'Belgium','Egypt':'Egypt',
  'Saudi Arabia':'SaudiArabia','KSA':'SaudiArabia',
  'Uruguay':'Uruguay','Iran':'Iran','New Zealand':'NewZealand',
  'France':'France','Senegal':'Senegal','Iraq':'Iraq','Norway':'Norway',
  'Argentina':'Argentina','Algeria':'Algeria','Austria':'Austria','Jordan':'Jordan',
  'Portugal':'Portugal',
  'DR Congo':'DRCongo','Congo DR':'DRCongo','D.R. Congo':'DRCongo',
  'Democratic Republic of the Congo':'DRCongo',
  'Democratic Republic of Congo':'DRCongo',
  'England':'England','Croatia':'Croatia','Ghana':'Ghana',
  'Panama':'Panama','Colombia':'Colombia','Uzbekistan':'Uzbekistan',
};

const STAGE_ZH = {
  GA:'小組賽：A組',GB:'小組賽：B組',GC:'小組賽：C組',GD:'小組賽：D組',
  GE:'小組賽：E組',GF:'小組賽：F組',GG:'小組賽：G組',GH:'小組賽：H組',
  GI:'小組賽：I組',GJ:'小組賽：J組',GK:'小組賽：K組',GL:'小組賽：L組',
  R32:'三十二強',R16:'十六強',QF:'八強',SF:'四強','3P':'季軍賽',FIN:'決賽',
};
const STAGE_EN = {
  GA:'Group A',GB:'Group B',GC:'Group C',GD:'Group D',
  GE:'Group E',GF:'Group F',GG:'Group G',GH:'Group H',
  GI:'Group I',GJ:'Group J',GK:'Group K',GL:'Group L',
  R32:'Round of 32',R16:'Round of 16',QF:'Quarterfinals',
  SF:'Semifinals','3P':'Third-Place Match',FIN:'Final',
};

// ─────────────────────────────────────────────
// 104 場賽事 [no, dtstart_utc, dur_min, venue, t1, t2, stage]
// ─────────────────────────────────────────────
const MATCHES = [
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
];

// ─────────────────────────────────────────────
// 工具函式
// ─────────────────────────────────────────────
function utcToTW(dtstart) {
  const y=+dtstart.slice(0,4), mo=+dtstart.slice(4,6)-1,
        d=+dtstart.slice(6,8), h=+dtstart.slice(9,11),
        mi=+dtstart.slice(11,13);
  const ms = Date.UTC(y,mo,d,h,mi) + 8*3600*1000;
  const dt = new Date(ms);
  return `${dt.getUTCFullYear()}/${String(dt.getUTCMonth()+1).padStart(2,'0')}/${String(dt.getUTCDate()).padStart(2,'0')} ${String(dt.getUTCHours()).padStart(2,'0')}:${String(dt.getUTCMinutes()).padStart(2,'0')}`;
}

function utcToLocal(dtstart, offsetH) {
  const y=+dtstart.slice(0,4), mo=+dtstart.slice(4,6)-1,
        d=+dtstart.slice(6,8), h=+dtstart.slice(9,11),
        mi=+dtstart.slice(11,13);
  const ms = Date.UTC(y,mo,d,h,mi) + offsetH*3600*1000;
  const dt = new Date(ms);
  return `${dt.getUTCFullYear()}/${String(dt.getUTCMonth()+1).padStart(2,'0')}/${String(dt.getUTCDate()).padStart(2,'0')} ${String(dt.getUTCHours()).padStart(2,'0')}:${String(dt.getUTCMinutes()).padStart(2,'0')}`;
}

function dtend(dtstart, durMin) {
  const y=+dtstart.slice(0,4), mo=+dtstart.slice(4,6)-1,
        d=+dtstart.slice(6,8), h=+dtstart.slice(9,11),
        mi=+dtstart.slice(11,13);
  const ms = Date.UTC(y,mo,d,h,mi) + durMin*60*1000;
  const dt = new Date(ms);
  return `${dt.getUTCFullYear()}${String(dt.getUTCMonth()+1).padStart(2,'0')}${String(dt.getUTCDate()).padStart(2,'0')}T${String(dt.getUTCHours()).padStart(2,'0')}${String(dt.getUTCMinutes()).padStart(2,'0')}00Z`;
}

/** ICS RFC 5545 line folding（依 UTF-8 bytes 計算） */
function foldLine(line) {
  const enc = new TextEncoder();
  const bytes = enc.encode(line);
  if (bytes.length <= 75) return line + '\r\n';
  const parts = [];
  let current = new Uint8Array(0);
  for (const char of line) {
    const cb = enc.encode(char);
    const next = new Uint8Array(current.length + cb.length);
    next.set(current); next.set(cb, current.length);
    if (next.length > 75) {
      parts.push(new TextDecoder().decode(current));
      const cont = new Uint8Array(1 + cb.length);
      cont[0] = 0x20; cont.set(cb, 1);
      current = cont;
    } else {
      current = next;
    }
  }
  if (current.length) parts.push(new TextDecoder().decode(current));
  return parts.join('\r\n') + '\r\n';
}

function zh(key) { return NAMES_ZH[key] || key; }

// ─────────────────────────────────────────────
// 主要比分來源：fifacom.tw HTML 解析
// 繁體中文隊名直接對應，不需 API Key，伺服器端渲染可直接抓取
// ─────────────────────────────────────────────

// 繁體中文隊名（fifacom.tw 用法）→ 內部 key
const ZH_ALIAS = {
  '墨西哥':'Mexico','南非':'South Africa','南韓':'South Korea','捷克':'Czechia',
  '加拿大':'Canada','波士尼亞':'Bosnia','美國':'USA','巴拉圭':'Paraguay',
  '卡達':'Qatar','瑞士':'Switzerland','巴西':'Brazil','摩洛哥':'Morocco',
  '海地':'Haiti','蘇格蘭':'Scotland',
  '澳大利亞':'Australia','澳洲':'Australia',  // 兩種寫法都支援
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
};

function parseFifacomTWHTML(html) {
  const scores = {};

  // 建立 MATCHES 的有效 key 集合（只取隊名已確定的場次）
  const validKeys = new Set();
  for (const [,,,, t1, t2] of MATCHES) {
    if (!t1.includes('組') && !t1.includes('最佳') && !t1.includes('強') &&
        !t1.includes('勝者') && !t1.includes('負者') && !t1.includes('待定')) {
      validKeys.add(`${t1}|${t2}`);
    }
  }

  // 解析 HTML 表格列
  const rows = html.match(/<tr[\s\S]*?<\/tr>/gi) || [];

  for (const row of rows) {
    const cellRegex = /<td[^>]*>([\s\S]*?)<\/td>/gi;
    const cells = [];
    let m;
    while ((m = cellRegex.exec(row)) !== null) {
      cells.push(
        m[1]
          .replace(/<[^>]+>/g, '')
          .replace(/&amp;/g, '&').replace(/&#039;/g, "'")
          .replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim()
      );
    }

    // 需要至少 5 欄：日期、主隊、比分、客隊、狀態
    if (cells.length < 5) continue;

    // 比分欄（第 3 欄，index 2）需符合「N : N」格式
    const scoreMatch = cells[2].match(/(\d+)\s*:\s*(\d+)/);
    if (!scoreMatch) continue;

    // 狀態欄（第 5 欄，index 4）需含「比賽結束」
    if (!(cells[4] || '').includes('比賽結束')) continue;

    const homeKey = ZH_ALIAS[cells[1]];
    const awayKey = ZH_ALIAS[cells[3]];
    if (!homeKey || !awayKey) {
      console.warn(`Unknown ZH team: "${cells[1]}" or "${cells[3]}"`);
      continue;
    }

    const hs = scoreMatch[1];
    const as = scoreMatch[2];
    const key1 = `${homeKey}|${awayKey}`;
    const key2 = `${awayKey}|${homeKey}`;

    if (validKeys.has(key1)) {
      // fifacom 主/客隊順序與 MATCHES 相同
      scores[key1] = `${hs}-${as}`;
    } else if (validKeys.has(key2)) {
      // fifacom 主/客隊順序與 MATCHES 相反，比分也要對調
      scores[key2] = `${as}-${hs}`;
    } else {
      console.warn(`Match not found in MATCHES: ${homeKey} vs ${awayKey}`);
    }
  }

  return scores;
}

async function fetchFifacomTWScores() {
  try {
    const r = await fetch('https://fifacom.tw/schedule/', {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.5',
        'Referer': 'https://fifacom.tw/',
      },
    });
    if (!r.ok) {
      console.error(`fifacom.tw HTTP ${r.status}`);
      return { scores: {}, error: `HTTP ${r.status}` };
    }
    const html = await r.text();
    const scores = parseFifacomTWHTML(html);
    console.log(`fifacom.tw: ${Object.keys(scores).length} scores found`);
    return { scores, error: null };
  } catch (e) {
    console.error('fifacom.tw error:', e.message);
    return { scores: {}, error: e.message };
  }
}

// ─────────────────────────────────────────────
// 補充來源：Sofascore / ESPN（用於今日即時比分）
// ─────────────────────────────────────────────
async function fetchDayScores(isoDate) {
  const scores = {};

  // --- Sofascore ---
  try {
    const url = `https://api.sofascore.com/api/v1/sport/football/scheduled-events/${isoDate}`;
    const r = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.sofascore.com/',
      }
    });
    if (r.ok) {
      const data = await r.json();
      for (const ev of (data.events || [])) {
        // 只取世界盃
        const tn = (ev.tournament?.name || '') + ' ' + (ev.tournament?.uniqueTournament?.name || '');
        if (!tn.toLowerCase().includes('world cup')) continue;
        const home = TEAM_ALIAS[ev.homeTeam?.name] || TEAM_ALIAS[ev.homeTeam?.shortName];
        const away = TEAM_ALIAS[ev.awayTeam?.name] || TEAM_ALIAS[ev.awayTeam?.shortName];
        if (!home || !away) continue;
        const st = ev.status?.type;
        if (st === 'finished' || ev.status?.description?.toLowerCase().includes('ended')) {
          const hs = ev.homeScore?.current ?? ev.homeScore?.display;
          const as = ev.awayScore?.current ?? ev.awayScore?.display;
          if (hs !== undefined && as !== undefined) {
            scores[`${home}|${away}`] = `${hs}-${as}`;
          }
        }
      }
    }
  } catch (e) {
    console.error('Sofascore error:', e.message);
  }

  // --- ESPN fallback ---
  if (Object.keys(scores).length === 0) {
    try {
      const d = isoDate.replace(/-/g, '');
      const url = `https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/scoreboard?dates=${d}`;
      const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
      if (r.ok) {
        const data = await r.json();
        for (const ev of (data.events || [])) {
          const comp = ev.competitions?.[0];
          if (!comp) continue;
          const home = comp.competitors?.find(c => c.homeAway === 'home');
          const away = comp.competitors?.find(c => c.homeAway === 'away');
          if (!home || !away) continue;
          const hKey = TEAM_ALIAS[home.team?.displayName] || TEAM_ALIAS[home.team?.name];
          const aKey = TEAM_ALIAS[away.team?.displayName] || TEAM_ALIAS[away.team?.name];
          if (!hKey || !aKey) continue;
          const status = comp.status?.type?.name;
          if (status === 'STATUS_FINAL' || status === 'STATUS_FULL_TIME') {
            scores[`${hKey}|${aKey}`] = `${home.score}-${away.score}`;
          }
        }
      }
    } catch (e) {
      console.error('ESPN error:', e.message);
    }
  }

  return scores;
}

// ─────────────────────────────────────────────
// 生成 ICS 內容
// ─────────────────────────────────────────────
function generateICS(scoresMap) {
  const lines = [];

  lines.push('BEGIN:VCALENDAR');
  lines.push('VERSION:2.0');
  lines.push('PRODID:-//2026 FIFA World Cup//ZH-TW//');
  lines.push('X-WR-CALNAME:2026世界盃足球賽');
  lines.push('X-WR-CALDESC:2026年FIFA世界盃足球賽完整賽程（含台灣時間，比分自動更新）');
  lines.push('X-WR-TIMEZONE:Asia/Taipei');
  lines.push('CALSCALE:GREGORIAN');
  lines.push('METHOD:PUBLISH');

  for (const [no, dtstart, durMin, vkey, t1, t2, stage] of MATCHES) {
    const v = VENUES[vkey];
    const stageZH = STAGE_ZH[stage];
    const stageEN = STAGE_EN[stage];
    const t1zh = zh(t1);
    const t2zh = zh(t2);
    const scoreKey = `${t1}|${t2}`;
    const score = scoresMap[scoreKey];

    const summary = score
      ? `${stageZH}｜${t1zh} vs ${t2zh}（${score}）`
      : `${stageZH}｜${t1zh} vs ${t2zh}`;

    const location = `${v.name}\\, ${v.city}`;
    const twTime = utcToTW(dtstart);
    const localTime = utcToLocal(dtstart, v.off);
    const desc = [
      `對戰：${t1zh} vs ${t2zh}`,
      `階段：${stageZH} / ${stageEN}`,
      `台灣時間：${twTime}（UTC+8）`,
      `當地時間：${localTime}（${v.tz}）`,
      `地點：${v.name}\\, ${v.city}`,
      `提醒：賽程可能因 FIFA 公告更新而調整。`,
    ].join('\\n');

    lines.push('');
    lines.push('BEGIN:VEVENT');
    lines.push(`UID:wc2026-match-${String(no).padStart(3,'0')}@calendar`);
    lines.push(`DTSTART:${dtstart}`);
    lines.push(`DTEND:${dtend(dtstart, durMin)}`);
    lines.push(`SUMMARY:${summary}`);
    lines.push(`LOCATION:${location}`);
    lines.push(`DESCRIPTION:${desc}`);
    lines.push('END:VEVENT');
  }

  lines.push('');
  lines.push('END:VCALENDAR');

  return lines.map(foldLine).join('');
}

// ─────────────────────────────────────────────
// 更新比分並重新生成 ICS
// ─────────────────────────────────────────────
async function refreshScores(env) {
  const now = new Date();
  const log = [];

  // 1. fifacom.tw：一次取得所有歷史比分（主要來源，繁體中文台灣網站）
  const { scores: fifaScores, error: fifaError } = await fetchFifacomTWScores();
  log.push(`[fifacom.tw] ${Object.keys(fifaScores).length} scores${fifaError ? ' (Error: ' + fifaError + ')' : ''}`);

  const allScores = { ...fifaScores };

  // 2. 今日比分：用 Sofascore / ESPN 補充（可能比 wiki 更即時）
  const todayISO = now.toISOString().split('T')[0];
  const todayScores = await fetchDayScores(todayISO);
  log.push(`[Today ${todayISO}] ${Object.keys(todayScores).length} scores`);
  Object.assign(allScores, todayScores);

  const total = Object.keys(allScores).length;
  log.push(`[Total] ${total} scores`);

  const ics = generateICS(allScores);

  // 不設 TTL，確保 ICS 永遠存在（每小時 cron 會更新）
  await env.WC2026.put('ics', ics);
  await env.WC2026.put('scores_json', JSON.stringify(allScores));
  await env.WC2026.put('last_updated', now.toISOString());
  await env.WC2026.put('refresh_log', log.join('\n'));

  console.log('Refresh done:', log.join(' | '));
  return { total, log };
}

// ─────────────────────────────────────────────
// Worker 入口點
// ─────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // GET /debug — 查看目前 KV 狀態
    if (url.pathname === '/debug') {
      const ics = await env.WC2026.get('ics') || '';
      const scoresJson = await env.WC2026.get('scores_json') || '{}';
      const lastUpdated = await env.WC2026.get('last_updated') || 'Never';
      const scores = JSON.parse(scoresJson);
      // 從 ICS 裡數有比分的場次（含「（x-x）」）
      const scoredEvents = (ics.match(/SUMMARY:.*（\d+-\d+）/g) || []).length;
      const scoresText = Object.entries(scores).map(([k,v]) => `  ${k}: ${v}`).join('\n');
      const body = [
        `=== 2026 WC Calendar Debug ===`,
        `Last Updated: ${lastUpdated}`,
        `ICS size: ${ics.length} bytes`,
        `ICS scored events: ${scoredEvents}`,
        `scores_json count: ${Object.keys(scores).length}`,
        ``,
        `Scores:`,
        scoresText || '  (none)',
      ].join('\n');
      return new Response(body, {
        status: 200,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      });
    }

    // GET / — 提供 ICS 訂閱（由本機 update_scores.py 生成並寫入 KV）
    const ics = await env.WC2026.get('ics');
    if (!ics) {
      return new Response(
        'ICS not yet generated. Please run update_scores.py first.',
        { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }
      );
    }
    const lastUpdated = await env.WC2026.get('last_updated') || 'N/A';
    return new Response(ics, {
      headers: {
        'Content-Type': 'text/calendar; charset=utf-8',
        'Content-Disposition': 'attachment; filename="wc2026.ics"',
        'Cache-Control': 'no-cache, no-store',
        'X-Last-Updated': lastUpdated,
        'Access-Control-Allow-Origin': '*',
      },
    });
  },

  // Cron — 不再做任何事（ICS 由本機 Python 腳本負責生成）
  async scheduled(event, env, ctx) {
    ctx.waitUntil((async () => {
      console.log('Cron triggered — no-op (ICS managed by update_scores.py)');
    })());
  },
};
