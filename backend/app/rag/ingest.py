"""
One-time ingestion: handbook PDF -> page-aware chunks -> (embeddings + FAISS) -> data/index/<role>/

Run from the backend/ folder:
    python -m app.rag.ingest              # both handbooks
    python -m app.rag.ingest student      # only one
    python -m app.rag.ingest --no-embed   # chunks only (BM25 keyword index; no model download)

Each role gets its OWN folder, chunks file and FAISS index. They are never merged.
"""
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass

import pymupdf

from app.config import settings

HANDBOOKS = {
    "student": {"label": "Student Handbook", "pdf": "student_handbook.pdf"},
    "faculty": {"label": "Faculty Handbook", "pdf": "faculty_handbook.pdf"},
}

TARGET_CHARS = 1100   # aim for chunks of about this size (~250 tokens)
MAX_CHARS = 1500      # hard-ish ceiling before we force a split
OVERLAP_CHARS = 180   # tail of the previous chunk repeated at the start of the next
SMALL_CHARS = 350    # fragments smaller than this are merged into the previous chunk of the same section
MIN_CHARS = 60        # drop chunks smaller than this (page numbers, stray fragments)

_NUMBERED = re.compile(r"^(\d{1,2}(\.\d{1,2}){0,3}\.?)\s+\S")
_ANNEX = re.compile(r"^annexure\b", re.I)
_BULLET = re.compile(r"^([•\-–▪●○]|\(?[a-zA-Z0-9]{1,3}[.)])\s*")


@dataclass
class Chunk:
    id: str
    role: str
    handbook: str
    source: str
    page_start: int          # PDF page number (what a PDF viewer shows)
    page_end: int
    printed_start: int | None  # page number printed on the handbook page (None = front matter)
    printed_end: int | None
    section: str
    text: str                # text shown as evidence
    kind: str = "text"       # text | table
    major_key: str = ""      # annexure + numbered heading this chunk belongs to
    overlap: int = 0         # characters at the start that are copied from the previous chunk


# --------------------------------------------------------------------------- extraction
def _is_bold(span) -> bool:
    return "bold" in span["font"].lower() or bool(span["flags"] & 16)


def _printed_offset(doc) -> int:
    """Printed page number = PDF page - offset. Found by majority vote over page footers."""
    votes = Counter()
    for i, page in enumerate(doc):
        h = page.rect.height
        for w in page.get_text("words"):
            if w[1] > h * 0.90 and re.fullmatch(r"\d{1,3}", w[4]):
                votes[(i + 1) - int(w[4])] += 1
    return votes.most_common(1)[0][0] if votes else 0


def _in_any(rect, rects, frac=0.5) -> bool:
    area = rect.get_area() or 1
    for r in rects:
        inter = rect & r
        if not inter.is_empty and inter.get_area() / area >= frac:
            return True
    return False


def extract_items(page):
    """Return a top-to-bottom list of ('heading'|'text'|'table', text) for one page."""
    h = page.rect.height
    tables = page.find_tables().tables
    trects = [pymupdf.Rect(t.bbox) for t in tables]
    items = []  # (y, kind, text)
    pending_num = None  # a bare bold section number ("2.15.") waiting for its title line

    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        para = []
        para_y = None

        def flush():
            nonlocal para, para_y
            if para:
                items.append((para_y, "text", "\n".join(para)))
            para, para_y = [], None

        for ln in b["lines"]:
            spans = [s for s in ln["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in ln["spans"]).strip()
            y = ln["bbox"][1]
            # lines that sit inside a detected table are emitted via the table's markdown instead
            lr = pymupdf.Rect(ln["bbox"])
            cx, cy = (lr.x0 + lr.x1) / 2, (lr.y0 + lr.y1) / 2
            if any(r.x0 - 2 <= cx <= r.x1 + 2 and r.y0 - 2 <= cy <= r.y1 + 2 for r in trects):
                flush()
                continue
            # page numbers in header/footer margins
            if re.fullmatch(r"\d{1,3}", text) and (y < h * 0.09 or y > h * 0.90):
                continue
            all_bold = all(_is_bold(s) for s in spans)
            if all_bold and re.fullmatch(r"\d{1,2}(\.\d{1,2}){0,3}\.?", text):
                flush()
                pending_num = text
                continue
            if all_bold and pending_num and len(text) <= 110:
                text = f"{pending_num} {text}"
                pending_num = None
            elif not all_bold:
                pending_num = None
            if all_bold and len(text) <= 110 and not re.match(r"^note\b", text, re.I) and not re.fullmatch(r"[\d\W]+", text):
                flush()
                items.append((y, "heading", text))
                continue
            if para_y is None:
                para_y = y
            if para and not _BULLET.match(text):
                para[-1] += " " + text
            else:
                para.append(text)
        flush()

    for t, r in zip(tables, trects):
        try:
            md = t.to_markdown().strip()
        except Exception:
            continue
        md = re.sub(r"<br>", " ", md)
        if md:
            items.append((r.y0, "table", md))

    items.sort(key=lambda x: x[0])
    return [(k, t) for _, k, t in items]


_TOC_LINE = re.compile(r"(\s\d{1,3}\s*$)|(^\s*\d{1,2}(\.\d{1,2}){0,3}\.?\s+\S)|(^\s*annexure\b)|(^\s*[IVX]+\.\s)|(^\s*\d{1,3}\s*$)|(^\s*\d{1,2}(\.\d{1,2}){0,3}\.?\s*$)", re.I)


def toc_pages(doc) -> set:
    """Pages that are part of the table of contents (they would otherwise pollute headings)."""
    pages, in_toc = set(), False
    for i, page in enumerate(doc, start=1):
        lines = [l.strip() for l in page.get_text("text").splitlines() if l.strip()]
        head = " ".join(lines[:4]).lower()
        if "table of contents" in head or "contents" == head.strip():
            in_toc = True
        elif in_toc:
            tocish = sum(bool(_TOC_LINE.search(l)) and len(l) < 110 for l in lines)
            if not lines or tocish / len(lines) < 0.6:
                in_toc = False
        if in_toc:
            pages.add(i)
    return pages


def merge_headings(items):
    """Join consecutive heading lines that are really one wrapped heading."""
    out = []
    for kind, text in items:
        if kind == "heading" and out and out[-1][0] == "heading" and not _NUMBERED.match(text) and not _ANNEX.match(text) and len(out[-1][1]) > 70:
            out[-1] = ("heading", out[-1][1] + " " + text)
        else:
            out.append((kind, text))
    return out


# --------------------------------------------------------------------------- chunking
def _split_long(text: str):
    """Split one very long paragraph on sentence boundaries."""
    sents = re.split(r"(?<=[.;:])\s+", text)
    parts, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) + 1 > MAX_CHARS:
            parts.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        parts.append(cur)
    return parts


def _split_table(md: str):
    """Split a big markdown table by rows, repeating the header row."""
    lines = md.splitlines()
    if len(md) <= MAX_CHARS or len(lines) < 4:
        return [md]
    head, rows = lines[:2], lines[2:]
    parts, cur = [], []
    for r in rows:
        if cur and len("\n".join(head + cur + [r])) > MAX_CHARS:
            parts.append("\n".join(head + cur))
            cur = []
        cur.append(r)
    if cur:
        parts.append("\n".join(head + cur))
    return parts


def build_chunks(role: str):
    meta = HANDBOOKS[role]
    pdf_path = settings.handbook_dir / meta["pdf"]
    if not pdf_path.exists():
        raise FileNotFoundError(f"Handbook PDF not found: {pdf_path}")
    doc = pymupdf.open(pdf_path)
    offset = _printed_offset(doc)

    def printed(p):
        return p - offset if p - offset >= 1 else None

    # 1) flatten the document into (page, kind, text, section) pieces
    annex = major = sub = ""
    last_top = None
    pieces = []
    skip = toc_pages(doc)
    print(f"[{role}] skipping table-of-contents pages: {sorted(skip)}")
    for pno, page in enumerate(doc, start=1):
        if pno in skip:
            continue
        for kind, text in merge_headings(extract_items(page)):
            if kind == "heading":
                if _ANNEX.match(text):
                    annex, major, sub = text, "", ""
                    last_top = None
                elif _NUMBERED.match(text):
                    n = int(re.match(r"\d+", text).group())
                    if annex and last_top is not None and n > last_top + 1:
                        annex = ""  # numbering jumped (e.g. 11 -> 24): we have left the annexure
                    if not annex and major and last_top is not None and n < last_top and "." not in text.split()[0].rstrip("."):
                        sub = text  # numbering restarted: a nested list inside the current section
                    else:
                        major, sub, last_top = text, "", n
                else:
                    sub = text
                continue
            section = " > ".join(x for x in (annex, major, sub) if x)
            pieces.append({"page": pno, "kind": kind, "text": text, "section": section, "major": (annex, major)})

    # 2) group pieces into chunks. A new chunk always starts when the numbered heading changes,
    #    and tables never share a chunk with prose.
    chunks, cur, cur_len, cur_major = [], [], 0, None

    def emit(carry_overlap: bool):
        nonlocal cur, cur_len
        real = [p for p in cur if not p.get("ov")]
        if not real:
            cur, cur_len = [], 0
            return
        body = "\n".join(p["text"] for p in cur)
        if len(body) >= MIN_CHARS:
            pages = [p["page"] for p in real]
            chunks.append(
                Chunk(
                    id=f"{role}-{len(chunks):04d}",
                    role=role,
                    handbook=meta["label"],
                    source=meta["pdf"],
                    page_start=min(pages),
                    page_end=max(pages),
                    printed_start=printed(min(pages)),
                    printed_end=printed(max(pages)),
                    section=real[0]["section"],
                    text=body,
                    kind="table" if all(p["kind"] == "table" for p in real) else "text",
                    major_key=" | ".join(real[0]["major"]),
                    overlap=(len(cur[0]["text"]) + 1) if cur[0].get("ov") else 0,
                )
            )
        last = cur[-1]
        cur, cur_len = [], 0
        if carry_overlap and last["kind"] == "text":
            tail = last["text"][-OVERLAP_CHARS:]
            tail = tail[tail.find(" ") + 1:] if " " in tail else tail
            cur = [{**last, "text": tail, "ov": True}]
            cur_len = len(tail)

    for p in pieces:
        if p["kind"] == "table":
            subparts = _split_table(p["text"])
        elif len(p["text"]) > MAX_CHARS:
            subparts = _split_long(p["text"])
        else:
            subparts = [p["text"]]
        for sp in subparts:
            piece = {**p, "text": sp}
            if cur and p["major"] != cur_major:
                emit(False)
            elif cur and (
                cur_len + len(sp) > MAX_CHARS
                or cur_len >= TARGET_CHARS
                or p["kind"] == "table"
                or cur[-1]["kind"] == "table"
            ):
                emit(p["kind"] == "text")
            cur.append(piece)
            cur_len += len(sp)
            cur_major = p["major"]
    emit(False)
    return _merge_small(chunks)


def _merge_small(chunks):
    """Glue tiny fragments (table remnants, one-line sub-sections) onto the previous chunk of the same section."""
    out = []
    for c in chunks:
        body_len = len(c.text) - c.overlap
        if (
            out
            and body_len < SMALL_CHARS
            and c.major_key == out[-1].major_key
            and len(out[-1].text) + body_len <= MAX_CHARS + 300
            and c.page_start - out[-1].page_end <= 1
        ):
            prev = out[-1]
            prev.text = prev.text + "\n" + c.text[c.overlap:]
            prev.page_end = max(prev.page_end, c.page_end)
            prev.printed_end = c.printed_end if c.printed_end else prev.printed_end
            if c.kind != "table" or prev.kind != "table":
                prev.kind = "text"
        else:
            out.append(c)
    for i, c in enumerate(out):
        c.id = f"{c.role}-{i:04d}"
    return out


def retrieval_text(c: dict) -> str:
    """Text used for embedding/BM25: section path + body (the section name helps retrieval)."""
    return (c["section"] + "\n" if c["section"] else "") + c["text"]


# --------------------------------------------------------------------------- CLI
def ingest_role(role: str, embed: bool = True):
    out = settings.index_dir / role
    out.mkdir(parents=True, exist_ok=True)
    chunks = [asdict(c) for c in build_chunks(role)]
    (out / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    info = {"role": role, "handbook": HANDBOOKS[role]["label"], "n_chunks": len(chunks), "embed_model": None}
    print(f"[{role}] {len(chunks)} chunks -> {out/'chunks.json'}")

    if embed:
        import faiss
        import numpy as np

        from app.rag.embeddings import embed_passages

        vecs = np.asarray(embed_passages([retrieval_text(c) for c in chunks]), dtype="float32")
        faiss.normalize_L2(vecs)
        index = faiss.IndexFlatIP(vecs.shape[1])
        index.add(vecs)
        faiss.write_index(index, str(out / "vectors.faiss"))
        info["embed_model"] = settings.embed_model
        info["dim"] = int(vecs.shape[1])
        print(f"[{role}] FAISS index built ({vecs.shape[0]} x {vecs.shape[1]}) with {settings.embed_model}")
    (out / "meta.json").write_text(json.dumps(info, indent=1), encoding="utf-8")


def main(argv):
    embed = "--no-embed" not in argv
    roles = [a for a in argv if a in HANDBOOKS] or list(HANDBOOKS)
    for r in roles:
        ingest_role(r, embed=embed)


if __name__ == "__main__":
    main(sys.argv[1:])
