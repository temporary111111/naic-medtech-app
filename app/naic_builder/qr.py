from __future__ import annotations

import io

import segno


def qr_svg(value: str, *, scale: int = 8, border: int = 4) -> str:
    qr = segno.make(value, error="m", micro=False)
    return qr.svg_inline(scale=scale, border=border, dark="#111111", light="#ffffff")


def qr_svg_bytes(value: str, *, scale: int = 10, border: int = 4) -> bytes:
    qr = segno.make(value, error="m", micro=False)
    buffer = io.BytesIO()
    qr.save(
        buffer,
        kind="svg",
        scale=scale,
        border=border,
        xmldecl=True,
        dark="#111111",
        light="#ffffff",
    )
    return buffer.getvalue()
