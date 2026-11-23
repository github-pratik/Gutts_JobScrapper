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
        assert quality.check_live(j, lambda u: (403, "")) == "Unverified"
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
                   notes="Jane Doe (Service Manager)", jobs=[dict(title="HVAC Helper", level="Entry", location="Fairfax, VA", url="http://x/1", source="Indeed", live="Live")])]
        p = tmp_path / "t.xlsx"; sheet.build(co, str(p), datetime.date(2026, 11, 23))
        wb = openpyxl.load_workbook(p); ws = wb["This Week - Call Sheet"]
        assert ws["B5"].value == "Acme HVAC" and ws["F5"].value == "NOT FOUND" and ws["I6"].value == "HVAC Helper" and ws["M6"].value == "Live"
        assert set(wb.sheetnames) == {"Lists", "This Week - Call Sheet", "Where Hiring Is", "Contact History", "All Employers"}

if __name__ == '__main__':
    unittest.main()
