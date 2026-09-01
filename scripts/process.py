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
# Curriculum activities sheet (source of teach/exam/retake data)
SHEET_ID = "1yC2wcen3-uWT2Ax58Tpr64Kr4LqKeR835gnMQD11HoE"
CSV_URL  = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

# Master courses sheet (whitelist of real courses + SM grouping)
COURSES_SHEET_ID = "1mhZCbj-UOnfY_0NkQAEJC-_HGrPXPh4nyVDIMqXBDN8"
COURSES_GID      = "1788765045"
COURSES_URL      = f"https://docs.google.com/spreadsheets/d/{COURSES_SHEET_ID}/export?format=csv&gid={COURSES_GID}"

EARLY_KEYWORDS = ("early chance", "extra chance", "alternative track")

# Aliases: master-sheet course name → dashboard display name.
# Use when two official courses share one combined dashboard row.
COURSE_ALIASES = {
    "Assessment 3":    "Assessment & Interventions 3",
    "Interventions 3": "Assessment & Interventions 3",
}

# ── FETCH ─────────────────────────────────────────────────────────────────────
def fetch_csv(url):
    print(f"Fetching: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")

# ── PARSE COURSES MASTER ───────────────────────────────────────────────────────
def parse_courses(text):
    """Return dict: display_course_name -> sm (int 1-6, or 0 if unknown)."""
    reader = csv.DictReader(StringIO(text))
    headers = reader.fieldnames or []
    print(f"Courses sheet headers: {headers}")

    # Find the course-name column (try several likely names)
    name_col = next(
        (h for h in headers
         if h.strip().lower() in ("course", "coursename", "name", "vak", "module")),
        None
    )
    # Find the SM column ("SM 3-yr" as specified in the sheet)
    sm_col = next(
        (h for h in headers
         if h.strip().lower() in ("sm 3-yr", "sm 3yr", "sm3-yr", "sm", "semester")),
        None
    )

    if not name_col:
        print(f"WARNING: no course-name column found in {headers}", file=sys.stderr)
        return {}
    if not sm_col:
        print(f"WARNING: no SM column found in {headers}", file=sys.stderr)
        return {}

    print(f"Using columns -> name: '{name_col}', sm: '{sm_col}'")

    course_sm = {}
    for row in reader:
        raw_name = (row.get(name_col) or "").strip()
        raw_sm   = (row.get(sm_col)   or "").strip()
        if not raw_name:
            continue
        display_name = COURSE_ALIASES.get(raw_name, raw_name)
        try:
            sm = int(float(raw_sm))   # handles "3" or "3.0"
        except (ValueError, TypeError):
            sm = 0
        if display_name not in course_sm:
            course_sm[display_name] = sm

    print(f"Parsed {len(course_sm)} courses from master sheet")
    return course_sm

# ── PROCESS ───────────────────────────────────────────────────────────────────
def process(text, course_sm=None):
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

        # Filter: if we have a whitelist, skip anything not on it
        if course_sm is not None and course not in course_sm:
            continue

        try:
            cw = int(cw_raw)
        except ValueError:
            continue

        if dtype not in ("TEACH", "EXAM", "RETAKE"):
            continue

        if course not in data:
            sm = course_sm.get(course, 0) if course_sm else 0
            data[course] = {
                "teach": set(), "exam": set(), "retake": set(),
                "early": set(), "acts": {}, "sm": sm
            }

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

    # Convert sets -> sorted lists for JSON serialisation
    return {
        course: {
            "teach":  sorted(d["teach"]),
            "exam":   sorted(d["exam"]),
            "retake": sorted(d["retake"]),
            "early":  sorted(d["early"]),
            "acts":   d["acts"],
            "sm":     d["sm"],
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
        "      acts:   d.acts,\n"
        "      sm:     d.sm || 0\n"
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

    print(f"Embedded {n} courses (built {today}) -> {html_path}")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    html_path = os.path.join(os.path.dirname(__file__), "..", "index.html") \
                if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "scripts" \
                else "index.html"

    # 1. Fetch the master courses list (whitelist + SM grouping)
    try:
        courses_text = fetch_csv(COURSES_URL)
        course_sm    = parse_courses(courses_text)
    except Exception as e:
        print(f"WARNING: could not fetch master courses sheet: {e}", file=sys.stderr)
        print("Continuing without course filter — all activities will be shown.")
        course_sm = None

    # 2. Fetch curriculum activities and process
    text = fetch_csv(CSV_URL)
    data = process(text, course_sm)

    # 3. Embed into index.html
    embed(data, html_path)
