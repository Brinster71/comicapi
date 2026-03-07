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
    assert "input.value = combinePickedFolderWithCurrentPath(current, handle.name);" in html
    assert "setStatus('Folder selected: ' + input.value" in html
    assert "try {" in html and "setStatus('Write failed: ' + (err && err.message ? err.message : 'request failed'), true);" in html
