import os
import sys
import tempfile
import zipfile

sys.path.insert(0, '/workspace')

from comicapi.comicarchive import ComicArchive, MetaDataStyle
from comicapi.comicinfoxml import ComicInfoXml
from comicapi.comet import CoMet
from comicapi.genericmetadata import GenericMetadata


def make_temp_cbz():
    fd, path = tempfile.mkstemp(suffix='.cbz')
    os.close(fd)
    os.unlink(path)
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('1.jpg', b'\xff\xd8\xff\xd9')
    return path


def make_md():
    md = GenericMetadata()
    md.series = 'Saga'
    md.title = 'Chapter One'
    md.issue = '1'
    return md


def test_comicinfoxml_string_from_metadata_returns_str():
    out = ComicInfoXml().stringFromMetadata(make_md())
    assert isinstance(out, str)
    assert out.startswith('<?xml version="1.0"?>')


def test_comet_string_from_metadata_returns_str():
    out = CoMet().stringFromMetadata(make_md())
    assert isinstance(out, str)
    assert out.startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_write_cix_metadata_no_str_bytes_typeerror():
    path = make_temp_cbz()
    try:
        ca = ComicArchive(path, default_image_path=path)
        md = ca.metadataFromFilename(parse_scan_info=True)
        md.series = 'Saga'
        md.issue = '1'
        ok = ca.writeMetadata(md, MetaDataStyle.CIX)
        assert ok is True
    finally:
        if os.path.exists(path):
            os.remove(path)
