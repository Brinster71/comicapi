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
    assert "if (base && base.toLowerCase() === picked.toLowerCase()) return normalized;" in html
    assert "clearScanResults();" in html
    assert "fetch('/api/pick_directory?current=' + encodeURIComponent(previous || ''))" in html
    assert "Folder picker unavailable:" in html
    assert "setStatus('Folder selected: ' + input.value + '. Click Scan.'" in html
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
