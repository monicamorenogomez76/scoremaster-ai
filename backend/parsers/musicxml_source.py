"""Uncompressed MusicXML from a .musicxml/.xml upload or a compressed .mxl container."""
import io
from typing import Optional
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile, is_zipfile


def extract_musicxml(content: bytes) -> Optional[bytes]:
    """Returns the score document, or None when the content is not a MusicXML score."""
    try:
        if is_zipfile(io.BytesIO(content)):
            with ZipFile(io.BytesIO(content)) as archive:
                container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
                rootfile = next(
                    element for element in container.iter()
                    if element.tag.rsplit("}", 1)[-1] == "rootfile"
                )
                score_xml = archive.read(rootfile.attrib["full-path"])
        else:
            score_xml = content
        root = ElementTree.fromstring(score_xml)
    except (BadZipFile, ElementTree.ParseError, KeyError, StopIteration, OSError):
        return None

    if root.tag.rsplit("}", 1)[-1] not in {"score-partwise", "score-timewise"}:
        return None
    return score_xml
