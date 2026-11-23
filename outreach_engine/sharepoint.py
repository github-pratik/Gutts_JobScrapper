"""Save the weekly sheet into a SharePoint folder (Microsoft Graph, app-only sign-in).

Settings come from environment variables only (GitHub Secrets / Variables) - never from files:
  MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET   app registration that may write to the site
  SHAREPOINT_SITE_URL                            e.g. https://contoso.sharepoint.com/sites/Operations
  SHAREPOINT_FOLDER                              e.g. Employer Outreach/Weekly Call Sheets
If any is missing, SharePoint is skipped and the run still finishes (sheet stays a GitHub artifact).
"""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

GRAPH = "https://graph.microsoft.com/v1.0"
NEEDED = ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET", "SHAREPOINT_SITE_URL", "SHAREPOINT_FOLDER")
MASTER_PATH = "_engine/master.csv"  # run-to-run memory of every company already listed


@dataclass
class SharePoint:
    token: str
    site_id: str
    folder: str

    @property
    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _item(self, rel: str) -> str:
        return f"{GRAPH}/sites/{self.site_id}/drive/root:/{quote(self.folder.strip('/') + '/' + rel)}"

    def upload(self, local: Path, rel: str, overwrite: bool = False) -> str:
        """Upload one file. overwrite=False never replaces a file people may have typed in:
        a same-named file gets a numbered copy instead. Returns the file's web link."""
        mode = "replace" if overwrite else "rename"
        r = requests.put(f"{self._item(rel)}:/content?@microsoft.graph.conflictBehavior={mode}",
                         headers=self._auth, data=local.read_bytes(), timeout=120)
        r.raise_for_status()
        return r.json().get("webUrl", "")

    def download(self, rel: str, local: Path) -> bool:
        """Fetch a file if it exists. Returns False when it is not there yet."""
        r = requests.get(f"{self._item(rel)}:/content", headers=self._auth, timeout=120)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        local.write_bytes(r.content)
        return True


def connect(env: dict[str, str] | None = None) -> SharePoint | None:
    """Sign in and find the site. Returns None when SharePoint is not configured."""
    env = os.environ if env is None else env
    missing = [k for k in NEEDED if not env.get(k)]
    if missing:
        print(f"  SharePoint not configured (missing {', '.join(missing)}) - skipping upload")
        return None
    t = requests.post(f"https://login.microsoftonline.com/{env['MS_TENANT_ID']}/oauth2/v2.0/token", timeout=60,
                      data={"grant_type": "client_credentials", "client_id": env["MS_CLIENT_ID"],
                            "client_secret": env["MS_CLIENT_SECRET"], "scope": "https://graph.microsoft.com/.default"})
    t.raise_for_status()
    token = t.json()["access_token"]
    u = urlparse(env["SHAREPOINT_SITE_URL"])
    s = requests.get(f"{GRAPH}/sites/{u.netloc}:{u.path.rstrip('/')}", headers={"Authorization": f"Bearer {token}"}, timeout=60)
    s.raise_for_status()
    return SharePoint(token=token, site_id=s.json()["id"], folder=env["SHAREPOINT_FOLDER"])
