import pathlib, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import requests
import sharepoint

ENV = dict(MS_TENANT_ID="t", MS_CLIENT_ID="c", MS_CLIENT_SECRET="s",
           SHAREPOINT_SITE_URL="https://x.sharepoint.com/sites/Ops/", SHAREPOINT_FOLDER="/Employer Outreach/Weekly/")


def resp(status=200, payload=None, content=b""):
    r = mock.Mock(status_code=status, content=content)
    r.json.return_value = payload or {}
    r.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(str(status))
    return r


class SharePointTests(unittest.TestCase):
    def test_not_configured_returns_none(self):
        self.assertIsNone(sharepoint.connect({}))
        self.assertIsNone(sharepoint.connect({**ENV, "MS_CLIENT_SECRET": ""}))

    def test_connect_resolves_site(self):
        with mock.patch("sharepoint.requests.post", return_value=resp(payload={"access_token": "tok"})) as p, \
             mock.patch("sharepoint.requests.get", return_value=resp(payload={"id": "site123"})) as g:
            sp = sharepoint.connect(ENV)
        self.assertEqual((sp.token, sp.site_id), ("tok", "site123"))
        self.assertIn("/t/oauth2/v2.0/token", p.call_args[0][0])
        self.assertEqual(g.call_args[0][0], "https://graph.microsoft.com/v1.0/sites/x.sharepoint.com:/sites/Ops")

    def test_bad_login_raises(self):
        with mock.patch("sharepoint.requests.post", return_value=resp(401)):
            with self.assertRaises(requests.HTTPError):
                sharepoint.connect(ENV)

    def test_upload_never_overwrites_by_default(self):
        sp = sharepoint.SharePoint("tok", "site123", ENV["SHAREPOINT_FOLDER"])
        f = pathlib.Path(tempfile.mkdtemp()) / "a b.xlsx"; f.write_bytes(b"x")
        with mock.patch("sharepoint.requests.put", return_value=resp(payload={"webUrl": "https://link"})) as p:
            self.assertEqual(sp.upload(f, f.name), "https://link")
            self.assertIn("root:/Employer%20Outreach/Weekly/a%20b.xlsx:/content?@microsoft.graph.conflictBehavior=rename", p.call_args[0][0])
            sp.upload(f, sharepoint.MASTER_PATH, overwrite=True)
            self.assertTrue(p.call_args[0][0].endswith("_engine/master.csv:/content?@microsoft.graph.conflictBehavior=replace"))

    def test_download_missing_and_present(self):
        sp = sharepoint.SharePoint("tok", "site123", "F")
        out = pathlib.Path(tempfile.mkdtemp()) / "m.csv"
        with mock.patch("sharepoint.requests.get", return_value=resp(404)):
            self.assertFalse(sp.download("m.csv", out)); self.assertFalse(out.exists())
        with mock.patch("sharepoint.requests.get", return_value=resp(content=b"key\n")):
            self.assertTrue(sp.download("m.csv", out)); self.assertEqual(out.read_bytes(), b"key\n")


if __name__ == "__main__":
    unittest.main()
