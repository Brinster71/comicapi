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
    :root{
      --bg1:#fff8db; --bg2:#fff1a8; --bg3:#ffe082; --ink:#4a2b00;
      --muted:rgba(74,43,0,.68); --line:rgba(74,43,0,.10); --line-strong:rgba(74,43,0,.18);
      --card:rgba(255,255,255,.42); --card-strong:rgba(255,255,255,.62);
      --shadow:0 20px 48px rgba(117,74,0,.10); --shadow-soft:0 10px 26px rgba(117,74,0,.06);
      --radius-xl:1.35rem; --radius-lg:1rem; --radius-pill:999px; --max:1560px;
    }
    *{ box-sizing:border-box; }
    html, body{ height:100%; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(250,204,21,.35), transparent 26%),
        radial-gradient(circle at bottom right, rgba(251,191,36,.28), transparent 30%),
        radial-gradient(circle at 80% 20%, rgba(253,224,71,.22), transparent 22%),
        linear-gradient(180deg, var(--bg1) 0%, var(--bg2) 52%, var(--bg3) 100%);
      overflow-x: hidden;
    }
    .page {
      max-width: var(--max);
      padding: 1rem 1rem 2rem;
      margin-left: auto;
      margin-right: auto;
    }
    .top-shell {
      border: 1px solid var(--line);
      border-radius: 1.5rem;
      background: var(--card);
      backdrop-filter: blur(14px);
      box-shadow: var(--shadow);
      padding: 1rem 1rem .75rem;
      margin-bottom: .8rem;
    }
    .titlebar {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:1rem;
      margin-bottom:.65rem;
    }
    .title-left {
      display:flex;
      align-items:center;
      gap:.8rem;
    }
    .mark {
      width:2.25rem;
      height:2.25rem;
      border-radius:.75rem;
      display:grid;
      place-items:center;
      background:#4a2b00;
      color:#fde68a;
      font-weight:800;
    }
    .eyebrow {
      font-size:.74rem;
      text-transform:uppercase;
      letter-spacing:.16em;
      color:rgba(74,43,0,.55);
    }
    h1 {
      margin:.05rem 0 0;
      font-size:1.16rem;
      line-height:1.1;
    }
    .hero-pills {
      display:flex;
      flex-wrap:wrap;
      gap:.5rem;
    }
    .hero-pill {
      border:1px solid var(--line);
      background:rgba(255,251,235,.76);
      border-radius:999px;
      padding:.4rem .72rem;
      font-size:.78rem;
      font-weight:700;
    }
    h2 {
      margin: .2rem auto .35rem;
      font-size: 1.08rem;
      letter-spacing: -.01em;
    }
    h3 {
      margin: 1.05rem auto .4rem;
      font-size: 1.1rem;
      letter-spacing: -.01em;
    }
    .row {
      display: flex;
      gap: .5rem;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: .6rem;
      padding: .55rem .65rem;
      border: 1px solid var(--line);
      border-radius: 1rem;
      background: var(--card);
      backdrop-filter: blur(10px);
      box-shadow: 0 10px 28px rgba(117,74,0,.06);
    }
    .muted { color: var(--muted); font-size: .92rem; }
    input, select, button, textarea {
      font: inherit;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: .85rem;
      background: rgba(255,255,255,.72);
      padding: .45rem .6rem;
      transition: border-color .18s ease, background-color .18s ease, transform .12s ease;
    }
    input:focus, select:focus, button:focus, textarea:focus {
      outline: none;
      border-color: rgba(234,179,8,.6);
      background: #fff;
    }
    button {
      background: #4a2b00;
      color: #fff4b5;
      font-weight: 600;
      cursor: pointer;
    }
    button:hover { transform: translateY(-1px); opacity: .95; }
    label { color: rgba(74,43,0,.86); }
    input[type=text] { min-width: 18rem; }
    textarea {
      width: 100%;
      min-height: 10rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      background: var(--card-strong);
    }
    table {
      border-collapse: separate;
      border-spacing: 0 .35rem;
      width: 100%;
      margin-top: .5rem;
      background: transparent;
    }
    th, td {
      border: none;
      padding: .58rem .62rem;
      text-align: left;
    }
    th {
      background: transparent;
      color: rgba(74,43,0,.54);
      text-transform: uppercase;
      font-size: .74rem;
      letter-spacing: .1em;
      padding: 0 .62rem .05rem;
    }
    td {
      background: var(--card-strong);
      border-top: 1px solid rgba(255,255,255,.46);
      border-bottom: 1px solid rgba(74,43,0,.05);
      vertical-align: top;
    }
    tr td:first-child { border-radius: .75rem 0 0 .75rem; }
    tr td:last-child { border-radius: 0 .75rem .75rem 0; }
    tr:hover td { background: rgba(255,255,255,.74); }
    .pill { border-radius: var(--radius-pill); padding: .1rem .5rem; font-size: .8rem; }
    .good { background: #d7f6dd; color: #145a2a; }
    .warn { background: #fff3cd; color: #7a5b00; }
    .grid2 { display:grid; grid-template-columns: 220px 1fr; gap:.4rem .8rem; align-items:start; }
    .meta-card {
      border:1px solid var(--line);
      padding:.8rem;
      border-radius:var(--radius-xl);
      margin:.65rem 0;
      background: var(--card);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }
    .thumb {
      width:180px;
      height:260px;
      object-fit:contain;
      border:1px solid var(--line);
      border-radius: .75rem;
      background: rgba(255,255,255,.8);
    }
    .mapping-grid { display:grid; grid-template-columns: 22px 160px 1fr; gap:.35rem .5rem; align-items:center; margin:.35rem 0; }
    .small { font-size:.85rem; }
    .tight { min-width: 8rem !important; }
    .status {
      margin-top:.45rem;
      font-size:.95rem;
      color:#145a2a;
      padding: .35rem .55rem;
      border-radius: .6rem;
      background: rgba(255,255,255,.52);
      border: 1px solid var(--line);
    }
    .diag {
      border:1px solid rgba(120,70,0,.14);
      background:rgba(255,247,223,.84);
      padding:.5rem .65rem;
      border-radius:.75rem;
      font-size:.83rem;
      margin-bottom:.65rem;
      box-shadow: 0 10px 26px rgba(117,74,0,.06);
    }
    #pathPickOverlay {
      position:fixed; inset:0;
      background:rgba(0,0,0,.55);
      display:flex; align-items:center; justify-content:center;
      z-index:9999;
    }
    .path-pick-card {
      background:#fff;
      border-radius:1rem;
      padding:1.4rem 1.8rem;
      max-width:520px; width:90%;
      box-shadow:0 8px 32px rgba(0,0,0,.35);
      display:flex; flex-direction:column; gap:.75rem;
    }
    .path-pick-card p { margin:0; font-size:.96rem; }
    .path-pick-card input[type=text] { width:100%; box-sizing:border-box; }
    .path-pick-btns { display:flex; gap:.5rem; justify-content:flex-end; }
    button:disabled { opacity:.55; cursor:wait; }
    button.btn-busy { opacity:.7; cursor:wait; }
    details {
      border: 1px solid var(--line);
      border-radius: 1rem;
      background: rgba(255,255,255,.45);
      padding: .5rem .7rem;
      margin: .55rem 0;
      box-shadow: var(--shadow-soft);
    }
    summary {
      cursor: pointer;
      font-weight: 600;
      color: rgba(74,43,0,.88);
      margin-bottom: .4rem;
    }
    .tabs {
      display: flex;
      gap: .5rem;
      margin-bottom: 0;
      padding: .55rem .65rem;
      border: 1px solid var(--line);
      border-radius: 1rem;
      background: var(--card);
      backdrop-filter: blur(10px);
      box-shadow: 0 10px 28px rgba(117,74,0,.06);
    }
    .tab-btn {
      background: rgba(255,255,255,.72);
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: var(--radius-pill);
      padding: .4rem .8rem;
      font-weight: 700;
    }
    .tab-btn.active {
      background: #4a2b00;
      color: #fff4b5;
      border-color: #4a2b00;
    }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: .6rem;
    }
    .section-head-title {
      display:flex;
      align-items:flex-end;
      gap:.45rem;
    }
    .section-head-title h3 {
      margin: 0;
      font-size: 1.28rem;
      font-weight: 900;
      letter-spacing: -.01em;
    }
    .scan-size-btn {
      font-size: .72rem;
      padding: .16rem .42rem;
      border-radius: .5rem;
      background: rgba(255,255,255,.62);
      color: rgba(74,43,0,.72);
      border: 1px solid var(--line);
      line-height: 1.1;
      transform: translateY(2px);
      opacity: .92;
    }
    .scan-size-btn:hover {
      transform: translateY(2px);
      background: rgba(255,255,255,.9);
      opacity: 1;
    }
    .section-head h3 {
      margin-bottom: .3rem;
    }
    .scan-results-shell {
      max-height: 11.5rem;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: .9rem;
      padding: .25rem .2rem .35rem;
      background: rgba(255,255,255,.28);
      transition: max-height .2s ease;
    }
    .scan-results-shell.expanded {
      max-height: 56vh;
    }
    .scan-results-shell thead th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: rgba(255,245,204,.95);
      backdrop-filter: blur(4px);
    }
    .bulk-hero {
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      background: var(--card);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
      padding: 1rem;
      margin-bottom: .75rem;
    }
    .bulk-cards {
      display: grid;
      grid-template-columns: repeat(5, minmax(110px, 1fr));
      gap: .5rem;
      margin-top: .6rem;
    }
    .bulk-card {
      border: 1px solid var(--line);
      border-radius: .9rem;
      background: rgba(255,255,255,.56);
      padding: .6rem;
      box-shadow: 0 10px 20px rgba(117,74,0,.05);
    }
    .bulk-layout {
      display: grid;
      grid-template-columns: 290px 1fr;
      gap: .6rem;
      align-items: start;
    }
    .bulk-panel {
      border: 1px solid var(--line);
      border-radius: 1rem;
      background: var(--card);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
      padding: .7rem;
    }
    .bulk-panel.is-collapsed {
      display: none;
    }
    .bulk-title {
      margin: 0 0 .5rem;
      font-size: 1rem;
      letter-spacing: -.01em;
    }
    .bulk-preview {
      margin-bottom: .6rem;
    }
    .bulk-preview table {
      margin-top: .35rem;
    }
    .bulk-actions {
      display: flex;
      flex-wrap: wrap;
      gap: .35rem;
      margin-bottom: .5rem;
    }
    .bulk-chip {
      padding: .3rem .55rem;
      border-radius: var(--radius-pill);
      background: rgba(255,255,255,.7);
      border: 1px solid var(--line);
      font-size: .82rem;
      color: var(--ink);
      font-weight: 600;
    }
    .bulk-chip.primary {
      background: #4a2b00;
      color: #fff4b5;
      border-color: #4a2b00;
    }
    button.is-active, .bulk-chip.is-active {
      background: #14532d;
      color: #dcfce7;
      border-color: #14532d;
    }
    .bulk-note {
      font-size: .84rem;
      color: var(--muted);
      margin-top: .35rem;
    }
    .naming-toolbar {
      display:flex;
      justify-content:space-between;
      align-items:center;
      gap:.5rem;
      flex-wrap: wrap;
    }
    .naming-bottom {
      display:flex;
      justify-content:space-between;
      align-items:center;
      gap:.5rem;
      flex-wrap: wrap;
      margin-top: .5rem;
    }
    .naming-preview {
      min-height: 6rem;
    }
    .naming-pattern-input {
      flex: 1 1 56rem;
      width: 100%;
      min-width: min(56rem, 100%);
    }
    .naming-destination-row {
      margin-top: .45rem;
    }
    .stacked-checkbox {
      display: inline-flex;
      align-items: flex-start;
      gap: .4rem;
      line-height: 1.05;
    }
    .stacked-checkbox .stacked-text {
      display: inline-flex;
      flex-direction: column;
      gap: .08rem;
    }
    .bulk-field-grid {
      display: grid;
      gap: .45rem;
      margin-top: .55rem;
    }
    .bulk-field-row {
      display: grid;
      grid-template-columns: 78px 1fr auto auto;
      gap: .4rem;
      align-items: center;
    }
    .bulk-field-row label {
      font-size: .82rem;
      color: var(--muted);
      font-weight: 700;
    }
    .bulk-apply {
      font-size: .78rem;
      padding: .32rem .52rem;
      border-radius: var(--radius-pill);
    }
    .gap-kpis {
      display: flex;
      flex-wrap: wrap;
      gap: .35rem;
      margin: .35rem 0 .2rem;
    }
    .gap-badge {
      display: inline-flex;
      align-items: center;
      gap: .25rem;
      padding: .18rem .52rem;
      border-radius: var(--radius-pill);
      border: 1px solid var(--line);
      background: rgba(255,255,255,.72);
      font-size: .77rem;
      font-weight: 700;
      color: rgba(74,43,0,.85);
    }
    .gap-badge.hit {
      background: rgba(220,252,231,.72);
      border-color: rgba(22,101,52,.24);
      color: #14532d;
    }
    .gap-badge.miss {
      background: rgba(255,237,213,.82);
      border-color: rgba(154,52,18,.22);
      color: #9a3412;
    }
    .gap-grid {
      display: grid;
      gap: .45rem;
      grid-template-columns: 1fr 1fr;
      margin-top: .35rem;
    }
    .gap-col {
      border: 1px solid var(--line);
      border-radius: .75rem;
      background: rgba(255,255,255,.62);
      padding: .45rem .5rem;
    }
    .gap-col h4 {
      margin: .1rem 0 .35rem;
      font-size: .84rem;
      color: rgba(74,43,0,.82);
    }
    .meta-kv {
      display: grid;
      grid-template-columns: 130px 1fr;
      gap: .2rem .5rem;
      padding: .15rem 0;
      border-bottom: 1px dashed rgba(74,43,0,.12);
      font-size: .81rem;
    }
    .meta-kv:last-child {
      border-bottom: none;
    }
    .meta-kv b {
      color: rgba(74,43,0,.84);
      font-weight: 700;
    }
    .meta-kv.meta-hit {
      background: linear-gradient(90deg, rgba(220,252,231,.42), transparent 64%);
    }
    .meta-kv.meta-miss {
      background: linear-gradient(90deg, rgba(255,237,213,.62), transparent 64%);
    }
    .is-hidden {
      display: none;
    }
    .bulk-search-row input[type=text] {
      min-width: 12rem;
      flex: 1 1 18rem;
    }
    #bulkCvSeriesSelect, #bulkCvIssueSelect {
      min-width: 14rem;
    }
    .bulk-queue-row.dragging {
      opacity: .55;
    }
    .bulk-queue-row.drop-target {
      outline: 2px dashed rgba(74,43,0,.42);
      outline-offset: -2px;
    }
    .drag-handle {
      cursor: grab;
      font-size: .95rem;
      user-select: none;
      color: rgba(74,43,0,.70);
    }
    .drag-handle:active {
      cursor: grabbing;
    }
    @media (max-width: 900px){
      .grid2 { grid-template-columns: 1fr; }
      .mapping-grid { grid-template-columns: 22px 130px 1fr; }
      input[type=text] { min-width: 14rem; }
      .bulk-layout { grid-template-columns: 1fr; }
      .bulk-cards { grid-template-columns: repeat(2, minmax(110px, 1fr)); }
      .bulk-field-row { grid-template-columns: 1fr; }
      .gap-grid { grid-template-columns: 1fr; }
      .meta-kv { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class='page'>
  <div class='top-shell'>
    <div class='titlebar'>
      <div class='title-left'>
        <div class='mark'>◈</div>
        <div>
          <div class='eyebrow'>Single-comic workflow</div>
          <h1>Comic Metadata UI</h1>
        </div>
      </div>
      <div class='hero-pills'>
        <div class='hero-pill'>AUTO style</div>
        <div class='hero-pill'>ComicVine linked</div>
        <div class='hero-pill'>Single + bulk flow</div>
      </div>
    </div>
    <div class='tabs'>
      <button id='tabSingleBtn' class='tab-btn active' onclick='switchTab("single")'>Single</button>
      <button id='tabBulkBtn' class='tab-btn' onclick='switchTab("bulk")'>Bulk identification</button>
    </div>
  </div>

  <div id='singleTab' class='tab-panel active'>
  <div id='diagBanner' class='diag'>Loading runtime diagnostics…</div>
  <p class='muted'>Single-comic workflow: scan, inspect detected metadata, choose series then issue, map fields, apply, write.</p>

  <div class='row'>
    <label>Library path:</label>
    <input id='rootPath' type='text' placeholder='/path/to/comics'>
    <button id='browseLibraryBtn' onclick='browseLibraryPath()'>Browse…</button>
    <input id='rootPathPicker' type='file' webkitdirectory directory style='display:none' onchange='onLibraryFolderPicked(event)'>
    <button onclick='scanLibrary()'>Scan</button>
  </div>

  <div class='row'>
    <label class='stacked-checkbox'><input id='scanRecursive' type='checkbox' checked><span class='stacked-text'><span>Recurse</span><span>over subfolders</span></span></label>
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

  <div class='section-head'>
    <div class='section-head-title'>
      <h3>Scan results</h3>
      <button id='scanSizeToggle' class='scan-size-btn' type='button' onclick='toggleScanResultsSize()' aria-expanded='false'>Expand</button>
    </div>
  </div>
  <div class='muted'>Click a row to select a comic file.</div>
  <div id='scanResultsShell' class='scan-results-shell'>
    <table id='scanTable'>
      <thead><tr><th>Path</th><th>Pages</th><th>CIX</th><th>CBI</th><th>COMET</th><th>Error</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

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

  <details>
    <summary>Naming Convention</summary>
    <div class='naming-toolbar'>
      <div class='row' style='margin:0; flex:1;'>
        <label>Pattern:</label>
        <input id='singleNamingPattern' class='naming-pattern-input' type='text' placeholder='{Series}/{VolumeNumber} - {Year}/{IssueNumber} - {Title}'>
        <button onclick='previewNaming("single")'>Preview naming</button>
        <button id='singleNamingApplyBtn' onclick='toggleNamingApply("single")'>Apply</button>
      </div>
      <div class='row' style='margin:0;'>
        <button onclick='saveNamingPattern("single")'>Save</button>
        <button onclick='previousNamingPattern("single")'>Previous</button>
      </div>
    </div>
    <div class='muted small'>Use variables like {Series}, {IssueNumber}, {VolumeNumber}, {Year}, {Title}, {Publisher}, {Month}, {Day}. Missing values fall back to variable names in preview.</div>
    <textarea id='singleNamingPreview' class='naming-preview' placeholder='Naming preview will appear here...' readonly></textarea>
    <div class='naming-bottom'>
      <button onclick='clearNamingSection("single")'>Clear</button>
      <button id='singleNamingOverrideBtn' onclick='toggleNamingOverride("single")'>Override</button>
    </div>
  </details>
  </div>

  <div id='bulkTab' class='tab-panel'>
    <section class='bulk-hero'>
      <h3 style='margin-top:0;'>Bulk Session Dashboard</h3>
      <div class='grid2 small'>
        <div><b>Batch root</b></div><div id='bulkRootLabel'>/comics/To Process/DC Bronze Age</div>
        <div><b>Parse pattern</b></div><div id='bulkPatternLabel'>{Series} ({Year}) #{IssueNumber}</div>
        <div><b>Write style target</b></div><div id='bulkStyleLabel'>ComicInfo.xml</div>
        <div><b>API status</b></div><div id='bulkApiLabel'>Ready</div>
      </div>
      <div class='bulk-cards'>
        <div class='bulk-card'><div class='small muted'>Files queued</div><div><b id='bulkCountQueued'>0</b></div></div>
        <div class='bulk-card'><div class='small muted'>Auto-matched</div><div><b id='bulkCountMatched'>0</b></div></div>
        <div class='bulk-card'><div class='small muted'>Needs review</div><div><b id='bulkCountReview'>0</b></div></div>
        <div class='bulk-card'><div class='small muted'>Conflicts</div><div><b id='bulkCountConflicts'>0</b></div></div>
        <div class='bulk-card'><div class='small muted'>Ready to write</div><div><b id='bulkCountReady'>0</b></div></div>
      </div>
      <div class='bulk-note'>This tab is the dedicated bulk-identification workflow surface. We can now iterate on behavior in-place.</div>
    </section>

    <section class='bulk-layout'>
      <section id='bulkPreviewPanel' class='bulk-panel bulk-preview is-collapsed' style='grid-column: 1 / -1;'>
        <h4 class='bulk-title'>Batch mapped metadata preview</h4>
        <div class='small muted'>Core mapped values are shown directly for fast review before write.</div>
        <table id='bulkPreviewTable'>
          <thead>
            <tr><th>Path</th><th>Series</th><th>Issue</th><th>Year</th><th>Publisher</th><th>Volume</th><th>Status</th><th>Confidence</th><th>Write</th></tr>
          </thead>
          <tbody></tbody>
        </table>
      </section>

      <aside class='bulk-panel'>
        <h4 class='bulk-title'>Batch controls</h4>
        <div class='row'>
          <label>Match mode:</label>
          <select id='bulkMatchMode' class='tight'>
            <option value='strict'>strict</option>
            <option value='balanced' selected>balanced</option>
            <option value='aggressive'>aggressive</option>
          </select>
          <button onclick='bulkAutoMatchSelected()'>Auto-match selected</button>
          <button onclick='bulkSortCurrentRows()'>Sort numerically</button>
        </div>
        <div class='row'>
          <button onclick='bulkSelectVisible(true)'>Select visible</button>
          <button onclick='bulkSelectVisible(false)'>Clear visible</button>
        </div>
        <div class='row'>
          <button class='bulk-chip primary' onclick='bulkWriteSelected()'>Write selected</button>
          <button class='bulk-chip' onclick='bulkRetryFailed()'>Retry failed</button>
        </div>
        <div class='row'>
          <label><input type='checkbox' id='bulkRuleExact' checked> Auto-apply exact series+issue</label>
        </div>
        <div class='row'>
          <label><input type='checkbox' id='bulkRulePublisher' checked> Auto-fill publisher/date/volume on high confidence</label>
        </div>
      </aside>

      <main class='bulk-panel'>
        <h4 class='bulk-title'>Bulk review queue</h4>
        <div class='row bulk-search-row'>
          <label>Library path:</label>
          <input id='bulkRootPath' type='text' placeholder='/path/to/comics'>
          <button id='browseBulkLibraryBtn' onclick='browseBulkLibraryPath()'>Browse…</button>
          <input id='bulkRootPathPicker' type='file' webkitdirectory directory style='display:none' onchange='onBulkLibraryFolderPicked(event)'>
          <button onclick='copySinglePathToBulk()'>Use single path</button>
          <label class='stacked-checkbox'><input id='bulkScanRecursive' type='checkbox' checked><span class='stacked-text'><span>Recurse</span><span>over subfolders</span></span></label>
          <button onclick='bulkScanFromRoot()'>Scan batch</button>
        </div>
        <div class='row bulk-search-row'>
          <label>ComicVine API key:</label>
          <input id='bulkApiKey' type='text' placeholder='leave empty to reuse single-comic API key'>
          <label>Search:</label>
          <input id='bulkCvQuery' type='text' list='bulkCvQueryList' placeholder='Series + issue, e.g. Death The High Cost Of Living 1'>
          <datalist id='bulkCvQueryList'></datalist>
          <button onclick='bulkSearchComicVine()'>Search ComicVine</button>
        </div>
        <div class='row bulk-search-row'>
          <label>Series:</label>
          <select id='bulkCvSeriesSelect' class='tight' onchange='onBulkCvSeriesSelected()'></select>
          <label>Issue:</label>
          <select id='bulkCvIssueSelect' class='tight' onchange='onBulkCvIssueSelected()'></select>
          <button onclick='bulkApplyCvToSelected()'>Apply to selected row</button>
          <button onclick='bulkApplyCvToBatch("selected")'>Apply to checked rows (by issue)</button>
          <button onclick='bulkApplyCvToBatch("visible")'>Apply to visible rows (by issue)</button>
          <span id='bulkCvHint' class='small muted'></span>
        </div>
        <div class='bulk-actions'>
          <button class='bulk-chip' onclick='bulkFilter("all")'>All</button>
          <button class='bulk-chip' onclick='bulkFilter("ready")'>Ready</button>
          <button class='bulk-chip' onclick='bulkFilter("review")'>Needs Review</button>
          <button class='bulk-chip' onclick='bulkFilter("conflict")'>Conflicts</button>
          <button class='bulk-chip' onclick='bulkFilter("written")'>Written</button>
          <button class='bulk-chip' onclick='bulkFilter("skip")'>Skipped</button>
        </div>
        <table id='bulkQueueTable'>
          <thead>
            <tr><th>↕</th><th></th><th>Status</th><th>Path</th><th>Series</th><th>Issue</th><th>Year</th><th>Best match</th><th>Confidence</th><th>Notes</th></tr>
          </thead>
          <tbody></tbody>
        </table>
        <details>
          <summary>Naming Convention (bulk)</summary>
          <div class='naming-toolbar'>
            <div class='row' style='margin:0; flex:1;'>
              <label>Pattern:</label>
              <input id='bulkNamingPattern' class='naming-pattern-input' type='text' placeholder='{Series}/{VolumeNumber} - {Year}/{IssueNumber} - {Title}'>
              <button onclick='previewNaming("bulk")'>Preview naming</button>
              <button id='bulkNamingApplyBtn' onclick='toggleNamingApply("bulk")'>Apply</button>
            </div>
            <div class='row' style='margin:0;'>
              <button onclick='saveNamingPattern("bulk")'>Save</button>
              <button onclick='previousNamingPattern("bulk")'>Previous</button>
            </div>
          </div>
          <div class='muted small'>Use variables like {Series}, {IssueNumber}, {VolumeNumber}, {Year}, {Title}, {Publisher}, {Month}, {Day}. Missing values fall back to variable names in preview.</div>
          <textarea id='bulkNamingPreview' class='naming-preview' placeholder='Naming preview will appear here...' readonly></textarea>
          <div class='naming-bottom'>
            <button onclick='clearNamingSection("bulk")'>Clear</button>
            <button id='bulkNamingOverrideBtn' onclick='toggleNamingOverride("bulk")'>Override</button>
          </div>
        </details>
      </main>

      <aside id='bulkInspectorPanel' class='bulk-panel is-collapsed' style='grid-column: 1 / -1;'>
        <h4 class='bulk-title'>Selected item inspector</h4>
        <div id='bulkInspectorSummary' class='small muted'>Select a row in the bulk queue to inspect details.</div>
        <div class='row'>
          <button id='bulkGapToggleBtn' type='button' class='bulk-chip' onclick='toggleBulkFieldGapSection()' aria-expanded='false'>Show field gap view</button>
        </div>
        <div id='bulkFieldGapSection' class='meta-card is-hidden'>
          <div id='bulkFieldGapSummary' class='small muted'>Press the button to compare ComicVine-available fields against what will be written.</div>
          <div id='bulkFieldGapBody' class='small muted'></div>
        </div>
        <div class='bulk-field-grid'>
          <div class='bulk-field-row'>
            <label for='bulkFieldSeries'>Series</label>
            <input id='bulkFieldSeries' type='text' oninput='bulkSetSelectedField("series", this.value)'>
            <button class='bulk-apply' onclick='bulkApplyFieldToOthers("series")'>Apply to rest</button>
            <button class='bulk-apply' onclick='bulkIncrementFieldFromSelected("series")'>Inc ↓</button>
          </div>
          <div class='bulk-field-row'>
            <label for='bulkFieldIssue'>Issue</label>
            <input id='bulkFieldIssue' type='text' oninput='bulkSetSelectedField("issue", this.value)'>
            <button class='bulk-apply' onclick='bulkApplyFieldToOthers("issue")'>Apply to rest</button>
            <button class='bulk-apply' onclick='bulkIncrementFieldFromSelected("issue")'>Inc ↓</button>
          </div>
          <div class='bulk-field-row'>
            <label for='bulkFieldYear'>Year</label>
            <input id='bulkFieldYear' type='text' oninput='bulkSetSelectedField("year", this.value)'>
            <button class='bulk-apply' onclick='bulkApplyFieldToOthers("year")'>Apply to rest</button>
            <button class='bulk-apply' onclick='bulkIncrementFieldFromSelected("year")'>Inc ↓</button>
          </div>
          <div class='bulk-field-row'>
            <label for='bulkFieldPublisher'>Publisher</label>
            <input id='bulkFieldPublisher' type='text' oninput='bulkSetSelectedField("publisher", this.value)'>
            <button class='bulk-apply' onclick='bulkApplyFieldToOthers("publisher")'>Apply to rest</button>
            <button class='bulk-apply' onclick='bulkIncrementFieldFromSelected("publisher")'>Inc ↓</button>
          </div>
          <div class='bulk-field-row'>
            <label for='bulkFieldVolume'>Volume</label>
            <input id='bulkFieldVolume' type='text' oninput='bulkSetSelectedField("volume", this.value)'>
            <button class='bulk-apply' onclick='bulkApplyFieldToOthers("volume")'>Apply to rest</button>
            <button class='bulk-apply' onclick='bulkIncrementFieldFromSelected("volume")'>Inc ↓</button>
          </div>
        </div>
        <details>
          <summary>Applied metadata (human-readable)</summary>
          <div id='bulkAppliedReadable' class='small muted'>Select a row to preview the exact metadata patch that will be written.</div>
        </details>
        <details>
          <summary>Detected metadata JSON</summary>
          <textarea id='bulkDetectedJson' readonly placeholder='Detected metadata for selected row'></textarea>
        </details>
        <details>
          <summary>Assessment JSON</summary>
          <textarea id='bulkAssessmentJson' readonly placeholder='Assessment for selected row'></textarea>
        </details>
      </aside>


    </section>
  </div>

  </div>

  <script>
    function showJson(id, obj) { document.getElementById(id).value = JSON.stringify(obj, null, 2); }

    const appState = {
      cvData: null,
      seriesIssues: [],
      lastIssue: null,
      lastSeries: null,
      volumeDetails: null,
      writePathManual: false,
      bulkRows: [],
      bulkSelectedId: null,
      bulkFilter: 'all',
      bulkDragId: null,
      bulkManualOrder: false,
      bulkCvData: null,
      bulkCvIssues: [],
      bulkGapVisible: false,
      naming: {
        single: { apply: false, override: false, history: [], historyIndex: -1 },
        bulk: { apply: false, override: false, history: [], historyIndex: -1 },
      },
    };

    const DEFAULT_NAMING_PATTERN = '{Series}/{VolumeNumber} - {Year}/{IssueNumber} - {Title}';

    function refreshWritePathManualFlag() {
      const comic = (document.getElementById('comicPath').value || '').trim();
      const write = (document.getElementById('writePath').value || '').trim();
      appState.writePathManual = Boolean(write) && write !== comic;
    }

    function maybeSyncWritePath(force=false) {
      const comic = (document.getElementById('comicPath').value || '').trim();
      const writeEl = document.getElementById('writePath');
      const write = (writeEl.value || '').trim();
      if (force || !appState.writePathManual || !write) {
        writeEl.value = comic;
        appState.writePathManual = false;
      }
    }

    function setComicPathValue(path) {
      document.getElementById('comicPath').value = path || '';
      maybeSyncWritePath(true);
      savePersistentFields();
    }

    function savePersistentFields() {
      localStorage.setItem('comicapi.rootPath', document.getElementById('rootPath').value || '');
      localStorage.setItem('comicapi.apiKey', document.getElementById('apiKey').value || '');
      localStorage.setItem('comicapi.comicPath', document.getElementById('comicPath').value || '');
      localStorage.setItem('comicapi.writePath', document.getElementById('writePath').value || '');
      localStorage.setItem('comicapi.pathPattern', document.getElementById('pathPattern').value || '');
      localStorage.setItem('comicapi.scanRecursive', document.getElementById('scanRecursive').checked ? '1' : '0');
      localStorage.setItem('comicapi.bulkScanRecursive', document.getElementById('bulkScanRecursive').checked ? '1' : '0');
      localStorage.setItem('comicapi.singleNamingPattern', document.getElementById('singleNamingPattern').value || '');
      localStorage.setItem('comicapi.bulkNamingPattern', document.getElementById('bulkNamingPattern').value || '');
      localStorage.setItem('comicapi.naming.single.apply', appState.naming.single.apply ? '1' : '0');
      localStorage.setItem('comicapi.naming.single.override', appState.naming.single.override ? '1' : '0');
      localStorage.setItem('comicapi.naming.bulk.apply', appState.naming.bulk.apply ? '1' : '0');
      localStorage.setItem('comicapi.naming.bulk.override', appState.naming.bulk.override ? '1' : '0');
      localStorage.setItem('comicapi.naming.single.history', JSON.stringify(appState.naming.single.history || []));
      localStorage.setItem('comicapi.naming.bulk.history', JSON.stringify(appState.naming.bulk.history || []));
    }

    function loadPersistentFields() {
      document.getElementById('rootPath').value = localStorage.getItem('comicapi.rootPath') || '';
      document.getElementById('apiKey').value = localStorage.getItem('comicapi.apiKey') || '';
      document.getElementById('comicPath').value = localStorage.getItem('comicapi.comicPath') || '';
      document.getElementById('writePath').value = localStorage.getItem('comicapi.writePath') || '';
      document.getElementById('pathPattern').value = localStorage.getItem('comicapi.pathPattern') || '{Series}/{VolumeNumber} - {Year}/{IssueNumber} - {Title}';
      document.getElementById('scanRecursive').checked = localStorage.getItem('comicapi.scanRecursive') !== '0';
      document.getElementById('bulkScanRecursive').checked = localStorage.getItem('comicapi.bulkScanRecursive') !== '0';
      document.getElementById('singleNamingPattern').value = localStorage.getItem('comicapi.singleNamingPattern') || DEFAULT_NAMING_PATTERN;
      document.getElementById('bulkNamingPattern').value = localStorage.getItem('comicapi.bulkNamingPattern') || DEFAULT_NAMING_PATTERN;
      appState.naming.single.apply = localStorage.getItem('comicapi.naming.single.apply') === '1';
      appState.naming.single.override = localStorage.getItem('comicapi.naming.single.override') === '1';
      appState.naming.bulk.apply = localStorage.getItem('comicapi.naming.bulk.apply') === '1';
      appState.naming.bulk.override = localStorage.getItem('comicapi.naming.bulk.override') === '1';
      try { appState.naming.single.history = JSON.parse(localStorage.getItem('comicapi.naming.single.history') || '[]'); }
      catch (_) { appState.naming.single.history = []; }
      try { appState.naming.bulk.history = JSON.parse(localStorage.getItem('comicapi.naming.bulk.history') || '[]'); }
      catch (_) { appState.naming.bulk.history = []; }
      appState.naming.single.historyIndex = appState.naming.single.history.length;
      appState.naming.bulk.historyIndex = appState.naming.bulk.history.length;
      if (!document.getElementById('writePath').value) document.getElementById('writePath').value = document.getElementById('comicPath').value;
      refreshWritePathManualFlag();
      ['rootPath','apiKey','comicPath','writePath','pathPattern','scanRecursive','bulkScanRecursive','singleNamingPattern','bulkNamingPattern'].forEach(id => document.getElementById(id).addEventListener('change', savePersistentFields));
      document.getElementById('comicPath').addEventListener('input', () => {
        maybeSyncWritePath(true);
        savePersistentFields();
      });
      document.getElementById('writePath').addEventListener('input', () => {
        refreshWritePathManualFlag();
        savePersistentFields();
      });
      ['singleNamingPattern', 'bulkNamingPattern'].forEach(id => document.getElementById(id).addEventListener('input', savePersistentFields));
      updateNamingButtons('single');
      updateNamingButtons('bulk');
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

    function normalizeSeriesId(val) {
      const s = String(val || '').trim();
      if (!s) return '';
      const parts = s.split('-').filter(Boolean);
      const tail = parts.length ? parts[parts.length - 1] : s;
      return tail.replace(/^0+/, '') || '0';
    }

    function sameSeriesId(a, b) {
      const x = normalizeSeriesId(a);
      const y = normalizeSeriesId(b);
      return Boolean(x && y && x === y);
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
      const m = path.match(/(?:^|[^\\d])(\\d{1,4})(?:[^\\d]|$)/);
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
      const m = cands.match(/(?:volume|vol\\.?|v\\.)\\s*(\\d+)/i);
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

    function buildSingleFlowMetadataFromIssue(issue, details=null, seriesFallback=null) {
      const srcIssue = issue || {};
      const volume = srcIssue.volume || {};
      const info = details || {};
      const seriesObj = seriesFallback || {};
      const coverDate = String(srcIssue.cover_date || '');
      const dateParts = coverDate.split('-');
      const credits = srcIssue.person_credits || [];
      const arc = (Array.isArray(srcIssue.story_arc_credits) && srcIssue.story_arc_credits.length) ? srcIssue.story_arc_credits[0] : null;
      const pubFromIssue = (volume.publisher && volume.publisher.name) || '';
      const pubFromDetails = info.publisher ? (info.publisher.name || '') : '';
      const seriesStartYear = info.start_year || volume.start_year || '';
      const publishedYear = coverDate.length >= 4 ? coverDate.slice(0,4) : '';
      const guessedVolume = extractVolumeGuess(srcIssue, info || {}) || extractVolumeGuess(srcIssue, seriesObj || {});
      return {
        series: volume.name || info.name || '',
        issue: srcIssue.issue_number || '',
        title: srcIssue.name || srcIssue.title || '',
        issueName: srcIssue.name || srcIssue.title || '',
        year: publishedYear,
        publishedYear,
        startYear: seriesStartYear,
        volume: guessedVolume || '1',
        publisher: pubFromDetails || pubFromIssue || '',
        comicVineIssueId: srcIssue.id || '',
        comicVineSeriesId: volume.id || info.id || '',
        description: srcIssue.description || srcIssue.deck || info.deck || '',
        month: dateParts.length > 1 ? dateParts[1] : '',
        day: dateParts.length > 2 ? dateParts[2] : '',
        writer: firstCreditNames(credits, ['writer']),
        coverArtist: firstCreditNames(credits, ['cover']),
        editor: firstCreditNames(credits, ['editor']),
        penciller: firstCreditNames(credits, ['penciller', 'pencil']),
        inker: firstCreditNames(credits, ['inker', 'ink']),
        colorist: firstCreditNames(credits, ['colorist', 'color']),
        letterer: firstCreditNames(credits, ['letterer', 'letter']),
        storyArc: arc ? (arc.name || '') : '',
        storyArcNumber: '',
        tags: '',
        pageCount: srcIssue.page_count || '',
        isbn: srcIssue.isbn || '',
        barcode: srcIssue.upc || '',
        language: info.site_detail_url ? 'en' : 'en',
      };
    }

    function fillMappingFromIssue(issue) {
      appState.lastIssue = issue || {};
      const details = appState.volumeDetails || {};
      const mapped = buildSingleFlowMetadataFromIssue(issue, details, appState.lastSeries || {});
      setFieldWithCandidates('map_series', mapped.series || '', [details.name || '']);
      setFieldWithCandidates('map_issue', mapped.issue || '', []);
      setFieldWithCandidates('map_title', mapped.title || '', [issue.title || '', (details.first_issue || {}).name || '']);
      setFieldWithCandidates('map_issue_name', mapped.issueName || '', [issue.title || '']);
      setFieldWithCandidates('map_year', mapped.year || '', []);
      setFieldWithCandidates('map_published_year', mapped.publishedYear || '', []);
      setFieldWithCandidates('map_start_year', mapped.startYear || '', [mapped.publishedYear || '']);
      setFieldWithCandidates('map_volume', mapped.volume || '', [mapped.startYear || '']);
      setFieldWithCandidates('map_publisher', mapped.publisher || '', []);
      setFieldWithCandidates('map_issue_id', mapped.comicVineIssueId || '', []);
      setFieldWithCandidates('map_series_id', mapped.comicVineSeriesId || '', []);
      setFieldWithCandidates('map_description', mapped.description || '', []);
      setFieldWithCandidates('map_month', mapped.month || '', []);
      setFieldWithCandidates('map_day', mapped.day || '', []);
      setFieldWithCandidates('map_writer', mapped.writer || '', []);
      setFieldWithCandidates('map_cover_artist', mapped.coverArtist || '', []);
      setFieldWithCandidates('map_editor', mapped.editor || '', []);
      setFieldWithCandidates('map_penciller', mapped.penciller || '', []);
      setFieldWithCandidates('map_inker', mapped.inker || '', []);
      setFieldWithCandidates('map_colorist', mapped.colorist || '', []);
      setFieldWithCandidates('map_letterer', mapped.letterer || '', []);
      setFieldWithCandidates('map_story_arc', mapped.storyArc || '', []);
      setFieldWithCandidates('map_story_arc_num', mapped.storyArcNumber || '', []);
      setFieldWithCandidates('map_tags', mapped.tags || '', []);
      setFieldWithCandidates('map_page_count', mapped.pageCount || '', []);
      setFieldWithCandidates('map_isbn', mapped.isbn || '', []);
      setFieldWithCandidates('map_barcode', mapped.barcode || '', []);
      setFieldWithCandidates('map_language', mapped.language || '', []);
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
    }

    function renderIssueReferenceTable(issues, md) {
      const issueBody = document.querySelector('#issueTable tbody');
      issueBody.innerHTML = '';
      const rows = (issues || []);
      if (!rows.length) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan='7'><span class='muted'>No issues found for selected series.</span></td>`;
        issueBody.appendChild(tr);
        return;
      }
      rows.forEach(i => {
        const volume = i.volume || {};
        const hint = looksLikeMatch(md || {}, i);
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
          if (sameSeriesId(opt.value, sid)) { seriesSel.value = opt.value; break; }
        }
      }
      await onSeriesSelected(issue);
    }

    async function onSeriesSelected(preferredIssue=null) {
      const seriesSel = document.getElementById('seriesSelect');
      const sid = seriesSel.value;
      const data = appState.cvData || {series:[], issues:[]};
      const series = (data.series || []).find(s => sameSeriesId(s.id, sid)) || null;
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
        issues = (data.issues || []).filter(i => sameSeriesId((i.volume || {}).id, sid));
      }
      appState.seriesIssues = issues;

      if (!issues.length) {
        document.getElementById('issueHint').textContent = 'No issues found for selected series. Try Search ComicVine again with a more specific query.';
        renderIssueReferenceTable([], parseLoadedMetadata());
        return;
      }

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

      renderIssueReferenceTable(issues, md);

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
      const issue = (appState.seriesIssues || []).find(i => String(i.id || '') === iid);
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

    let _pathPickResolve = null;

    function showInlinePathEntry(message, initialValue) {
      return new Promise(function(resolve) {
        _pathPickResolve = resolve;
        const overlay = document.getElementById('pathPickOverlay');
        const msg = document.getElementById('pathPickMsg');
        const inp = document.getElementById('pathPickInput');
        if (!overlay || !msg || !inp) { resolve(null); return; }
        msg.textContent = message || 'Enter the absolute folder path on the server:';
        inp.value = String(initialValue || '').trim() || '/home/travis/comics';
        overlay.style.display = 'flex';
        setTimeout(function() { inp.focus(); inp.select(); }, 60);
      });
    }

    function _pathPickConfirm() {
      const inp = document.getElementById('pathPickInput');
      const val = inp ? inp.value.trim() : '';
      if (!val.startsWith('/')) {
        setStatus('Please enter a path starting with /.', true);
        if (inp) inp.focus();
        return;
      }
      _pathPickClose(val);
    }

    function _pathPickCancel() {
      _pathPickClose(null);
    }

    function _pathPickClose(result) {
      const overlay = document.getElementById('pathPickOverlay');
      if (overlay) overlay.style.display = 'none';
      const resolve = _pathPickResolve;
      _pathPickResolve = null;
      if (resolve) resolve(result);
    }

    function _pathPickKeydown(evt) {
      if (!_pathPickResolve) return;
      if (evt.key === 'Enter') { evt.preventDefault(); _pathPickConfirm(); }
      if (evt.key === 'Escape') { evt.preventDefault(); _pathPickCancel(); }
    }

    /* Keep legacy wrapper so existing code still compiles; callers have been updated to await showInlinePathEntry */
    function promptForAbsolutePath(message, initialValue) {
      let suggested = String(initialValue || '').trim() || '/home/travis/comics';
      while (true) {
        const entered = window.prompt(message, suggested);
        if (entered == null) return null;
        const value = String(entered).trim();
        if (value.startsWith('/')) return value;
        setStatus('Please enter an absolute path that starts with /.', true);
        if (value) suggested = value;
      }
    }

    function combinePickedFolderWithCurrentPath(currentPath, pickedFolderName) {
      const current = String(currentPath || '').trim();
      const picked = String(pickedFolderName || '').trim();
      if (!picked) return current;
      if (!current) return '';
      const normalized = current.replace(/\\\\/g, '/').replace(/\/+$/, '');
      if (!normalized || !normalized.startsWith('/')) return '';
      const parts = normalized.split('/').filter(Boolean);
      const base = parts.length ? parts[parts.length - 1] : '';
      if (base && base.toLowerCase() === picked.toLowerCase()) return normalized;
      return normalized + '/' + picked;
    }

    function extractPickedFolderNameFromFiles(files) {
      const pickedFiles = Array.isArray(files) ? files : [];
      if (!pickedFiles.length) return '';
      const rel = String(pickedFiles[0].webkitRelativePath || pickedFiles[0].name || '').replace(/\\\\/g, '/');
      if (!rel) return '';
      const parts = rel.split('/').filter(Boolean);
      return parts.length ? parts[0] : '';
    }

    function applyPickedFolderToInput(inputEl, pickedFolderName, fallbackBase) {
      if (!inputEl) return '';
      const picked = String(pickedFolderName || '').trim();
      const previous = String(fallbackBase || inputEl.value || '').trim();
      if (!picked) return previous;
      if (previous.startsWith('/')) {
        const combined = combinePickedFolderWithCurrentPath(previous, picked);
        if (combined) return combined;
      }
      return '';
    }

    async function browseLibraryPathNative(previous) {
      const prior = String(previous || '').trim();
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000);
        const res = await fetch('/api/pick_directory?current=' + encodeURIComponent(prior || ''), { signal: controller.signal });
        clearTimeout(timeoutId);
        const data = await res.json();
        if (res.ok && data.path) {
          return { path: String(data.path || '').trim(), error: '' };
        }
        return { path: '', error: (data && data.error) ? String(data.error) : 'Folder picker unavailable' };
      } catch (err) {
        if (err && err.name === 'AbortError') {
          return { path: '', error: 'Folder picker timed out; enter absolute path manually' };
        }
        return { path: '', error: (err && err.message) ? String(err.message) : 'Folder picker request failed' };
      }
    }

    async function browseBulkLibraryPathNative(previous) {
      const prior = String(previous || '').trim();
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000);
        const res = await fetch('/api/pick_directory?current=' + encodeURIComponent(prior || ''), { signal: controller.signal });
        clearTimeout(timeoutId);
        const data = await res.json();
        if (res.ok && data.path) {
          return { path: String(data.path || '').trim(), error: '' };
        }
        return { path: '', error: (data && data.error) ? String(data.error) : 'Folder picker unavailable' };
      } catch (err) {
        if (err && err.name === 'AbortError') {
          return { path: '', error: 'Folder picker timed out; enter absolute path manually' };
        }
        return { path: '', error: (err && err.message) ? String(err.message) : 'Folder picker request failed' };
      }
    }

    function clearScanResults() {
      const tbody = document.querySelector('#scanTable tbody');
      if (tbody) tbody.innerHTML = '';
    }

    function toggleScanResultsSize() {
      const shell = document.getElementById('scanResultsShell');
      const btn = document.getElementById('scanSizeToggle');
      if (!shell || !btn) return;
      const expanded = shell.classList.toggle('expanded');
      btn.textContent = expanded ? 'Compact' : 'Expand';
      btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    }

    async function browseLibraryPath() {
      const input = document.getElementById('rootPath');
      const btn = document.getElementById('browseLibraryBtn');
      const picker = document.getElementById('rootPathPicker');
      const previous = (input.value || '').trim();
      clearScanResults();
      if (picker && typeof picker.click === 'function') {
        picker.value = '';
        setStatus('Opening browser folder picker…', false);
        picker.click();
        return;
      }

      setStatus('Opening folder picker — look for a dialog window on your desktop…', false);
      if (btn) { btn.disabled = true; btn.classList.add('btn-busy'); btn.textContent = 'Picking…'; }
      let picked;
      try { picked = await browseLibraryPathNative(previous); }
      finally { if (btn) { btn.disabled = false; btn.classList.remove('btn-busy'); btn.textContent = 'Browse…'; } }
      if (picked.path) {
        input.value = picked.path;
        savePersistentFields();
        setStatus('Folder selected: ' + input.value + '. Click Scan.', false);
        return;
      }
      if (picked.error) {
        setStatus('Folder picker unavailable: ' + picked.error + '. Enter absolute path manually.', true);
      }

      const value = await showInlinePathEntry('Enter absolute folder path to scan on the server:', previous || '/home/travis/comics');
      if (value != null) {
        input.value = value;
        savePersistentFields();
        setStatus('Library path set. Click Scan to scan this folder.', false);
        return;
      }

      setStatus('Folder selection cancelled.', true);
    }

    async function onLibraryFolderPicked(evt) {
      const input = document.getElementById('rootPath');
      const previous = (input && input.value) ? input.value.trim() : '';
      const files = (evt && evt.target && evt.target.files) ? Array.from(evt.target.files) : [];
      const pickedFolder = extractPickedFolderNameFromFiles(files);
      if (pickedFolder) {
        const resolved = applyPickedFolderToInput(input, pickedFolder, previous);
        if (resolved.startsWith('/')) {
          input.value = resolved;
          clearScanResults();
          savePersistentFields();
          setStatus('Folder selected: ' + resolved + '. Click Scan.', false);
          return;
        }

        input.value = pickedFolder;
        clearScanResults();
        savePersistentFields();
        setStatus('Folder selected in browser: ' + pickedFolder + '. Update to an absolute server path before Scan if needed.', true);
        return;
      }

      setStatus('Browser folder picker not available; trying native picker…', false);
      const picked = await browseLibraryPathNative(previous);
      if (picked.path) {
        input.value = picked.path;
        clearScanResults();
        savePersistentFields();
        setStatus('Folder selected: ' + input.value + '. Click Scan.', false);
        return;
      }

      const value = await showInlinePathEntry('Enter absolute folder path to scan on the server:', previous || '/home/travis/comics');
      if (value != null) {
        input.value = value;
        clearScanResults();
        savePersistentFields();
        setStatus('Library path set. Click Scan to scan this folder.', false);
        return;
      }

      setStatus('Folder selection cancelled.', true);
    }

    async function browseBulkLibraryPath() {
      const input = document.getElementById('bulkRootPath');
      const btn = document.getElementById('browseBulkLibraryBtn');
      const picker = document.getElementById('bulkRootPathPicker');
      const previous = (input.value || '').trim();
      if (picker && typeof picker.click === 'function') {
        picker.value = '';
        setStatus('Opening browser folder picker…', false);
        picker.click();
        return;
      }

      setStatus('Opening bulk folder picker — look for a dialog window on your desktop…', false);
      if (btn) { btn.disabled = true; btn.classList.add('btn-busy'); btn.textContent = 'Picking…'; }
      let picked;
      try { picked = await browseBulkLibraryPathNative(previous); }
      finally { if (btn) { btn.disabled = false; btn.classList.remove('btn-busy'); btn.textContent = 'Browse…'; } }
      if (picked.path) {
        input.value = picked.path;
        document.getElementById('bulkRootLabel').textContent = input.value || '(not set)';
        setStatus('Bulk folder selected: ' + input.value + '. Click Scan batch.', false);
        return;
      }
      if (picked.error) {
        setStatus('Bulk folder picker unavailable: ' + picked.error + '. Enter absolute path manually.', true);
      }

      const value = await showInlinePathEntry('Enter absolute folder path to scan for bulk processing:', previous || '/home/travis/comics');
      if (value != null) {
        input.value = value;
        document.getElementById('bulkRootLabel').textContent = value || '(not set)';
        setStatus('Bulk library path set. Click Scan batch.', false);
        return;
      }

      setStatus('Bulk folder selection cancelled.', true);
    }

    async function onBulkLibraryFolderPicked(evt) {
      const input = document.getElementById('bulkRootPath');
      const previous = (input && input.value) ? input.value.trim() : '';
      const files = (evt && evt.target && evt.target.files) ? Array.from(evt.target.files) : [];
      const pickedFolder = extractPickedFolderNameFromFiles(files);
      if (pickedFolder) {
        const resolved = applyPickedFolderToInput(input, pickedFolder, previous);
        if (resolved.startsWith('/')) {
          input.value = resolved;
          document.getElementById('bulkRootLabel').textContent = resolved || '(not set)';
          setStatus('Bulk folder selected: ' + resolved + '. Click Scan batch.', false);
          return;
        }

        input.value = pickedFolder;
        document.getElementById('bulkRootLabel').textContent = pickedFolder || '(not set)';
        setStatus('Bulk folder selected in browser: ' + pickedFolder + '. Update to an absolute server path before Scan batch if needed.', true);
        return;
      }

      setStatus('Browser folder picker not available; trying native picker…', false);
      const picked = await browseBulkLibraryPathNative(previous);
      if (picked.path) {
        input.value = picked.path;
        document.getElementById('bulkRootLabel').textContent = input.value || '(not set)';
        setStatus('Bulk folder selected: ' + input.value + '. Click Scan batch.', false);
        return;
      }

      const value = await showInlinePathEntry('Enter absolute folder path to scan for bulk processing:', previous || '/home/travis/comics');
      if (value != null) {
        input.value = value;
        document.getElementById('bulkRootLabel').textContent = value || '(not set)';
        setStatus('Bulk library path set. Click Scan batch.', false);
        return;
      }

      setStatus('Bulk folder selection cancelled.', true);
    }

    function browseComicFile() {
      document.getElementById('comicPathPicker').click();
    }

      function onComicFilePicked(evt) {
      const files = (evt && evt.target && evt.target.files) ? Array.from(evt.target.files) : [];
      if (!files.length) return;
      const f = files[0];
      const rel = f.webkitRelativePath || f.name || '';
      setComicPathValue(rel);
      setStatus('File selected: ' + rel + '. Note: enter absolute server path manually if different.', false);
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
      appState.writePathManual = true;
      savePersistentFields();
      setStatus('Write target: ' + rel + '. Enter absolute server path if server differs from browser.', false);
    }

    function setWritePathFromSelected() {
      const path = (document.getElementById('comicPath').value || '').trim();
      if (!path) return alert('Select a comic file first.');
      document.getElementById('writePath').value = path;
      appState.writePathManual = false;
      savePersistentFields();
      setStatus('Write target set to selected file.', false);
    }

    async function scanLibrary() {
      const root = document.getElementById('rootPath').value.trim();
      if (!root) return alert('Enter a library path first.');
      const recurse = document.getElementById('scanRecursive').checked ? '1' : '0';
      setStatus('Scanning library…', false);
      try {
        const res = await fetch('/api/scan?root=' + encodeURIComponent(root) + '&recurse=' + recurse);
        const data = await res.json();
        const tbody = document.querySelector('#scanTable tbody');
        tbody.innerHTML = '';
        if (!res.ok || data.error) {
          setStatus('Scan failed: ' + (data.error || ('HTTP ' + res.status)), true);
          return;
        }
        (data.results || []).forEach(r => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${r.path || ''}</td><td>${r.pages ?? ''}</td><td>${r.has_cix ?? ''}</td><td>${r.has_cbi ?? ''}</td><td>${r.has_comet ?? ''}</td><td>${r.error || r.warning || ''}</td>`;
          tr.onclick = () => { if (r.path) { setComicPathValue(r.path); } };
          tbody.appendChild(tr);
        });
        const note = data.note ? (' ' + data.note) : '';
        setStatus('Scan complete. ' + (data.count || 0) + ' comic file(s) found.' + note, false);
      } catch (err) {
        setStatus('Scan failed: ' + (err && err.message ? err.message : 'request failed'), true);
      }
    }

    async function readMetadata() {
      const path = document.getElementById('comicPath').value.trim();
      const style = document.getElementById('style').value;
      if (!path) return alert('Select or enter a comic file path first.');
      setStatus('Reading metadata…', false);
      const res = await fetch('/api/read?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style));
      const data = await res.json();
      showJson('metadataJson', data);
      if (!res.ok || data.error) {
        document.getElementById('styleInfo').textContent = data.detected_style ? `Detected: ${data.detected_style}` : 'Detected: none';
        renderSummary(data.summary || {});
        document.getElementById('coverThumb').src = '';
        setStatus('Read failed: ' + (data.error || ('HTTP ' + res.status)), true);
        return;
      }
      if (data.style) document.getElementById('style').value = data.style;
      maybeSyncWritePath(false);
      savePersistentFields();
      document.getElementById('styleInfo').textContent = data.detected_style ? `Detected: ${data.detected_style}` : 'Detected: none';
      renderSummary(data.summary || {});
      const thumb = '/api/thumbnail?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style) + '&_=' + Date.now();
      document.getElementById('coverThumb').src = thumb;
      if (data.warning) {
        setStatus('Metadata loaded with warning: ' + data.warning, true);
      } else {
        setStatus('Metadata loaded.', false);
      }
    }

    function buildComicVineQueryFromAssessment(data) {
      const md = (data && data.recommended_metadata) ? data.recommended_metadata : {};
      const summary = (data && data.summary) ? data.summary : {};
      const series = String(md.series || summary.series || '').trim();
      const issue = String(md.issue || summary.issue || '').trim();
      const title = String(md.title || summary.title || '').trim();
      const parts = [series, issue, title].filter(Boolean);
      return parts.join(' ').replace(/\\s+/g, ' ').trim();
    }

    function deriveQueryFromPath(pathText) {
      const hints = parseFilenameHints(pathText || '');
      const pieces = [hints.series || '', hints.issue || ''].filter(Boolean);
      return pieces.join(' ').replace(/\\s+/g, ' ').trim();
    }

    async function assessFile() {
      const path = document.getElementById('comicPath').value.trim();
      const style = document.getElementById('style').value;
      if (!path) return alert('Select or enter a comic file path first.');
      setStatus('Assessing file…', false);
      const res = await fetch('/api/assess?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style));
      const data = await res.json();
      showJson('assessmentJson', data);
      if (!res.ok || data.error) {
        if (data.summary) renderSummary(data.summary);
        document.getElementById('coverThumb').src = '';
        setStatus('Assessment failed: ' + (data.error || ('HTTP ' + res.status)), true);
        return;
      }
      if (data.summary) renderSummary(data.summary);
      if (data.recommended_metadata) showJson('metadataJson', { metadata: data.recommended_metadata });
      if (data.style) document.getElementById('style').value = data.style;
      document.getElementById('styleInfo').textContent = data.detected_style ? `Detected: ${data.detected_style}` : 'Detected: none';
      const cvQuery = document.getElementById('cvQuery');
      const autoQuery = buildComicVineQueryFromAssessment(data);
      if (cvQuery && autoQuery) {
        cvQuery.value = autoQuery;
        savePersistentFields();
      }
      const thumb = '/api/thumbnail?path=' + encodeURIComponent(path) + '&style=' + encodeURIComponent(style) + '&_=' + Date.now();
      document.getElementById('coverThumb').src = thumb;
      if (data.warning) {
        setStatus('Assessment complete with warning: ' + data.warning, true);
      } else {
        setStatus('Assessment complete. Review recommended metadata, then write.', false);
      }
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
      const tokenRe = /\\{([A-Za-z][A-Za-z0-9_]*)\\}/g;
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

    function namingState(mode) {
      return mode === 'bulk' ? appState.naming.bulk : appState.naming.single;
    }

    function getNamingElements(mode) {
      const prefix = mode === 'bulk' ? 'bulk' : 'single';
      return {
        pattern: document.getElementById(prefix + 'NamingPattern'),
        preview: document.getElementById(prefix + 'NamingPreview'),
        applyBtn: document.getElementById(prefix + 'NamingApplyBtn'),
        overrideBtn: document.getElementById(prefix + 'NamingOverrideBtn'),
      };
    }

    function updateNamingButtons(mode) {
      const state = namingState(mode);
      const els = getNamingElements(mode);
      if (els.applyBtn) {
        els.applyBtn.classList.toggle('is-active', !!state.apply);
        els.applyBtn.textContent = state.apply ? 'Apply ✓' : 'Apply';
      }
      if (els.overrideBtn) {
        els.overrideBtn.classList.toggle('is-active', !!state.override);
        els.overrideBtn.textContent = state.override ? 'Override ✓' : 'Override';
      }
    }

    function sanitizeNamingValue(value) {
      return String(value == null ? '' : value).replace(/[\\/]+/g, '-').trim();
    }

    function buildNamingValueMap(sourceMeta) {
      const md = sourceMeta || {};
      return {
        Series: sanitizeNamingValue(md.series || md.Series || ''),
        IssueNumber: sanitizeNamingValue(md.issue || md.IssueNumber || ''),
        VolumeNumber: sanitizeNamingValue(md.volume || md.VolumeNumber || ''),
        Year: sanitizeNamingValue(md.year || md.publishedYear || md.Year || ''),
        Title: sanitizeNamingValue(md.title || md.issueName || md.Title || ''),
        Publisher: sanitizeNamingValue(md.publisher || md.Publisher || ''),
        Month: sanitizeNamingValue(md.month || md.Month || ''),
        Day: sanitizeNamingValue(md.day || md.Day || ''),
      };
    }

    function renderNamingFromPattern(pattern, sourceMeta, sourcePath) {
      const extMatch = String(sourcePath || '').match(/(\\.[A-Za-z0-9]+)$/);
      const ext = extMatch ? extMatch[1] : '';
      const tokens = buildNamingValueMap(sourceMeta);
      const replaced = String(pattern || '').replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/g, (_, token) => {
        const value = tokens[token];
        return value ? value : token;
      }).replace(/[\\\\/]+/g, '/').trim();

      const withExt = (!ext || /\.[A-Za-z0-9]+$/.test(replaced)) ? replaced : (replaced + ext);
      const normalizedSource = String(sourcePath || '').replace(/\\\\/g, '/').trim();
      const sourceDir = normalizedSource.includes('/')
        ? normalizedSource.slice(0, normalizedSource.lastIndexOf('/'))
        : '';
      const normalizedTarget = String(withExt || '').replace(/\\\\/g, '/').replace(/\/+$/, '');
      if (!normalizedTarget) return '';

      // Keep absolute paths as-is (Unix, UNC, or Windows drive paths).
      if (/^(?:\/|[A-Za-z]:\/|\\\\)/.test(normalizedTarget)) return normalizedTarget;

      // Relative naming patterns resolve under the source file folder so preview/write shows full path.
      if (!sourceDir) return normalizedTarget;
      return (sourceDir + '/' + normalizedTarget).replace(/\/+/g, '/');
    }

    function buildSingleNamingSourceMetadata() {
      const loaded = parseLoadedMetadata() || {};
      const issueNumber = (document.getElementById('map_issue') && document.getElementById('map_issue').value) || loaded.issue || '';
      const publishedYear = (document.getElementById('map_year') && document.getElementById('map_year').value) || loaded.year || '';
      const startYear = (document.getElementById('map_start_year') && document.getElementById('map_start_year').value) || loaded.startYear || '';
      return {
        series: (document.getElementById('map_series') && document.getElementById('map_series').value) || loaded.series || '',
        issue: issueNumber,
        volume: (document.getElementById('map_volume') && document.getElementById('map_volume').value) || loaded.volume || '1',
        year: publishedYear || startYear,
        title: (document.getElementById('map_title') && document.getElementById('map_title').value) || loaded.title || loaded.issueName || '',
        publisher: (document.getElementById('map_publisher') && document.getElementById('map_publisher').value) || loaded.publisher || '',
        month: (document.getElementById('map_month') && document.getElementById('map_month').value) || loaded.month || '',
        day: (document.getElementById('map_day') && document.getElementById('map_day').value) || loaded.day || '',
      };
    }

    function getBulkPreviewRow() {
      const rows = appState.bulkRows || [];
      if (!rows.length) return null;
      const selected = getBulkRowById(appState.bulkSelectedId);
      return selected || rows[0];
    }

    function buildBulkNamingSourceMetadata(row) {
      const r = row || {};
      return {
        series: r.series || '',
        issue: r.issue || '',
        volume: r.volume || '1',
        year: r.year || r.publishedYear || '',
        title: r.title || r.issueName || '',
        publisher: r.publisher || '',
        month: r.month || '',
        day: r.day || '',
      };
    }

    function previewNaming(mode) {
      const els = getNamingElements(mode);
      const pattern = (els.pattern && els.pattern.value ? els.pattern.value : '').trim();
      if (!pattern) {
        if (els.preview) els.preview.value = '';
        setStatus('Naming preview cleared: pattern is empty.', false);
        savePersistentFields();
        return;
      }

      if (mode === 'single') {
        const sourcePath = (document.getElementById('comicPath').value || '').trim();
        if (!sourcePath) {
          setStatus('Select a comic file before previewing single naming.', true);
          return;
        }
        const rendered = renderNamingFromPattern(pattern, buildSingleNamingSourceMetadata(), sourcePath);
        if (els.preview) els.preview.value = rendered;
      } else {
        const row = getBulkPreviewRow();
        if (!row) {
          setStatus('Bulk naming preview requires at least one scanned file.', true);
          return;
        }
        const rendered = renderNamingFromPattern(pattern, buildBulkNamingSourceMetadata(row), row.path || '');
        if (els.preview) els.preview.value = rendered;
      }

      savePersistentFields();
      setStatus('Naming preview updated (' + mode + ').', false);
    }

    function saveNamingPattern(mode) {
      const els = getNamingElements(mode);
      const pattern = (els.pattern && els.pattern.value ? els.pattern.value : '').trim();
      if (!pattern) {
        setStatus('Nothing to save: naming pattern is empty.', true);
        return;
      }
      const state = namingState(mode);
      const existingIdx = (state.history || []).findIndex(x => x === pattern);
      if (existingIdx >= 0) state.history.splice(existingIdx, 1);
      state.history.push(pattern);
      state.historyIndex = state.history.length;
      savePersistentFields();
      setStatus('Saved naming convention (' + mode + ').', false);
    }

    function previousNamingPattern(mode) {
      const els = getNamingElements(mode);
      const state = namingState(mode);
      if (!state.history || !state.history.length) {
        setStatus('No saved naming conventions for ' + mode + '.', true);
        return;
      }
      if (state.historyIndex <= 0 || state.historyIndex > state.history.length) {
        state.historyIndex = state.history.length;
      }
      state.historyIndex -= 1;
      const next = state.history[state.historyIndex] || '';
      if (els.pattern) els.pattern.value = next;
      savePersistentFields();
      previewNaming(mode);
      setStatus('Loaded previous naming convention (' + mode + ').', false);
    }

    function clearNamingSection(mode) {
      const els = getNamingElements(mode);
      if (els.pattern) els.pattern.value = '';
      if (els.preview) els.preview.value = '';
      savePersistentFields();
      setStatus('Cleared naming pattern (' + mode + ').', false);
    }

    function toggleNamingApply(mode) {
      const state = namingState(mode);
      state.apply = !state.apply;
      if (!state.apply) state.override = false;
      updateNamingButtons(mode);
      savePersistentFields();
      setStatus('Naming apply ' + (state.apply ? 'enabled' : 'disabled') + ' (' + mode + ').', false);
    }

    function toggleNamingOverride(mode) {
      const state = namingState(mode);
      state.override = !state.override;
      if (state.override) state.apply = true;
      updateNamingButtons(mode);
      savePersistentFields();
      setStatus('Naming override ' + (state.override ? 'enabled' : 'disabled') + ' (' + mode + ').', false);
    }

    function buildSingleNamingWriteTarget(path) {
      const state = namingState('single');
      if (!state.apply) return '';
      const pattern = (document.getElementById('singleNamingPattern').value || '').trim();
      if (!pattern) return '';
      return renderNamingFromPattern(pattern, buildSingleNamingSourceMetadata(), path || '');
    }

    function buildBulkNamingWriteTarget(row) {
      const state = namingState('bulk');
      if (!state.apply) return '';
      const pattern = (document.getElementById('bulkNamingPattern').value || '').trim();
      if (!pattern) return '';
      return renderNamingFromPattern(pattern, buildBulkNamingSourceMetadata(row), (row && row.path) || '');
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
        const singleNaming = namingState('single');
        const namingTarget = buildSingleNamingWriteTarget(path);
        const primaryTarget = (singleNaming.apply && singleNaming.override && namingTarget)
          ? namingTarget
          : (writePath || '');

        async function postWrite(target) {
          const res = await fetch('/api/write', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path, write_path: target, style, metadata: patch })
          });
          const raw = await res.text();
          let out;
          try { out = JSON.parse(raw || '{}'); }
          catch (_) { out = { ok: false, error: raw || ('HTTP ' + res.status) }; }
          return { res, out };
        }

        const first = await postWrite(primaryTarget);
        showJson('metadataJson', first.out);
        if (!first.res.ok || !first.out.ok) {
          setStatus('Write failed: ' + (first.out.error || ('HTTP ' + first.res.status)), true);
          return;
        }

        const firstPath = first.out.written_path || first.out.path || path;
        if (singleNaming.apply && !singleNaming.override && namingTarget && namingTarget !== firstPath) {
          const mirror = await postWrite(namingTarget);
          showJson('metadataJson', mirror.out);
          if (!mirror.res.ok || !mirror.out.ok) {
            setStatus('Primary write succeeded, naming mirror failed: ' + (mirror.out.error || ('HTTP ' + mirror.res.status)), true);
            return;
          }
          setStatus('Metadata written to primary and naming target: ' + firstPath + ' ; ' + (mirror.out.written_path || namingTarget), false);
          return;
        }

        setStatus('Metadata written to: ' + firstPath, false);
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
      const input = document.getElementById('cvQuery');
      let query = (input && input.value) ? input.value.trim() : '';
      if (!query) {
        const fallback = deriveQueryFromPath((document.getElementById('comicPath').value || '').trim());
        if (fallback) {
          query = fallback;
          if (input) input.value = fallback;
          savePersistentFields();
          setStatus('Auto-filled search query from filename.', false);
        }
      }
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

    function switchTab(tab) {
      const single = tab !== 'bulk';
      const singlePanel = document.getElementById('singleTab');
      const bulkPanel = document.getElementById('bulkTab');
      const singleBtn = document.getElementById('tabSingleBtn');
      const bulkBtn = document.getElementById('tabBulkBtn');
      if (singlePanel) singlePanel.classList.toggle('active', single);
      if (bulkPanel) bulkPanel.classList.toggle('active', !single);
      if (singleBtn) singleBtn.classList.toggle('active', single);
      if (bulkBtn) bulkBtn.classList.toggle('active', !single);
      localStorage.setItem('comicapi.activeTab', single ? 'single' : 'bulk');
    }

    function copySinglePathToBulk() {
      const root = (document.getElementById('rootPath').value || '').trim();
      document.getElementById('bulkRootPath').value = root;
      document.getElementById('bulkRootLabel').textContent = root || '(not set)';
    }

    function buildBulkCvQuerySuggestions(row) {
      const hints = (row && row.hints) ? row.hints : parseFilenameHints((row && row.path) || '');
      const filename = row && row.path ? String(row.path).split('/').pop() : '';
      const stem = filename && filename.includes('.') ? filename.slice(0, filename.lastIndexOf('.')) : filename;
      const values = dedupeKeepOrder([
        `${row && row.series ? row.series : ''} ${row && row.issue ? row.issue : ''}`.trim(),
        `${hints.series || ''} ${hints.issue || ''}`.trim(),
        hints.series || '',
        stem || '',
      ]).filter(Boolean);
      const dl = document.getElementById('bulkCvQueryList');
      if (!dl) return values;
      dl.innerHTML = values.map(v => `<option value="${String(v).replace(/"/g, '&quot;')}"></option>`).join('');
      return values;
    }

    function syncBulkSearchFromSelection() {
      const row = getBulkRowById(appState.bulkSelectedId);
      const input = document.getElementById('bulkCvQuery');
      if (!input) return;
      const suggestions = buildBulkCvQuerySuggestions(row);
      if (!input.value.trim() && suggestions.length) input.value = suggestions[0];
    }

    function getBulkApiKey() {
      const bulk = (document.getElementById('bulkApiKey') && document.getElementById('bulkApiKey').value) ? document.getElementById('bulkApiKey').value.trim() : '';
      if (bulk) return bulk;
      return (document.getElementById('apiKey') && document.getElementById('apiKey').value) ? document.getElementById('apiKey').value.trim() : '';
    }

    function setBulkCvHint(text) {
      const el = document.getElementById('bulkCvHint');
      if (el) el.textContent = text || '';
    }

    function populateBulkCvSeries(data) {
      appState.bulkCvData = data || { series: [], issues: [] };
      const seriesSel = document.getElementById('bulkCvSeriesSelect');
      const issueSel = document.getElementById('bulkCvIssueSelect');
      if (!seriesSel || !issueSel) return;
      seriesSel.innerHTML = '';
      issueSel.innerHTML = '';

      let series = (appState.bulkCvData.series || []).slice();
      const issues = (appState.bulkCvData.issues || []).slice();
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
        setBulkCvHint('No ComicVine series found for this query. Try editing the search text manually.');
        return;
      }

      series.forEach((s, idx) => {
        const opt = document.createElement('option');
        opt.value = String(s.id || '');
        opt.textContent = `${s.name || ''} (${s.start_year || '?'}) [${s.count_of_issues || '?'} issues]`;
        if (idx === 0) opt.selected = true;
        seriesSel.appendChild(opt);
      });
      setBulkCvHint('Series loaded. Batch apply maps each row by its issue number; selected issue is fallback only.');
      onBulkCvSeriesSelected();
    }

    async function bulkSearchComicVine() {
      const queryInput = document.getElementById('bulkCvQuery');
      let query = queryInput ? queryInput.value.trim() : '';
      if (!query) {
        const selected = getBulkRowById(appState.bulkSelectedId);
        const candidateRow = selected || (appState.bulkRows || []).find(passesBulkFilter) || (appState.bulkRows || [])[0] || null;
        const suggestions = buildBulkCvQuerySuggestions(candidateRow);
        if (suggestions.length) {
          query = suggestions[0];
          if (queryInput) queryInput.value = query;
          setStatus('Auto-filled bulk search query from filename hints.', false);
        }
      }
      const apiKey = getBulkApiKey();
      if (!query) return alert('Enter a ComicVine search query first.');

      setStatus('Bulk ComicVine search in progress…', false);
      const qp = '/api/comicvine/search?query=' + encodeURIComponent(query) + (apiKey ? '&api_key=' + encodeURIComponent(apiKey) : '');
      try {
        const res = await fetch(qp);
        const data = await res.json();
        if (!res.ok || data.error) {
          setStatus('Bulk ComicVine search failed: ' + (data.error || ('HTTP ' + res.status)), true);
          setBulkCvHint('Search failed. Edit query and retry.');
          return;
        }
        populateBulkCvSeries(data);
        setStatus('Bulk ComicVine search complete.', false);
      } catch (err) {
        setStatus('Bulk ComicVine search failed: ' + (err && err.message ? err.message : 'request failed'), true);
        setBulkCvHint('Search request failed.');
      }
    }

    async function onBulkCvSeriesSelected() {
      const seriesSel = document.getElementById('bulkCvSeriesSelect');
      const issueSel = document.getElementById('bulkCvIssueSelect');
      if (!seriesSel || !issueSel) return;
      const sid = seriesSel.value;
      issueSel.innerHTML = '';
      if (!sid) return;

      const apiKey = getBulkApiKey();
      let issues = [];
      try {
        const q = '/api/comicvine/issues_for_series?series_id=' + encodeURIComponent(sid) + (apiKey ? '&api_key=' + encodeURIComponent(apiKey) : '');
        const r = await fetch(q);
        const payload = await r.json();
        issues = payload.issues || [];
      } catch (_) {}
      if (!issues.length) {
        const dataIssues = (appState.bulkCvData && appState.bulkCvData.issues) ? appState.bulkCvData.issues : [];
        issues = dataIssues.filter(i => sameSeriesId((i.volume || {}).id, sid));
      }

      appState.bulkCvIssues = issues;
      if (!issues.length) {
        setBulkCvHint('No issues found for selected series.');
        return;
      }

      issues.forEach((i, idx) => {
        const opt = document.createElement('option');
        opt.value = String(i.id || '');
        opt.textContent = `#${i.issue_number || '?'} - ${i.name || i.title || '(no name)'} (${i.cover_date || '?'})`;
        if (idx === 0) opt.selected = true;
        issueSel.appendChild(opt);
      });
      onBulkCvIssueSelected();
    }

    function onBulkCvIssueSelected() {
      const issueSel = document.getElementById('bulkCvIssueSelect');
      if (!issueSel) return;
      const issue = (appState.bulkCvIssues || []).find(i => String(i.id || '') === String(issueSel.value || ''));
      if (!issue) {
        setBulkCvHint('Pick an issue to apply metadata to selected row.');
        return;
      }
      const volume = issue.volume || {};
      setBulkCvHint(`Selected: ${volume.name || ''} #${issue.issue_number || '?'} (${issue.cover_date || '?'})`);
    }

    function applyComicVineIssueToBulkRow(row, issue) {
      if (!row || !issue) return false;
      const mapped = buildSingleFlowMetadataFromIssue(issue, null, issue.volume || {});
      row.series = mapped.series || row.series;
      row.issue = mapped.issue || row.issue;
      row.year = mapped.year || row.year;
      row.publisher = mapped.publisher || row.publisher;
      row.volume = mapped.volume || row.volume || '1';
      row.title = mapped.title || row.title;
      row.issueName = mapped.issueName || row.issueName;
      row.startYear = mapped.startYear || row.startYear;
      row.publishedYear = mapped.publishedYear || row.publishedYear;
      row.comicVineIssueId = mapped.comicVineIssueId || row.comicVineIssueId;
      row.comicVineSeriesId = mapped.comicVineSeriesId || row.comicVineSeriesId;
      row.description = mapped.description || row.description;
      row.month = mapped.month || row.month;
      row.day = mapped.day || row.day;
      row.writer = mapped.writer || row.writer;
      row.coverArtist = mapped.coverArtist || row.coverArtist;
      row.editor = mapped.editor || row.editor;
      row.penciller = mapped.penciller || row.penciller;
      row.inker = mapped.inker || row.inker;
      row.colorist = mapped.colorist || row.colorist;
      row.letterer = mapped.letterer || row.letterer;
      row.storyArc = mapped.storyArc || row.storyArc;
      row.storyArcNumber = row.storyArcNumber || '';
      row.tags = row.tags || '';
      row.pageCount = mapped.pageCount || row.pageCount;
      row.isbn = mapped.isbn || row.isbn;
      row.barcode = mapped.barcode || row.barcode;
      row.language = mapped.language || row.language || 'en';
      row.cvAvailable = buildBulkCvAvailableFromIssue(issue);
      if (row.writeState === 'written' || row.writeState === 'failed' || row.writeState === 'skipped') {
        row.writeState = '';
        row.writeError = '';
      }
      return true;
    }

    function buildBulkCvAvailableFromIssue(issue) {
      if (!issue) return {};
      const volume = issue.volume || {};
      const coverDate = String(issue.cover_date || '');
      const dateParts = coverDate.split('-');
      const credits = issue.person_credits || [];
      const arcs = (issue.story_arc_credits || []).map(a => (a && a.name) ? a.name : '').filter(Boolean).join(', ');
      const candidate = {
        series: volume.name || '',
        issue: issue.issue_number || '',
        title: issue.name || issue.title || '',
        issueName: issue.name || issue.title || '',
        publisher: ((volume.publisher || {}).name) || '',
        year: coverDate.slice(0, 4) || '',
        volume: volume.start_year || '',
        startYear: volume.start_year || '',
        publishedYear: coverDate.slice(0, 4) || '',
        comicVineIssueId: issue.id || '',
        comicVineSeriesId: volume.id || '',
        description: issue.description || issue.deck || '',
        month: dateParts.length > 1 ? dateParts[1] : '',
        day: dateParts.length > 2 ? dateParts[2] : '',
        writer: firstCreditNames(credits, ['writer']) || '',
        coverArtist: firstCreditNames(credits, ['cover']) || '',
        editor: firstCreditNames(credits, ['editor']) || '',
        storyArc: arcs || '',
        pageCount: issue.page_count || '',
        isbn: issue.isbn || '',
        barcode: issue.upc || '',
        language: 'en',
        penciller: firstCreditNames(credits, ['penciller', 'pencil']) || '',
        inker: firstCreditNames(credits, ['inker', 'ink']) || '',
        colorist: firstCreditNames(credits, ['colorist', 'color']) || '',
        letterer: firstCreditNames(credits, ['letterer', 'letter']) || '',
      };
      const out = {};
      Object.entries(candidate).forEach(([k, v]) => {
        const text = String(v || '').trim();
        if (text) out[k] = text;
      });
      return out;
    }

    function bulkResolveIssueForRow(row, issues, fallbackIssue) {
      const token = normalizeIssue(
        row.issue ||
        ((row.detected || {}).issue || '') ||
        ((row.hints || {}).issue || '')
      );
      if (token) {
        const matched = (issues || []).find(i => normalizeIssue(i.issue_number || '') === token);
        if (matched) return { issue: matched, mode: 'matched' };
      }
      if (fallbackIssue) return { issue: fallbackIssue, mode: 'fallback' };
      return { issue: null, mode: 'missing' };
    }

    function bulkApplyCvToSelected() {
      const row = getBulkRowById(appState.bulkSelectedId);
      if (!row) {
        setStatus('Select a bulk queue row first, then apply ComicVine values.', true);
        return;
      }
      const issueSel = document.getElementById('bulkCvIssueSelect');
      const issue = (appState.bulkCvIssues || []).find(i => String(i.id || '') === String((issueSel && issueSel.value) || ''));
      if (!issue) {
        setStatus('Choose a ComicVine issue first.', true);
        return;
      }

      applyComicVineIssueToBulkRow(row, issue);
      renderBulkQueue();
      setStatus('Applied ComicVine selection to selected bulk row.', false);
    }

    function bulkApplyCvToBatch(scope) {
      const issueSel = document.getElementById('bulkCvIssueSelect');
      const selectedIssue = (appState.bulkCvIssues || []).find(i => String(i.id || '') === String((issueSel && issueSel.value) || ''));
      if (!(appState.bulkCvIssues || []).length) {
        setStatus('Load ComicVine issues for the selected series first.', true);
        return;
      }

      let rows = [];
      if (scope === 'visible') rows = (appState.bulkRows || []).filter(passesBulkFilter);
      else rows = (appState.bulkRows || []).filter(r => !!r.selected);

      if (!rows.length) {
        setStatus(scope === 'visible' ? 'No visible rows to apply.' : 'No checked rows selected for batch apply.', true);
        return;
      }

      let changed = 0;
      let matched = 0;
      let fallback = 0;
      let missing = 0;
      rows.forEach(r => {
        const resolved = bulkResolveIssueForRow(r, appState.bulkCvIssues || [], selectedIssue || null);
        if (!resolved.issue) {
          missing += 1;
          return;
        }
        if (applyComicVineIssueToBulkRow(r, resolved.issue)) {
          changed += 1;
          if (resolved.mode === 'matched') matched += 1;
          else fallback += 1;
        }
      });

      renderBulkQueue();
      const suffix = scope === 'visible' ? 'visible' : 'checked';
      if (!changed) {
        setStatus('Batch apply could not map any ' + suffix + ' rows to ComicVine issues.', true);
        return;
      }
      setStatus('Applied ComicVine metadata to ' + changed + ' ' + suffix + ' row(s): ' + matched + ' matched by issue, ' + fallback + ' fallback, ' + missing + ' missing.', false);
    }

    function getBulkRowById(id) {
      return (appState.bulkRows || []).find(r => String(r.id) === String(id)) || null;
    }

    function toNumericToken(value) {
      const s = String(value || '').trim();
      if (!s) return null;
      const m = s.match(/\\d{1,6}/);
      if (!m) return null;
      const n = parseInt(m[0], 10);
      return Number.isNaN(n) ? null : n;
    }

    function parseYearToken(value) {
      const s = String(value || '').trim();
      if (!s) return null;
      const m = s.match(/\\d{4}/);
      if (!m) return null;
      const y = parseInt(m[0], 10);
      return Number.isNaN(y) ? null : y;
    }

    function classifyBulkRow(r) {
      if (r.writeState === 'written') return 'written';
      if (r.writeState === 'skipped') return 'skip';
      if (r.writeState === 'failed') return 'conflict';
      if (r.error) return 'conflict';
      const hasPatchData = !!Object.keys(buildBulkMetadataPatch(r)).length;
      if (!r.has_cix && !r.has_cbi && !r.has_comet && !hasPatchData) return 'review';
      return 'ready';
    }

    function confidenceForBulkRow(r) {
      if (r.error) return 10;
      let score = 35;
      if (r.has_cix) score += 30;
      if (r.has_cbi) score += 20;
      if (r.has_comet) score += 10;
      return Math.min(99, score);
    }

    function parseFilenameHints(path) {
      const base = (path || '').split('/').pop() || '';
      const noExt = base.replace(/\\.[^.]+$/, '');
      const m = noExt.match(/^(.*?)(?:\\s*[#\\-]?\\s*(\\d{1,4}[A-Za-z]?))?(?:\\s*\\((\\d{4})\\))?$/);
      return {
        series: (m && m[1]) ? m[1].trim() : noExt,
        issue: (m && m[2]) ? m[2] : '',
        year: (m && m[3]) ? m[3] : ''
      };
    }

    function createBulkRow(raw, idx) {
      const hints = parseFilenameHints(raw.path || '');
      return {
        id: idx + 1,
        path: raw.path || '',
        pages: raw.pages,
        has_cix: !!raw.has_cix,
        has_cbi: !!raw.has_cbi,
        has_comet: !!raw.has_comet,
        error: raw.error || '',
        hints,
        selected: false,
        writeState: '',
        writeError: '',
        series: hints.series || '',
        issue: hints.issue || '',
        year: hints.year || '',
        publisher: '',
        volume: '',
        title: '',
        issueName: '',
        startYear: '',
        publishedYear: '',
        comicVineIssueId: '',
        comicVineSeriesId: '',
        description: '',
        month: '',
        day: '',
        writer: '',
        coverArtist: '',
        editor: '',
        storyArc: '',
        storyArcNumber: '',
        tags: '',
        pageCount: '',
        isbn: '',
        barcode: '',
        language: '',
        penciller: '',
        inker: '',
        colorist: '',
        letterer: '',
        cvAvailable: {},
        detected: {},
      };
    }

    function issueTokenForRow(row) {
      return toNumericToken(row.issue || row.detected.issue || row.hints.issue || '');
    }

    function yearTokenForRow(row) {
      return parseYearToken(row.year || row.detected.year || row.hints.year || '');
    }

    function compareBulkRows(a, b) {
      const ai = issueTokenForRow(a);
      const bi = issueTokenForRow(b);
      if (ai != null && bi != null && ai !== bi) return ai - bi;
      if (ai != null && bi == null) return -1;
      if (ai == null && bi != null) return 1;

      const ay = yearTokenForRow(a);
      const by = yearTokenForRow(b);
      if (ay != null && by != null && ay !== by) return ay - by;
      if (ay != null && by == null) return -1;
      if (ay == null && by != null) return 1;

      return String(a.path || '').localeCompare(String(b.path || ''), undefined, { numeric: true, sensitivity: 'base' });
    }

    async function bulkEnrichRowsFromMetadata(rows) {
      const tasks = (rows || []).map(async row => {
        if (!row || !row.path || row.error) return;
        try {
          const res = await fetch('/api/read?path=' + encodeURIComponent(row.path) + '&style=AUTO');
          const data = await res.json();
          if (!res.ok || data.error) return;
          const md = (data.metadata && typeof data.metadata === 'object') ? data.metadata : {};
          row.detected = {
            series: md.series || '',
            issue: md.issue || '',
            year: md.year || '',
            publisher: md.publisher || '',
            volume: md.volume || '',
            title: md.title || '',
            issueName: md.issueName || '',
            startYear: md.startYear || '',
            publishedYear: md.publishedYear || '',
            comicVineIssueId: md.comicVineIssueId || '',
            comicVineSeriesId: md.comicVineSeriesId || '',
            description: md.description || '',
            month: md.month || '',
            day: md.day || '',
            writer: md.writer || '',
            coverArtist: md.coverArtist || '',
            editor: md.editor || '',
            storyArc: md.storyArc || '',
            storyArcNumber: md.storyArcNumber || '',
            tags: md.tags || '',
            pageCount: md.pageCount || '',
            isbn: md.isbn || '',
            barcode: md.barcode || '',
            language: md.language || '',
            penciller: md.penciller || '',
            inker: md.inker || '',
            colorist: md.colorist || '',
            letterer: md.letterer || '',
          };
          if (!row.series && row.detected.series) row.series = row.detected.series;
          if (!row.issue && row.detected.issue) row.issue = String(row.detected.issue);
          if (!row.year && row.detected.year) row.year = String(row.detected.year);
          if (!row.publisher && row.detected.publisher) row.publisher = row.detected.publisher;
          if (!row.volume && row.detected.volume) row.volume = String(row.detected.volume);
          if (!row.title && row.detected.title) row.title = String(row.detected.title);
          if (!row.issueName && row.detected.issueName) row.issueName = String(row.detected.issueName);
          if (!row.startYear && row.detected.startYear) row.startYear = String(row.detected.startYear);
          if (!row.publishedYear && row.detected.publishedYear) row.publishedYear = String(row.detected.publishedYear);
          if (!row.comicVineIssueId && row.detected.comicVineIssueId) row.comicVineIssueId = String(row.detected.comicVineIssueId);
          if (!row.comicVineSeriesId && row.detected.comicVineSeriesId) row.comicVineSeriesId = String(row.detected.comicVineSeriesId);
          if (!row.description && row.detected.description) row.description = String(row.detected.description);
          if (!row.month && row.detected.month) row.month = String(row.detected.month);
          if (!row.day && row.detected.day) row.day = String(row.detected.day);
          if (!row.writer && row.detected.writer) row.writer = String(row.detected.writer);
          if (!row.coverArtist && row.detected.coverArtist) row.coverArtist = String(row.detected.coverArtist);
          if (!row.editor && row.detected.editor) row.editor = String(row.detected.editor);
          if (!row.storyArc && row.detected.storyArc) row.storyArc = String(row.detected.storyArc);
          if (!row.storyArcNumber && row.detected.storyArcNumber) row.storyArcNumber = String(row.detected.storyArcNumber);
          if (!row.tags && row.detected.tags) row.tags = String(row.detected.tags);
          if (!row.pageCount && row.detected.pageCount) row.pageCount = String(row.detected.pageCount);
          if (!row.isbn && row.detected.isbn) row.isbn = String(row.detected.isbn);
          if (!row.barcode && row.detected.barcode) row.barcode = String(row.detected.barcode);
          if (!row.language && row.detected.language) row.language = String(row.detected.language);
          if (!row.penciller && row.detected.penciller) row.penciller = String(row.detected.penciller);
          if (!row.inker && row.detected.inker) row.inker = String(row.detected.inker);
          if (!row.colorist && row.detected.colorist) row.colorist = String(row.detected.colorist);
          if (!row.letterer && row.detected.letterer) row.letterer = String(row.detected.letterer);
        } catch (_) {}
      });
      await Promise.all(tasks);
    }

    function bulkSortCurrentRows(showMessage=true) {
      appState.bulkRows.sort(compareBulkRows);
      appState.bulkManualOrder = false;
      renderBulkQueue();
      if (showMessage) setStatus('Bulk queue sorted by issue/year/path.', false);
    }

    function updateBulkCounters(rows) {
      const by = {queued: rows.length, matched: 0, review: 0, conflicts: 0, ready: 0};
      rows.forEach(r => {
        const st = classifyBulkRow(r);
        if (st === 'conflict') by.conflicts += 1;
        if (st === 'review') by.review += 1;
        if (st === 'ready') by.ready += 1;
        if (st === 'written' || st === 'skip') return;
        if (confidenceForBulkRow(r) >= 85) by.matched += 1;
      });
      document.getElementById('bulkCountQueued').textContent = String(by.queued);
      document.getElementById('bulkCountMatched').textContent = String(by.matched);
      document.getElementById('bulkCountReview').textContent = String(by.review);
      document.getElementById('bulkCountConflicts').textContent = String(by.conflicts);
      document.getElementById('bulkCountReady').textContent = String(by.ready);
    }

    function renderBulkPreview() {
      const tbody = document.querySelector('#bulkPreviewTable tbody');
      if (!tbody) return;
      tbody.innerHTML = '';
      const shown = (appState.bulkRows || []).filter(passesBulkFilter);
      if (!shown.length) {
        const tr = document.createElement('tr');
        tr.innerHTML = "<td colspan='9'><span class='muted'>No files in current view.</span></td>";
        tbody.appendChild(tr);
        return;
      }
      shown.forEach(r => {
        const status = classifyBulkRow(r);
        const confidence = confidenceForBulkRow(r);
        const writeState = r.writeState || '-';
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.path || ''}</td><td>${r.series || ''}</td><td>${r.issue || ''}</td><td>${r.year || ''}</td><td>${r.publisher || ''}</td><td>${r.volume || ''}</td><td>${status}</td><td>${confidence}%</td><td>${writeState}</td>`;
        tbody.appendChild(tr);
      });
    }

    function passesBulkFilter(row) {
      const st = classifyBulkRow(row);
      return appState.bulkFilter === 'all' || st === appState.bulkFilter;
    }

    function clearBulkDropTargets() {
      Array.from(document.querySelectorAll('#bulkQueueTable tbody tr')).forEach(tr => tr.classList.remove('drop-target'));
    }

    function bulkMoveRow(dragId, targetId) {
      const rows = appState.bulkRows || [];
      const from = rows.findIndex(r => String(r.id) === String(dragId));
      const to = rows.findIndex(r => String(r.id) === String(targetId));
      if (from < 0 || to < 0 || from === to) return;
      const moved = rows.splice(from, 1)[0];
      rows.splice(to, 0, moved);
      appState.bulkManualOrder = true;
      renderBulkQueue();
      setStatus('Row order updated by drag-and-drop.', false);
    }

    function renderBulkQueue() {
      const tbody = document.querySelector('#bulkQueueTable tbody');
      if (!tbody) return;
      tbody.innerHTML = '';
      (appState.bulkRows || []).filter(passesBulkFilter).forEach((r) => {
        const hints = r.hints || parseFilenameHints(r.path || '');
        const st = classifyBulkRow(r);
        const conf = confidenceForBulkRow(r);
        const bestSeries = r.series || hints.series || 'Unknown';
        const bestIssue = r.issue || hints.issue || '';
        const best = st === 'ready' ? (bestSeries + (bestIssue ? (' #' + bestIssue) : '')) : (st === 'conflict' ? 'No safe match' : 'Needs review');
        const note = r.writeState === 'written'
          ? 'Written'
          : (r.writeState === 'failed'
            ? ('Write failed: ' + (r.writeError || 'unknown error'))
            : (r.writeState === 'skipped'
              ? ('Skipped: ' + (r.writeError || 'no metadata fields'))
                : (r.error || (st === 'review' ? 'Needs review' : ((r.has_cix || r.has_cbi || r.has_comet) ? 'Ready' : 'Ready (write will create metadata style)')))));
        const tr = document.createElement('tr');
        tr.className = 'bulk-queue-row';
        tr.setAttribute('draggable', 'true');
        tr.innerHTML = `<td><span class='drag-handle'>☰</span></td><td><input type='checkbox' data-bulk-id='${r.id}' ${r.selected ? 'checked' : ''}></td><td><span class='pill ${st === 'ready' ? 'good' : 'warn'}'>${st}</span></td><td>${r.path || ''}</td><td>${r.series || hints.series || ''}</td><td>${r.issue || hints.issue || ''}</td><td>${r.year || hints.year || ''}</td><td>${best}</td><td>${conf}%</td><td>${note}</td>`;
        tr.onclick = () => selectBulkRow(r.id, conf, st, best, note);
        tr.ondragstart = ev => {
          appState.bulkDragId = r.id;
          tr.classList.add('dragging');
          if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = 'move';
            ev.dataTransfer.setData('text/plain', String(r.id));
          }
        };
        tr.ondragend = () => {
          tr.classList.remove('dragging');
          clearBulkDropTargets();
          appState.bulkDragId = null;
        };
        tr.ondragover = ev => {
          ev.preventDefault();
          tr.classList.add('drop-target');
        };
        tr.ondragleave = () => tr.classList.remove('drop-target');
        tr.ondrop = ev => {
          ev.preventDefault();
          tr.classList.remove('drop-target');
          const dragId = appState.bulkDragId != null ? appState.bulkDragId : (ev.dataTransfer ? ev.dataTransfer.getData('text/plain') : '');
          bulkMoveRow(dragId, r.id);
        };

        const cb = tr.querySelector("input[type='checkbox']");
        if (cb) {
          cb.onclick = ev => ev.stopPropagation();
          cb.onchange = () => { r.selected = !!cb.checked; };
        }
        tbody.appendChild(tr);
      });
      updateBulkCounters(appState.bulkRows || []);
      renderBulkPreview();
      syncBulkEditorFromSelection();
    }

    function selectBulkRow(rowId, conf, st, best, note) {
      const r = getBulkRowById(rowId);
      if (!r) return;
      const hints = r.hints || parseFilenameHints(r.path || '');
      appState.bulkSelectedId = r.id;
      const panel = document.getElementById('bulkInspectorPanel');
      if (panel) panel.classList.remove('is-collapsed');
      document.getElementById('bulkInspectorSummary').textContent = `${hints.series || '(unknown)'} ${hints.issue ? ('#' + hints.issue) : ''} — ${st.toUpperCase()} — ${conf}%`;
      showJson('bulkDetectedJson', {
        path: r.path || '',
        pages: r.pages,
        parsed: hints,
        editable_fields: {
          series: r.series || '',
          issue: r.issue || '',
          year: r.year || '',
          publisher: r.publisher || '',
          volume: r.volume || '',
          title: r.title || '',
          issueName: r.issueName || '',
          startYear: r.startYear || '',
          publishedYear: r.publishedYear || '',
          comicVineIssueId: r.comicVineIssueId || '',
          comicVineSeriesId: r.comicVineSeriesId || '',
          description: r.description || '',
          month: r.month || '',
          day: r.day || '',
          writer: r.writer || '',
          coverArtist: r.coverArtist || '',
          editor: r.editor || '',
          storyArc: r.storyArc || '',
          storyArcNumber: r.storyArcNumber || '',
          tags: r.tags || '',
          pageCount: r.pageCount || '',
          isbn: r.isbn || '',
          barcode: r.barcode || '',
          language: r.language || '',
          penciller: r.penciller || '',
          inker: r.inker || '',
          colorist: r.colorist || '',
          letterer: r.letterer || '',
        },
        detected_metadata: r.detected || {},
        write_patch_preview: buildBulkMetadataPatch(r),
        has_styles: { cix: !!r.has_cix, cbi: !!r.has_cbi, comet: !!r.has_comet }
      });
      showJson('bulkAssessmentJson', {
        status: st,
        confidence: conf,
        best_match: best,
        note: note,
      });
      renderBulkAppliedReadable(r);
      syncBulkEditorFromSelection();
      syncBulkSearchFromSelection();
    }

    function renderBulkAppliedReadable(row) {
      const el = document.getElementById('bulkAppliedReadable');
      if (!el) return;
      if (!row) {
        el.textContent = 'Select a row to preview the exact metadata patch that will be written.';
        return;
      }
      const patch = buildBulkMetadataPatch(row);
      const order = [
        'series','issue','title','issueName','publisher','year','volume','startYear','publishedYear',
        'comicVineIssueId','comicVineSeriesId','description','month','day','writer','coverArtist',
        'editor','storyArc','storyArcNumber','tags','pageCount','isbn','barcode','language',
        'penciller','inker','colorist','letterer'
      ];
      const labels = {
        series: 'Series', issue: 'Issue', title: 'Title', issueName: 'Issue name', publisher: 'Publisher',
        year: 'Year', volume: 'Volume', startYear: 'Start year', publishedYear: 'Published year',
        comicVineIssueId: 'ComicVine issue ID', comicVineSeriesId: 'ComicVine series ID', description: 'Description',
        month: 'Month', day: 'Day', writer: 'Writer', coverArtist: 'Cover artist', editor: 'Editor',
        storyArc: 'Story arc', storyArcNumber: 'Story arc number', tags: 'Tags', pageCount: 'Page count',
        isbn: 'ISBN', barcode: 'Barcode', language: 'Language', penciller: 'Penciller', inker: 'Inker',
        colorist: 'Colorist', letterer: 'Letterer'
      };
      const lines = order.filter(k => Object.prototype.hasOwnProperty.call(patch, k)).map(k => {
        return `<div><b>${labels[k] || k}</b>: ${String(patch[k])}</div>`;
      });
      if (!lines.length) {
        el.innerHTML = '<span class="muted">No metadata fields are currently set for this row.</span>';
        return;
      }
      el.innerHTML = lines.join('');
    }

    function setBulkGapVisibility(visible) {
      appState.bulkGapVisible = !!visible;
      const section = document.getElementById('bulkFieldGapSection');
      const btn = document.getElementById('bulkGapToggleBtn');
      if (section) section.classList.toggle('is-hidden', !appState.bulkGapVisible);
      if (btn) {
        btn.setAttribute('aria-expanded', appState.bulkGapVisible ? 'true' : 'false');
        btn.textContent = appState.bulkGapVisible ? 'Hide field gap view' : 'Show field gap view';
      }
    }

    function toggleBulkFieldGapSection() {
      setBulkGapVisibility(!appState.bulkGapVisible);
      if (appState.bulkGapVisible) {
        renderBulkFieldGap(getBulkRowById(appState.bulkSelectedId));
      }
    }

    function renderBulkFieldGap(row) {
      const summary = document.getElementById('bulkFieldGapSummary');
      const body = document.getElementById('bulkFieldGapBody');
      if (!summary || !body) return;
      if (!appState.bulkGapVisible) {
        summary.textContent = 'Click “Show field gap view” to compare available ComicVine fields with fields that will be written.';
        body.innerHTML = '<span class="muted">Hidden until requested.</span>';
        return;
      }
      if (!row) {
        summary.textContent = 'No row selected.';
        body.innerHTML = '<span class="muted">Select a row in the queue, then open this section to inspect missing vs applied fields.</span>';
        return;
      }
      const patch = buildBulkMetadataPatch(row);
      const available = row.cvAvailable || {};
      const order = [
        'series','issue','title','issueName','publisher','year','volume','startYear','publishedYear',
        'comicVineIssueId','comicVineSeriesId','description','month','day','writer','coverArtist',
        'editor','storyArc','storyArcNumber','tags','pageCount','isbn','barcode','language',
        'penciller','inker','colorist','letterer'
      ];
      const labels = {
        series: 'Series', issue: 'Issue', title: 'Title', issueName: 'Issue name', publisher: 'Publisher',
        year: 'Year', volume: 'Volume', startYear: 'Start year', publishedYear: 'Published year',
        comicVineIssueId: 'ComicVine issue ID', comicVineSeriesId: 'ComicVine series ID', description: 'Description',
        month: 'Month', day: 'Day', writer: 'Writer', coverArtist: 'Cover artist', editor: 'Editor',
        storyArc: 'Story arc', storyArcNumber: 'Story arc number', tags: 'Tags', pageCount: 'Page count',
        isbn: 'ISBN', barcode: 'Barcode', language: 'Language', penciller: 'Penciller', inker: 'Inker',
        colorist: 'Colorist', letterer: 'Letterer'
      };
      const appliedKeys = order.filter(k => Object.prototype.hasOwnProperty.call(patch, k));
      const availableKeys = order.filter(k => Object.prototype.hasOwnProperty.call(available, k));
      const missingKeys = availableKeys.filter(k => !Object.prototype.hasOwnProperty.call(patch, k));

      summary.textContent = 'Field coverage snapshot for the selected bulk row.';
      const kpis = `<div class='gap-kpis'>
        <span class='gap-badge hit'>Applied ${appliedKeys.length}</span>
        <span class='gap-badge'>ComicVine ${availableKeys.length}</span>
        <span class='gap-badge miss'>Missing ${missingKeys.length}</span>
      </div>`;

      const renderList = (keys, css, title) => {
        if (!keys.length) return `<div class='meta-kv'><b>${title}:</b> <span class='muted'>none</span></div>`;
        return keys.map(k => `<div class='meta-kv ${css}'><b>${labels[k] || k}</b><span>${String((patch[k] ?? available[k] ?? '') || '')}</span></div>`).join('');
      };

      body.innerHTML = [
        kpis,
        `<div class='gap-grid'>`,
        `<section class='gap-col'><h4>Applied now</h4>${renderList(appliedKeys, 'meta-hit', 'Applied')}</section>`,
        `<section class='gap-col'><h4>Available but not applied</h4>${renderList(missingKeys, 'meta-miss', 'Missing from patch')}</section>`,
        `</div>`
      ].join('');
    }

    function syncBulkEditorFromSelection() {
      const row = getBulkRowById(appState.bulkSelectedId);
      const panel = document.getElementById('bulkInspectorPanel');
      const set = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value || '';
      };
      if (!row) {
        if (panel) panel.classList.add('is-collapsed');
        const summary = document.getElementById('bulkInspectorSummary');
        if (summary) summary.textContent = 'Select a row in the bulk queue to inspect details.';
        showJson('bulkDetectedJson', {});
        showJson('bulkAssessmentJson', {});
        renderBulkAppliedReadable(null);
        renderBulkFieldGap(null);
        set('bulkFieldSeries', '');
        set('bulkFieldIssue', '');
        set('bulkFieldYear', '');
        set('bulkFieldPublisher', '');
        set('bulkFieldVolume', '');
        return;
      }
      if (panel) panel.classList.remove('is-collapsed');
      set('bulkFieldSeries', row.series);
      set('bulkFieldIssue', row.issue);
      set('bulkFieldYear', row.year);
      set('bulkFieldPublisher', row.publisher);
      set('bulkFieldVolume', row.volume);
      renderBulkAppliedReadable(row);
      renderBulkFieldGap(row);
    }

    function bulkSetSelectedField(field, value) {
      const row = getBulkRowById(appState.bulkSelectedId);
      if (!row) return;
      row[field] = String(value || '').trim();
      if (row.writeState === 'written' || row.writeState === 'failed' || row.writeState === 'skipped') {
        row.writeState = '';
        row.writeError = '';
      }
      renderBulkQueue();
    }

    function bulkApplyFieldToOthers(field) {
      const row = getBulkRowById(appState.bulkSelectedId);
      if (!row) {
        setStatus('Select a bulk row first, then apply field value to the rest.', true);
        return;
      }
      const value = String(row[field] || '').trim();
      if (!value) {
        setStatus('Cannot apply empty ' + field + ' value.', true);
        return;
      }
      let count = 0;
      (appState.bulkRows || []).forEach(r => {
        if (r.id === row.id) return;
        r[field] = value;
        if (r.writeState === 'written' || r.writeState === 'failed' || r.writeState === 'skipped') {
          r.writeState = '';
          r.writeError = '';
        }
        count += 1;
      });
      renderBulkQueue();
      setStatus('Applied ' + field + ' = "' + value + '" to ' + count + ' other file(s).', false);
    }

    function incrementFirstNumberInText(text, offset) {
      const src = String(text || '');
      const m = src.match(/(\\d+)/);
      if (!m) return null;
      const oldText = m[1];
      const oldNum = parseInt(oldText, 10);
      if (Number.isNaN(oldNum)) return null;
      const nextNum = oldNum + offset;
      const width = oldText.length;
      const replacement = String(nextNum).padStart(width, '0');
      return src.slice(0, m.index) + replacement + src.slice((m.index || 0) + oldText.length);
    }

    function bulkIncrementFieldFromSelected(field) {
      const selected = getBulkRowById(appState.bulkSelectedId);
      if (!selected) {
        setStatus('Select a bulk row first, then increment down.', true);
        return;
      }
      const rows = appState.bulkRows || [];
      const startIdx = rows.findIndex(r => r.id === selected.id);
      if (startIdx < 0) {
        setStatus('Could not resolve selected bulk row.', true);
        return;
      }
      const baseValue = String(selected[field] || '').trim();
      if (!baseValue) {
        setStatus('Selected ' + field + ' is empty; enter a value first.', true);
        return;
      }
      if (!/(\\d+)/.test(baseValue)) {
        setStatus('Selected ' + field + ' has no number to increment.', true);
        return;
      }

      let changed = 0;
      for (let i = startIdx + 1; i < rows.length; i += 1) {
        const offset = i - startIdx;
        const next = incrementFirstNumberInText(baseValue, offset);
        if (next == null) break;
        rows[i][field] = next;
        if (rows[i].writeState === 'written' || rows[i].writeState === 'failed' || rows[i].writeState === 'skipped') {
          rows[i].writeState = '';
          rows[i].writeError = '';
        }
        changed += 1;
      }

      renderBulkQueue();
      if (!changed) {
        setStatus('No subsequent files to increment for ' + field + '.', false);
        return;
      }
      setStatus('Incremented ' + field + ' down ' + changed + ' subsequent file(s) from selected row.', false);
    }

    async function bulkScanFromRoot() {
      const rootInput = document.getElementById('bulkRootPath');
      const root = (rootInput.value || '').trim();
      if (!root) return alert('Enter a batch root path first.');
      const recurse = document.getElementById('bulkScanRecursive').checked ? '1' : '0';
      document.getElementById('bulkRootLabel').textContent = root;
      setStatus('Bulk scan in progress…', false);
      try {
        const res = await fetch('/api/scan?root=' + encodeURIComponent(root) + '&recurse=' + recurse);
        const data = await res.json();
        if (!res.ok || data.error) {
          appState.bulkRows = [];
          appState.bulkSelectedId = null;
          renderBulkQueue();
          setStatus('Bulk scan failed: ' + (data.error || ('HTTP ' + res.status)), true);
          return;
        }
        appState.bulkRows = (data.results || []).map((r, idx) => createBulkRow(r, idx));
        appState.bulkSelectedId = null;
        appState.bulkManualOrder = false;
        renderBulkQueue();
        setStatus('Bulk scan complete: ' + String(data.count || 0) + ' files. Loading metadata hints for numeric ordering…', false);
        await bulkEnrichRowsFromMetadata(appState.bulkRows);
        bulkSortCurrentRows(false);
        syncBulkSearchFromSelection();
        setStatus('Bulk scan complete: ' + String(data.count || 0) + ' files.', false);
      } catch (err) {
        appState.bulkRows = [];
        appState.bulkSelectedId = null;
        renderBulkQueue();
        setStatus('Bulk scan failed: ' + (err && err.message ? err.message : 'request failed'), true);
      }
    }

    function bulkFilter(kind) {
      appState.bulkFilter = kind || 'all';
      renderBulkQueue();
    }

    function bulkSelectVisible(checked) {
      const rows = (appState.bulkRows || []).filter(passesBulkFilter);
      rows.forEach(r => { r.selected = !!checked; });
      renderBulkQueue();
      setStatus((checked ? 'Selected ' : 'Cleared ') + rows.length + ' visible row(s).', false);
    }

    function bulkAutoMatchSelected() {
      const selected = (appState.bulkRows || []).filter(r => !!r.selected);
      if (!selected.length) {
        setStatus('Bulk auto-match: no rows selected.', true);
        return;
      }
      let changed = 0;
      selected.forEach(r => {
        const d = r.detected || {};
        if (!r.series && d.series) { r.series = d.series; changed += 1; }
        if (!r.issue && d.issue) { r.issue = String(d.issue); changed += 1; }
        if (!r.year && d.year) { r.year = String(d.year); changed += 1; }
        if (!r.publisher && d.publisher) { r.publisher = d.publisher; changed += 1; }
        if (!r.volume && d.volume) { r.volume = String(d.volume); changed += 1; }
      });
      renderBulkQueue();
      setStatus('Bulk auto-match applied to ' + selected.length + ' selected row(s), updated ' + changed + ' field(s).', false);
    }

    function buildBulkMetadataPatch(row) {
      const patch = {};
      const map = {
        series: row.series,
        issue: row.issue,
        title: row.title,
        issueName: row.issueName,
        startYear: row.startYear,
        publishedYear: row.publishedYear,
        comicVineIssueId: row.comicVineIssueId,
        comicVineSeriesId: row.comicVineSeriesId,
        description: row.description,
        month: row.month,
        day: row.day,
        writer: row.writer,
        coverArtist: row.coverArtist,
        editor: row.editor,
        storyArc: row.storyArc,
        storyArcNumber: row.storyArcNumber,
        tags: row.tags,
        pageCount: row.pageCount,
        isbn: row.isbn,
        barcode: row.barcode,
        language: row.language,
        penciller: row.penciller,
        inker: row.inker,
        colorist: row.colorist,
        letterer: row.letterer,
        year: row.year,
        publisher: row.publisher,
        volume: row.volume,
      };
      Object.entries(map).forEach(([k, v]) => {
        const text = String(v || '').trim();
        if (text) patch[k] = text;
      });
      return patch;
    }

    async function bulkWriteRows(rows, label) {
      if (!rows.length) {
        setStatus('Bulk write: no rows to process.', true);
        return;
      }
      const style = (document.getElementById('style') && document.getElementById('style').value) ? document.getElementById('style').value : 'AUTO';
      let ok = 0;
      let failed = 0;
      let skipped = 0;
      setStatus('Bulk write started (' + label + '): ' + rows.length + ' file(s)…', false);

      for (const row of rows) {
        const patch = buildBulkMetadataPatch(row);
        if (!Object.keys(patch).length) {
          row.writeState = 'skipped';
          row.writeError = 'No metadata values set in editable bulk fields';
          skipped += 1;
          continue;
        }
        try {
          const bulkNaming = namingState('bulk');
          const namingTarget = buildBulkNamingWriteTarget(row);
          const primaryTarget = (bulkNaming.apply && bulkNaming.override && namingTarget) ? namingTarget : '';

          async function postBulkWrite(target) {
            const res = await fetch('/api/write', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ path: row.path, write_path: target, style, metadata: patch })
            });
            const payload = await res.json();
            return { res, payload };
          }

          const primary = await postBulkWrite(primaryTarget);
          if (!primary.res.ok || !primary.payload || !primary.payload.ok) {
            row.writeState = 'failed';
            row.writeError = (primary.payload && primary.payload.error) ? primary.payload.error : ('HTTP ' + primary.res.status);
            failed += 1;
            continue;
          }

          const writtenPrimary = primary.payload.written_path || row.path;
          if (bulkNaming.apply && !bulkNaming.override && namingTarget && namingTarget !== writtenPrimary) {
            const mirror = await postBulkWrite(namingTarget);
            if (!mirror.res.ok || !mirror.payload || !mirror.payload.ok) {
              row.writeState = 'failed';
              row.writeError = 'Primary write succeeded; naming mirror failed: ' + ((mirror.payload && mirror.payload.error) ? mirror.payload.error : ('HTTP ' + mirror.res.status));
              failed += 1;
              continue;
            }
          }

          row.writeState = 'written';
          row.writeError = '';
          row.selected = false;
          ok += 1;
        } catch (err) {
          row.writeState = 'failed';
          row.writeError = (err && err.message) ? err.message : 'request failed';
          failed += 1;
        }
      }

      renderBulkQueue();
      const summary = 'Bulk write complete: ' + ok + ' written, ' + failed + ' failed, ' + skipped + ' skipped.';
      setStatus(summary, failed > 0);
    }

    async function bulkWriteSelected() {
      const selected = (appState.bulkRows || []).filter(r => !!r.selected);
      await bulkWriteRows(selected, 'selected');
    }

    async function bulkRetryFailed() {
      const failed = (appState.bulkRows || []).filter(r => r.writeState === 'failed');
      await bulkWriteRows(failed, 'retry failed');
    }

    loadPersistentFields();
    loadRuntimeDiagnostics();
    copySinglePathToBulk();
    const bulkApi = document.getElementById('bulkApiKey');
    const singleApi = document.getElementById('apiKey');
    if (bulkApi && singleApi) {
      bulkApi.value = singleApi.value || '';
      singleApi.addEventListener('change', () => {
        if (!bulkApi.value.trim()) bulkApi.value = singleApi.value || '';
      });
    }
    syncBulkSearchFromSelection();
    setBulkGapVisibility(false);
    renderBulkFieldGap(null);
    switchTab(localStorage.getItem('comicapi.activeTab') === 'bulk' ? 'bulk' : 'single');
  </script>

  <div id='pathPickOverlay' role='dialog' aria-modal='true' aria-labelledby='pathPickMsg' style='display:none'>
    <div class='path-pick-card'>
      <p id='pathPickMsg'></p>
      <input id='pathPickInput' type='text' placeholder='/absolute/path/on/server' onkeydown='_pathPickKeydown(event)'>
      <div class='path-pick-btns'>
        <button onclick='_pathPickConfirm()'>OK</button>
        <button onclick='_pathPickCancel()'>Cancel</button>
      </div>
    </div>
  </div>
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
    warning: str = ""


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
    archive = archive_diagnostics(ca, path)
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
        "archive": archive,
        "warning": archive.get("warning", ""),
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


def sniff_archive_signature(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
    except Exception:
        return "unknown"

    if head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip"
    if head.startswith(b"Rar!\x1a\x07\x00") or head.startswith(b"Rar!\x1a\x07\x01\x00"):
        return "rar"
    if head.startswith(b"%PDF-"):
        return "pdf"
    return "unknown"


def archive_diagnostics(ca, path):
  ext = Path(path).suffix.lower()
  signature = sniff_archive_signature(path)

  is_zip = getattr(ca, "isZip", lambda: False)()
  is_rar = getattr(ca, "isRar", lambda: False)()
  is_pdf = getattr(ca, "isPdf", lambda: False)()

  if is_zip:
    detected_archive_type = "zip"
  elif is_rar:
    detected_archive_type = "rar"
  elif is_pdf:
    detected_archive_type = "pdf"
  else:
    detected_archive_type = "unknown"

  warning = ""
  if detected_archive_type == "unknown" and signature == "rar":
    warning = (
      "Archive appears to be RAR but RAR support is unavailable in this runtime. "
      "Install python-unrar/unrar bindings or convert the file to ZIP/CBZ."
    )
  elif detected_archive_type == "unknown" and signature != "unknown":
    warning = f"Archive signature looks like {signature.upper()}, but the file could not be opened."

  if ext in {".cbz", ".zip"} and signature == "rar":
    mismatch = "File extension is .cbz/.zip but content signature is RAR."
    warning = (warning + " " + mismatch).strip() if warning else mismatch
  elif ext in {".cbr", ".rar"} and signature == "zip":
    mismatch = "File extension is .cbr/.rar but content signature is ZIP."
    warning = (warning + " " + mismatch).strip() if warning else mismatch

  return {
    "path": path,
    "extension": ext,
    "signature": signature,
    "detected_archive_type": detected_archive_type,
    "warning": warning,
  }


def resolve_scan_root(root):
    requested = str(root or "").strip().strip('"').strip("'")
    if not requested:
        return None, None, "root query param required"

    candidate = os.path.abspath(os.path.expanduser(requested))
    if os.path.isdir(candidate):
        return candidate, None, None

    trimmed = candidate.rstrip("/\\")
    if trimmed and os.path.isdir(trimmed):
        return trimmed, f"Normalized scan root to existing directory: {trimmed}", None

    parent = os.path.dirname(trimmed)
    leaf = os.path.basename(trimmed)
    if parent and leaf and os.path.isdir(parent):
        matches = []
        try:
            for p in Path(parent).rglob("*"):
                if p.is_dir() and p.name == leaf:
                    matches.append(str(p))
                    if len(matches) > 2:
                        break
        except Exception:
            matches = []

        if len(matches) == 1:
            resolved = matches[0]
            return resolved, f"Requested root not found; auto-resolved to unique nested match: {resolved}", None
        if len(matches) > 1:
            return None, None, (
                f"root directory not found: {requested}. Found multiple nested matches for '{leaf}' under {parent}; "
                "please enter a more specific path."
            )

    # Browser folder pickers may only provide a folder name (no absolute path).
    # If so, search common comic roots and auto-resolve only on unique match.
    if not os.path.isabs(requested) and "/" not in requested and "\\" not in requested:
        preferred_roots = []
        broad_roots = []
        home = os.path.expanduser("~")
        env_hint = os.environ.get("COMICAPI_LIBRARY_ROOT", "").strip()
        if env_hint:
            preferred_roots.append(os.path.abspath(os.path.expanduser(env_hint)))
        preferred_roots.append(os.path.join(home, "comics"))
        broad_roots.append(home)

        uniq_preferred = []
        uniq_broad = []
        seen = set()
        for r in preferred_roots:
            rr = os.path.abspath(r)
            if rr in seen or not os.path.isdir(rr):
                continue
            seen.add(rr)
            uniq_preferred.append(rr)
        for r in broad_roots:
            rr = os.path.abspath(r)
            if rr in seen or not os.path.isdir(rr):
                continue
            seen.add(rr)
            uniq_broad.append(rr)

        def _find_named_dirs(base_dir, name):
            found = []
            found_seen = set()
            try:
                for p in Path(base_dir).rglob("*"):
                    if p.is_dir() and p.name == name:
                        resolved = str(p.resolve())
                        if resolved in found_seen:
                            continue
                        found_seen.add(resolved)
                        found.append(resolved)
                        if len(found) > 1:
                            break
            except Exception:
                return []
            return found

        for base in uniq_preferred:
            found = _find_named_dirs(base, requested)
            if len(found) == 1:
                resolved = found[0]
                return resolved, (
                    f"Relative root '{requested}' auto-resolved under preferred root {base}: {resolved}"
                ), None
            if len(found) > 1:
                return None, None, (
                    f"root directory '{requested}' is ambiguous under preferred root {base}. "
                    "Please enter an absolute path."
                )

        matches = []
        seen_matches = set()
        for base in uniq_broad:
            try:
                for p in Path(base).rglob("*"):
                    if p.is_dir() and p.name == requested:
                        found = str(p.resolve())
                        if found in seen_matches:
                            continue
                        seen_matches.add(found)
                        matches.append(found)
                        if len(matches) > 1:
                            break
            except Exception:
                continue
            if len(matches) > 1:
                break

        if len(matches) == 1:
            resolved = matches[0]
            return resolved, (
                f"Relative root '{requested}' auto-resolved to unique match: {resolved}"
            ), None
        if len(matches) > 1:
            return None, None, (
                f"root directory '{requested}' is ambiguous; multiple matches found under {', '.join(uniq_preferred + uniq_broad)}. "
                "Please enter an absolute path."
            )

    return None, None, f"root directory does not exist or is not a directory: {requested}"


def _safe_start_dir(candidate):
    text = str(candidate or "").strip().strip('"').strip("'")
    if text:
        expanded = os.path.abspath(os.path.expanduser(text))
        if os.path.isdir(expanded):
            return expanded
        parent = os.path.dirname(expanded)
        if parent and os.path.isdir(parent):
            return parent
    home = os.path.expanduser("~")
    if os.path.isdir(home):
        return home
    return "/"


def _has_interactive_desktop_session():
    env = os.environ

    # Check Wayland socket presence
    wayland_display = (env.get("WAYLAND_DISPLAY") or "").strip()
    xdg_runtime_dir = (env.get("XDG_RUNTIME_DIR") or "").strip()
    wayland_ok = bool(
        wayland_display
        and xdg_runtime_dir
        and os.path.exists(os.path.join(xdg_runtime_dir, wayland_display))
    )

    # Check X11 socket presence
    display = (env.get("DISPLAY") or "").strip()
    x11_ok = False
    if display:
        m = re.match(r"^:?([0-9]+)", display)
        if m:
            x11_socket = f"/tmp/.X11-unix/X{m.group(1)}"
            x11_ok = os.path.exists(x11_socket)

    # Session hints: helps avoid launching pickers in non-desktop shells
    has_session_hint = bool(
        (env.get("DBUS_SESSION_BUS_ADDRESS") or "").strip()
        or (env.get("XDG_CURRENT_DESKTOP") or "").strip()
        or (env.get("DESKTOP_SESSION") or "").strip()
    )

    return (wayland_ok or x11_ok) and has_session_hint


def pick_directory_native(start_dir):
    start = _safe_start_dir(start_dir)
    if not _has_interactive_desktop_session():
        return None, (
            "No interactive desktop session detected; native folder picker unavailable. "
            "Enter an absolute path manually."
        )

    candidates = []
    if shutil.which("zenity"):
        candidates.append([
            "zenity",
            "--file-selection",
            "--directory",
            "--title=Select library folder",
            "--timeout=30",
            f"--filename={start.rstrip('/')}/",
        ])
    if shutil.which("kdialog"):
        candidates.append(["kdialog", "--getexistingdirectory", start, "Select library folder"])

    if not candidates:
        return None, "No supported native picker found (install zenity or kdialog)"

    last_error = "Picker failed"
    for cmd in candidates:
        try: proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            last_error = "Folder picker timed out; enter absolute path manually"
        except Exception as exc:
            last_error = str(exc)
        else:
            if proc.returncode == 0:
                picked = (proc.stdout or "").strip()
                if picked and os.path.isdir(picked):
                    return os.path.abspath(picked), None
                return None, "Picker returned invalid directory"
            stderr = (proc.stderr or "").strip()
            if stderr:
                last_error = stderr
            else:
                last_error = "Picker cancelled"
    return None, last_error


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
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _bytes(self, status, payload, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except BrokenPipeError:
            pass

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
            return self._json(200, {
                "server_version": self.server_version,
                "git_commit": "unknown",
                "module_path": "unknown",
                "features": ["assess", "browse_paths", "write_status", "version_endpoint"],
            })

        if parsed.path == "/api/scan":
            root = qs.get("root", [""])[0]
            recurse_raw = qs.get("recurse", ["1"])[0]
            recurse = str(recurse_raw).strip().lower() not in {"0", "false", "no", "off"}
            resolved_root, scan_note, scan_error = resolve_scan_root(root)
            if scan_error:
                return self._json(400, {"error": scan_error})
            exts = {".cbz", ".cbr", ".cbt", ".pdf", ".zip", ".rar"}
            results = []
            walker = Path(resolved_root).rglob("*") if recurse else Path(resolved_root).glob("*")
            for p in walker:
                if p.is_file() and p.suffix.lower() in exts:
                    try:
                        ca = ComicArchive(str(p), default_image_path=str(p))
                        archive = archive_diagnostics(ca, str(p))
                        summary = ComicSummary(
                            str(p),
                            ca.getNumberOfPages(),
                            ca.hasMetadata(MetaDataStyle.CIX),
                            ca.hasMetadata(MetaDataStyle.CBI),
                            ca.hasMetadata(MetaDataStyle.COMET),
                            archive.get("warning", ""),
                        )
                        results.append(asdict(summary))
                    except Exception as exc:
                        results.append({"path": str(p), "error": str(exc)})
            return self._json(200, {
                "count": len(results),
                "results": results,
                "requested_root": root,
                "root": resolved_root,
                "recurse": recurse,
                "note": scan_note,
            })

        if parsed.path == "/api/pick_directory":
          current = qs.get("current", [""])[0]
          picked, error = pick_directory_native(current)
          if error:
            return self._json(200, {"path": "", "error": error, "current": current})
          return self._json(200, {"path": picked, "current": current})

        if parsed.path == "/api/read":
            path = qs.get("path", [""])[0]
            style = qs.get("style", ["AUTO"])[0].upper()
            if not path:
                return self._json(400, {"error": "path query param required"})
            if style != "AUTO" and style not in STYLE_MAP:
                return self._json(400, {"error": "style must be AUTO, CIX, CBI, or COMET"})
            ca = ComicArchive(path, default_image_path=path)
            archive = archive_diagnostics(ca, path)
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
                "archive": archive,
                "warning": archive.get("warning", ""),
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
                archive = archive_diagnostics(ca, path)
                if archive.get("warning"):
                    return self._json(422, {"error": archive["warning"], "archive": archive})
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

            # IMPORTANT: Always create fresh metadata from patch, don't rely on isEmpty
            # Only use existing metadata as a base if patch is truly empty
            if patch:  # If user provided metadata in the patch
                if getattr(md, "isEmpty", False):
                    md = ca.metadataFromFilename(parse_scan_info=True)
                apply_metadata(md, patch)
            else:  # No metadata provided in patch
                return self._json(400, {"error": "metadata patch is required", "path": path, "written_path": target_path})

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
