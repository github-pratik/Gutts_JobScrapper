from __future__ import annotations

from pathlib import Path

import streamlit as st

from jobspy_scrape import (
    GUTTS_DEFAULT_LOCATION,
    GUTTS_DEFAULT_SEARCH,
    GUTTS_SECOND_PASS_SEARCH,
    ScrapeConfig,
    run_gutts_scrape,
)

SITE_CHOICES = [
    ("Indeed", "indeed"),
    ("ZipRecruiter", "zip_recruiter"),
    ("LinkedIn", "linkedin"),
    ("Glassdoor", "glassdoor"),
    ("Google", "google"),
]

COUNTRY_CHOICES = ["USA", "Canada", "UK", "India", "Australia"]
WORK_MODE_CHOICES = ["remote", "hybrid", "onsite"]

MANUAL_FILTER_SITE_SET = {"indeed", "zip_recruiter", "linkedin"}

FAIRFAX_COMBINED_PRIMARY = (
    '(("plumbing apprentice" OR "apprentice plumber" OR "plumber helper" OR "service plumber") '
    'OR ("hvac apprentice" OR "hvac helper" OR "hvac technician" OR "refrigeration technician")) '
    '(install OR service OR maintenance OR troubleshooting) '
    '(construction OR "property management" OR facilities OR "data center" OR "commercial hvac" '
    'OR "residential hvac") '
    '-software -developer -IT -sales -marketing -dispatcher'
)

FAIRFAX_COMBINED_SECONDARY = (
    '("maintenance technician" OR "building engineer" OR "service technician" OR "pipefitter" '
    'OR "sheet metal mechanic" OR "hvacr technician") '
    '(apprentice OR helper OR trainee OR "entry level") '
    '(commercial OR residential OR facilities OR contractor OR "property management") '
    '-software -developer -IT -sales -marketing'
)

FAIRFAX_PLUMBING_PRIMARY = (
    '("plumbing apprentice" OR "apprentice plumber" OR "plumber helper" OR "entry level plumber" '
    'OR "service plumber" OR "plumber trainee") '
    '(install OR repair OR maintenance OR troubleshooting) '
    '(construction OR "property management" OR facilities OR residential OR commercial) '
    '-software -developer -IT -sales -marketing'
)

FAIRFAX_HVAC_PRIMARY = (
    '("hvac apprentice" OR "hvac helper" OR "hvac technician" OR "entry level hvac" '
    'OR "refrigeration technician" OR "hvacr technician") '
    '(install OR service OR maintenance OR troubleshooting) '
    '("commercial hvac" OR "residential hvac" OR facilities OR construction OR "property management") '
    '-software -developer -IT -sales -marketing'
)

STRICT_ENTRY_EXCLUSIONS = (
    "-manager -supervisor -director -lead -senior -sr -principal "
    "-foreman -estimator -projectmanager -\"project manager\" -\"service manager\" "
    "-\"operations manager\" -\"maintenance manager\" -sales -marketing -dispatcher"
)

EMPLOYMENT_TARGET_TERMS: dict[str, str] = {
    "All targets": (
        '("new construction" OR "service company" OR "service technician" OR '
        '"service plumber" OR "hvac service" OR "property management" OR '
        '"maintenance technician" OR "facilities maintenance" OR '
        '"building engineer" OR "data center" OR "critical facilities" OR '
        '"mission critical")'
    ),
    "New Construction": '("new construction" OR "ground-up construction" OR "construction project")',
    "Service Companies": (
        '("service company" OR "service technician" OR "service plumber" OR '
        '"hvac service" OR "field service")'
    ),
    "Property Management / Maintenance": (
        '("property management" OR "maintenance technician" OR '
        '"facilities maintenance" OR "building engineer")'
    ),
    "Data Centers": '("data center" OR "critical facilities" OR "mission critical")',
}


def apply_search_preset(preset: str) -> None:
    if preset == "GUTTS default":
        st.session_state.primary_keywords = GUTTS_DEFAULT_SEARCH
        st.session_state.second_keywords = GUTTS_SECOND_PASS_SEARCH
        st.session_state.strict_entry = False
        st.session_state.location = GUTTS_DEFAULT_LOCATION
        st.session_state.distance = 100
        st.session_state.selected_sites = [value for _, value in SITE_CHOICES]
        return
    if preset == "Fairfax Entry - Combined":
        st.session_state.primary_keywords = FAIRFAX_COMBINED_PRIMARY
        st.session_state.second_keywords = FAIRFAX_COMBINED_SECONDARY
    elif preset == "Fairfax Entry - Plumbing":
        st.session_state.primary_keywords = FAIRFAX_PLUMBING_PRIMARY
        st.session_state.second_keywords = FAIRFAX_COMBINED_SECONDARY
    elif preset == "Fairfax Entry - HVAC":
        st.session_state.primary_keywords = FAIRFAX_HVAC_PRIMARY
        st.session_state.second_keywords = FAIRFAX_COMBINED_SECONDARY
    st.session_state.location = "Fairfax, VA"
    st.session_state.distance = 50
    st.session_state.days = 14
    st.session_state.results = 60
    st.session_state.second_pass = True
    st.session_state.strict_entry = True
    st.session_state.employment_target = "All targets"
    st.session_state.selected_sites = sorted(MANUAL_FILTER_SITE_SET)


def apply_parameter_preset(preset: str) -> None:
    if preset == "Custom":
        return
    if preset == "Fairfax Entry - Standard":
        st.session_state.location = "Fairfax, VA"
        st.session_state.distance = 50
        st.session_state.days = 14
        st.session_state.results = 60
        st.session_state.second_pass = True
        st.session_state.strict_entry = True
        st.session_state.selected_sites = sorted(MANUAL_FILTER_SITE_SET)
    elif preset == "Fairfax Entry - Deep":
        st.session_state.location = "Fairfax, VA"
        st.session_state.distance = 50
        st.session_state.days = 30
        st.session_state.results = 100
        st.session_state.second_pass = True
        st.session_state.strict_entry = True
        st.session_state.selected_sites = sorted(MANUAL_FILTER_SITE_SET)
    elif preset == "DMV Entry - Broad":
        st.session_state.location = "Washington, DC"
        st.session_state.distance = 75
        st.session_state.days = 21
        st.session_state.results = 80
        st.session_state.second_pass = True
        st.session_state.strict_entry = True
        st.session_state.selected_sites = [value for _, value in SITE_CHOICES]


def apply_target_filter(term: str, target_name: str) -> str:
    target_terms = EMPLOYMENT_TARGET_TERMS.get(target_name)
    if not target_terms:
        return term
    return f"{term} {target_terms}".strip()


def apply_strict_filter(term: str, strict_entry: bool) -> str:
    if not strict_entry:
        return term
    compact = term.lower()
    if "-manager" in compact and "-senior" in compact:
        return term
    return f"{term} {STRICT_ENTRY_EXCLUSIONS}".strip()


def _split_csv_terms(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _format_for_query(value: str) -> str:
    if " " in value and not (value.startswith('"') and value.endswith('"')):
        return f'"{value}"'
    return value


def add_structured_terms_to_query(base_term: str, include_terms: str, exclude_terms: str) -> str:
    term = base_term.strip()
    include_values = _split_csv_terms(include_terms)
    exclude_values = _split_csv_terms(exclude_terms)

    for value in include_values:
        token = _format_for_query(value)
        term = f"{term} {token}".strip()

    for value in exclude_values:
        token = _format_for_query(value)
        term = f'{term} -{token}'.strip()

    return term


def effective_terms() -> tuple[str, str]:
    primary = st.session_state.primary_keywords.strip()
    second = st.session_state.second_keywords.strip()
    target_name = st.session_state.employment_target
    strict_entry = st.session_state.strict_entry
    primary = apply_target_filter(primary, target_name)
    second = apply_target_filter(second, target_name)
    primary = apply_strict_filter(primary, strict_entry)
    second = apply_strict_filter(second, strict_entry)
    primary = add_structured_terms_to_query(
        primary,
        st.session_state.include_keywords,
        st.session_state.exclude_keywords,
    )
    second = add_structured_terms_to_query(
        second,
        st.session_state.include_keywords,
        st.session_state.exclude_keywords,
    )
    return primary, second


def get_experience_bounds() -> tuple[int | None, int | None]:
    min_val = st.session_state.exp_min
    max_val = st.session_state.exp_max
    min_exp = None if min_val == "Any" else int(min_val)
    max_exp = None if max_val == "Any" else int(max_val)
    if min_exp is not None and max_exp is not None and min_exp > max_exp:
        min_exp, max_exp = max_exp, min_exp
    return min_exp, max_exp


def get_query_validation_hints(primary_query: str) -> list[str]:
    hints: list[str] = []
    if len(primary_query.strip()) < 8:
        hints.append("Primary query looks too short. Add role and skill keywords.")
    if len(_split_csv_terms(st.session_state.include_keywords)) == 0:
        hints.append("Tip: Add include keywords to improve search precision.")
    if st.session_state.results > 200:
        hints.append("Large result limits may increase duplicates and slower runs.")
    return hints


def init_state() -> None:
    if st.session_state.get("_initialized"):
        return
    st.session_state.search_preset = "Fairfax Entry - Combined"
    st.session_state.parameter_preset = "Fairfax Entry - Standard"
    st.session_state.run_profile = "Standard"
    st.session_state.employment_target = "All targets"
    st.session_state.second_pass = True
    st.session_state.strict_entry = True
    st.session_state.location = "Fairfax, VA"
    st.session_state.distance = 50
    st.session_state.days = 14
    st.session_state.results = 60
    st.session_state.country = "USA"
    st.session_state.output_dir = str((Path.cwd() / "data" / "output").resolve())
    st.session_state.output_file = ""
    st.session_state.google_override = ""
    st.session_state.linkedin_fetch = False
    st.session_state.verbose = 1
    st.session_state.show_manual_editor = False
    st.session_state.selected_sites = sorted(MANUAL_FILTER_SITE_SET)
    st.session_state.primary_keywords = FAIRFAX_COMBINED_PRIMARY
    st.session_state.second_keywords = FAIRFAX_COMBINED_SECONDARY
    st.session_state.last_logs = []
    st.session_state.last_output_path = ""
    st.session_state.last_row_count = 0
    st.session_state.last_error = ""
    st.session_state.include_keywords = ""
    st.session_state.exclude_keywords = ""
    st.session_state.must_have_skills = ""
    st.session_state.exp_min = "Any"
    st.session_state.exp_max = "Any"
    st.session_state.work_modes = []
    st.session_state.include_unknown_links = False
    st.session_state._initialized = True


def main() -> None:
    st.set_page_config(page_title="GUTTS Job Runner Web", page_icon="🛠", layout="wide")
    init_state()

    st.title("GUTTS Job Runner")
    st.caption("Preset-first job scraping for entry-level Plumbing/HVAC placements.")

    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        st.selectbox(
            "Search preset",
            ["GUTTS default", "Fairfax Entry - Combined", "Fairfax Entry - Plumbing", "Fairfax Entry - HVAC", "Custom"],
            key="search_preset",
        )
    with c2:
        st.selectbox(
            "Parameters preset",
            ["Custom", "Fairfax Entry - Standard", "Fairfax Entry - Deep", "DMV Entry - Broad"],
            key="parameter_preset",
        )
    with c3:
        ac1, ac2 = st.columns([1, 1])
        with ac1:
            if st.button("Apply search preset", use_container_width=True):
                apply_search_preset(st.session_state.search_preset)
        with ac2:
            if st.button("Apply parameter preset", use_container_width=True):
                apply_parameter_preset(st.session_state.parameter_preset)

    left, right = st.columns([1, 1])
    with left:
        st.text_input("Location", key="location")
    with right:
        st.number_input("Distance (miles)", min_value=1, max_value=500, step=1, key="distance")

    col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])
    with col_a:
        st.number_input("Job age (days)", min_value=1, max_value=90, step=1, key="days")
    with col_b:
        st.number_input("Results per site", min_value=1, max_value=1000, step=5, key="results")
    with col_c:
        st.selectbox("Country", COUNTRY_CHOICES, key="country")
    with col_d:
        st.selectbox("Verbose", [0, 1, 2], key="verbose")

    col_e, col_f, col_g = st.columns([2, 2, 2])
    with col_e:
        st.checkbox("Run second pass (merge + dedupe)", key="second_pass")
    with col_f:
        st.checkbox("Entry-level only (strict)", key="strict_entry")
    with col_g:
        st.selectbox("Employment target", list(EMPLOYMENT_TARGET_TERMS.keys()), key="employment_target")

    site_values = [value for _, value in SITE_CHOICES]
    site_labels = {value: label for label, value in SITE_CHOICES}
    selected_sites = st.multiselect(
        "Job boards",
        options=site_values,
        format_func=lambda v: site_labels[v],
        key="selected_sites",
    )
    if not selected_sites:
        st.warning("Select at least one site before running.")

    st.subheader("Search and filter controls")
    q1, q2 = st.columns([1, 1])
    with q1:
        st.text_input(
            "Include keywords (comma-separated)",
            key="include_keywords",
            help="These terms are added to the search query and used in post-filtering.",
        )
    with q2:
        st.text_input(
            "Exclude keywords (comma-separated)",
            key="exclude_keywords",
            help="These terms are excluded from query and filtered from results.",
        )

    q3, q4, q5 = st.columns([2, 1, 1])
    with q3:
        st.text_input(
            "Must-have skills (comma-separated)",
            key="must_have_skills",
            help="Results must contain these skills in extracted skills text.",
        )
    with q4:
        st.selectbox("Min experience (years)", ["Any", 0, 1, 2, 3, 4, 5, 7, 10], key="exp_min")
    with q5:
        st.selectbox("Max experience (years)", ["Any", 0, 1, 2, 3, 4, 5, 7, 10], key="exp_max")

    q6, q7 = st.columns([2, 1])
    with q6:
        st.multiselect(
            "Work mode filter",
            options=WORK_MODE_CHOICES,
            key="work_modes",
            help="Keep only jobs matching these work arrangements.",
        )
    with q7:
        st.checkbox(
            "Include unknown links",
            key="include_unknown_links",
            help="Keep links we cannot verify as live. Default is off for stricter quality.",
        )

    with st.expander("Manual keyword editor (optional)", expanded=st.session_state.show_manual_editor):
        st.text_area("Primary keywords", key="primary_keywords", height=140)
        st.text_area("Second-pass keywords", key="second_keywords", height=120)
        st.text_input("Google Jobs override query (optional)", key="google_override")

    eff_primary, eff_second = effective_terms()
    for hint in get_query_validation_hints(eff_primary):
        st.info(hint)

    st.subheader("Effective query preview")
    preview_a, preview_b = st.columns([1, 1])
    with preview_a:
        st.text_area(
            "Primary (effective)",
            value=eff_primary,
            height=140,
            disabled=True,
        )
    with preview_b:
        st.text_area(
            "Second pass (effective)",
            value=eff_second,
            height=140,
            disabled=True,
        )

    st.subheader("Output")
    o1, o2, o3 = st.columns([3, 3, 2])
    with o1:
        st.text_input("Output folder", key="output_dir")
    with o2:
        st.text_input("Output file name (optional)", key="output_file")
    with o3:
        st.checkbox("LinkedIn: fetch full descriptions (slower)", key="linkedin_fetch")

    run_clicked = st.button("Run scrape", type="primary", use_container_width=True)
    log_box = st.empty()
    status_box = st.empty()

    if run_clicked:
        if not selected_sites:
            st.error("Please select at least one job board.")
            st.stop()
        if not eff_primary.strip():
            st.error("Primary query is empty. Please add keywords.")
            st.stop()
        logs: list[str] = []

        def log(msg: str) -> None:
            logs.append(str(msg))
            log_box.code("\n".join(logs[-300:]), language="text")

        min_experience_years, max_experience_years = get_experience_bounds()

        config = ScrapeConfig(
            search_term=eff_primary,
            second_pass_search=eff_second,
            location=st.session_state.location.strip(),
            distance=int(st.session_state.distance),
            sites=selected_sites,
            results_wanted=int(st.session_state.results),
            multi_query=bool(st.session_state.second_pass),
            hours_old=int(st.session_state.days) * 24,
            country_indeed=st.session_state.country,
            google_search_term=st.session_state.google_override.strip() or None,
            output=st.session_state.output_file.strip() or None,
            output_dir=st.session_state.output_dir.strip() or ".",
            linkedin_fetch_description=bool(st.session_state.linkedin_fetch),
            verbose=int(st.session_state.verbose),
            include_keywords=st.session_state.include_keywords.strip(),
            exclude_keywords=st.session_state.exclude_keywords.strip(),
            must_have_skills=st.session_state.must_have_skills.strip(),
            min_experience_years=min_experience_years,
            max_experience_years=max_experience_years,
            work_modes=st.session_state.work_modes,
            include_unknown_links=bool(st.session_state.include_unknown_links),
        )

        try:
            with st.spinner("Scraping job boards..."):
                out_path, row_count = run_gutts_scrape(config=config, log=log)
            st.session_state.last_logs = logs
            st.session_state.last_output_path = str(out_path)
            st.session_state.last_row_count = row_count
            st.session_state.last_error = ""
            status_box.success(f"Saved {row_count} jobs to {out_path}")
        except Exception as exc:
            st.session_state.last_logs = logs
            st.session_state.last_error = str(exc)
            status_box.error(f"Scrape failed: {exc}")

    if st.session_state.last_output_path:
        st.subheader("Last result")
        st.write(f"Rows: **{st.session_state.last_row_count}**")
        st.write(f"File: `{st.session_state.last_output_path}`")
        out_file = Path(st.session_state.last_output_path)
        if out_file.exists():
            st.download_button(
                "Download latest CSV",
                data=out_file.read_bytes(),
                file_name=out_file.name,
                mime="text/csv",
                use_container_width=True,
            )

    if st.session_state.last_logs:
        with st.expander("Last run logs", expanded=False):
            st.code("\n".join(st.session_state.last_logs[-300:]), language="text")


if __name__ == "__main__":
    main()
