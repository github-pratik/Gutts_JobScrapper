/* App.jsx — Focused single-page GUTTS Job Runner (CRM-style) */

const G = window.GUTTS;

const SITE_LABELS = Object.fromEntries(G.SITE_CHOICES.map(([l, v]) => [v, l]));
const SITE_VALUES = G.SITE_CHOICES.map(([, v]) => v);
const MANUAL_FILTER_SITES = ["indeed", "zip_recruiter", "linkedin"];

/* ── Mock job rows (realistic GUTTS data) ── */
const MOCK_JOBS = [
  { job_title:"Plumbing Helper",              company:"Roto-Rooter Services",       source_site:"indeed",        posted_date:"2026-04-24", location:"Fairfax, VA",          work_type:"On-site",  salary:"USD 18 - 22 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc001" },
  { job_title:"HVAC Apprentice",              company:"Comfort Systems USA",         source_site:"linkedin",      posted_date:"2026-04-24", location:"Arlington, VA",        work_type:"On-site",  salary:"USD 20 - 24 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/001" },
  { job_title:"Plumbing Apprentice",          company:"Michael & Son Services",      source_site:"zip_recruiter", posted_date:"2026-04-23", location:"Alexandria, VA",       work_type:"On-site",  salary:"USD 19 - 23 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/001" },
  { job_title:"HVAC Helper / Installer",      company:"ARS / Rescue Rooter",         source_site:"indeed",        posted_date:"2026-04-23", location:"Manassas, VA",         work_type:"On-site",  salary:"USD 17 - 21 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc002" },
  { job_title:"Refrigeration Technician",     company:"Centrica Business Solutions", source_site:"linkedin",      posted_date:"2026-04-23", location:"Tysons, VA",           work_type:"On-site",  salary:"USD 25 - 32 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/002" },
  { job_title:"Plumber I – Entry Level",      company:"Foulger-Pratt Contracting",  source_site:"indeed",        posted_date:"2026-04-22", location:"Rockville, MD",        work_type:"On-site",  salary:"USD 22 - 27 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc003" },
  { job_title:"Building Engineer Helper",     company:"JBG SMITH Properties",       source_site:"linkedin",      posted_date:"2026-04-22", location:"Bethesda, MD",         work_type:"On-site",  salary:"USD 21 - 26 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/003" },
  { job_title:"HVAC Maintenance Tech",        company:"Cushman & Wakefield",        source_site:"zip_recruiter", posted_date:"2026-04-22", location:"Washington, DC",       work_type:"On-site",  salary:"USD 24 - 30 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/002" },
  { job_title:"Pipe Layer / Plumbing Helper", company:"Rand Construction Corp",     source_site:"indeed",        posted_date:"2026-04-21", location:"Chantilly, VA",        work_type:"On-site",  salary:"USD 18 - 22 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc004" },
  { job_title:"Service Plumber – Trainee",   company:"Service Experts HVAC",       source_site:"linkedin",      posted_date:"2026-04-21", location:"Sterling, VA",         work_type:"On-site",  salary:"USD 20 - 25 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/004" },
  { job_title:"Commercial HVAC Apprentice",   company:"Shapiro & Duncan",           source_site:"indeed",        posted_date:"2026-04-21", location:"Gaithersburg, MD",     work_type:"On-site",  salary:"",                    link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc005" },
  { job_title:"Plumbing Helper – New Const.", company:"Turner Construction",        source_site:"zip_recruiter", posted_date:"2026-04-20", location:"Falls Church, VA",     work_type:"On-site",  salary:"USD 19 - 24 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/003" },
  { job_title:"HVAC Tech – Data Center",      company:"CBRE Group",                 source_site:"linkedin",      posted_date:"2026-04-20", location:"Ashburn, VA",          work_type:"On-site",  salary:"USD 28 - 35 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/005" },
  { job_title:"Maintenance Technician",       company:"AvalonBay Communities",      source_site:"indeed",        posted_date:"2026-04-20", location:"Reston, VA",           work_type:"On-site",  salary:"USD 22 - 28 / hour",  link_status:"unknown", job_url:"https://www.indeed.com/viewjob?jk=abc006" },
  { job_title:"Plumbing Apprentice",          company:"Enviro Star Inc",            source_site:"glassdoor",     posted_date:"2026-04-19", location:"Herndon, VA",          work_type:"On-site",  salary:"USD 18 - 23 / hour",  link_status:"live",    job_url:"https://www.glassdoor.com/job/001" },
  { job_title:"HVAC Helper / Trainee",        company:"Winfield Mechanical",        source_site:"indeed",        posted_date:"2026-04-19", location:"Woodbridge, VA",       work_type:"On-site",  salary:"USD 17 - 20 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc007" },
  { job_title:"Facilities Engineer – Entry",  company:"Amazon Data Services",       source_site:"linkedin",      posted_date:"2026-04-19", location:"Dulles, VA",           work_type:"On-site",  salary:"USD 30 - 38 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/006" },
  { job_title:"Plumber Helper",               company:"Heidler Plumbing",           source_site:"zip_recruiter", posted_date:"2026-04-18", location:"Annapolis, MD",        work_type:"On-site",  salary:"USD 17 - 21 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/004" },
  { job_title:"HVAC Apprentice – Res/Comm",   company:"F.H. Furr",                  source_site:"indeed",        posted_date:"2026-04-18", location:"Fairfax, VA",          work_type:"On-site",  salary:"USD 19 - 23 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc008" },
  { job_title:"Building Engineer Apprentice", company:"Equity Residential",         source_site:"linkedin",      posted_date:"2026-04-18", location:"Arlington, VA",        work_type:"On-site",  salary:"USD 23 - 29 / hour",  link_status:"unknown", job_url:"https://www.linkedin.com/jobs/view/007" },
  { job_title:"Plumbing Helper – Immediate",  company:"Donaldson Plumbing",         source_site:"indeed",        posted_date:"2026-04-17", location:"Leesburg, VA",         work_type:"On-site",  salary:"USD 16 - 20 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc009" },
  { job_title:"HVAC Tech Trainee",            company:"Carrier Corporation",        source_site:"zip_recruiter", posted_date:"2026-04-17", location:"Rockville, MD",        work_type:"On-site",  salary:"USD 20 - 26 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/005" },
  { job_title:"Service Plumber – Entry",      company:"Roto-Rooter Services",       source_site:"indeed",        posted_date:"2026-04-17", location:"Bowie, MD",            work_type:"On-site",  salary:"USD 18 - 22 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc010" },
  { job_title:"Refrigeration Helper",         company:"Sysco Corporation",          source_site:"linkedin",      posted_date:"2026-04-16", location:"Landover, MD",         work_type:"On-site",  salary:"",                    link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/008" },
  { job_title:"Plumbing Apprentice – Union",  company:"UNITE HERE Local 25",        source_site:"indeed",        posted_date:"2026-04-16", location:"Washington, DC",       work_type:"On-site",  salary:"USD 24 - 30 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc011" },
  { job_title:"HVAC Install Helper",          company:"Comfort Systems USA",        source_site:"zip_recruiter", posted_date:"2026-04-16", location:"Fredericksburg, VA",   work_type:"On-site",  salary:"USD 17 - 22 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/006" },
  { job_title:"Mech. Maintenance Tech I",     company:"Marriott International",     source_site:"indeed",        posted_date:"2026-04-15", location:"Bethesda, MD",         work_type:"On-site",  salary:"USD 22 - 27 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc012" },
  { job_title:"Plumbing Helper – Training",   company:"Benjamin Franklin Plumbing", source_site:"linkedin",      posted_date:"2026-04-15", location:"Fairfax, VA",          work_type:"On-site",  salary:"USD 17 - 21 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/009" },
  { job_title:"HVAC Apprentice – Comm.",      company:"Therma-Stor LLC",            source_site:"glassdoor",     posted_date:"2026-04-15", location:"Sterling, VA",         work_type:"On-site",  salary:"USD 19 - 25 / hour",  link_status:"live",    job_url:"https://www.glassdoor.com/job/002" },
  { job_title:"Critical Facilities Tech",     company:"Equinix",                    source_site:"linkedin",      posted_date:"2026-04-14", location:"Ashburn, VA",          work_type:"On-site",  salary:"USD 32 - 42 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/010" },
  { job_title:"Plumbing Helper / Trainee",    company:"Len The Plumber",            source_site:"indeed",        posted_date:"2026-04-14", location:"Laurel, MD",           work_type:"On-site",  salary:"USD 17 - 21 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc013" },
  { job_title:"HVAC Apprentice – Data Ctr",   company:"Microsoft Corporation",      source_site:"linkedin",      posted_date:"2026-04-14", location:"Boydton, VA",          work_type:"On-site",  salary:"USD 28 - 36 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/011" },
  { job_title:"Pipe Fitter Helper",           company:"Mechanical Inc.",            source_site:"zip_recruiter", posted_date:"2026-04-13", location:"Manassas, VA",         work_type:"On-site",  salary:"USD 19 - 23 / hour",  link_status:"unknown", job_url:"https://www.ziprecruiter.com/jobs/007" },
  { job_title:"Building Maint. Tech",         company:"Douglas Development Corp",   source_site:"indeed",        posted_date:"2026-04-13", location:"Washington, DC",       work_type:"On-site",  salary:"USD 21 - 26 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc014" },
  { job_title:"HVAC Helper – Willing Train",  company:"Sila Services LLC",          source_site:"zip_recruiter", posted_date:"2026-04-12", location:"Chantilly, VA",        work_type:"On-site",  salary:"USD 17 - 21 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/008" },
  { job_title:"Plumbing Apprentice I",        company:"Kinetics Systems Inc",       source_site:"linkedin",      posted_date:"2026-04-12", location:"Herndon, VA",          work_type:"On-site",  salary:"USD 21 - 27 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/012" },
  { job_title:"Maintenance Tech – HVAC/Plbg", company:"Greystar Real Estate",      source_site:"indeed",        posted_date:"2026-04-12", location:"Reston, VA",           work_type:"On-site",  salary:"USD 22 - 28 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc015" },
  { job_title:"HVAC Install Apprentice",      company:"Daikin Applied Americas",   source_site:"glassdoor",     posted_date:"2026-04-11", location:"Falls Church, VA",     work_type:"On-site",  salary:"",                    link_status:"live",    job_url:"https://www.glassdoor.com/job/003" },
  { job_title:"Plumbing Helper – No Exp Req", company:"RooterMan Plumbing",        source_site:"indeed",        posted_date:"2026-04-11", location:"Springfield, VA",      work_type:"On-site",  salary:"USD 16 - 19 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc016" },
  { job_title:"HVAC Technician – Entry",      company:"JLL (Jones Lang LaSalle)",  source_site:"linkedin",      posted_date:"2026-04-11", location:"McLean, VA",           work_type:"On-site",  salary:"USD 24 - 30 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/013" },
  { job_title:"Plumbing Trainee",             company:"John C Flood",              source_site:"zip_recruiter", posted_date:"2026-04-10", location:"Alexandria, VA",       work_type:"On-site",  salary:"USD 17 - 22 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/009" },
  { job_title:"HVAC Helper – Comm. Systems",  company:"Southland Industries",      source_site:"indeed",        posted_date:"2026-04-10", location:"Dulles, VA",           work_type:"On-site",  salary:"USD 19 - 24 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc017" },
  { job_title:"Building Eng. Apprentice",     company:"Transwestern Real Estate",  source_site:"linkedin",      posted_date:"2026-04-10", location:"Washington, DC",       work_type:"On-site",  salary:"USD 22 - 28 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/014" },
  { job_title:"Plumbing Helper – Comm.",      company:"Balfour Beatty",            source_site:"zip_recruiter", posted_date:"2026-04-09", location:"Fairfax, VA",          work_type:"On-site",  salary:"USD 20 - 25 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/010" },
  { job_title:"HVAC Apprentice – Prop Mgmt",  company:"UDR Apartment Communities", source_site:"indeed",        posted_date:"2026-04-09", location:"Rockville, MD",        work_type:"On-site",  salary:"USD 20 - 26 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc018" },
  { job_title:"Mech. Systems Apprentice",     company:"Clark Construction Group",  source_site:"linkedin",      posted_date:"2026-04-09", location:"Bethesda, MD",         work_type:"On-site",  salary:"USD 22 - 27 / hour",  link_status:"unknown", job_url:"https://www.linkedin.com/jobs/view/015" },
  { job_title:"Plumber Helper – Immediate",   company:"Roto-Rooter Services",      source_site:"indeed",        posted_date:"2026-04-08", location:"Gaithersburg, MD",     work_type:"On-site",  salary:"USD 17 - 21 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc019" },
  { job_title:"HVAC Trainee – No Exp Needed", company:"ARS / Rescue Rooter",      source_site:"zip_recruiter", posted_date:"2026-04-08", location:"Leesburg, VA",         work_type:"On-site",  salary:"USD 17 - 20 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/011" },
  { job_title:"Refrigeration Tech Apprentice",company:"Performance Food Group",    source_site:"linkedin",      posted_date:"2026-04-08", location:"Landover, MD",         work_type:"On-site",  salary:"USD 22 - 28 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/016" },
  { job_title:"Plumbing Helper – Data Ctr",   company:"Iron Mountain",             source_site:"indeed",        posted_date:"2026-04-07", location:"Manassas, VA",         work_type:"On-site",  salary:"USD 19 - 24 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc020" },
  { job_title:"HVAC Apprentice – Union",      company:"UA Local 602",              source_site:"linkedin",      posted_date:"2026-04-07", location:"Washington, DC",       work_type:"On-site",  salary:"USD 25 - 35 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/017" },
  { job_title:"Plumbing Apprentice – Res.",   company:"Michael & Son Services",    source_site:"zip_recruiter", posted_date:"2026-04-07", location:"Alexandria, VA",       work_type:"On-site",  salary:"USD 18 - 22 / hour",  link_status:"live",    job_url:"https://www.ziprecruiter.com/jobs/012" },
  { job_title:"HVAC Helper – Property Mgmt",  company:"AIMCO",                     source_site:"indeed",        posted_date:"2026-04-06", location:"Arlington, VA",        work_type:"On-site",  salary:"USD 20 - 24 / hour",  link_status:"live",    job_url:"https://www.indeed.com/viewjob?jk=abc021" },
  { job_title:"Mechanical Apprentice",        company:"Forrester Construction",    source_site:"linkedin",      posted_date:"2026-04-06", location:"Rockville, MD",        work_type:"On-site",  salary:"USD 21 - 26 / hour",  link_status:"live",    job_url:"https://www.linkedin.com/jobs/view/018" },
];

const SITE_COLORS = {
  indeed:       { bg: '#E8F1FF', color: '#1A56CC' },
  linkedin:     { bg: '#E7F3FC', color: '#0A66C2' },
  zip_recruiter:{ bg: '#EDF7EE', color: '#1A7F37' },
  glassdoor:    { bg: '#FFF0E6', color: '#CC5A00' },
  google:       { bg: '#FDE8E8', color: '#B01212' },
};

/* ── Results Table component ── */
function ResultsTable({ jobs }) {
  const [search, setSearch] = useState('');
  const [siteFilter, setSiteFilter] = useState('all');
  const [sortCol, setSortCol] = useState('posted_date');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 12;

  const sites = useMemo(() => ['all', ...new Set(jobs.map(j => j.source_site))], [jobs]);

  const filtered = useMemo(() => {
    let rows = jobs;
    if (siteFilter !== 'all') rows = rows.filter(j => j.source_site === siteFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(j =>
        j.job_title.toLowerCase().includes(q) ||
        j.company.toLowerCase().includes(q) ||
        j.location.toLowerCase().includes(q)
      );
    }
    rows = [...rows].sort((a, b) => {
      const va = a[sortCol] || '', vb = b[sortCol] || '';
      return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    });
    return rows;
  }, [jobs, search, siteFilter, sortCol, sortDir]);

  const pageCount = Math.ceil(filtered.length / PAGE_SIZE);
  const pageRows  = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const sort = (col) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('asc'); }
    setPage(0);
  };
  const arrow = (col) => sortCol === col ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';

  const liveCount    = jobs.filter(j => j.link_status === 'live').length;
  const unknownCount = jobs.filter(j => j.link_status === 'unknown').length;

  return (
    <div className="resultsTable">
      {/* Table toolbar */}
      <div className="rtToolbar">
        <div className="rtStats">
          <span className="rtStatChip live">✓ {liveCount} live</span>
          {unknownCount > 0 && <span className="rtStatChip unknown">? {unknownCount} unverified</span>}
          <span className="rtStatChip total">{filtered.length} shown</span>
        </div>
        <div className="rtControls">
          <div className="rtSearch">
            <span className="rtSearchIcon">⌕</span>
            <input className="rtSearchInput" placeholder="Search jobs, companies, locations…"
              value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} />
            {search && <button className="rtSearchClear" onClick={() => { setSearch(''); setPage(0); }}>×</button>}
          </div>
          <select className="crmSelect" style={{ width: 'auto', fontSize: 13, height: 36 }}
            value={siteFilter} onChange={e => { setSiteFilter(e.target.value); setPage(0); }}>
            {sites.map(s => <option key={s} value={s}>{s === 'all' ? 'All boards' : SITE_LABELS[s] || s}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="rtScroll">
        <table className="rtTable">
          <thead>
            <tr>
              <th className="rtTh sortable" onClick={() => sort('job_title')}>Job Title{arrow('job_title')}</th>
              <th className="rtTh sortable" onClick={() => sort('company')}>Company{arrow('company')}</th>
              <th className="rtTh">Board</th>
              <th className="rtTh sortable" onClick={() => sort('posted_date')}>Posted{arrow('posted_date')}</th>
              <th className="rtTh sortable" onClick={() => sort('location')}>Location{arrow('location')}</th>
              <th className="rtTh">Salary</th>
              <th className="rtTh">Status</th>
              <th className="rtTh">Link</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr><td colSpan={8} className="rtEmpty">No jobs match your search.</td></tr>
            ) : pageRows.map((job, i) => {
              const sc = SITE_COLORS[job.source_site] || { bg: '#F0F2F5', color: '#525861' };
              return (
                <tr key={i} className="rtRow">
                  <td className="rtTd rtTitle">{job.job_title}</td>
                  <td className="rtTd rtCompany">{job.company}</td>
                  <td className="rtTd">
                    <span className="rtSiteChip" style={{ background: sc.bg, color: sc.color }}>
                      {SITE_LABELS[job.source_site] || job.source_site}
                    </span>
                  </td>
                  <td className="rtTd rtDate">{job.posted_date.slice(5)}</td>
                  <td className="rtTd rtLoc">{job.location}</td>
                  <td className="rtTd rtSalary">{job.salary || <span className="rtNone">—</span>}</td>
                  <td className="rtTd">
                    {job.link_status === 'live'
                      ? <span className="crmBadge ok">✓ live</span>
                      : <span className="crmBadge warn">? unverified</span>}
                  </td>
                  <td className="rtTd rtLink">
                    <a href={job.job_url} target="_blank" rel="noopener noreferrer"
                      className="rtLinkBtn" title="Open job posting">↗</a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pageCount > 1 && (
        <div className="rtPager">
          <button className="rtPageBtn" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span className="rtPageInfo">Page {page + 1} of {pageCount} · {filtered.length} jobs</span>
          <button className="rtPageBtn" disabled={page >= pageCount - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}

/* ── Main App ── */
function App() {
  const { tweaks, setTweak } = useTweaks(window.TWEAK_DEFAULTS);
  const [showTweaks, setShowTweaks] = useState(false);

  const [searchPreset, setSearchPreset] = useState("Fairfax Entry - Combined");
  const [paramPreset,  setParamPreset]  = useState("Fairfax Entry - Standard");
  const [location,  setLocation]  = useState("Fairfax, VA");
  const [distance,  setDistance]  = useState(50);
  const [days,      setDays]      = useState(14);
  const [results,   setResults]   = useState(60);
  const [country,   setCountry]   = useState("USA");
  const [secondPass,  setSecondPass]  = useState(true);
  const [strictEntry, setStrictEntry] = useState(true);
  const [employmentTarget, setEmploymentTarget] = useState("All targets");
  const [selectedSites, setSelectedSites] = useState(MANUAL_FILTER_SITES);
  const [primaryKw, setPrimaryKw] = useState(G.FAIRFAX_COMBINED_PRIMARY);
  const [secondKw,  setSecondKw]  = useState(G.FAIRFAX_COMBINED_SECONDARY);
  const [includeKw, setIncludeKw] = useState("");
  const [excludeKw, setExcludeKw] = useState("");
  const [mustHave,  setMustHave]  = useState("");
  const [expMin, setExpMin] = useState("Any");
  const [expMax, setExpMax] = useState("Any");
  const [workModes, setWorkModes]     = useState([]);
  const [includeUnknown, setIncludeUnknown] = useState(false);
  const [outputDir,  setOutputDir]  = useState("./data/output");
  const [outputFile, setOutputFile] = useState("");
  const [linkedinFetch, setLinkedinFetch] = useState(false);
  const [activeTab, setActiveTab]   = useState('search');

  const [running,    setRunning]    = useState(false);
  const [logs,       setLogs]       = useState([]);
  const [lastResult, setLastResult] = useState(null);
  const [jobRows,    setJobRows]    = useState(null);
  const [rightTab,   setRightTab]   = useState('console'); // 'console' | 'results'

  useEffect(() => { setDistance(tweaks.defaultDistance); }, [tweaks.defaultDistance]);

  const applySearchPreset = () => {
    if (searchPreset === "GUTTS default") {
      setPrimaryKw('plumbing OR hvac apprentice'); setSecondKw('helper OR trainee');
      setStrictEntry(false); setSelectedSites(SITE_VALUES); setDistance(100);
    } else if (searchPreset.startsWith("Fairfax")) {
      setPrimaryKw(G.FAIRFAX_COMBINED_PRIMARY); setSecondKw(G.FAIRFAX_COMBINED_SECONDARY);
      setLocation("Fairfax, VA"); setDistance(50); setDays(14); setResults(60);
      setSecondPass(true); setStrictEntry(true); setSelectedSites(MANUAL_FILTER_SITES);
    }
  };

  const applyParamPreset = () => {
    if (paramPreset === "Fairfax Entry - Standard") {
      setLocation("Fairfax, VA"); setDistance(50); setDays(14); setResults(60);
      setSecondPass(true); setStrictEntry(true); setSelectedSites(MANUAL_FILTER_SITES);
    } else if (paramPreset === "Fairfax Entry - Deep") {
      setLocation("Fairfax, VA"); setDistance(50); setDays(30); setResults(100);
      setSelectedSites(MANUAL_FILTER_SITES);
    } else if (paramPreset === "DMV Entry - Broad") {
      setLocation("Washington, DC"); setDistance(75); setDays(21); setResults(80);
      setSelectedSites(SITE_VALUES);
    }
  };

  const effective = useMemo(() => {
    const target = G.TARGET_TERMS[employmentTarget] || '';
    const strict = strictEntry ? ` ${G.STRICT_ENTRY}` : '';
    const incl = includeKw.split(',').map(s => s.trim()).filter(Boolean)
      .map(t => t.includes(' ') ? `"${t}"` : t).join(' ');
    const excl = excludeKw.split(',').map(s => s.trim()).filter(Boolean)
      .map(t => `-${t.includes(' ') ? `"${t}"` : t}`).join(' ');
    const tail = [target, strict, incl, excl].filter(Boolean).join(' ');
    return {
      primary: `${primaryKw} ${tail}`.trim(),
      second:  `${secondKw}  ${tail}`.trim(),
    };
  }, [primaryKw, secondKw, employmentTarget, strictEntry, includeKw, excludeKw]);

  const hints = [];
  if (effective.primary.length < 8) hints.push("Primary query looks too short.");
  if (results > 200) hints.push("Large result limits may increase duplicates.");

  const now = () => new Date().toLocaleTimeString('en-US', { hour12: false });

  const runScrape = () => {
    if (!selectedSites.length) return;
    setRunning(true); setLastResult(null); setLogs([]); setJobRows(null);
    setRightTab('console');
    const ts = new Date().toISOString().slice(0,19).replace('T','_').replace(/:/g,'');
    const filename = `gutts_jobs_${ts}.csv`;
    const rowCount = MOCK_JOBS.length;
    const steps = [
      { ts: now(), msg: `Output file → ${outputDir}/${filename}` },
      { ts: now(), msg: `sites=${selectedSites.join(', ')}, location='${location}' (+${distance}mi), results_wanted=${results}`, cls: 'ts' },
      { ts: now(), msg: `Pass 1/${secondPass?2:1}: scraping (${effective.primary.slice(0,60)}…)`, cls: 'pass' },
      { ts: now(), msg: `Pass 1 complete — 89 raw results`, cls: 'ok' },
      ...(secondPass ? [{ ts: now(), msg: 'Pass 2/2: second-pass merge running…', cls: 'pass' }] : []),
      { ts: now(), msg: 'Recency filter kept 71/89 rows' },
      { ts: now(), msg: 'Validating 71 links via HEAD/GET…' },
      { ts: now(), msg: 'Link-status filter kept 54/71 rows', cls: 'ok' },
      { ts: now(), msg: `Saved ${rowCount} curated rows to ${outputDir}/${filename}`, cls: 'ok' },
    ];
    const out = [];
    steps.forEach((s, i) => setTimeout(() => {
      out.push(s); setLogs([...out]);
      if (i === steps.length - 1) {
        setRunning(false);
        setLastResult({ rows: rowCount, path: `${outputDir}/${filename}` });
        setJobRows(MOCK_JOBS);
        setTimeout(() => setRightTab('results'), 400);
      }
    }, 380 * (i + 1)));
  };

  const accentStyle = { '--accent': tweaks.accentColor, '--accent-h': tweaks.accentColor, '--accent-d': tweaks.accentColor };

  return (
    <div className="pageWrap" style={accentStyle}>

      {/* ── TOP BAR ── */}
      <header className="topbar">
        <div className="topbar-brand">
          <div className="tbMark">G</div>
          <span className="tbName">GUTTS <span className="tbSub">Job Runner</span></span>
        </div>
        <div className="topbar-meta">
          <span className="tbChip">{selectedSites.length} board{selectedSites.length === 1 ? '' : 's'}</span>
          <span className="tbChip">{location} · {distance}mi</span>
          <span className="tbChip">{days}d window</span>
        </div>
        <div className="topbar-actions">
          <Btn kind="secondary" onClick={() => setShowTweaks(t => !t)}>⚙ Tweaks</Btn>
          <Btn kind="primary" disabled={running || !selectedSites.length} onClick={runScrape}>
            {running ? <><span className="crmSpinner" /> Running…</> : '▶ Run scrape'}
          </Btn>
        </div>
      </header>

      {/* ── BODY ── */}
      <div className="bodyGrid">

        {/* LEFT config panel */}
        <div className="configPanel">
          <div className="crmTabs">
            {['search','filters','advanced','preview'].map(t => (
              <button key={t} className={`crmTab${activeTab === t ? ' active' : ''}`} onClick={() => setActiveTab(t)}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
                {t === 'preview' && <span className="tabBadge">⟳</span>}
              </button>
            ))}
          </div>

          {activeTab === 'search' && (
            <div className="tabBody">
              <div className="sectionLabel">Presets</div>
              <div className="crmRow row-2" style={{ marginBottom: 8 }}>
                <Field label="Search preset">
                  <Select value={searchPreset} onChange={setSearchPreset}
                    options={["GUTTS default","Fairfax Entry - Combined","Fairfax Entry - Plumbing","Fairfax Entry - HVAC","Custom"]} />
                </Field>
                <Field label="Parameters preset">
                  <Select value={paramPreset} onChange={setParamPreset}
                    options={["Custom","Fairfax Entry - Standard","Fairfax Entry - Deep","DMV Entry - Broad"]} />
                </Field>
              </div>
              <div style={{ display:'flex', gap:8, marginBottom:16 }}>
                <Btn kind="secondary" onClick={applySearchPreset}>Apply search preset</Btn>
                <Btn kind="secondary" onClick={applyParamPreset}>Apply param preset</Btn>
              </div>

              <div className="sectionLabel">Location &amp; scope</div>
              <div className="crmRow row-2" style={{ marginBottom: 8 }}>
                <Field label="Location"><Input value={location} onChange={e => setLocation(e.target.value)} placeholder="City, State" /></Field>
                <Field label="Radius"><NumberInput value={distance} onChange={setDistance} min={1} max={500} suffix="mi" /></Field>
              </div>
              <div className="crmRow row-3" style={{ marginBottom: 16 }}>
                <Field label="Posted within"><NumberInput value={days} onChange={setDays} min={1} max={90} suffix="d" /></Field>
                <Field label="Results/board"><NumberInput value={results} onChange={setResults} min={1} max={1000} step={5} /></Field>
                <Field label="Country"><Select value={country} onChange={setCountry} options={G.COUNTRY_CHOICES} /></Field>
              </div>

              <div className="sectionLabel">Job boards</div>
              <div className="crmPills" style={{ marginBottom: 12 }}>
                {G.SITE_CHOICES.map(([label, value]) => {
                  const on = selectedSites.includes(value);
                  return (
                    <button key={value} type="button" className={`crmPill${on ? ' on' : ''}`}
                      onClick={() => setSelectedSites(on ? selectedSites.filter(x => x !== value) : [...selectedSites, value])}>
                      <span className="dot"></span>{label}
                    </button>
                  );
                })}
              </div>
              {!selectedSites.length && <Alert kind="warning">Select at least one board.</Alert>}

              <div className="sectionLabel">Options</div>
              <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
                <Toggle checked={secondPass} onChange={setSecondPass}>Run second pass (merge + dedupe)</Toggle>
                <Toggle checked={strictEntry} onChange={setStrictEntry}>Entry-level only (strict exclusions)</Toggle>
                <Field label="Employment target">
                  <Select value={employmentTarget} onChange={setEmploymentTarget} options={G.EMPLOYMENT_TARGETS} />
                </Field>
              </div>
            </div>
          )}

          {activeTab === 'filters' && (
            <div className="tabBody">
              <div className="sectionLabel">Keyword refinement</div>
              <Field label="Include keywords" help="Added to the query and used in post-filtering.">
                <Input value={includeKw} onChange={e => setIncludeKw(e.target.value)} placeholder="commercial, union, weekday" />
              </Field>
              <Field label="Exclude keywords" help="Removed from query results.">
                <Input value={excludeKw} onChange={e => setExcludeKw(e.target.value)} placeholder="travel, weekends, on-call" />
              </Field>
              <Field label="Must-have skills">
                <Input value={mustHave} onChange={e => setMustHave(e.target.value)} placeholder="EPA 608, PEX, soldering" />
              </Field>
              <div className="sectionLabel" style={{ marginTop: 16 }}>Experience range</div>
              <div className="crmRow row-2">
                <Field label="Min years"><Select value={expMin} onChange={setExpMin} options={["Any","0","1","2","3","4","5","7","10"]} /></Field>
                <Field label="Max years"><Select value={expMax} onChange={setExpMax} options={["Any","0","1","2","3","4","5","7","10"]} /></Field>
              </div>
              <div className="sectionLabel" style={{ marginTop: 16 }}>Work arrangement</div>
              <Multiselect value={workModes} onChange={setWorkModes} options={G.WORK_MODES}
                labels={{ remote:"Remote", hybrid:"Hybrid", onsite:"On-site" }} />
              <div style={{ marginTop: 12 }}>
                <Toggle checked={includeUnknown} onChange={setIncludeUnknown}>Include unverified links</Toggle>
              </div>
            </div>
          )}

          {activeTab === 'advanced' && (
            <div className="tabBody">
              <div className="sectionLabel">Keyword editor</div>
              <Field label="Primary keywords"><Textarea value={primaryKw} onChange={setPrimaryKw} rows={5} /></Field>
              <Field label="Second-pass keywords" help="Only used when second pass is enabled.">
                <Textarea value={secondKw} onChange={setSecondKw} disabled={!secondPass} rows={4} />
              </Field>
              <div className="sectionLabel" style={{ marginTop: 16 }}>Output</div>
              <Field label="Output folder"><Input value={outputDir} onChange={e => setOutputDir(e.target.value)} /></Field>
              <Field label="Output file name (optional)">
                <Input value={outputFile} onChange={e => setOutputFile(e.target.value)} placeholder="auto-timestamped if blank" />
              </Field>
              <div style={{ marginTop: 12 }}>
                <Toggle checked={linkedinFetch} onChange={setLinkedinFetch}>LinkedIn: fetch full descriptions (slower)</Toggle>
              </div>
            </div>
          )}

          {activeTab === 'preview' && (
            <div className="tabBody">
              <div className="sectionLabel">Resolved query</div>
              {hints.map((h, i) => <Alert key={i} kind="warning">{h}</Alert>)}
              <Field label="Primary (effective)"><Textarea value={effective.primary} onChange={() => {}} disabled rows={5} /></Field>
              <Field label="Second pass (effective)"><Textarea value={effective.second} onChange={() => {}} disabled rows={4} /></Field>
            </div>
          )}
        </div>

        {/* RIGHT panel */}
        <div className="consolePanel">
          <div className="consolePanelInner" style={{ maxWidth: '100%' }}>

            {/* Status bar */}
            <div className="statusCard" style={{ marginBottom: 12 }}>
              <div className="statusCardRow">
                <div>
                  <div className="statusTitle">
                    {running ? 'Scraping…' : lastResult ? 'Last run complete' : 'Ready to run'}
                  </div>
                  <div className="statusSub">
                    {running ? `${selectedSites.length} boards · ${location} · ${distance}mi`
                      : lastResult ? `${lastResult.rows} jobs saved · ${lastResult.path.split('/').pop()}`
                      : 'Configure search on the left, then hit Run.'}
                  </div>
                </div>
                <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                  {running     && <Badge kind="warn">Running</Badge>}
                  {!running && lastResult  && <Badge kind="ok">✓ {lastResult.rows} jobs</Badge>}
                  {!running && !lastResult && <Badge>Idle</Badge>}
                  {lastResult && !running && (
                    <Btn kind="primary" size="sm">⤓ Download CSV</Btn>
                  )}
                </div>
              </div>
            </div>

            {/* Right-side tab switcher */}
            {(logs.length > 0 || jobRows) && (
              <div className="rightTabs">
                <button className={`rightTab${rightTab==='console'?' on':''}`}
                  onClick={() => setRightTab('console')}>
                  Console {logs.length > 0 && <span className="rtBadge">{logs.length}</span>}
                </button>
                {jobRows && (
                  <button className={`rightTab${rightTab==='results'?' on':''}`}
                    onClick={() => setRightTab('results')}>
                    Results <span className="rtBadge">{jobRows.length}</span>
                  </button>
                )}
              </div>
            )}

            {/* Console view */}
            {rightTab === 'console' && (
              <>
                <div className="consoleBox">
                  <div className="consoleHeader">
                    <span>Run console</span>
                    {logs.length > 0 && <button className="consoleClear" onClick={() => setLogs([])}>Clear</button>}
                  </div>
                  <pre className="crmCode" style={{ margin:0, borderRadius:'0 0 8px 8px', maxHeight:'none', minHeight:200 }}>
                    {logs.length === 0 && !running && <span className="ts">Waiting for next run…</span>}
                    {logs.map((l, i) => (
                      <div key={i}><span className="ts">[{l.ts}]</span> <span className={l.cls||''}>{l.msg}</span></div>
                    ))}
                    {running && <div><span className="ts">…</span></div>}
                  </pre>
                </div>
                <div className="runMeta" style={{ marginTop: 10 }}>
                  <span className="metaChip">📍 {location} · {distance}mi</span>
                  <span className="metaChip">📅 Last {days} days</span>
                  <span className="metaChip">🎯 {results}/board</span>
                  {selectedSites.length > 0 && (
                    <span className="metaChip">{selectedSites.map(s => SITE_LABELS[s]).join(', ')}</span>
                  )}
                </div>
              </>
            )}

            {/* Results table view */}
            {rightTab === 'results' && jobRows && <ResultsTable jobs={jobRows} />}
          </div>
        </div>
      </div>

      {/* Tweaks panel */}
      {showTweaks && (
        <TweaksPanel onClose={() => setShowTweaks(false)}>
          <TweakSection title="Brand">
            <TweakColor label="Accent color" value={tweaks.accentColor} onChange={v => setTweak('accentColor', v)} />
          </TweakSection>
          <TweakSection title="Layout">
            <TweakToggle label="Compact density" value={tweaks.compact} onChange={v => setTweak('compact', v)} />
          </TweakSection>
          <TweakSection title="Defaults">
            <TweakSelect label="Default preset" value={tweaks.defaultPreset}
              options={["Fairfax Entry - Combined","Fairfax Entry - Plumbing","Fairfax Entry - HVAC","GUTTS default"]}
              onChange={v => setTweak('defaultPreset', v)} />
            <TweakSlider label="Default distance (mi)" min={10} max={200} step={5}
              value={tweaks.defaultDistance} onChange={v => setTweak('defaultDistance', v)} />
          </TweakSection>
        </TweaksPanel>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('app')).render(<App />);
