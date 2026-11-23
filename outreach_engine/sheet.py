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
HDR = ["#", "Company", "Industry Type", "Trade", "Phone", "Email", "Website", "Known Contacts / Notes", "Job Title", "Level",
       "Location", "Job Link", "Posting", "Status", "Date Called", "Called By", "Spoke With", "Outcome / Notes", "Follow-up Date"]
W = [5, 34, 22, 16, 18, 30, 24, 42, 40, 8, 18, 22, 12, 19, 13, 13, 18, 40, 14]


def build(companies, path, today=None, callers=("Christina", "Tony", "Pratik", "Other")):
    """companies: list of {company, industry, trade, phone, email, website, notes, jobs:[{title, level, location, url, source, live}]}"""
    today = today or datetime.date.today()
    thin = Side(style="thin", color="C9D1DB"); bd = Border(bottom=thin)
    hfont = Font(bold=True, color="FFFFFF", size=11); hfill = PatternFill("solid", fgColor=NAVY)
    inp = PatternFill("solid", fgColor="FFF9E5"); band = PatternFill("solid", fgColor="DCE6F1")
    red = PatternFill("solid", fgColor="FDE2E2")
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "This Week - Call Sheet"
    ws["A1"] = f"GUTTS Employer Call Sheet - Week of {today:%b %d, %Y}"; ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    ws["A2"] = ("Yellow cells are for the caller. Each company row has a Status dropdown. Posting: Live = checked today, "
                "Unverified = site blocked the check, click the link before calling. Phone/Email come from the company's own website.")
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
        vals = [n, co["company"], co["industry"], co["trade"], co["phone"] or MISSING, co["email"] or MISSING, co["website"],
                co.get("notes", ""), f"{len(co['jobs'])} open job(s)", "/".join(k for k in ("Entry", "Mid") if lv[k]),
                "", "", "", "Not called", "", "", "", "", ""]
        for i, v in enumerate(vals, 1):
            c = ws.cell(r, i, v); c.fill = band; c.font = Font(bold=True, size=12 if i == 2 else 11); c.border = bd
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for i in range(14, 20):
            ws.cell(r, i).fill = inp
        ws.cell(r, 15).number_format = "mm/dd/yyyy"; ws.cell(r, 19).number_format = "mm/dd/yyyy"
        for col in (5, 6):
            miss = ws.cell(r, col).value == MISSING
            ws.cell(r, col).font = Font(bold=True, size=11, color="C00000" if miss else "1B5E20")
            if miss:
                ws.cell(r, col).fill = red
        if co["website"]:
            ws.cell(r, 7).hyperlink = co["website"]; ws.cell(r, 7).font = Font(color="0563C1", underline="single")
        ws.row_dimensions[r].height = 44 if len(co.get("notes", "")) > 55 else 28
        for j in co["jobs"]:
            r += 1
            ws.cell(r, 9, j["title"]); ws.cell(r, 10, j["level"]); ws.cell(r, 11, j["location"])
            c = ws.cell(r, 12, f"Open posting ({j['source']})"); c.hyperlink = j["url"]; c.font = Font(color="0563C1", underline="single")
            c = ws.cell(r, 13, j["live"]); c.font = Font(color="1B5E20" if j["live"] == "Live" else "9C5700", bold=True)
            for i in range(1, 20):
                ws.cell(r, i).border = bd; ws.cell(r, i).alignment = Alignment(vertical="center", wrap_text=True)
            ws.row_dimensions[r].outlineLevel = 1; ws.row_dimensions[r].height = 20
    last = max(r, HR + 1)
    ws.sheet_properties.outlinePr.summaryBelow = False
    for i, wd in enumerate(W, 1):
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
    dv(ws, q(INDUSTRY), [ws.cell(rr, 3) for rr in rows]); dv(ws, q(STATUS), [ws.cell(rr, 14) for rr in rows])
    dv(ws, q(callers), [ws.cell(rr, 16) for rr in rows]); dv(ws, "=Lists!$A$2:$A$71", [ws.cell(rr, 15) for rr in rows], True)
    for txt, col in [("No answer", "E0E0E0"), ("Left voicemail", "FFE0B2"), ("Emailed", "BBDEFB"), ("Spoke - interested", "A5D6A7"),
                     ("Spoke - not hiring", "EF9A9A"), ("Call back later", "FFF59D"), ("Wrong number", "CE93D8"), ("Do not call", "BDBDBD")]:
        ws.conditional_formatting.add(f"N{HR+1}:N{last}", FormulaRule(formula=[f'$N{HR+1}="{txt}"'], fill=PatternFill("solid", bgColor=col, fgColor=col)))
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
              ("Top Hiring Companies", collections.Counter({co["company"]: len(co["jobs"]) for co in companies})),
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
    for i, x in enumerate(["Date", "Company", "Phone / Email used", "Spoke With", "Called By", "Status", "Outcome / Notes", "Follow-up Date", "Week Of"], 1):
        c = h.cell(3, i, x); c.font = hfont; c.fill = hfill
    for i, wd in enumerate([13, 40, 24, 20, 13, 19, 55, 14, 13], 1):
        h.column_dimensions[L(i)].width = wd
    h.freeze_panes = "A4"
    dv(h, q(STATUS), ["F4:F1003"]); dv(h, q(callers), ["E4:E1003"]); dv(h, "=Lists!$A$2:$A$71", ["A4:A1003"], True)

    a = wb.create_sheet("All Employers"); a["A1"] = "All employers on this sheet"; a["A1"].font = Font(bold=True, size=14, color=NAVY)
    for i, x in enumerate(["Company", "Industry Type", "Trade", "Phone", "Email", "Website", "Other phones", "Other emails", "Open jobs", "Times Contacted"], 1):
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
