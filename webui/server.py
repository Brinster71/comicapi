import json
import os
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .comicvine import ComicVineClient
from ..comicarchive import ComicArchive, MetaDataStyle

INDEX_HTML = """<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Comic Metadata UI</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 1rem; }
    .row { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; margin-bottom: .5rem; }
    input, select, button, textarea { padding: .4rem; }
    input[type=text] { min-width: 18rem; }
    textarea { width: 100%; min-height: 10rem; font-family: ui-monospace, monospace; }
    table { border-collapse: collapse; width: 100%; margin-top: .5rem; }
    th, td { border: 1px solid #ddd; padding: .35rem; text-align: left; }
    tr:hover { background: #f6f6f6; }
    .muted { color: #666; font-size: .9rem; }
    .pill { border-radius: 999px; padding: .1rem .5rem; font-size: .8rem; }
    .good { background: #d7f6dd; color: #145a2a; }
    .warn { background: #fff3cd; color: #7a5b00; }
    .grid2 { display:grid; grid-template-columns: 220px 1fr; gap:.4rem .8rem; align-items:start; }
    .meta-card { border:1px solid #ddd; padding:.8rem; border-radius:.5rem; margin:.6rem 0; }
    .thumb { width:180px; height:260px; object-fit:contain; border:1px solid #ddd; background:#fafafa; }
    .mapping-grid { display:grid; grid-template-columns: 22px 160px 1fr; gap:.35rem .5rem; align-items:center; margin:.35rem 0; }
    .small { font-size:.85rem; }
    .tight { min-width: 8rem !important; }
    .status { margin-top:.4rem; font-size:.9rem; color:#145a2a; }
    .diag { border:1px solid #e5d7a7; background:#fff7df; padding:.45rem .6rem; border-radius:.25rem; font-size:.8rem; margin-bottom:.6rem; }
  </style>
</head>
<body>
  <h2>Comic Metadata UI</h2>
  <div id='diagBanner' class='diag'>Loading runtime diagnostics…</div>
  <p class='muted'>Single-comic workflow: scan, inspect detected metadata, choose series then issue, map fields, apply, write.</p>

  <div class='row'>
    <label>Library path:</label>
    <input id='rootPath' type='text' placeholder='/path/to/comics'>
    <button onclick='browseLibraryPath()'>Browse…</button>
    <button onclick='scanLibrary()'>Scan</button>
  </div>

  <div class='row'>
    <label>Selected file:</label>
    <input id='comicPath' type='text' placeholder='/path/to/file.cbz'>
    <button onclick='browseComicFile()'>Browse…</button>
    <input id='comicPathPicker' type='file' accept='.cbz,.cbr,.cbt,.pdf,.zip,.rar' style='display:none' onchange='onComicFilePicked(event)'>
    <label>Write to:</label>
    <input id='writePath' type='text' placeholder='/path/to/output.cbz (defaults to selected file)'>
    <button onclick='browseWritePath()'>Browse…</button>
    <input id='writePathPicker' type='file' accept='.cbz,.cbr,.cbt,.pdf,.zip,.rar,.json' style='display:none' onchange='onWriteFilePicked(event)'>
    <button onclick='setWritePathFromSelected()'>Use selected file</button>
    <label>Style:</label>
    <select id='style' class='tight'>
      <option value='AUTO' selected>AUTO</option>
      <option value='CIX'>CIX</option>
      <option value='CBI'>CBI</option>
      <option value='COMET'>COMET</option>
    </select>
    <button onclick='readMetadata()'>Read metadata</button>
    <button onclick='assessFile()'>Assess file</button>
    <span id='styleInfo' class='muted'></span>
  </div>

  <div class='row'>
    <label>ComicVine API key:</label>
    <input id='apiKey' type='text' placeholder='paste API key here (or use COMICVINE_API_KEY env var)'>
    <label>Search:</label>
    <input id='cvQuery' type='text' placeholder='Series + issue, e.g. American Splendor 1'>
    <button onclick='searchComicVine()'>Search ComicVine</button>
  </div>

  <h3>Scan results</h3>
  <div class='muted'>Click a row to select a comic file.</div>
  <table id='scanTable'>
    <thead><tr><th>Path</th><th>Pages</th><th>CIX</th><th>CBI</th><th>COMET</th><th>Error</th></tr></thead>
    <tbody></tbody>
  </table>

  <h3>Detected current metadata</h3>
  <div class='meta-card'>
    <div class='row'>
      <img id='coverThumb' class='thumb' alt='Cover preview'>
      <div style='flex:1'>
        <div id='metadataSummary' class='grid2 small'></div>
      </div>
    </div>
  </div>

  <details>
    <summary>Parse metadata from folder/file name pattern</summary>
    <div class='row'>
      <label>Pattern:</label>
      <input id='pathPattern' type='text' placeholder='{Series}/{VolumeNumber} - {Year}/{IssueNumber} - {Title}'>
      <button onclick='previewPatternParse()'>Preview parse</button>
      <button onclick='applyPatternParseToMapping()'>Apply to mapping</button>
    </div>
    <div class='muted small'>Use variables like {Series}, {IssueNumber}, {VolumeNumber}, {Year}, {Title}, {Publisher}, {Month}, {Day}. Literal text and separators should match your folders/files.</div>
    <textarea id='patternParseJson' placeholder='Pattern parse preview will appear here...' readonly></textarea>
  </details>

  <details>
    <summary>Raw detected metadata JSON (editable)</summary>
    <textarea id='metadataJson' placeholder='Read metadata first, then edit JSON fields...'></textarea>
    <div class='row' style='margin-top:.5rem;'>
      <button onclick='writeManualMetadata()'>Write this raw metadata JSON to selected file</button>
    </div>
  </details>

  <details>
    <summary>File assessment JSON</summary>
    <textarea id='assessmentJson' placeholder='File assessment output will appear here...' readonly></textarea>
  </details>

  <div id='writeStatus' class='status'></div>

  <h3>ComicVine selection flow</h3>
  <div class='meta-card'>
    <div class='row'>
      <label>Series:</label>
      <select id='seriesSelect' class='tight' onchange='onSeriesSelected()'></select>
      <label><input type='checkbox' id='pinSeries' onchange='togglePin("series")'> Pin open</label>
      <span id='seriesHint' class='muted'></span>
    </div>
    <div class='row'>
      <label>Issue:</label>
      <select id='issueSelect' class='tight' onchange='onIssueSelected()'></select>
      <label><input type='checkbox' id='pinIssue' onchange='togglePin("issue")'> Pin open</label>
      <span id='issueHint' class='muted'></span>
    </div>
    <div class='row'>
      <label>Publisher choice:</label>
      <select id='publisherChoice' class='tight' onchange='onPublisherChoice()'></select>
      <span id='publisherHint' class='muted'></span>
    </div>
  </div>

  <h3>Series candidates (reference)</h3>
  <table id='seriesTable'>
    <thead><tr><th>Name</th><th>Start year</th><th>Issue count</th><th>ID</th></tr></thead>
    <tbody></tbody>
  </table>

  <h3>Issue candidates (reference)</h3>
  <table id='issueTable'>
    <thead><tr><th>Match hint</th><th>Issue #</th><th>Issue name</th><th>Series</th><th>Start year</th><th>Cover date</th><th>Issue ID</th></tr></thead>
    <tbody></tbody>
  </table>

  <h3>Selected field mapping</h3>
  <div class='meta-card'>
    <div class='mapping-grid'>
      <input type='checkbox' id='use_series' checked><label for='use_series'>Series</label><input id='map_series' type='text'>
      <input type='checkbox' id='use_issue' checked><label for='use_issue'>Issue</label><input id='map_issue' type='text'>
      <input type='checkbox' id='use_title' checked><label for='use_title'>Title</label><div><input id='map_title' type='text'><select id='title_source' onchange='applyAltSource("title")'><option value='manual'>manual</option><option value='issue_name'>issue.name</option><option value='issue_title'>issue.title</option><option value='series_first_issue_name'>series.first_issue.name</option><option value='series_name'>series.name</option></select></div>
      <input type='checkbox' id='use_issue_name' checked><label for='use_issue_name'>Issue name</label><div><input id='map_issue_name' type='text'><select id='issue_name_source' onchange='applyAltSource("issue_name")'><option value='manual'>manual</option><option value='issue_name'>issue.name</option><option value='issue_title'>issue.title</option><option value='title_field'>title field</option></select></div>
      <input type='checkbox' id='use_publisher' checked><label for='use_publisher'>Publisher</label><input id='map_publisher' type='text'>
      <input type='checkbox' id='use_year' checked><label for='use_year'>Year (published)</label><input id='map_year' type='text'>
      <input type='checkbox' id='use_volume' checked><label for='use_volume'>Volume</label><div><input id='map_volume' type='text'><select id='volume_source' onchange='applyAltSource("volume")'><option value='manual'>manual</option><option value='series_start_year'>series.start_year</option><option value='one'>1</option></select></div>
      <input type='checkbox' id='use_start_year' checked><label for='use_start_year'>Start year</label><input id='map_start_year' type='text'>
      <input type='checkbox' id='use_published_year' checked><label for='use_published_year'>Published year</label><input id='map_published_year' type='text'>
      <input type='checkbox' id='use_issue_id' checked><label for='use_issue_id'>ComicVine issue ID</label><input id='map_issue_id' type='text'>
      <input type='checkbox' id='use_series_id' checked><label for='use_series_id'>ComicVine series ID</label><input id='map_series_id' type='text'>
      <input type='checkbox' id='use_description' checked><label for='use_description'>Description</label><input id='map_description' type='text'>

      <input type='checkbox' id='use_month' checked><label for='use_month'>Month</label><input id='map_month' type='text'>
      <input type='checkbox' id='use_day' checked><label for='use_day'>Day</label><input id='map_day' type='text'>
      <input type='checkbox' id='use_writer' checked><label for='use_writer'>Writer</label><input id='map_writer' type='text'>
      <input type='checkbox' id='use_cover_artist' checked><label for='use_cover_artist'>CoverArtist</label><input id='map_cover_artist' type='text'>
      <input type='checkbox' id='use_editor' checked><label for='use_editor'>Editor</label><input id='map_editor' type='text'>
      <input type='checkbox' id='use_story_arc' checked><label for='use_story_arc'>StoryArc</label><input id='map_story_arc' type='text'>
      <input type='checkbox' id='use_story_arc_num' checked><label for='use_story_arc_num'>StoryArcNumber</label><input id='map_story_arc_num' type='text'>
      <input type='checkbox' id='use_tags' checked><label for='use_tags'>Tags</label><input id='map_tags' type='text'>
      <input type='checkbox' id='use_page_count' checked><label for='use_page_count'>PageCount</label><input id='map_page_count' type='text'>
      <input type='checkbox' id='use_isbn' checked><label for='use_isbn'>ISBN</label><input id='map_isbn' type='text'>
      <input type='checkbox' id='use_barcode' checked><label for='use_barcode'>Barcode</label><input id='map_barcode' type='text'>
    </div>

    <details>
      <summary>Hidden extra fields</summary>
      <div class='mapping-grid'>
        <input type='checkbox' id='use_language'><label for='use_language'>Language</label><input id='map_language' type='text'>
        <input type='checkbox' id='use_penciller'><label for='use_penciller'>Penciller</label><input id='map_penciller' type='text'>
        <input type='checkbox' id='use_inker'><label for='use_inker'>Inker</label><input id='map_inker' type='text'>
        <input type='checkbox' id='use_colorist'><label for='use_colorist'>Colorist</label><input id='map_colorist' type='text'>
        <input type='checkbox' id='use_letterer'><label for='use_letterer'>Letterer</label><input id='map_letterer' type='text'>
      </div>
    </details>

    <div class='row'>
      <button onclick='applySelectedComicVineFields()'>Apply selected fields to metadata JSON</button>
      <button onclick='writeMetadata()'>Write metadata to selected file</button>
    </div>
  </div>

  <details>
    <summary>Raw ComicVine JSON</summary>
    <textarea id='comicvineJson' placeholder='ComicVine search results appear here...'></textarea>
  </details>

  <script>
    function showJson(id, obj) { document.getElementById(id).value = JSON.stringify(obj, null, 2); }

    const appState = { cvData: null, seriesIssues: [], lastIssue: null, lastSeries: null, volumeDetails: null };

    function savePersistentFields() {
      localStorage.setItem('comicapi.rootPath', document.getElementById('rootPath').value || '');
      localStorage.setItem('comicapi.apiKey', document.getElementById('apiKey').value || '');
      localStorage.setItem('comicapi.comicPath', document.getElementById('comicPath').value || '');
      localStorage.setItem('comicapi.writePath', document.getElementById('writePath').value || '');
      localStorage.setItem('comicapi.pathPattern', document.getElementById('pathPattern').value || '');
    }

    function loadPersistentFields() {
      document.getElementById('rootPath').value = localStorage.getItem('comicapi.rootPath') || '';
      document.getElementById('apiKey').value = localStorage.getItem('comicapi.apiKey') || '';
      document.getElementById('comicPath').value = localStorage.getItem('comicapi.comicPath') || '';
      document.getElementById('writePath').value = localStorage.getItem('comicapi.writePath') || '';
      document.getElementById('pathPattern').value = localStorage.getItem('comicapi.pathPattern') || '{Series}/{VolumeNumber} - {Year}/{IssueNumber} - {Title}';
      if (!document.getElementById('writePath').value) document.getElementById('writePath').value = document.getElementById('comicPath').value;
      ['rootPath','apiKey','comicPath','writePath','pathPattern'].forEach(id => document.getElementById(id).addEventListener('change', savePersistentFields));
    }

    function togglePin(which) {
      const select = document.getElementById(which === 'series' ? 'seriesSelect' : 'issueSelect');
      const pin = document.getElementById(which === 'series' ? 'pinSeries' : 'pinIssue').checked;
      select.size = pin ? 12 : 1;
    }

    function normalizeIssue(val) {
      const s = String(val || '').trim();
      if (!s) return '';
      const m = s.match(/^(\\d+)(.*)$/);
      if (!m) return s.toLowerCase();
      const n = String(parseInt(m[1], 10));
      return (Number.isNaN(parseInt(m[1], 10)) ? m[1] : n) + (m[2] || '').toLowerCase();
    }

    function parseLoadedMetadataWrapper() {
      try { return JSON.parse(document.getElementById('metadataJson').value || '{}'); }
      catch (_) { return {}; }
    }

    function parseLoadedMetadata() {
      const raw = parseLoadedMetadataWrapper();
      return raw.metadata && typeof raw.metadata === 'object' ? raw.metadata : raw;
    }

    function getPreferredIssueNumber() {
      const md = parseLoadedMetadata();
      if (md.issue) return normalizeIssue(md.issue);
      const path = (document.getElementById('comicPath').value || '').split('/').pop() || '';
      const m = path.match(/(?:^|[^\d])(\d{1,4})(?:[^\d]|$)/);
      if (m) return normalizeIssue(m[1]);
      return '';
    }

    function renderSummary(summary) {
      const el = document.getElementById('metadataSummary');
      const rows = [
        ['Series', summary.series || ''], ['Issue', summary.issue || ''], ['Title', summary.title || ''],
        ['Volume', summary.volume || ''], ['Year', summary.year || ''], ['Publisher', summary.publisher || ''],
        ['Detected style', summary.detected_style || 'None'], ['Used style', summary.used_style || ''],
      ];
      el.innerHTML = rows.map(([k,v]) => `<div class='muted'><b>${k}</b></div><div>${v || '<span class="muted">(empty)</span>'}</div>`).join('');
    }

    function looksLikeMatch(md, issue) {
      const mdSeries = String(md.series || '').toLowerCase();
      const mdIssue = normalizeIssue(md.issue || '');
      const mdYear = String(md.year || '').trim();
      const mdVolume = String(md.volume || '').trim();
      const issueNum = normalizeIssue(issue.issue_number || '');
      const volume = issue.volume || {};
      const volumeName = String(volume.name || '').toLowerCase();
      const volumeYear = String(volume.start_year || '').trim();
      const pubYear = String(issue.cover_date || '').slice(0,4);
      const score = [
        mdIssue && issueNum && mdIssue === issueNum,
        mdSeries && volumeName && (mdSeries === volumeName || volumeName.includes(mdSeries)),
        (mdYear && pubYear && mdYear === pubYear) || (mdVolume && volumeYear && mdVolume === volumeYear),
      ].filter(Boolean).length;
      if (score >= 2) return {label: 'Likely', cls: 'good', score};
      if (score === 1) return {label: 'Possible', cls: 'warn', score};
      return {label: 'Unclear', cls: 'warn', score};
    }

    function extractVolumeGuess(issue, series) {
      const cands = [issue?.name, issue?.title, series?.name, issue?.deck, series?.deck, issue?.description, series?.description].filter(Boolean).join(' ');
      const m = cands.match(/(?:volume|vol\.?|v\.)\s*(\d+)/i);
      if (m) return m[1];
      return '';
    }

    function firstCreditNames(personCredits, roleNames) {
      if (!Array.isArray(personCredits) || !personCredits.length) return '';
      const wanted = roleNames.map(x => String(x || '').toLowerCase());
      const names = personCredits
        .filter(c => wanted.some(w => String(c.role || '').toLowerCase().includes(w)))
        .map(c => (c.person && c.person.name) || '')
        .filter(Boolean);
      return names.join(', ');
    }

    function dedupeKeepOrder(arr) {
      const seen = new Set();
      const out = [];
      (arr || []).forEach(v => {
        const key = String(v || '');
        if (!key || seen.has(key)) return;
        seen.add(key);
        out.push(key);
      });
      return out;
    }

    function setFieldWithCandidates(fieldId, preferred, candidates) {
      const el = document.getElementById(fieldId);
      const values = dedupeKeepOrder([preferred, ...(candidates || [])]);
      if (!el) return;
      el.value = values.length ? values[0] : '';
      el.dataset.candidates = JSON.stringify(values.slice(1));
      el.setAttribute('title', values.length > 1 ? ('Alternatives: ' + values.slice(1).join(' | ')) : '');
    }

    function fillMappingFromIssue(issue) {
      appState.lastIssue = issue || {};
      const volume = issue.volume || {};
      const details = appState.volumeDetails || {};
      const coverDate = String(issue.cover_date || '');
      const publishedYear = coverDate.length >= 4 ? coverDate.slice(0,4) : '';
      const seriesStartYear = details.start_year || volume.start_year || '';
      const titleCandidate = issue.name || issue.title || '';
      const issueTitleAlt = issue.title || '';
      const pubFromIssue = (volume.publisher && volume.publisher.name) || '';
      const pubFromDetails = details.publisher ? (details.publisher.name || '') : '';
      const publisherCandidates = [pubFromDetails, pubFromIssue];

      setFieldWithCandidates('map_series', volume.name || details.name || '', [details.name || '']);
      setFieldWithCandidates('map_issue', issue.issue_number || '', []);
      setFieldWithCandidates('map_title', titleCandidate, [issueTitleAlt, (details.first_issue || {}).name || '']);
      setFieldWithCandidates('map_issue_name', titleCandidate, [issueTitleAlt]);
      setFieldWithCandidates('map_year', publishedYear, []);
      setFieldWithCandidates('map_published_year', publishedYear, []);
      setFieldWithCandidates('map_start_year', seriesStartYear, [publishedYear]);
      const guessedVolume = extractVolumeGuess(issue, details || {}) || extractVolumeGuess(issue, appState.lastSeries || {});
      setFieldWithCandidates('map_volume', guessedVolume || '1', [seriesStartYear]);
      setFieldWithCandidates('map_publisher', publisherCandidates[0] || '', publisherCandidates.slice(1));
      setFieldWithCandidates('map_issue_id', issue.id || '', []);
      setFieldWithCandidates('map_series_id', volume.id || details.id || '', []);
      setFieldWithCandidates('map_description', issue.description || issue.deck || details.deck || '', []);
      const dateParts = coverDate.split('-');
      setFieldWithCandidates('map_month', dateParts.length > 1 ? dateParts[1] : '', []);
      setFieldWithCandidates('map_day', dateParts.length > 2 ? dateParts[2] : '', []);

      const credits = issue.person_credits || [];
      setFieldWithCandidates('map_writer', firstCreditNames(credits, ['writer']), []);
      setFieldWithCandidates('map_cover_artist', firstCreditNames(credits, ['cover']), []);
      setFieldWithCandidates('map_editor', firstCreditNames(credits, ['editor']), []);
      setFieldWithCandidates('map_penciller', firstCreditNames(credits, ['penciller', 'pencil']), []);
      setFieldWithCandidates('map_inker', firstCreditNames(credits, ['inker', 'ink']), []);
      setFieldWithCandidates('map_colorist', firstCreditNames(credits, ['colorist', 'color']), []);
      setFieldWithCandidates('map_letterer', firstCreditNames(credits, ['letterer', 'letter']), []);

      const arc = (Array.isArray(issue.story_arc_credits) && issue.story_arc_credits.length) ? issue.story_arc_credits[0] : null;
      setFieldWithCandidates('map_story_arc', arc ? (arc.name || '') : '', []);
      setFieldWithCandidates('map_story_arc_num', '', []);
      setFieldWithCandidates('map_tags', '', []);
      setFieldWithCandidates('map_page_count', '', []);
      setFieldWithCandidates('map_isbn', '', []);
      setFieldWithCandidates('map_barcode', '', []);
      setFieldWithCandidates('map_language', details.site_detail_url ? 'en' : '', []);
    }

    function applyAltSource(target) {
      const issue = appState.lastIssue || {};
      const series = appState.lastSeries || {};
      const first = series.first_issue || {};
      if (target === 'title') {
        const src = document.getElementById('title_source').value;
        const pick = {
          manual: document.getElementById('map_title').value,
          issue_name: issue.name || '',
          issue_title: issue.title || '',
          series_first_issue_name: first.name || '',
          series_name: series.name || '',
        };
        document.getElementById('map_title').value = pick[src] || '';
      }
      if (target === 'issue_name') {
        const src = document.getElementById('issue_name_source').value;
        const pick = {
          manual: document.getElementById('map_issue_name').value,
          issue_name: issue.name || '',
          issue_title: issue.title || '',
          title_field: document.getElementById('map_title').value || '',
        };
        document.getElementById('map_issue_name').value = pick[src] || '';
      }
      if (target === 'volume') {
        const src = document.getElementById('volume_source').value;
        const volume = issue.volume || {};
        if (src === 'series_start_year') document.getElementById('map_volume').value = volume.start_year || '';
        else if (src === 'one') document.getElementById('map_volume').value = '1';
      }
    }

    async function buildSeriesAndIssueSelectors(data) {
      appState.cvData = data || {series:[], issues:[]};
      const md = parseLoadedMetadata();
      const seriesSel = document.getElementById('seriesSelect');
      const issueSel = document.getElementById('issueSelect');
      seriesSel.innerHTML = '';
      issueSel.innerHTML = '';

      let series = (data.series || []).slice();
      const issues = (data.issues || []).slice();
      if (!series.length && issues.length) {
        const byId = new Map();
        issues.forEach(i => {
          const v = i.volume || {};
          const key = String(v.id || '');
          if (!key || byId.has(key)) return;
          byId.set(key, { id: v.id, name: v.name, start_year: v.start_year, count_of_issues: v.count_of_issues });
        });
        series = Array.from(byId.values());
      }
      if (!series.length) {
        document.getElementById('seriesHint').textContent = 'No series options found for this query.';
        document.getElementById('issueHint').textContent = 'Try a broader ComicVine search query.';
        return;
      }

      const scored = series.map(s => {
        const name = String(s.name || '').toLowerCase();
        const score = (md.series && name.includes(String(md.series).toLowerCase()) ? 2 : 0) +
                      (md.year && String(md.year) === String(s.start_year || '') ? 1 : 0);
        return {s, score};
      });
      scored.sort((a,b) => b.score - a.score);

      scored.forEach((x, idx) => {
        const opt = document.createElement('option');
        opt.value = String(x.s.id || '');
        opt.textContent = `${x.s.name || ''} (${x.s.start_year || '?'}) [${x.s.count_of_issues || '?'} issues]`;
        if (idx === 0) opt.selected = true;
        seriesSel.appendChild(opt);
      });

      document.getElementById('seriesHint').textContent = 'Best guess preselected from current metadata.';
      await onSeriesSelected();

      // reference tables
      const seriesBody = document.querySelector('#seriesTable tbody');
      seriesBody.innerHTML = '';
      scored.forEach(x => {
        const s = x.s;
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${s.name || ''}</td><td>${s.start_year || ''}</td><td>${s.count_of_issues || ''}</td><td>${s.id || ''}</td>`;
        tr.onclick = () => { seriesSel.value = String(s.id || ''); onSeriesSelected(); };
        seriesBody.appendChild(tr);
      });

      const issueBody = document.querySelector('#issueTable tbody');
      issueBody.innerHTML = '';
      issues.forEach(i => {
        const volume = i.volume || {};
        const hint = looksLikeMatch(md, i);
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><span class='pill ${hint.cls}'>${hint.label}</span></td><td>${i.issue_number || ''}</td><td>${i.name || i.title || ''}</td><td>${volume.name || ''}</td><td>${volume.start_year || ''}</td><td>${i.cover_date || ''}</td><td>${i.id || ''}</td>`;
        tr.onclick = () => { selectSeriesByIssue(i); };
        issueBody.appendChild(tr);
      });
    }

    async function selectSeriesByIssue(issue) {
      const sid = String((issue.volume || {}).id || '');
      const seriesSel = document.getElementById('seriesSelect');
      if (sid) {
        for (const opt of seriesSel.options) {
          if (opt.value === sid) { seriesSel.value = sid; break; }
        }
      }
      await onSeriesSelected(issue);
    }

    async function onSeriesSelected(preferredIssue=null) {
      const seriesSel = document.getElementById('seriesSelect');
      const sid = seriesSel.value;
      const data = appState.cvData || {series:[], issues:[]};
      const series = (data.series || []).find(s => String(s.id || '') === sid) || null;
      appState.lastSeries = series;
      appState.volumeDetails = null;
      if (series) {
        document.getElementById('map_series').value = series.name || '';
        document.getElementById('map_start_year').value = series.start_year || '';
        document.getElementById('map_series_id').value = series.id || '';
        const apiKeyForDetails = (document.getElementById('apiKey').value || '').trim();
        try {
          const qd = '/api/comicvine/series_details?series_id=' + encodeURIComponent(sid) + (apiKeyForDetails ? '&api_key=' + encodeURIComponent(apiKeyForDetails) : '');
          const rd = await fetch(qd);
          const detailsPayload = await rd.json();
          appState.volumeDetails = detailsPayload.series || null;
          if (appState.volumeDetails && appState.volumeDetails.start_year) {
            document.getElementById('map_start_year').value = appState.volumeDetails.start_year;
          }
        } catch (_) {}
      }

      const issueSel = document.getElementById('issueSelect');
      issueSel.innerHTML = '';
      const apiKey = (document.getElementById('apiKey').value || '').trim();
      let issues = [];
      try {
        const q = '/api/comicvine/issues_for_series?series_id=' + encodeURIComponent(sid) + (apiKey ? '&api_key=' + encodeURIComponent(apiKey) : '');
        const r = await fetch(q);
        const payload = await r.json();
        issues = payload.issues || [];
      } catch (_) {}
      if (!issues.length) {
        issues = (data.issues || []).filter(i => String((i.volume || {}).id || '') === sid);
      }
      if (!issues.length) issues = (data.issues || []).slice();
      appState.seriesIssues = issues;

      const md = parseLoadedMetadata();
      const preferredIssueNum = getPreferredIssueNumber();
      issues.sort((a,b) => {
        const as = looksLikeMatch(md,a).score + (normalizeIssue(a.issue_number||'') === preferredIssueNum ? 2 : 0);
        const bs = looksLikeMatch(md,b).score + (normalizeIssue(b.issue_number||'') === preferredIssueNum ? 2 : 0);
        return bs - as;
      });

      issues.forEach((i, idx) => {
        const opt = document.createElement('option');
        opt.value = String(i.id || '');
        opt.textContent = `#${i.issue_number || '?'} - ${i.name || i.title || '(no name)'} (${i.cover_date || '?'})`;
        if (preferredIssue && String(preferredIssue.id||'') === String(i.id||'')) opt.selected = true;
        else if (!preferredIssue && normalizeIssue(i.issue_number||'') === preferredIssueNum) opt.selected = true;
        else if (!preferredIssue && idx === 0) opt.selected = true;
        issueSel.appendChild(opt);
      });

      // publisher majority chooser
      const pubs = issues.map(i => ((i.volume||{}).publisher||{}).name).filter(Boolean);
      if (appState.volumeDetails && appState.volumeDetails.publisher && appState.volumeDetails.publisher.name) pubs.push(appState.volumeDetails.publisher.name);
      const counts = new Map();
      pubs.forEach(p => counts.set(p, (counts.get(p)||0)+1));
      const ordered = [...counts.entries()].sort((a,b)=>b[1]-a[1]);
      const pubSel = document.getElementById('publisherChoice');
      pubSel.innerHTML = '';
      ordered.forEach(([name, c], idx) => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = `${name} (${c})`;
        if (idx === 0) opt.selected = true;
        pubSel.appendChild(opt);
      });
      if (ordered.length) {
        document.getElementById('map_publisher').value = ordered[0][0];
        document.getElementById('publisherHint').textContent = 'Most common publisher preselected; alternatives available.';
      }

      onIssueSelected();
    }

    function onIssueSelected() {
      const issueSel = document.getElementById('issueSelect');
      const iid = issueSel.value;
      const fallbackIssues = (appState.cvData && appState.cvData.issues) ? appState.cvData.issues : [];
      const issue = (appState.seriesIssues || []).find(i => String(i.id || '') === iid) || fallbackIssues.find(i => String(i.id || '') === iid);
      if (issue) {
        fillMappingFromIssue(issue);
        document.getElementById('issueHint').textContent = 'Best-guess issue preselected; adjust if needed.';
      }
    }

    function onPublisherChoice() {
      const sel = document.getElementById('publisherChoice');
      if (sel.value) document.getElementById('map_publisher').value = sel.value;
    }


    function setStatus(msg, isError=false) {
      const el = document.getElementById('writeStatus');
      if (!el) return;
      el.textContent = msg || '';
      el.style.color = isError ? '#9b1c1c' : '#145a2a';
    }

    function combinePickedFolderWithCurrentPath(currentPath, pickedFolderName) {
      const current = String(currentPath || '').trim();
      const picked = String(pickedFolderName || '').trim();
      if (!picked) return current;
      if (!current) return picked;
      const normalized = current.replace(/\\/g, '/').replace(/\/+$/, '');
      if (!normalized) return picked;
      const idx = normalized.lastIndexOf('/');
      if (idx < 0) return picked;
      const parent = normalized.slice(0, idx);
      if (!parent) return '/' + picked;
      return parent + '/' + picked;
    }

    async function browseLibraryPath() {
      const input = document.getElementById('rootPath');
      const current = (input.value || '').trim();

      if (window.showDirectoryPicker) {
        try {
          const handle = await window.showDirectoryPicker();
          if (handle && handle.name) {
            input.value = combinePickedFolderWithCurrentPath(current, handle.name);
            savePersistentFields();
            setStatus('Folder selected: ' + input.value + '. Confirm it matches the server path, then Scan.', false);
            return;
          }
        } catch (_) {
          // user cancelled or browser blocked picker; fall back to prompt
        }
      }

      const entered = window.prompt('Enter folder path to scan on the server:', current || '');
      if (entered == null) return;
      input.value = String(entered).trim();
      savePersistentFields();
      setStatus('Library path set. Click Scan to scan this folder.', false);
    }

    function browseComicFile() {
      document.getElementById('comicPathPicker').click();
    }

    function onComicFilePicked(evt) {
      const files = (evt && evt.target && evt.target.files) ? Array.from(evt.target.files) : [];
      if (!files.length) return;
      const f = files[0];
      const rel = f.webkitRelativePath || f.name || '';
      document.getElementById('comicPath').value = rel;
      if (!document.getElementById('writePath').value) document.getElementById('writePath').value = rel;
      savePersistentFields();
      setStatus('File selected in browser. If server path differs, paste absolute path manually.', false);
    }

    function browseWritePath() {
      document.getElementById('writePathPicker').click();
    }

    function onWriteFilePicked(evt) {
      const files = (evt && evt.target && evt.target.files) ? Array.from(evt.target.files) : [];
      if (!files.length) return;
      const f = files[0];
      const rel = f.webkitRelativePath || f.name || '';
      document.getElementById('writePath').value = rel;
      savePersistentFields();
      setStatus('Write target selected in browser. If server path differs, paste absolute path manually.', false);
    }

    function setWritePathFromSelected() {
      const path = (document.getElementById('comicPath').value || '').trim();
      if (!path) return alert('Select a comic file first.');
      document.getElementById('writePath').value = path;
      savePersistentFields();
      setStatus('Write target set to selected file.', false);
    }

    async function scanLibrary() {
      const root = document.getElementById('rootPath').value.trim();
      if (!root) return alert('Enter a library path first.');
      const res = await fetch('/api/scan?root=' + encodeURIComponent(root));
      const data = await res.json();
      const tbody = document.querySelector('#scanTable tbody');
      tbody.innerHTML = '';
      (data.results || []).forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.path || ''}</td><td>${r.pages ?? ''}</td><td>${r.has_cix ?? ''}</td><td>${r.has_cbi ?? ''}</td><td>${r.has_comet ?? ''}</td><td>${r.error || ''}</td>`;
        tr.onclick = () => { if (r.path) { document.getElementById('comicPath').value = r.path; if (!document.getElementById('writePath').value) document.getElementById('writePath').value = r.path; savePersistentFields(); } };
        tbody.appendChild(tr);
      });
    }

    async function readMetadata() {
      const path = document.getElementById('comicPath').value.trim();
      const style = document.getElementById('style').value;
      if (!path) return alert('Select or enter a comic file path first.');
      setStatus('Reading metadata…', false);
      const res = await fetch('/api/read?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style));
      const data = await res.json();
      showJson('metadataJson', data);
      if (data.style) document.getElementById('style').value = data.style;
      if (!document.getElementById('writePath').value) document.getElementById('writePath').value = path;
      savePersistentFields();
      document.getElementById('styleInfo').textContent = data.detected_style ? `Detected: ${data.detected_style}` : 'Detected: none';
      renderSummary(data.summary || {});
      const thumb = '/api/thumbnail?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style) + '&_=' + Date.now();
      document.getElementById('coverThumb').src = thumb;
      setStatus('Metadata loaded.', false);
    }

    async function assessFile() {
      const path = document.getElementById('comicPath').value.trim();
      const style = document.getElementById('style').value;
      if (!path) return alert('Select or enter a comic file path first.');
      setStatus('Assessing file…', false);
      const res = await fetch('/api/assess?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style));
      const data = await res.json();
      showJson('assessmentJson', data);
      if (data.summary) renderSummary(data.summary);
      if (data.recommended_metadata) showJson('metadataJson', { metadata: data.recommended_metadata });
      if (data.style) document.getElementById('style').value = data.style;
      document.getElementById('styleInfo').textContent = data.detected_style ? `Detected: ${data.detected_style}` : 'Detected: none';
      const thumb = '/api/thumbnail?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style) + '&_=' + Date.now();
      document.getElementById('coverThumb').src = thumb;
      setStatus('Assessment complete. Review recommended metadata, then write.', false);
    }

    function escapeRegexLiteral(text) {
      const bs = String.fromCharCode(92);
      const specials = new Set([bs, '^', '$', '.', '*', '+', '?', '(', ')', '[', ']', '{', '}', '|']);
      return Array.from(String(text || '')).map(ch => (specials.has(ch) ? (bs + ch) : ch)).join('');
    }

    function patternToRegex(pattern) {
      const tokenMap = {
        Series: 'series', IssueNumber: 'issue', VolumeNumber: 'volume', Year: 'year', Title: 'title',
        Publisher: 'publisher', Month: 'month', Day: 'day'
      };
      const parts = [];
      let idx = 0;
      const norm = String(pattern || '').trim();
      const tokenRe = /\{([A-Za-z][A-Za-z0-9_]*)\}/g;
      let m;
      while ((m = tokenRe.exec(norm)) !== null) {
        const lit = norm.slice(idx, m.index);
        parts.push(escapeRegexLiteral(lit));
        const token = m[1];
        const key = tokenMap[token] || token.toLowerCase();
        parts.push('(?<' + key + '>.+?)');
        idx = m.index + m[0].length;
      }
      parts.push(escapeRegexLiteral(norm.slice(idx)));
      const source = '^' + parts.join('') + '$';
      return new RegExp(source, 'i');
    }

    async function previewPatternParse() {
      const path = document.getElementById('comicPath').value.trim();
      const pattern = document.getElementById('pathPattern').value.trim();
      if (!path) return alert('Select or enter a comic file path first.');
      if (!pattern) return alert('Enter a parse pattern first.');
      const bs = String.fromCharCode(92);
      const rel = path.split(bs).join('/');
      const normalized = rel.replace(/[.][^./]+$/, '');
      const rx = patternToRegex(pattern.split(bs).join('/'));
      const match = normalized.match(rx);
      const out = match && match.groups ? match.groups : {};
      showJson('patternParseJson', { pattern, source: normalized, extracted: out });
      savePersistentFields();
    }

    function applyPatternParseToMapping() {
      let obj;
      try { obj = JSON.parse(document.getElementById('patternParseJson').value || '{}'); }
      catch (e) { return alert('Pattern parse JSON is invalid: ' + e); }
      const parsed = obj.extracted || {};
      const map = {
        series: 'map_series', issue: 'map_issue', volume: 'map_volume', year: 'map_year',
        title: 'map_title', publisher: 'map_publisher', month: 'map_month', day: 'map_day'
      };
      Object.keys(map).forEach(k => {
        if (parsed[k] != null && parsed[k] !== '') document.getElementById(map[k]).value = String(parsed[k]);
      });
    }

    function applySelectedComicVineFields() {

      let wrapper;
      try { wrapper = JSON.parse(document.getElementById('metadataJson').value || '{}'); }
      catch (e) { return alert('Metadata JSON is invalid: ' + e); }
      const md = (wrapper.metadata && typeof wrapper.metadata === 'object') ? wrapper.metadata : wrapper;

      const fields = [
        ['series', 'use_series', 'map_series'], ['issue', 'use_issue', 'map_issue'], ['title', 'use_title', 'map_title'],
        ['issueName', 'use_issue_name', 'map_issue_name'], ['publisher', 'use_publisher', 'map_publisher'],
        ['year', 'use_year', 'map_year'], ['volume', 'use_volume', 'map_volume'], ['startYear', 'use_start_year', 'map_start_year'],
        ['publishedYear', 'use_published_year', 'map_published_year'], ['comicVineIssueId', 'use_issue_id', 'map_issue_id'],
        ['comicVineSeriesId', 'use_series_id', 'map_series_id'], ['description', 'use_description', 'map_description'],
        ['month', 'use_month', 'map_month'], ['day', 'use_day', 'map_day'], ['writer', 'use_writer', 'map_writer'],
        ['coverArtist', 'use_cover_artist', 'map_cover_artist'], ['editor', 'use_editor', 'map_editor'],
        ['storyArc', 'use_story_arc', 'map_story_arc'], ['storyArcNumber', 'use_story_arc_num', 'map_story_arc_num'],
        ['tags', 'use_tags', 'map_tags'], ['pageCount', 'use_page_count', 'map_page_count'], ['isbn', 'use_isbn', 'map_isbn'],
        ['barcode', 'use_barcode', 'map_barcode'], ['language', 'use_language', 'map_language'],
        ['penciller', 'use_penciller', 'map_penciller'], ['inker', 'use_inker', 'map_inker'],
        ['colorist', 'use_colorist', 'map_colorist'], ['letterer', 'use_letterer', 'map_letterer'],
      ];
      fields.forEach(([k, c, i]) => {
        if (document.getElementById(c) && document.getElementById(c).checked) {
          const v = document.getElementById(i).value;
          md[k] = v === '' ? null : v;
        }
      });

      if (wrapper.metadata && typeof wrapper.metadata === 'object') { wrapper.metadata = md; showJson('metadataJson', wrapper); }
      else showJson('metadataJson', md);
    }

    async function writeFromJsonPayload(payload) {
      const path = document.getElementById('comicPath').value.trim();
      const writePath = (document.getElementById('writePath').value || '').trim();
      const style = document.getElementById('style').value;
      if (!path) return alert('Select or enter a comic file path first.');
      const patch = payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : payload;
      setStatus('Writing metadata to file…', false);
      try {
        const res = await fetch('/api/write', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ path, write_path: writePath, style, metadata: patch })
        });
        const out = await res.json();
        showJson('metadataJson', out);
        if (res.ok && out.ok) setStatus('Metadata written to: ' + (out.written_path || out.path || ''), false);
        else setStatus('Write failed: ' + (out.error || 'unknown error'), true);
      } catch (err) {
        setStatus('Write failed: ' + (err && err.message ? err.message : 'request failed'), true);
      }
    }

    async function writeMetadata() {
      applySelectedComicVineFields();
      let obj;
      try { obj = JSON.parse(document.getElementById('metadataJson').value || '{}'); }
      catch (e) { return alert('Metadata JSON is invalid: ' + e); }
      await writeFromJsonPayload(obj);
    }

    async function writeManualMetadata() {
      let obj;
      try { obj = JSON.parse(document.getElementById('metadataJson').value || '{}'); }
      catch (e) { return alert('Metadata JSON is invalid: ' + e); }
      await writeFromJsonPayload(obj);
    }

    async function loadRuntimeDiagnostics() {
      const el = document.getElementById('diagBanner');
      if (!el) return;
      try {
        const res = await fetch('/api/version');
        const data = await res.json();
        const features = (data.features || []).join(', ') || 'none';
        el.textContent = `Running ${data.server_version || 'ComicWebUI'} build ${data.git_commit || 'unknown'} from ${data.module_path || ''}; features: ${features}.`;
      } catch (_) {
        el.textContent = 'Runtime diagnostics unavailable. Confirm server process/check-out if UI looks stale.';
      }
    }

    async function searchComicVine() {
      const query = document.getElementById('cvQuery').value.trim();
      const apiKey = document.getElementById('apiKey').value.trim();
      if (!query) return alert('Enter a ComicVine search query first.');
      setStatus('Searching ComicVine…', false);
      const qp = '/api/comicvine/search?query=' + encodeURIComponent(query) + (apiKey ? '&api_key=' + encodeURIComponent(apiKey) : '');
      const res = await fetch(qp);
      const data = await res.json();
      showJson('comicvineJson', data);
      if (!res.ok || data.error) {
        setStatus('ComicVine search failed: ' + (data.error || ('HTTP ' + res.status)), true);
        return;
      }
      await buildSeriesAndIssueSelectors(data);
      setStatus('ComicVine search complete.', false);
    }

    loadPersistentFields();
    loadRuntimeDiagnostics();
  </script>
</body>
</html>"""

STYLE_MAP = {"CBI": MetaDataStyle.CBI, "CIX": MetaDataStyle.CIX, "COMET": MetaDataStyle.COMET}


@dataclass
class ComicSummary:
    path: str
    pages: int
    has_cix: bool
    has_cbi: bool
    has_comet: bool


def metadata_to_dict(md):
    if md is None:
        return {}
    out = {}
    for k, v in vars(md).items():
        if k.startswith("_") or callable(v):
            continue
        out[k] = v
    return out


def metadata_summary(md_dict, detected_style, used_style):
    return {
        "series": md_dict.get("series"), "issue": md_dict.get("issue"), "title": md_dict.get("title"),
        "volume": md_dict.get("volume"), "year": md_dict.get("year"), "publisher": md_dict.get("publisher"),
        "detected_style": detected_style, "used_style": used_style,
    }


def build_assessment(ca, path, requested_style):
    detected_style = detect_style(ca)
    use_style = choose_style(requested_style, detected_style)
    current_md = ca.readMetadata(STYLE_MAP[use_style])
    current_md_dict = metadata_to_dict(current_md)
    filename_md_dict = metadata_to_dict(ca.metadataFromFilename(parse_scan_info=True))
    recommended = dict(current_md_dict)
    for key in ("series", "issue", "title", "volume", "year", "publisher", "scanInfo"):
        if not recommended.get(key) and filename_md_dict.get(key):
            recommended[key] = filename_md_dict[key]
    return {
        "path": path,
        "style": use_style,
        "detected_style": detected_style,
        "has_styles": {
            "CIX": ca.hasMetadata(MetaDataStyle.CIX),
            "CBI": ca.hasMetadata(MetaDataStyle.CBI),
            "COMET": ca.hasMetadata(MetaDataStyle.COMET),
        },
        "current_metadata": current_md_dict,
        "filename_metadata": filename_md_dict,
        "recommended_metadata": recommended,
        "summary": metadata_summary(recommended, detected_style, use_style),
    }


def apply_metadata(md, patch):
    for k, v in patch.items():
        setattr(md, k, v)


def detect_style(ca):
    for style_name in ("CIX", "CBI", "COMET"):
        if ca.hasMetadata(STYLE_MAP[style_name]):
            return style_name
    return None


def choose_style(requested_style, detected_style):
    return detected_style or "CIX" if requested_style == "AUTO" else requested_style


def cover_index_from_metadata(ca, md_dict):
    for page in (md_dict.get("pages") or []):
        ptype = str(page.get("Type", "")).lower()
        if "frontcover" in ptype:
            try:
                return int(page.get("Image", 0))
            except Exception:
                return 0
    cover_image_name = md_dict.get("coverImage")
    if cover_image_name:
        try:
            for idx, name in enumerate(ca.getPageNameList()):
                if name == cover_image_name:
                    return idx
        except Exception:
            pass
    return 0


def guess_content_type(blob):
    if blob.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if blob.startswith(b"\x89PNG"):
        return "image/png"
    if blob.startswith(b"GIF87a") or blob.startswith(b"GIF89a"):
        return "image/gif"
    if blob.startswith(b"RIFF") and blob[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


class Handler(BaseHTTPRequestHandler):
    server_version = "ComicWebUI/0.6"

    def _comicvine_client(self, qs):
        user_key = qs.get("api_key", [""])[0].strip()
        env_key = os.environ.get("COMICVINE_API_KEY", "").strip()
        key = user_key or env_key
        return ComicVineClient(key) if key else None

    def _json(self, status, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, status, payload, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(n) if n else b"{}"
        return json.loads(data.decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/version":
            module_path = str(Path(__file__).resolve())
            git_commit = "unknown"
            try:
                proc = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    text=True,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    timeout=1,
                    check=False,
                )
                if proc.returncode == 0:
                    git_commit = proc.stdout.strip() or "unknown"
            except Exception:
                pass
            return self._json(200, {
                "server_version": self.server_version,
                "git_commit": git_commit,
                "module_path": module_path,
                "features": ["assess", "browse_paths", "write_status", "version_endpoint"],
            })

        if parsed.path == "/api/scan":
            root = qs.get("root", [""])[0]
            if not root:
                return self._json(400, {"error": "root query param required"})
            exts = {".cbz", ".cbr", ".cbt", ".pdf", ".zip", ".rar"}
            results = []
            for p in Path(root).rglob("*"):
                if p.is_file() and p.suffix.lower() in exts:
                    try:
                        ca = ComicArchive(str(p), default_image_path=str(p))
                        summary = ComicSummary(str(p), ca.getNumberOfPages(), ca.hasMetadata(MetaDataStyle.CIX), ca.hasMetadata(MetaDataStyle.CBI), ca.hasMetadata(MetaDataStyle.COMET))
                        results.append(asdict(summary))
                    except Exception as exc:
                        results.append({"path": str(p), "error": str(exc)})
            return self._json(200, {"count": len(results), "results": results})

        if parsed.path == "/api/read":
            path = qs.get("path", [""])[0]
            style = qs.get("style", ["AUTO"])[0].upper()
            if not path:
                return self._json(400, {"error": "path query param required"})
            if style != "AUTO" and style not in STYLE_MAP:
                return self._json(400, {"error": "style must be AUTO, CIX, CBI, or COMET"})
            ca = ComicArchive(path, default_image_path=path)
            detected_style = detect_style(ca)
            use_style = choose_style(style, detected_style)
            md = ca.readMetadata(STYLE_MAP[use_style])
            md_dict = metadata_to_dict(md)
            return self._json(200, {
                "path": path,
                "style": use_style,
                "detected_style": detected_style,
                "has_styles": {"CIX": ca.hasMetadata(MetaDataStyle.CIX), "CBI": ca.hasMetadata(MetaDataStyle.CBI), "COMET": ca.hasMetadata(MetaDataStyle.COMET)},
                "metadata": md_dict,
                "summary": metadata_summary(md_dict, detected_style, use_style),
            })

        if parsed.path == "/api/assess":
            path = qs.get("path", [""])[0]
            style = qs.get("style", ["AUTO"])[0].upper()
            if not path:
                return self._json(400, {"error": "path query param required"})
            if style != "AUTO" and style not in STYLE_MAP:
                return self._json(400, {"error": "style must be AUTO, CIX, CBI, or COMET"})
            ca = ComicArchive(path, default_image_path=path)
            return self._json(200, build_assessment(ca, path, style))

        if parsed.path == "/api/parse_filename":
            path = qs.get("path", [""])[0]
            if not path:
                return self._json(400, {"error": "path query param required"})
            ca = ComicArchive(path, default_image_path=path)
            md = ca.metadataFromFilename(parse_scan_info=True)
            return self._json(200, {"path": path, "metadata": metadata_to_dict(md)})

        if parsed.path == "/api/thumbnail":
            path = qs.get("path", [""])[0]
            style = qs.get("style", ["AUTO"])[0].upper()
            if not path:
                return self._json(400, {"error": "path query param required"})
            if style != "AUTO" and style not in STYLE_MAP:
                return self._json(400, {"error": "style must be AUTO, CIX, CBI, or COMET"})
            try:
                ca = ComicArchive(path, default_image_path=path)
                detected_style = detect_style(ca)
                use_style = choose_style(style, detected_style)
                md = ca.readMetadata(STYLE_MAP[use_style])
                idx = cover_index_from_metadata(ca, metadata_to_dict(md))
                blob = ca.getPage(idx) or ca.getPage(0)
                if not blob:
                    return self._json(404, {"error": "No cover/page image found"})
                return self._bytes(200, blob, guess_content_type(blob))
            except Exception as exc:
                return self._json(500, {"error": str(exc)})

        if parsed.path == "/api/comicvine/issues_for_series":
            series_id = qs.get("series_id", [""])[0]
            if not series_id:
                return self._json(400, {"error": "series_id required"})
            client = self._comicvine_client(qs)
            if client is None:
                return self._json(400, {"error": "Provide api_key query param or set COMICVINE_API_KEY environment variable"})
            issues = client.volume_issues(series_id, limit=200)
            return self._json(200, {"series_id": series_id, "issues": issues})

        if parsed.path == "/api/comicvine/series_details":
            series_id = qs.get("series_id", [""])[0]
            if not series_id:
                return self._json(400, {"error": "series_id required"})
            client = self._comicvine_client(qs)
            if client is None:
                return self._json(400, {"error": "Provide api_key query param or set COMICVINE_API_KEY environment variable"})
            series = client.volume_details(series_id)
            return self._json(200, {"series_id": series_id, "series": series})

        if parsed.path == "/api/comicvine/search":
            query = qs.get("query", [""])[0]
            if not query:
                return self._json(400, {"error": "query required"})
            client = self._comicvine_client(qs)
            if client is None:
                return self._json(400, {"error": "Provide api_key query param or set COMICVINE_API_KEY environment variable"})
            series = client.search_series(query)
            issues = client.search_issue(query)
            return self._json(200, {"query": query, "series": series, "issues": issues})

        return self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/write":
            return self._json(404, {"error": "not found"})

        payload = self._read_json()
        path = payload.get("path", "")
        write_path = payload.get("write_path", "")
        style = str(payload.get("style", "AUTO")).upper()
        patch = payload.get("metadata", {})
        if not path:
            return self._json(400, {"error": "path is required"})
        if style != "AUTO" and style not in STYLE_MAP:
            return self._json(400, {"error": "style must be AUTO, CIX, CBI, or COMET"})

        target_path = write_path.strip() or path
        if target_path != path:
            target_dir = os.path.dirname(os.path.abspath(target_path))
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(path, target_path)

        try:
            ca = ComicArchive(target_path, default_image_path=target_path)
            detected_style = detect_style(ca)
            use_style = choose_style(style, detected_style)
            md = ca.readMetadata(STYLE_MAP[use_style])
            if getattr(md, "isEmpty", False):
                md = ca.metadataFromFilename(parse_scan_info=True)
            apply_metadata(md, patch)
            ok = ca.writeMetadata(md, STYLE_MAP[use_style])
            if not ok:
                return self._json(500, {"ok": False, "error": "Metadata write returned false", "path": path, "written_path": target_path, "style": use_style, "detected_style": detected_style})
            return self._json(200, {"ok": True, "path": path, "written_path": target_path, "style": use_style, "detected_style": detected_style})
        except Exception as exc:
            return self._json(500, {"ok": False, "error": str(exc), "path": path, "written_path": target_path})


def run(host="127.0.0.1", port=8080):
    srv = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"Serving Comic Metadata UI at http://{host}:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    run(host=os.environ.get("COMIC_WEBUI_HOST", "127.0.0.1"), port=os.environ.get("COMIC_WEBUI_PORT", "8080"))
