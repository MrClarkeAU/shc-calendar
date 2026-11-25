#!/usr/bin/env python3
"""Weekly update for the SHC staff calendar site.

Fetches the College's public Google calendars, sorts every event into a type,
department and year group, then writes:
  data/events.json   events for the school year, used by index.html
  data/meta.json     when the data was last checked, plus the feed list
  feeds/*.ics        ready-made filtered calendars staff can subscribe to

Standard library only. Run locally with:  python3 scripts/build.py
Use --from-dir DIR to read saved .ics files (named CODE.ics) instead of fetching.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

YEAR = 2027                      # school year the site covers
PERTH = ZoneInfo("Australia/Perth")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = "@group.calendar.google.com"

CALS = {  # code: (name, calendar id, kind, year group)
    "AS": ("All School", "cewa.edu.au_qsjrpbbi7db58ppka9bfuv4sts", "events", 0),
    "SW": ("School Weeks", "cewa.edu.au_tv2uo13ksq02jdcc4afna53vek", "weeks", 0),
    "7E": ("Y07 Events", "cewa.edu.au_c8uu66vogahsi8dj762i1tshm4", "events", 7),
    "7A": ("Y07 Assessments", "cewa.edu.au_80kn74fq9jvqhhrc37o055nv3c", "assess", 7),
    "8E": ("Y08 Events", "cewa.edu.au_v7g5d38bsvuhth75lgk3eu8j58", "events", 8),
    "8A": ("Y08 Assessments", "cewa.edu.au_v1pdik2lo29j8qi4tku4pu27vc", "assess", 8),
    "9E": ("Y09 Events", "cewa.edu.au_7nbepunfrm2u1po90akt9ucfj4", "events", 9),
    "9A": ("Y09 Assessments", "cewa.edu.au_o5gbsvs7nkrekmjrknvkafvrho", "assess", 9),
    "10E": ("Y10 Events", "cewa.edu.au_mr1b75a413q6vjf82slok8mkb4", "events", 10),
    "10A": ("Y10 Assessments", "cewa.edu.au_tbutno4c2222iuv6oi8mm31vr0", "assess", 10),
    "11E": ("Y11 Events", "cewa.edu.au_bv859n02p8q4sk85uldcp06je0", "events", 11),
    "11A": ("Y11 Assessments", "cewa.edu.au_5u67g3od5vv9nvvoc72q2rvpr0", "assess", 11),
    "12E": ("Y12 Events", "cewa.edu.au_psbsgs4v9at8n89bv26qknlrms", "events", 12),
    "12A": ("Y12 Assessments", "cewa.edu.au_s7hrcim0r18qt2bj3ud3h8277s", "assess", 12),
}

def ics_url(code):
    return f"https://calendar.google.com/calendar/ical/{CALS[code][1]}%40group.calendar.google.com/public/basic.ics"

# ---------------------------------------------------------------- classify
TYPES = [
    ("noclass", "No classes"), ("term", "Term dates"), ("assess", "Assessments"), ("exams", "Exams & testing"),
    ("faith", "Masses, assemblies & services"), ("arts", "Arts & performances"), ("sport", "Sport & carnivals"),
    ("comps", "Academic & competitions"), ("trips", "Camps, retreats & excursions"), ("careers", "Careers & subject selection"),
    ("pastoral", "Wellbeing & health"), ("community", "Parents, community & evenings"), ("note", "Days of note"),
    ("admin", "Admin & other"),
]
TL = dict(TYPES)
RULES = [(k, re.compile(p)) for k, p in [
    ("noclass", r"pupil free|learning conference|public holiday|holidays|new year'?s day|australia day|labour day|good friday|easter (saturday|sunday|monday|tuesday)|^anzac day|wa day|king'?s official birthday"),
    ("term", r"\bterm \d|students commence|students return|\bfinish\b|final day"),
    ("exams", r"exam|naplan|olna|assessment free|\btest\b"),
    ("admin", r"photo|attendance audit|homework supper"),
    ("pastoral", r"litherland|surf online"),
    ("community", r"dinner dance|\bball\b"),
    ("faith", r"\bmass\b|liturgy|assembly|ash wednesday|sacred heart day|feast of|commissioning|project compassion|service\b"),
    ("arts", r"musical|rehears|drama|\bdance|music|concert|exhibition|\barts?\b|hearts|showcase|\bband|cpaf|production|theatre|jazz"),
    ("sport", r"carnival|athletics|swim|cross country|hockey|soccer|netball|volleyball|surf|triathlon|golf|\bnas\b|\bacc\b|afl|super series|sport"),
    ("comps", r"decathlon|ethics|scholars cup|\btom\b|tournament|challenge|icas"),
    ("careers", r"career|subject selection|\bvet\b|workplace"),
    ("community", r"college tour|orientation day\b|information (night|evening)|parent|reunion|p&f|picnic|high tea|morning tea|coffee morning|fundraiser|fun day|6pm|alumni|families|grandparents|awards night"),
    ("trips", r"camp\b|camp |tour\b|excursion|expedi|retreat|rottnest|seatrek|scuba|snorkel|hiking|roping|abseil|climbing|mtb|river cruise|sleep out|reccy|zoo|activity day|immersion|facilitation"),
    ("pastoral", r"presentation|seminar|paul dillon|bstreetsmart|vaccin|leadership|peer mentor|theme:|independent learning|indep\. learning|orientation|catch up"),
    ("note", r"feast day|st patrick|remembrance day|harmony week|daffodil|r u ok|mother'?s day"),
]]
DEPTS = [(k, re.compile(p)) for k, p in [
    ("English", r"\beng\b|english|literature|debat|writing"), ("Maths", r"\bmaths?\b|mathematic"),
    ("Science", r"science|biology|\bhb\b|human bio|chem|physics|psych|\bmms\b|marine|seatrek|scuba|engineering challenge"),
    ("Humanities", r"humanit|\bhass\b|history|geograph|economic|politic|legal|business|civics|accounting"),
    ("RE", r"\bre\b|religio|ethics|respectful relationships"), ("Languages", r"french|italian|japanese|indonesian|chinese|language|fukui"),
    ("Dance", r"(?<!dinner )\bdance"), ("Drama", r"drama|theatre|musical|production"), ("Music", r"music|\bband|concert|jazz|cpaf"),
    ("Media", r"\bmedia\b|\bfilm"), ("Visual Art", r"\bart\b|\barts? exhibition|visual art"),
    ("HPE", r"\bhpe\b|health|physical ed|\boed\b|outdoor|sport|carnival|athletics|swim|cross country|hockey|afl|\bnas\b|\bacc\b|surf(?! online)|triathlon|golf|volleyball|super series|hiking|roping|mtb|abseil|climbing|snorkel|expedi"),
    ("Technologies", r"digital tech|\bit\b|design|food|textile|wood|metal|engineering|computer|coding|robotic|technolog|hospitality"),
]]
ARTS = {"Dance", "Drama", "Media", "Music", "Visual Art"}

def classify(title, kind):
    lt = title.lower()
    if kind == "assess":
        typ = "assess"
    else:
        typ = next((k for k, r in RULES if r.search(lt)), "admin")
    return typ, [k for k, r in DEPTS if r.search(lt)]

YR_RE = re.compile(r"\bY(?:ea)?rs?\.?\s?((?:\d{1,2}(?:\s?(?:-|/|,|&|and)\s?)?)+)", re.I)
def years_in(title):
    if re.search(r"whole school", title, re.I):
        return []
    s = re.sub(r"\bYr\s?\d{1,2}\s+20\d\d\b", "", title, flags=re.I)  # "Yr7 2029 ..." = a future intake
    out = set()
    for m in YR_RE.finditer(s):
        seg = m.group(1)
        for a, b in re.findall(r"(\d{1,2})\s?-\s?(\d{1,2})", seg):
            out.update(range(int(a), int(b) + 1))
        seg = re.sub(r"(\d{1,2})\s?-\s?(\d{1,2})", "", seg)
        out.update(int(n) for n in re.findall(r"\d{1,2}", seg))
    ys = sorted(y for y in out if 7 <= y <= 12)
    return [] if len(ys) == 6 else ys

# ---------------------------------------------------------------- parse ICS
def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text).replace("\r", "")

def unescape(v):
    return re.sub(r"\\([,;\\nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), v)

def parse_props(block):
    props = {}
    for line in block.split("\n"):
        if ":" not in line:
            continue
        head, val = line.split(":", 1)
        name, *params = head.split(";")
        p = dict(x.split("=", 1) for x in params if "=" in x)
        props.setdefault(name.upper(), []).append((p, val.strip()))
    return props

def parse_dt(p, v):
    """Return (value, allday). value is a date, or a naive Perth datetime."""
    if p.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", v):
        return dt.datetime.strptime(v[:8], "%Y%m%d").date(), True
    fmt = "%Y%m%dT%H%M%S" if len(v.rstrip("Z")) == 15 else "%Y%m%dT%H%M"
    t = dt.datetime.strptime(v.rstrip("Z"), fmt)
    if v.endswith("Z"):
        t = t.replace(tzinfo=dt.timezone.utc)
    else:
        try:
            t = t.replace(tzinfo=ZoneInfo(p.get("TZID", "Australia/Perth")))
        except Exception:
            t = t.replace(tzinfo=PERTH)
    return t.astimezone(PERTH).replace(tzinfo=None), False

WD = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
def expand(start, rrule, exdates, limit_end):
    """Simple RRULE expansion (DAILY/WEEKLY/MONTHLY with INTERVAL, COUNT, UNTIL, BYDAY)."""
    r = dict(x.split("=", 1) for x in rrule.split(";") if "=" in x)
    freq, step = r.get("FREQ"), int(r.get("INTERVAL", "1"))
    count = int(r["COUNT"]) if "COUNT" in r else None
    until = None
    if "UNTIL" in r:
        u = r["UNTIL"]
        until = dt.datetime.strptime(u[:8], "%Y%m%d").date()
    days = [WD[d[-2:]] for d in r.get("BYDAY", "").split(",") if d[-2:] in WD]
    is_dt = isinstance(start, dt.datetime)
    d0 = start.date() if is_dt else start
    out, n, cur = [], 0, d0
    while cur <= limit_end and n < 2000:
        cands = []
        if freq == "WEEKLY":
            wk = cur - dt.timedelta(days=cur.weekday())
            cands = [wk + dt.timedelta(days=x) for x in (days or [d0.weekday()])]
        elif freq == "DAILY":
            cands = [cur]
        elif freq == "MONTHLY":
            cands = [cur]
        else:
            break
        for c in sorted(cands):
            if c < d0 or (until and c > until) or c > limit_end:
                continue
            n += 1
            if count and n > count:
                return out
            occ = dt.datetime.combine(c, start.time()) if is_dt else c
            if occ not in exdates:
                out.append(occ)
        if freq == "WEEKLY":
            cur = cur - dt.timedelta(days=cur.weekday()) + dt.timedelta(weeks=step)
        elif freq == "DAILY":
            cur += dt.timedelta(days=step)
        else:
            m = cur.month - 1 + step
            try:
                cur = cur.replace(year=cur.year + m // 12, month=m % 12 + 1)
            except ValueError:
                break
        if until and cur > until:
            break
    return out

def events_from_ics(code, text):
    y0, y1 = dt.date(YEAR, 1, 1), dt.date(YEAR + 1, 1, 1)
    blocks = unfold(text).split("BEGIN:VEVENT")[1:]
    overrides, raws = {}, []
    for b in blocks:
        props = parse_props(b.split("END:VEVENT")[0])
        g = lambda k: props.get(k, [({}, "")])[0]
        if "DTSTART" not in props:
            continue
        title = unescape(g("SUMMARY")[1]).strip()
        if not title:
            continue
        if g("STATUS")[1].upper() == "CANCELLED" or title.lower().startswith("cancelled"):
            continue
        s, allday = parse_dt(*g("DTSTART"))
        if "DTEND" in props:
            e, _ = parse_dt(*g("DTEND"))
        else:
            e = s + (dt.timedelta(days=1) if allday else dt.timedelta(hours=1))
        item = {"uid": g("UID")[1], "s": s, "e": e, "allday": allday, "title": title,
                "desc": unescape(g("DESCRIPTION")[1]), "rrule": g("RRULE")[1],
                "ex": {parse_dt(p, x)[0] for p, v in props.get("EXDATE", []) for x in v.split(",")}}
        if "RECURRENCE-ID" in props:
            rid, _ = parse_dt(*g("RECURRENCE-ID"))
            overrides[(item["uid"], rid)] = item
        else:
            raws.append(item)
    out = []
    for it in raws:
        dur = it["e"] - it["s"]
        starts = expand(it["s"], it["rrule"], it["ex"], y1) if it["rrule"] else [it["s"]]
        for st in starts:
            occ = overrides.get((it["uid"], st), None)
            s, e = (occ["s"], occ["e"]) if occ else (st, st + dur)
            title = occ["title"] if occ else it["title"]
            sd = s.date() if isinstance(s, dt.datetime) else s
            ed = e.date() if isinstance(e, dt.datetime) else e
            if sd < y1 and (ed > y0 or sd >= y0):
                out.append({"code": code, "s": s, "e": e, "allday": it["allday"], "title": title, "desc": it["desc"]})
    return out

def clean_title(t):
    t = re.sub(r"\s*\($", "", t.strip())
    return re.sub(r"\s+", " ", t)

def clean_desc(d):
    d = re.sub(r"<[^>]+>", " ", d)
    d = re.sub(r"&nbsp;", " ", d)
    return re.sub(r"\s+", " ", d).strip()[:300]

def fmt(v):
    return v.isoformat() if isinstance(v, dt.date) and not isinstance(v, dt.datetime) else v.strftime("%Y-%m-%dT%H:%M")

# ---------------------------------------------------------------- feeds
def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def fold(line):
    out = []
    while len(line.encode()) > 74:
        cut = 74
        while len(line[:cut].encode()) > 74:
            cut -= 1
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return "\r\n".join(out)

def to_ics(name, events, generated):
    now = generated.strftime("%Y%m%dT%H%M%SZ")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Mr Clarke//SHC staff calendar//EN", "CALSCALE:GREGORIAN",
         "METHOD:PUBLISH", f"X-WR-CALNAME:{ics_escape(name)}", "X-WR-TIMEZONE:Australia/Perth",
         "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:P1D"]
    for ev in events:
        cals = ", ".join(CALS[c][0] for c in ev["c"])
        desc = "\n".join(([ev["x"], ""] if ev["x"] else []) + [f"Calendar: {cals}", f"Type: {TL.get(ev['type'], 'Week label')}"]
                         + ([f"Department: {', '.join(ev['d'])}"] if ev["d"] else []))
        L += ["BEGIN:VEVENT", f"UID:{ev['id']}@shc-calendar", f"DTSTAMP:{now}"]
        if ev["allday"]:
            L += [f"DTSTART;VALUE=DATE:{ev['s'].replace('-', '')}", f"DTEND;VALUE=DATE:{ev['e'].replace('-', '')}"]
        else:
            for k, key in (("DTSTART", "s"), ("DTEND", "e")):
                t = dt.datetime.strptime(ev[key], "%Y-%m-%dT%H:%M").replace(tzinfo=PERTH).astimezone(dt.timezone.utc)
                L.append(f"{k}:{t.strftime('%Y%m%dT%H%M%SZ')}")
        L += [f"SUMMARY:{ics_escape('SHC: ' + ev['t'])}", f"DESCRIPTION:{ics_escape(desc)}",
              f"CATEGORIES:SHC,{ics_escape(TL.get(ev['type'], 'Week labels'))}", "TRANSP:TRANSPARENT",
              "X-MICROSOFT-CDO-BUSYSTATUS:FREE", "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in L) + "\r\n"

def presets(events, weeks):
    base = lambda e: e["type"] in ("noclass", "term") and "AS" in e["c"]
    for_year = lambda y: (lambda e: base(e) or y in e["y"])
    dept = lambda names: (lambda e: base(e) or bool(set(e["d"]) & names))
    P = [
        ("interruptions", "Whole-school interruptions", "No-class days, term dates, and whole-school Masses, assemblies and services.",
         lambda e: base(e) or (e["type"] == "faith" and e["w"])),
        ("no-classes", "No-class days and term dates", "Public holidays, pupil free days, Learning Conference days, holidays, and term start and end.", base),
    ]
    P += [(f"year-{y}", f"Year {y}: everything", f"Year {y} events and assessments, plus no-class days and term dates.", for_year(y)) for y in range(7, 13)]
    P += [("all-assessments", "All assessments, Years 7–12", "Every assessment from the six year-group assessment calendars.", lambda e: e["type"] == "assess")]
    P += [("dept-arts", "Arts: Dance, Drama, Media, Music, Visual Art", "Arts events and assessments across all years, plus no-class days and term dates.", dept(ARTS))]
    for d in ("English", "Maths", "Science", "Humanities", "RE", "Languages", "HPE", "Technologies"):
        P.append((f"dept-{d.lower()}", f"{d}: all years", f"{d} events and assessments across all years, plus no-class days and term dates.", dept({d})))
    out = [(slug, name, desc, [e for e in events if f(e)]) for slug, name, desc, f in P]
    out.append(("week-labels", "School week labels", "“Week 3, Term 2” across the top of each school week (Monday to Friday).", weeks))
    return out

# ---------------------------------------------------------------- main
def fetch(code, tries=3):
    req = urllib.request.Request(ics_url(code), headers={"User-Agent": "shc-calendar-site (GitHub Actions)"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            err = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{CALS[code][0]}: {err}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir", help="read CODE.ics files from this folder instead of fetching")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    meta_path = os.path.join(ROOT, "data", "meta.json")
    old = json.load(open(meta_path)) if os.path.exists(meta_path) else {}

    texts, errors = {}, []
    for code in CALS:
        try:
            if a.from_dir:
                texts[code] = open(os.path.join(a.from_dir, f"{code}.ics"), encoding="utf-8").read()
            else:
                texts[code] = fetch(code)
        except Exception as e:
            errors.append(str(e))

    if errors:  # keep the last good data; record the failed attempt (this also keeps the repo active)
        old.update({"checked": now.isoformat(), "ok": False, "errors": errors})
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        json.dump(old, open(meta_path, "w"), indent=1, ensure_ascii=False)
        print("Update failed:", *errors, sep="\n  ")
        return 0

    raw = [ev for code, t in texts.items() for ev in events_from_ics(code, t)]
    weeks, merged = [], {}
    for ev in raw:
        name, _, kind, yr = CALS[ev["code"]]
        title = clean_title(ev["title"])
        if kind == "weeks":
            m = re.match(r"Week (\d+) Term (\d)", title)
            if m and ev["allday"]:
                mon = ev["s"] + dt.timedelta(days=(7 - ev["s"].weekday()) % 7)  # labels sit on Sunday; use Monday
                weeks.append({"id": "wk-" + mon.isoformat(), "c": ["SW"], "s": mon.isoformat(), "e": (mon + dt.timedelta(days=5)).isoformat(),
                              "allday": True, "t": f"Week {m.group(1)}, Term {m.group(2)}", "x": "", "type": "week", "d": [], "y": [], "w": True,
                              "term": int(m.group(2)), "week": int(m.group(1))})
            continue
        typ, depts = classify(title, kind)
        yrs = [yr] if yr else years_in(title)
        key = (fmt(ev["s"]), fmt(ev["e"]), title.lower())
        if key in merged:
            m = merged[key]
            if ev["code"] not in m["c"]:
                m["c"].append(ev["code"])
            m["y"] = sorted(set(m["y"]) | set(yrs))
            continue
        merged[key] = {"id": "shc-" + hashlib.sha1(f"{ev['code']}|{fmt(ev['s'])}|{title}".encode()).hexdigest()[:12],
                       "c": [ev["code"]], "s": fmt(ev["s"]), "e": fmt(ev["e"]), "allday": ev["allday"], "t": title,
                       "x": clean_desc(ev["desc"]), "type": typ, "d": depts, "y": yrs, "w": ev["code"] == "AS" and not yrs}
    events = sorted(merged.values(), key=lambda e: (e["s"], e["t"].lower()))
    weeks.sort(key=lambda w: w["s"])

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "feeds"), exist_ok=True)
    json.dump({"year": YEAR, "types": TYPES, "depts": [k for k, _ in DEPTS], "events": events, "weeks": weeks},
              open(os.path.join(ROOT, "data", "events.json"), "w"), ensure_ascii=False, separators=(",", ":"))

    feeds = []
    for slug, name, desc, evs in presets(events, weeks):
        open(os.path.join(ROOT, "feeds", f"{slug}.ics"), "w", newline="").write(to_ics(f"SHC {name}", evs, now))
        feeds.append({"file": f"feeds/{slug}.ics", "name": name, "desc": desc, "count": len(evs)})

    counts = {c: sum(1 for e in events if c in e["c"]) for c in CALS}
    counts["SW"] = len(weeks)
    meta = {"year": YEAR, "checked": now.isoformat(), "updated": now.isoformat(), "ok": True, "errors": [],
            "events": len(events), "counts": counts, "feeds": feeds,
            "calendars": [{"code": c, "name": CALS[c][0], "kind": CALS[c][2], "yr": CALS[c][3], "url": ics_url(c)} for c in CALS]}
    json.dump(meta, open(meta_path, "w"), indent=1, ensure_ascii=False)
    print(f"OK: {len(events)} events, {len(weeks)} week labels, {len(feeds)} feeds")
    return 0

if __name__ == "__main__":
    sys.exit(main())
