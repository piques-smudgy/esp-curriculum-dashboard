#!/usr/bin/env python3
"""
ESP Curriculum Dashboard — data refresh script
Run this to fetch the latest Google Sheets data and rebuild index.html.
Called automatically by GitHub Actions; can also be run locally.

Usage:
    python3 scripts/process.py
"""

import csv, json, re, sys, urllib.request, datetime
from io import StringIO

# ── CONFIG ────────────────────────────────────────────────────────────────────
# The "export" URL works server-side (no CORS); keep the sheet shared as
# "Anyone with the link → Viewer".
SHEET_ID = "1yC2wcen3-uWT2Ax58Tpr64Kr4LqKeR835gnMQD11HoE"
CSV_URL  = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

EARLY_KEYWORDS = ("early chance", "extra chance", "alternative track")

# ── FETCH ─────────────────────────────────────────────────────────────────────
def fetch_csv(url):
    print(f"Fetching: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")

# ── PROCESS ───────────────────────────────────────────────────────────────────
def process(text):
    reader = csv.DictReader(StringIO(text))
    data = {}

    for row in reader:
        course  = (row.get("Course") or "").strip()
        act     = (row.get("ActivityName") or "").strip()
        aud     = (row.get("AudienceLevel") or "").strip()
        dtype   = (row.get("DisplayType") or "").strip()
        cw_raw  = (row.get("CalendarWeek") or "").strip()

        if not course or aud != "Student" or not cw_raw or cw_raw == "-":
            continue
        try:
            cw = int(cw_raw)
        except ValueError:
            continue

        if dtype not in ("TEACH", "EXAM", "RETAKE"):
            continue

        if course not in data:
            data[course] = {"teach": set(), "exam": set(), "retake": set(), "early": set(), "acts": {}}

        data[course]["acts"].setdefault(str(cw), [])
        if act:
            data[course]["acts"][str(cw)].append(act)

        nl = act.lower()
        is_early = any(k in nl for k in EARLY_KEYWORDS)

        if dtype == "TEACH":
            data[course]["teach"].add(cw)
        elif dtype == "RETAKE":
            data[course]["retake"].add(cw)
        elif dtype == "EXAM":
            (data[course]["early"] if is_early else data[course]["exam"]).add(cw)

    # Convert sets → sorted lists for JSON serialisation
    return {
        course: {
            "teach":  sorted(d["teach"]),
            "exam":   sorted(d["exam"]),
            "retake": sorted(d["retake"]),
            "early":  sorted(d["early"]),
            "acts":   d["acts"],
        }
        for course, d in data.items()
    }

# ── EMBED ─────────────────────────────────────────────────────────────────────
def embed(data, html_path="index.html"):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    today   = datetime.date.today().strftime("%d %b %Y")
    n       = len(data)
    js_data = "const EMBEDDED = " + json.dumps(data, ensure_ascii=False) + ";"

    new_block = (
        f"// ── EMBEDDED DATA — rebuilt: {today} ──────────────────\n"
        + js_data + "\n\n"
        + "// ── LOAD ──────────────────────────────────────────────────\n"
        "function load() {\n"
        "  const dot   = document.getElementById('syncDot');\n"
        "  const label = document.getElementById('syncLabel');\n"
        "\n"
        "  const data = {};\n"
        "  for (const [course, d] of Object.entries(EMBEDDED)) {\n"
        "    data[course] = {\n"
        "      teach:  new Set(d.teach),\n"
        "      exam:   new Set(d.exam),\n"
        "      retake: new Set(d.retake),\n"
        "      early:  new Set(d.early),\n"
        "      acts:   d.acts\n"
        "    };\n"
        "  }\n"
        "\n"
        f"  dot.className = 'sync-dot live';\n"
        f"  label.textContent = `${{Object.keys(data).length}} courses · {today}`;\n"
        "  document.getElementById('syncRefreshIcon').style.display = '';\n"
        "\n"
        "  render(data);\n"
        "}\n"
        "\n"
        "load();\n"
    )

    # Replace everything from the EMBEDDED/LOAD block to </script>
    for marker in ("// ── EMBEDDED DATA", "// ── LOAD ──"):
        pos = html.find(marker)
        if pos != -1:
            break
    else:
        print("ERROR: could not find insertion point in index.html", file=sys.stderr)
        sys.exit(1)

    script_end = html.find("</script>")
    html = html[:pos] + new_block + html[script_end:]

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Embedded {n} courses (built {today}) → {html_path}")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    html_path = os.path.join(os.path.dirname(__file__), "..", "index.html") \
                if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "scripts" \
                else "index.html"

    text = fetch_csv(CSV_URL)
    data = process(text)
    embed(data, html_path)
