import datetime, sys, pathlib, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import contacts, quality, sheet, jobs, yaml, openpyxl

HOME = '''<html><body><a href="/contact-us">Contact</a><a href="/careers">Careers</a><a href="https://facebook.com/x">fb</a>
<script type="application/ld+json">{"@type":"LocalBusiness","telephone":"+1-703-555-0101","email":"mailto:office@acmehvac.com"}</script>
<p>Call 1-800-555-0199 today</p></body></html>'''
CONTACT = '''<html><body><a href="tel:7035550101">Call</a> <a href="mailto:careers@acmehvac.com?subject=Hi">jobs</a>
<a class="__cf_email__" data-cfemail="5a32281a3b39373f322c3b39743935370000">[email protected]</a>
<p>Jane Doe, Service Manager</p><p>President: John Smith</p><p>vendor@wixpress.com 703.555.0101</p></body></html>'''

def enc(e, k=0x5a):
    return f"{k:02x}" + "".join(f"{ord(c)^k:02x}" for c in e)

class Fake:
    pages = {"https://acmehvac.com": HOME, "https://acmehvac.com/contact-us": CONTACT.replace("5a32281a3b39373f322c3b39743935370000", enc("hr@acmehvac.com"))}
    def get(self, u): return self.pages.get(u)


class OutreachTests(unittest.TestCase):
    def test_parse_and_crawl(self):
        r = contacts.crawl_site("https://acmehvac.com", Fake())
        assert r["phone"] == "(703) 555-0101"            # local tel:/JSON-LD number beats the 800 number
        assert r["email"] == "hr@acmehvac.com"           # Cloudflare-hidden HR email decoded and ranked first
        assert "careers@acmehvac.com" in r["all_emails"] and not any("wixpress" in e for e in r["all_emails"])
        assert r["people"] == {"Jane Doe": "Service Manager", "John Smith": "President"}

    def test_quality(self):
        assert quality.level("HVAC Helper") == "Entry" and quality.level("Senior HVAC Technician") == "Senior"
        assert quality.level("Maintenance Technician") == "Mid" and quality.level("Plumbing Apprentice - Lead Program") == "Entry"
        assert quality.sector("Sabey Data Centers", "Operations Technician") == "Technology"
        assert quality.sector("KETTLER", "Maintenance Technician") == "Property Management"
        assert quality.trade("Plumber Helper") == "Plumbing"
        j = dict(source="Indeed", url="u", title="HVAC Helper")
        assert quality.check_live(j, lambda u: (404, "")) == "Expired"
        assert quality.check_live(j, lambda u: (200, "Sorry, this job has expired")) == "Expired"
        assert quality.check_live(j, lambda u: (200, "<h1>HVAC Helper</h1> apply now")) == "Live"
        assert quality.check_live(j, lambda u: (403, "")) == "Active"          # board listed it today but blocks the check
        assert quality.check_live(dict(source="Other", url="u", title="x"), lambda u: (403, "")) == "Unverified"
        d = dict(source="Indeed", url="u", direct_url="https://employer/apply", title="HVAC Helper")
        assert quality.check_live(d, lambda u: (200, "HVAC Helper - apply") if "employer" in u else (403, "")) == "Live"
        assert quality.level("Experienced HVAC Installer") == "Mid" and quality.level("Maintenance Mechanic Assistant Supervisor") == "Senior"
        assert quality.level("HVAC Technician", "No experience necessary, we will train") == "Entry"
        assert quality.requirements("EPA 608 required. 2+ years of HVAC experience. Valid driver's license.") == "2+ yrs experience; EPA 608; Driver's license"
        assert quality.requirements("") == "" and quality.requirements(None) == ""
        assert quality.sector("Cardinal Plumbing Heating & Air Inc.", "Residential Service Plumber") == "Services"
        assert contacts.name_matches("Metropolitan Washington Airports Authority", "www.mwaa.com")
        assert not contacts.name_matches("Fairland Plumbing and Heating", "www.carrier.com")
        assert jobs._pay("20", "24", "hourly") == "$20-24/hr" and jobs._pay("", "", "") == ""
        assert quality.check_live(dict(source="Lever", url="u", title="x"), None) == "Live"
        assert not quality.is_fresh("2026-10-01", datetime.date(2026, 11, 23), 14)

    def test_clean_and_sheet(self):
        tmp_path = pathlib.Path(tempfile.mkdtemp())
        cfg = yaml.safe_load(open(pathlib.Path(__file__).parent.parent / "config.yaml"))
        raw = [dict(company="Acme HVAC", title="HVAC Helper", location="Fairfax, VA", url="http://x/1", source="Indeed"),
               dict(company="Acme HVAC", title="HVAC Helper", location="Fairfax, VA", url="http://x/1", source="ZipRecruiter"),
               dict(company="Acme HVAC", title="Software Engineer", location="Fairfax, VA", url="http://x/2", source="Indeed"),
               dict(company="Far Co", title="Plumber", location="Austin, TX", url="http://x/3", source="Indeed"),
               dict(company="Aerotek", title="Plumber", location="Reston, VA", url="http://x/4", source="Indeed")]
        kept = jobs.clean(raw, cfg)
        assert [(j["company"], j["title"]) for j in kept] == [("Acme HVAC", "HVAC Helper")]
        co = [dict(company="Acme HVAC", industry="Services", trade="HVAC", phone="(703) 555-0101", email="", website="https://acmehvac.com",
                   contact_name="Jane Doe", contact_title="Service Manager", notes="",
                   jobs=[dict(title="HVAC Helper", level="Entry", location="Fairfax, VA", url="http://x/1", source="Indeed", live="Live", pay="$20-24/hr", requirements="EPA 608", posted="2026-11-20")])]
        p = tmp_path / "t.xlsx"; sheet.build(co, str(p), datetime.date(2026, 11, 23))
        wb = openpyxl.load_workbook(p); ws = wb["This Week - Call Sheet"]
        C = sheet.C; v = lambda row, h: ws.cell(row, C[h]).value
        assert v(5, "Company") == "Acme HVAC" and v(5, "Email") == "NOT FOUND" and v(5, "Contact Name") == "Jane Doe" and v(5, "Status") == "Not called"
        assert v(6, "Job Title") == "HVAC Helper" and v(6, "Posting") == "Live" and v(6, "Pay") == "$20-24/hr" and v(6, "Requirements") == "EPA 608"
        import run
        merged = run.collapse([dict(title="Plumber", location=f"{c}, VA", live="Active", posted="2026-11-2%d" % i, url=str(i)) for i, c in enumerate(["Fairfax", "Reston", "Vienna", "Herndon", "Fairfax"])])
        assert len(merged) == 1 and merged[0]["location"] == "Fairfax, Reston, Vienna +1 more (VA area)" and merged[0]["openings"] == 5
        assert set(wb.sheetnames) == {"Lists", "This Week - Call Sheet", "Where Hiring Is", "Contact History", "All Employers"}

if __name__ == '__main__':
    unittest.main()
