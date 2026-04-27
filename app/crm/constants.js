/* global */
const { useState, useEffect, useMemo } = React;

const SITE_CHOICES = [
  ["Indeed", "indeed"],
  ["ZipRecruiter", "zip_recruiter"],
  ["LinkedIn", "linkedin"],
  ["Glassdoor", "glassdoor"],
  ["Google", "google"],
];

const COUNTRY_CHOICES = ["USA", "Canada", "UK", "India", "Australia"];
const WORK_MODES = ["remote", "hybrid", "onsite"];
const EMPLOYMENT_TARGETS = ["All targets","New Construction","Service Companies","Property Management / Maintenance","Data Centers"];

const FAIRFAX_COMBINED_PRIMARY =
  '("plumbing helper" OR "plumbing apprentice" OR "entry-level plumber" OR "plumber i" OR "pipe-layer" OR "service plumber" OR "maintenance technician" OR "helper apprentice" OR "building engineer helper" OR "building engineer apprentice" OR "hvac technician" OR "hvac tech" OR "hvac helper" OR "hvac apprentice" OR "hvac maintenance" OR "hvac service" OR "commercial hvac" OR "refrigeration tech" OR "fridge tech") ("new construction" OR "service company" OR "property management" OR maintenance OR "data center") -software -developer -IT -sales';
const FAIRFAX_COMBINED_SECONDARY =
  '("plumbing" OR "plumbing helper" OR "hvac" OR "hvac helper" OR "hvac apprentice" OR "hvac service") (apprentice OR helper OR "entry level" OR trainee OR "willing to train") ("new construction" OR "property management" OR "data center") -software -developer -IT';
const STRICT_ENTRY = '-manager -supervisor -director -lead -senior -sr -principal -foreman -estimator';
const TARGET_TERMS = {
  "All targets": '("new construction" OR "service company" OR "property management" OR "data center" OR "maintenance technician")',
  "New Construction": '("new construction" OR "ground-up construction")',
  "Service Companies": '("service company" OR "service technician" OR "field service")',
  "Property Management / Maintenance": '("property management" OR "facilities maintenance" OR "building engineer")',
  "Data Centers": '("data center" OR "critical facilities" OR "mission critical")',
};

const TWEAK_DEFAULTS = {
  accentColor:     '#FF7A59',
  compact:         false,
  defaultPreset:   'Fairfax Entry - Combined',
  defaultDistance: 50,
};

window.GUTTS = {
  SITE_CHOICES, COUNTRY_CHOICES, WORK_MODES, EMPLOYMENT_TARGETS,
  FAIRFAX_COMBINED_PRIMARY, FAIRFAX_COMBINED_SECONDARY, STRICT_ENTRY, TARGET_TERMS,
};
window.TWEAK_DEFAULTS = TWEAK_DEFAULTS;
