from __future__ import annotations

from email.parser import BytesParser
from email.policy import default

UploadedFile = tuple[str, str, bytes]


def parse_multipart_form(
    body: bytes,
    content_type: str,
) -> tuple[dict[str, UploadedFile], dict[str, str]]:
    """Parse a bounded multipart request without the deprecated cgi module."""
    if not content_type.lower().startswith("multipart/form-data"):
        raise ValueError("Expected a multipart/form-data request.")

    envelope = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("ascii") + body
    message = BytesParser(policy=default).parsebytes(envelope)
    if not message.is_multipart():
        raise ValueError("Malformed multipart request.")

    files: dict[str, UploadedFile] = {}
    fields: dict[str, str] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is not None:
            files[name] = (
                filename,
                part.get_content_type(),
                payload,
            )
        else:
            charset = part.get_content_charset() or "utf-8"
            fields[name] = payload.decode(charset, errors="replace")
    return files, fields
