import requests, math, json, glob, os, datetime as dt
from zoneinfo import ZoneInfo

PRODUCT_ID = 0                 # FILL: OG product id จาก Network tab หน้า CME settlements
REPO = "seed_beoner_gcoi"
CT = ZoneInfo("America/Chicago")
EXP_H, EXP_M = 12, 30
URL = "https://www.cmegroup.com/CmeWS/mvc/Settlements/Options/Settlements/{pid}/OOF"
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
       "Referer": "https://www.cmegroup.com/markets/metals/precious/gold.settlements.options.html"}

def next_expiries(n=5):
    now, out = dt.datetime.now(CT), []
    for d in range(14):
        c = (now + dt.timedelta(days=d)).replace(hour=EXP_H, minute=EXP_M, second=0, microsecond=0)
        if c.weekday() < 5 and c > now:
            out.append(c.date())
    return out[:n]

def series(d):
    w = math.ceil(d.day / 7)
    root = {0: f"G{w}M", 1: f"G{w}T", 2: f"G{w}W", 3: f"G{w}R", 4: f"OG{w}"}[d.weekday()]
    return f"{root}{'FGHJKMNQUVXZ'[d.month - 1]}{d.year % 10}"

def fetch(day, ser):
    r = requests.get(URL.format(pid=PRODUCT_ID), headers=HDR, timeout=20,
                     params={"strategy": "DEFAULT", "tradeDate": day.strftime("%Y%m%d"), "monthYear": ser})
    r.raise_for_status()
    return r.json()

def rows(j):
    out = {}
    for s in j.get("settlements", []):                       # FILL: ตรวจชื่อ key กับ json จริง
        k = int(float(s["strike"].replace(",", "")))
        oi = int(str(s["openInterest"]).replace(",", "") or 0)
        c, p = out.get(k, (0, 0))
        out[k] = (oi, p) if s["type"].lower().startswith("c") else (c, oi)   # FILL: field call/put
    return out

os.makedirs("data", exist_ok=True)
os.makedirs("symbol_info", exist_ok=True)

for exp in next_expiries():
    ser = series(exp)
    for back in range(5):
        day = dt.date.today() - dt.timedelta(days=back)
        if day.weekday() >= 5:
            continue
        try:
            data = rows(fetch(day, ser))
        except Exception as e:
            print(ser, day, "fail:", e)
            continue
        if data:
            for k, (c, p) in data.items():
                with open(f"data/{ser}_{k}.csv", "w") as f:
                    f.write("time,open,high,low,close,volume\n")
                    # call OI = close, put OI = volume (OHLC เท่ากันเพื่อไม่ผิดกฎ high/low)
                    f.write(f"{day:%Y%m%d}T,{c},{c},{c},{c},{p}\n")
            print(ser, day, len(data), "strikes")
            break

# ลบไฟล์เก่าเกิน 10 วัน
cut = (dt.date.today() - dt.timedelta(days=10)).strftime("%Y%m%d")
for fp in glob.glob("data/*.csv"):
    if open(fp).read().strip().splitlines()[-1][:8] < cut:
        os.remove(fp)

syms = sorted(os.path.basename(f)[:-4] for f in glob.glob("data/*.csv"))
info = {"symbol": syms, "description": syms, "currency": ["USD"] * len(syms),
        "session-regular": ["24x7"] * len(syms), "timezone": ["Etc/UTC"] * len(syms)}
json.dump(info, open(f"symbol_info/{REPO}.json", "w"), indent=1)
