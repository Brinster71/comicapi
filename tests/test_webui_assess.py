from comicapi.webui import server


class DummyMd:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class DummyArchive:
    def hasMetadata(self, style):
        return style == server.MetaDataStyle.CIX

    def readMetadata(self, style):
        return DummyMd(series="", issue="", title="", year=None, publisher="")

    def metadataFromFilename(self, parse_scan_info=True):
        return DummyMd(series="Saga", issue="1", title="Chapter One", year=2012, publisher="Image")


def test_build_assessment_prefers_filename_when_current_missing():
    result = server.build_assessment(DummyArchive(), "/tmp/Saga 001.cbz", "AUTO")

    assert result["style"] == "CIX"
    assert result["detected_style"] == "CIX"
    assert result["recommended_metadata"]["series"] == "Saga"
    assert result["recommended_metadata"]["issue"] == "1"
    assert result["summary"]["series"] == "Saga"



def test_index_html_has_library_picker_field_update_and_write_error_status():
    html = server.INDEX_HTML
    assert "function combinePickedFolderWithCurrentPath" in html
    assert "current.replace(/\\\\/g, '/')" in html
    assert ".replace(/\\/+$/, '')" in html
    assert "if (base && base.toLowerCase() === picked.toLowerCase()) return normalized;" in html
    assert "parts[parts.length - 1] = picked;" in html
    assert "return '/' + parts.join('/')" in html
    assert "clearScanResults();" in html
    assert "id='rootPathPicker'" in html
    assert "function extractPickedFolderNameFromFiles(files)" in html
    assert "async function browseLibraryPathNative(previous)" in html
    assert "fetch('/api/pick_directory?current=' + encodeURIComponent(prior || ''), { signal: controller.signal })" in html
    assert "const controller = new AbortController();" in html
    assert "setTimeout(() => controller.abort(), 25000);" in html
    assert "showInlinePathEntry(" in html
    assert "id='pathPickOverlay'" in html
    assert "Folder picker timed out; enter absolute path manually" in html
    assert "async function browseLibraryPath()" in html
    assert "window.showDirectoryPicker" in html
    assert "browseDirectoryPathBrowser(previous)" in html
    assert "async function browseBulkLibraryPath()" in html
    assert "Bulk folder selected in browser: " in html
    assert "const picked = await browseLibraryPathNative(previous);" in html
    assert "const picked = await browseBulkLibraryPathNative(previous);" in html
    assert "Folder picker unavailable:" in html
    assert "setStatus('Folder selected: ' + input.value + '. Click Scan.'" in html
    assert "Folder selected in browser: " in html
    assert "Names with spaces also work (e.g. {Start Year})" in html
    assert "id='singleNamingPreview' class='naming-preview' placeholder='Naming preview will appear here...'" in html
    assert "id='singleNamingPreview' class='naming-preview' placeholder='Naming preview will appear here...' readonly" not in html
    assert "const preview = (document.getElementById('singleNamingPreview').value || '').trim();" in html
    assert "function isAbsolutePath(path)" in html
    assert "path = combinePath(rootPath, path);" in html
    assert "selected file path must be absolute on the server" in html
    assert "try {" in html and "setStatus('Write failed: ' + (err && err.message ? err.message : 'request failed'), true);" in html



def test_index_html_has_diagnostics_and_write_browse_hooks():
    html = server.INDEX_HTML
    assert "id='diagBanner'" in html
    assert "async function loadRuntimeDiagnostics()" in html
    assert "fetch('/api/version')" in html
    assert "function browseWritePath()" in html
    assert "function onWriteFilePicked(evt)" in html
    assert "setStatus('Scanning library…', false);" in html
    assert "setStatus('Scan failed: ' + (data.error || ('HTTP ' + res.status)), true);" in html
    assert "function buildComicVineQueryFromAssessment(data)" in html
    assert "const parts = [series, issue, title].filter(Boolean);" in html
    assert "const autoQuery = buildComicVineQueryFromAssessment(data);" in html
    assert "cvQuery.value = autoQuery;" in html


def test_index_html_has_bulk_apply_sort_and_drag_controls():
    html = server.INDEX_HTML
    assert "onclick='bulkApplyFieldToOthers(\"series\")'" in html
    assert "onclick='bulkApplyFieldToOthers(\"publisher\")'" in html
    assert "function bulkApplyFieldToOthers(field)" in html
    assert "onclick='bulkIncrementFieldFromSelected(\"issue\")'" in html
    assert "function incrementFirstNumberInText(text, offset)" in html
    assert "function bulkIncrementFieldFromSelected(field)" in html
    assert "Incremented ' + field + ' down" in html
    assert "function bulkSortCurrentRows(showMessage=true)" in html
    assert "tr.setAttribute('draggable', 'true');" in html
    assert "function bulkMoveRow(dragId, targetId)" in html
    assert "onclick='bulkWriteSelected()'" in html
    assert "onclick='bulkRetryFailed()'" in html
    assert "function buildBulkMetadataPatch(row)" in html
    assert "async function bulkWriteRows(rows, label)" in html
    assert "async function bulkWriteSelected()" in html
    assert "async function bulkRetryFailed()" in html
    assert "id='bulkPreviewTable'" in html
    assert "function renderBulkPreview()" in html
    assert "Core mapped values are shown directly for fast review before write." in html
    assert "<th>Status</th><th>Confidence</th><th>Write</th>" in html
    assert "onclick='bulkApplyCvToBatch(\"selected\")'" in html
    assert "onclick='bulkApplyCvToBatch(\"visible\")'" in html
    assert "function applyComicVineIssueToBulkRow(row, issue)" in html
    assert "function bulkApplyCvToBatch(scope)" in html
    assert "function deriveQueryFromPath(pathText)" in html
    assert "setStatus('Auto-filled search query from filename.', false);" in html
    assert "setStatus('Auto-filled bulk search query from filename hints.', false);" in html
    assert "id='bulkAppliedReadable'" in html
    assert "function renderBulkAppliedReadable(row)" in html
    assert "Ready (write will create metadata style)" in html
    assert "id='bulkGapToggleBtn'" in html
    assert "function toggleBulkFieldGapSection()" in html
    assert "function renderBulkFieldGap(row)" in html
    assert "issueName: row.issueName" in html
    assert "comicVineIssueId: row.comicVineIssueId" in html


def test_index_html_has_naming_and_recursive_scan_controls():
    html = server.INDEX_HTML
    assert "id='scanRecursive'" in html
    assert "id='bulkScanRecursive'" in html
    assert "&recurse=' + recurse" in html
    assert "id='singleNamingPattern'" in html
    assert "id='bulkNamingPattern'" in html
    assert "function previewNaming(mode)" in html
    assert "function saveNamingPattern(mode)" in html
    assert "function previousNamingPattern(mode)" in html
    assert "function clearNamingSection(mode)" in html
    assert "function toggleNamingApply(mode)" in html
    assert "function toggleNamingOverride(mode)" in html
    assert "function buildSingleNamingWriteTarget(path)" in html
    assert "function buildBulkNamingWriteTarget(row)" in html
