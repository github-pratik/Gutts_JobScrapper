import pathlib, sys, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import jobs

JOB_PAGE = '''<html><script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"HVAC Helper",
"datePosted":"2026-11-20T08:00:00","validThrough":"2026-12-20","description":"<p>We will train. EPA 608 a plus.</p>",
"hiringOrganization":{"@type":"Organization","name":"Acme HVAC","sameAs":"https://acmehvac.com"},
"jobLocation":{"@type":"Place","address":{"addressLocality":"Fairfax","addressRegion":"VA"}}}</script></html>'''
LIST_PAGE = '<a href="/jobs/view/111">a</a><a href="https://www.ihireconstruction.com/jobs/view/222">b</a><a href="/jobs/view/111">dup</a>'


class Pages:
    def __init__(self, pages): self.pages = pages
    def get(self, url): return self.pages.get(url)


class BoardTests(unittest.TestCase):
    def test_detect_board(self):
        d = jobs.detect_board
        self.assertEqual(d("https://boards.greenhouse.io/seatown/jobs/123"), ("greenhouse", "seatown"))
        self.assertEqual(d("https://boards.greenhouse.io/embed/job_board/js?for=acme"), ("greenhouse", "acme"))
        self.assertEqual(d("https://jobs.lever.co/lightedge/75e8/apply"), ("lever", "lightedge"))
        self.assertEqual(d("https://apply.workable.com/novo/j/ABC/"), ("workable", "novo"))
        self.assertEqual(d("https://jobs.ashbyhq.com/acme/1"), ("ashby", "acme"))
        self.assertEqual(d("https://jobs.smartrecruiters.com/AcmeCo/744"), ("smartrecruiters", "AcmeCo"))
        self.assertEqual(d("https://acme.recruitee.com/o/tech"), ("recruitee", "acme"))
        self.assertEqual(d("https://jll.wd1.myworkdayjobs.com/en-US/jllcareers/job/x"), ("workday", "jll|wd1|jllcareers"))
        self.assertIsNone(d("https://www.indeed.com/viewjob?jk=1")); self.assertIsNone(d("")); self.assertIsNone(d(None))

    def test_discover_boards_uses_apply_links(self):
        found = jobs.discover_boards([dict(company="Seatown", url="https://indeed.com/x", direct_url="https://boards.greenhouse.io/seatown/jobs/1"),
                                      dict(company="Other", url="https://indeed.com/y", direct_url="")])
        self.assertEqual(found, {("greenhouse", "seatown"): "Seatown"})

    def test_job_page_structured_data(self):
        j = jobs.from_job_page(JOB_PAGE, "https://x/1", "iHireConstruction")
        self.assertEqual((j["company"], j["title"], j["location"], j["posted"], j["website"]),
                         ("Acme HVAC", "HVAC Helper", "Fairfax, VA", "2026-11-20", "https://acmehvac.com"))
        self.assertIn("We will train", j["description"])
        self.assertIsNone(jobs.from_job_page("<html>nothing</html>", "u", "s"))
        self.assertIsNone(jobs.from_job_page('<script type="application/ld+json">{bad json</script>', "u", "s"))

    def test_ihire_reads_listing_then_job_pages(self):
        base = "https://www.ihireconstruction.com"
        f = Pages({"L": LIST_PAGE, base + "/jobs/view/111": JOB_PAGE, base + "/jobs/view/222": "<html></html>"})
        out = jobs.ihire(["L", "missing"], f)
        self.assertEqual([(j["company"], j["url"]) for j in out], [("Acme HVAC", base + "/jobs/view/111")])

    def test_board_jobs_outside_metro_are_dropped(self):
        import yaml
        cfg = yaml.safe_load(open(pathlib.Path(__file__).parent.parent / "config.yaml"))
        rows = [dict(company="ColonialWebb", title="Plumbing Helper", location="Richmond, VA", url="u1", source="Workday"),
                dict(company="ColonialWebb", title="Plumbing Helper", location="Sterling, VA", url="u2", source="Workday"),
                dict(company="Acme", title="Plumber Helper", location="Richmond, VA", url="u3", source="Indeed")]
        self.assertEqual([j["url"] for j in jobs.clean(rows, cfg)], ["u2", "u3"])   # radius sources are trusted as-is

    def test_board_readers(self):
        with mock.patch("jobs._get", return_value={"jobs": [{"title": "Tech", "location": "Reston, VA", "jobUrl": "u", "publishedAt": "2026-11-01T00:00"}]}):
            self.assertEqual(jobs.ashby("A", "a")[0]["posted"], "2026-11-01")
        with mock.patch("jobs._get", return_value={"content": [{"name": "Tech", "id": "9", "location": {"city": "Reston", "region": "va"}}]}):
            j = jobs.smartrecruiters("A", "Acme")[0]
            self.assertEqual((j["location"], j["url"]), ("Reston, VA", "https://jobs.smartrecruiters.com/Acme/9"))
        with mock.patch("jobs._get", side_effect=RuntimeError("blocked")):
            self.assertEqual(jobs.board_jobs("A", "lever", "a"), [])   # a board that fails never stops the run


if __name__ == "__main__":
    unittest.main()
