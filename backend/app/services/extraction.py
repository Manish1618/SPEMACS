"""Document text extraction and entity/relationship extraction.

Text extraction handles what is actually installed, and reports honestly when a
format cannot be read rather than substituting a placeholder string. The previous
implementation returned "Extracted forensic OCR text for <file>" for anything that
was not UTF-8, which looked like a successful extraction and was not.

Entity extraction runs the model when one is configured and falls back to pattern
matching otherwise. Extracted entities are proposals: they are returned for
confirmation and are not written into the graph until an investigator accepts
them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.services.llm import LLMUnavailable, get_provider


@dataclass
class ExtractionResult:
    text: str
    method: str
    ok: bool
    note: str = ""


def extract_text(content: bytes, filename: str, content_type: str = "") -> ExtractionResult:
    """Get readable text out of an uploaded file."""
    lowered = (filename or "").lower()

    if lowered.endswith((".txt", ".csv", ".json", ".md", ".log")) or content_type.startswith("text/"):
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return ExtractionResult(content.decode(encoding), f"text ({encoding})", True)
            except UnicodeDecodeError:
                continue
        return ExtractionResult("", "text", False, "The file could not be decoded as text.")

    if lowered.endswith(".pdf"):
        try:
            import pypdf  # noqa: PLC0415

            import io

            reader = pypdf.PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(pages).strip()
            if text:
                return ExtractionResult(text, f"pypdf ({len(pages)} pages)", True)
            return ExtractionResult(
                "",
                "pypdf",
                False,
                "The PDF holds no extractable text layer. It is probably a scan, which needs "
                "optical character recognition; no OCR engine is installed.",
            )
        except ImportError:
            return ExtractionResult(
                "", "none", False,
                "No PDF reader is installed. Install pypdf to extract text from PDF files.",
            )
        except Exception as exc:  # noqa: BLE001
            return ExtractionResult("", "pypdf", False, f"The PDF could not be read: {exc}")

    if lowered.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")):
        try:
            import io

            import pytesseract  # noqa: PLC0415
            from PIL import Image  # noqa: PLC0415

            text = pytesseract.image_to_string(Image.open(io.BytesIO(content))).strip()
            if text:
                return ExtractionResult(text, "tesseract", True)
            return ExtractionResult("", "tesseract", False, "No text was recognised in the image.")
        except ImportError:
            return ExtractionResult(
                "", "none", False,
                "No optical character recognition engine is installed. Install pytesseract and "
                "Tesseract to read text from images.",
            )
        except Exception as exc:  # noqa: BLE001
            return ExtractionResult("", "tesseract", False, f"The image could not be read: {exc}")

    # Unknown type: try text, and say so plainly if that fails.
    try:
        return ExtractionResult(content.decode("utf-8"), "text (assumed)", True)
    except UnicodeDecodeError:
        return ExtractionResult(
            "", "none", False,
            f"No extractor is available for {filename or 'this file'}. The file is stored and "
            "hashed, but its content has not been indexed and will not be searchable.",
        )


# ---------------------------------------------------------------------------
# Entity and relationship extraction
# ---------------------------------------------------------------------------

_PATTERNS = {
    "PHONE": re.compile(r"\+?\d{1,3}[-\s]?\d{5}[-\s]?\d{5}|\+?\d{10,13}"),
    "VEHICLE": re.compile(r"\b[A-Z]{2}-\d{2}-[A-Z]{1,2}-\d{4}\b"),
    "ACCOUNT": re.compile(r"\b(?:account|a/c)\s*(?:no\.?|number)?\s*#?\s*(\d{4,12})\b", re.IGNORECASE),
    "AMOUNT": re.compile(r"\b(?:USD|INR|EUR|GBP|Rs\.?)\s?[\d,]+(?:\.\d{2})?\b"),
    "DATE": re.compile(r"\b\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b"),
}

_EXTRACTION_INSTRUCTION = """\
You extract structured investigative information from a document. Report only what the text
states. Do not infer, complete, or add anything from outside the document.

Return a JSON object:
{
  "entities": [
    {"label": string, "entity_type": "PERSON"|"PHONE"|"VEHICLE"|"ORGANIZATION"|"LOCATION"|"ACCOUNT",
     "mention": string (the exact wording in the text), "confidence": number 0-1}
  ],
  "relationships": [
    {"source": string, "target": string, "rel_type": string,
     "quote": string (the exact sentence supporting it), "confidence": number 0-1}
  ],
  "events": [
    {"title": string, "timestamp": string or null, "location": string or null,
     "quote": string, "confidence": number 0-1}
  ]
}

Use the labels exactly as they appear in the text. If the document does not state a
relationship explicitly, do not include it. Return the JSON object only."""


def extract_entities(text: str, use_model: bool = True) -> Dict[str, Any]:
    """Propose entities, relationships and events found in a document."""
    if not text or not text.strip():
        return {
            "entities": [], "relationships": [], "events": [],
            "method": "none", "note": "The document holds no text to extract from.",
        }

    provider = get_provider() if use_model else None
    if provider is not None:
        try:
            payload = provider.complete_json(
                _EXTRACTION_INSTRUCTION,
                f"DOCUMENT\n\n{text[:12000]}",
            )
            if payload and isinstance(payload.get("entities"), list):
                payload.setdefault("relationships", [])
                payload.setdefault("events", [])
                payload["method"] = f"model:{provider.active_model}"
                payload["note"] = (
                    "Extracted entities are proposals. Nothing is written to the knowledge graph "
                    "until an investigator confirms them."
                )
                return payload
        except LLMUnavailable:
            pass
        except Exception:  # noqa: BLE001
            pass

    # Pattern fallback: high precision on identifiers, no relationship inference.
    entities: List[Dict[str, Any]] = []
    seen = set()

    for entity_type, pattern in _PATTERNS.items():
        if entity_type in ("AMOUNT", "DATE"):
            continue
        for match in pattern.finditer(text):
            value = match.group(0).strip()
            key = (entity_type, value.lower())
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                {
                    "label": value,
                    "entity_type": entity_type,
                    "mention": value,
                    "confidence": 0.9,
                }
            )

    # Personal names: honorific followed by capitalised words.
    for match in re.finditer(r"\b(?:Mr|Mrs|Ms|Dr|Shri|Smt)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", text):
        name = match.group(1)
        if ("PERSON", name.lower()) in seen:
            continue
        seen.add(("PERSON", name.lower()))
        entities.append(
            {"label": name, "entity_type": "PERSON", "mention": match.group(0), "confidence": 0.75}
        )

    for match in re.finditer(
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+"
        r"(?:Ltd|Limited|Pvt|Holdings|Logistics|AG|FZE|LLC|Corporation|Company))\b",
        text,
    ):
        name = match.group(1)
        if ("ORGANIZATION", name.lower()) in seen:
            continue
        seen.add(("ORGANIZATION", name.lower()))
        entities.append(
            {"label": name, "entity_type": "ORGANIZATION", "mention": name, "confidence": 0.8}
        )

    return {
        "entities": entities,
        "relationships": [],
        "events": [],
        "method": "pattern matching",
        "note": (
            "Extracted by pattern matching because no language model was available. Identifiers "
            "such as phone numbers and registration marks are reliable; names are less so, and no "
            "relationships were inferred. Nothing is written to the knowledge graph until an "
            "investigator confirms it."
        ),
    }
