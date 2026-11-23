"""Builds the call-sheet workbook: company row + posting sub-rows, dropdowns, hiring summary, history tabs."""
import collections
import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule

NAVY = "1F3A5F"
STATUS = ["Not called", "No answer", "Left voicemail", "Emailed", "Spoke - interested", "Spoke - not hiring",
          "Call back later", "Wrong number", "Do not call"]
INDUSTRY = ["Property Management", "Facility Management Commercial", "Real Estate", "Technology", "Services",
            "Education", "Commercial Construction"]
MISSING = "NOT FOUND"
INTEREST = ["Hire a grad", "Join employer list", "Tour the campus", "Send info", "Not now"]
COLS = [  # (header, width)
    ("#", 5), ("Company", 34), ("Industry Type", 22), ("Trade", 16), ("Phone", 18), ("Email", 30), ("Website", 24),
    ("Contact Name", 20), ("Contact Title", 20), ("Notes", 40),
    ("Job Title", 40), ("Level", 8), ("Location", 26), ("Pay", 14), ("Requirements", 32), ("Date Posted", 12),
    ("Job Link", 22), ("Posting", 10),
    ("Status", 19), ("Date Called", 13), ("Email Sent", 13), ("Called By", 13), ("Spoke With", 18),
    ("Interested In", 18), ("Outcome / Notes", 40), ("Follow-up Date", 14)]
HDR = [c[0] for c in COLS]
C = {name: i for i, name in enumerate(HDR, 1)}  # column number by header
INPUT = ["Status", "Date Called", "Email Sent", "Called By", "Spoke With", "Interested In", "Outcome / Notes", "Follow-up Date"]
DATES = ["Date Called", "Email Sent", "Follow-up Date"]


def build(companies, path, today=None, callers=("Christina", "Tony", "Pratik", "Other")):
    """companies: list of {company, industry, trade, phone, email, website, contact_name, contact_title, notes,
    jobs:[{title, level, location, pay, requirements, posted, url, source, live}]}"""
    today = today or datetime.date.today()
    thin = Side(style="thin", color="C9D1DB"); bd = Border(bottom=thin)
    hfont = Font(bold=True, color="FFFFFF", size=11); hfill = PatternFill("solid", fgColor=NAVY)
    inp = PatternFill("solid", fgColor="FFF9E5"); band = PatternFill("solid", fgColor="DCE6F1")
    red = PatternFill("solid", fgColor="FDE2E2")
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "This Week - Call Sheet"
    ws["A1"] = f"GUTTS Employer Call Sheet - Week of {today:%b %d, %Y}"; ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    ws["A2"] = ("Yellow cells are for the caller. Posting: Live = we opened the posting today. Active = the job board listed it today "
                "but blocks automatic checks, so click the link before calling. Phone/Email come from the employer's own website.")
    ws["A2"].font = Font(italic=True, color="555555")
    HR = 4
    for i, h in enumerate(HDR, 1):
        c = ws.cell(HR, i, h); c.font = hfont; c.fill = hfill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[HR].height = 30
    r = HR
    for n, co in enumerate(companies, 1):
        r += 1
        lv = collections.Counter(j["level"] for j in co["jobs"])
        vals = {"#": n, "Company": co["company"], "Industry Type": co["industry"], "Trade": co["trade"],
                "Phone": co["phone"] or MISSING, "Email": co["email"] or MISSING, "Website": co["website"],
                "Contact Name": co.get("contact_name", ""), "Contact Title": co.get("contact_title", ""), "Notes": co.get("notes", ""),
                "Job Title": f"{len(co['jobs'])} open role(s)", "Level": "/".join(k for k in ("Entry", "Mid") if lv[k]), "Status": "Not called"}
        for i, h in enumerate(HDR, 1):
            c = ws.cell(r, i, vals.get(h, "")); c.fill = band; c.font = Font(bold=True, size=12 if h == "Company" else 11); c.border = bd
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for h in INPUT:
            ws.cell(r, C[h]).fill = inp
        for h in DATES:
            ws.cell(r, C[h]).number_format = "mm/dd/yyyy"
        for h in ("Phone", "Email"):
            miss = ws.cell(r, C[h]).value == MISSING
            ws.cell(r, C[h]).font = Font(bold=True, size=11, color="C00000" if miss else "1B5E20")
            if miss:
                ws.cell(r, C[h]).fill = red
        if co["website"]:
            ws.cell(r, C["Website"]).hyperlink = co["website"]; ws.cell(r, C["Website"]).font = Font(color="0563C1", underline="single")
        ws.row_dimensions[r].height = 44 if len(co.get("notes", "")) > 50 else 28
        for j in co["jobs"]:
            r += 1
            ws.cell(r, C["Job Title"], j["title"]); ws.cell(r, C["Level"], j["level"]); ws.cell(r, C["Location"], j["location"])
            ws.cell(r, C["Pay"], j.get("pay", "")); ws.cell(r, C["Requirements"], j.get("requirements", ""))
            ws.cell(r, C["Date Posted"], j.get("posted", ""))
            c = ws.cell(r, C["Job Link"], f"Open posting ({j['source']})"); c.hyperlink = j["url"]; c.font = Font(color="0563C1", underline="single")
            c = ws.cell(r, C["Posting"], j["live"]); c.font = Font(color="1B5E20" if j["live"] == "Live" else "9C5700", bold=True)
            for i in range(1, len(HDR) + 1):
                ws.cell(r, i).border = bd; ws.cell(r, i).alignment = Alignment(vertical="center", wrap_text=True)
            ws.row_dimensions[r].outlineLevel = 1; ws.row_dimensions[r].height = 30 if len(j.get("requirements", "")) > 34 else 20
    last = max(r, HR + 1)
    ws.sheet_properties.outlinePr.summaryBelow = False
    for i, (_, wd) in enumerate(COLS, 1):
        ws.column_dimensions[L(i)].width = wd
    ws.freeze_panes = ws.cell(HR + 1, 3); ws.auto_filter.ref = f"A{HR}:{L(len(HDR))}{last}"

    ls = wb.create_sheet("Lists"); ls["A1"] = "Dates"; d = today; k = 1
    while k <= 70:
        if d.weekday() < 5:
            k += 1; ls.cell(k, 1, d).number_format = "ddd mm/dd/yyyy"
        d += datetime.timedelta(days=1)
    ls.sheet_state = "hidden"

    def dv(sheet, formula, cells, warn=False):
        x = DataValidation(type="list", formula1=formula, allow_blank=True)
        if warn:
            x.errorStyle = "warning"; x.showErrorMessage = False
        sheet.add_data_validation(x)
        for c in cells:
            x.add(c)
    q = lambda xs: '"' + ",".join(xs) + '"'
    rows = [rr for rr in range(HR + 1, last + 1) if ws.cell(rr, 1).value]
    pick = lambda h: [ws.cell(rr, C[h]) for rr in rows]
    dv(ws, q(INDUSTRY), pick("Industry Type")); dv(ws, q(STATUS), pick("Status")); dv(ws, q(callers), pick("Called By"))
    dv(ws, q(INTEREST), pick("Interested In"))
    for h in DATES:
        dv(ws, "=Lists!$A$2:$A$71", pick(h), True)
    sc = L(C["Status"])
    for txt, col in [("No answer", "E0E0E0"), ("Left voicemail", "FFE0B2"), ("Emailed", "BBDEFB"), ("Spoke - interested", "A5D6A7"),
                     ("Spoke - not hiring", "EF9A9A"), ("Call back later", "FFF59D"), ("Wrong number", "CE93D8"), ("Do not call", "BDBDBD")]:
        ws.conditional_formatting.add(f"{sc}{HR+1}:{sc}{last}", FormulaRule(formula=[f'${sc}{HR+1}="{txt}"'], fill=PatternFill("solid", bgColor=col, fgColor=col)))
    ws.page_setup.orientation = "landscape"; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True; ws.print_title_rows = f"{HR}:{HR}"

    # ---- Hiring summary: where the openings are ----
    s = wb.create_sheet("Where Hiring Is"); s["A1"] = "Where the hiring is this week (live entry + mid-level postings)"
    s["A1"].font = Font(bold=True, size=14, color=NAVY)
    jobs = [(co, j) for co in companies for j in co["jobs"]]
    blocks = [("By Industry Type", collections.Counter(co["industry"] for co, _ in jobs)),
              ("By Trade", collections.Counter(co["trade"] for co, _ in jobs)),
              ("By Level", collections.Counter(j["level"] for _, j in jobs)),
              ("By City", collections.Counter(j["location"].split(",")[0].strip() or "Unknown" for _, j in jobs)),
              ("Top Hiring Companies", collections.Counter({co["company"]: sum(j.get("openings", 1) for j in co["jobs"]) for co in companies})),
              ("By Source", collections.Counter(j["source"] for _, j in jobs))]
    col = 1
    for title, cnt in blocks:
        for i, x in enumerate([title, "Open jobs"]):
            c = s.cell(3, col + i, x); c.font = hfont; c.fill = hfill
        for k, (name, v) in enumerate(cnt.most_common(15)):
            s.cell(4 + k, col, name); s.cell(4 + k, col + 1, v)
        s.column_dimensions[L(col)].width = 32; s.column_dimensions[L(col + 1)].width = 10; s.column_dimensions[L(col + 2)].width = 3
        col += 3

    h = wb.create_sheet("Contact History"); h["A1"] = "Contact History - one row per call or email"
    h["A1"].font = Font(bold=True, size=14, color=NAVY)
    for i, x in enumerate(["Date", "Company", "Phone / Email used", "Spoke With", "Called By", "Status", "Interested In", "Outcome / Notes", "Follow-up Date"], 1):
        c = h.cell(3, i, x); c.font = hfont; c.fill = hfill
    for i, wd in enumerate([13, 40, 24, 20, 13, 19, 18, 55, 14], 1):
        h.column_dimensions[L(i)].width = wd
    h.freeze_panes = "A4"
    dv(h, q(STATUS), ["F4:F1003"]); dv(h, q(callers), ["E4:E1003"]); dv(h, q(INTEREST), ["G4:G1003"]); dv(h, "=Lists!$A$2:$A$71", ["A4:A1003"], True)

    a = wb.create_sheet("All Employers"); a["A1"] = "All employers on this sheet"; a["A1"].font = Font(bold=True, size=14, color=NAVY)
    for i, x in enumerate(["Company", "Industry Type", "Trade", "Phone", "Email", "Website", "Other phones", "Other emails", "Open roles", "Times Contacted"], 1):
        c = a.cell(3, i, x); c.font = hfont; c.fill = hfill
    for k, co in enumerate(companies, 4):
        for i, v in enumerate([co["company"], co["industry"], co["trade"], co["phone"], co["email"], co["website"],
                               "; ".join(co.get("all_phones", [])), "; ".join(co.get("all_emails", [])), len(co["jobs"])], 1):
            a.cell(k, i, v)
        a.cell(k, 10, f"=COUNTIF('Contact History'!$B$4:$B$1003,A{k})")
    for i, wd in enumerate([40, 24, 16, 18, 30, 28, 34, 44, 10, 14], 1):
        a.column_dimensions[L(i)].width = wd
    a.freeze_panes = "A4"
    wb.save(path)
    return last
