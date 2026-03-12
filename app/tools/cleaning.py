import re
import uuid
import hashlib
from datetime import datetime
from typing import Optional


def remove_boilerplate(text: str) -> str:
    """Hapus header redaksi umum dari situs berita Indonesia"""
    patterns = [
        r"Jakarta,?\s*CNBC Indonesia\s*[-–]\s*",
        r"Jakarta,?\s*Bisnis\.com\s*[-–]\s*",
        r"Jakarta,?\s*Detik\.com\s*[-–]\s*",
        r"Jakarta,?\s*Kompas\.com\s*[-–]\s*",
        r"JAKARTA,?\s*[-–]\s*",
        r"Liputan6\.com,?\s*Jakarta\s*[-–]\s*",
        r"Bisnis\.com,\s*JAKARTA\s*[-–]\s*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text


def remove_noise(text: str) -> str:
    """Hapus karakter noise: emoji, tag HTML sisa, whitespace berlebihan"""
    # Hapus tag HTML yang mungkin lolos dari trafilatura
    text = re.sub(r"<[^>]+>", " ", text)
    # Hapus URL yang ikut ter-scrape
    text = re.sub(r"https?://\S+", "", text)
    # Hapus karakter non-printable dan emoji (di luar latin & aksara umum)
    text = re.sub(r"[^\x20-\x7E\u00C0-\u024F\u0600-\u06FF\u0400-\u04FF]", " ", text)
    # Normalisasi whitespace & newline
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fix_truncated_sentence(text: str) -> str:
    """
    Buang kalimat terakhir yang terpotong (tidak diakhiri tanda baca).
    Relevan karena content di-limit 500 karakter.
    """
    if not text:
        return text
    sentence_enders = (".", "!", "?", "\"", "'")
    if text.endswith(sentence_enders):
        return text
    # Potong sampai tanda baca terakhir yang valid
    last_end = max(
        text.rfind("."),
        text.rfind("!"),
        text.rfind("?"),
    )
    if last_end > len(text) * 0.4:  # minimal 40% teks masih tersisa
        return text[: last_end + 1].strip()
    return text  # fallback: kembalikan apa adanya


def normalize_title(title: str) -> str:
    """Ubah HURUF KAPITAL SEMUA jadi Title Case yang lebih rapi"""
    if title.isupper():
        return title.title()
    return title.strip()


def clean_text(text: str) -> str:
    """Pipeline cleaning lengkap untuk body artikel"""
    if not text:
        return ""
    text = remove_boilerplate(text)
    text = remove_noise(text)
    text = fix_truncated_sentence(text)
    return text

def parse_article(raw: dict) -> dict:
    """
    Strukturisasi field dari output MacroCommodityNews (.dict() / model_dump()).
    Input: dict hasil .model_dump() dari MacroCommodityNews
    Output: dict bersih siap di-embed dan di-upsert ke Qdrant
    """
    # Pastikan published_at adalah string ISO yang konsisten
    published_at = raw.get("published_at")
    if isinstance(published_at, datetime):
        published_at_str = published_at.isoformat()
    elif isinstance(published_at, str):
        published_at_str = published_at
    else:
        published_at_str = datetime.utcnow().isoformat()

    return {
        "title":               normalize_title(raw.get("title", "")),
        "summary":             raw.get("summary", "") or "",
        "url":                 raw.get("url", "").strip(),
        "published_at":        published_at_str,
        "source":              raw.get("source", "unknown"),
        "content":             raw.get("content", "") or "",
        "related_commodities": raw.get("related_commodities", []),
        "related_stocks":      raw.get("related_stocks", []),
        "embedding_source":    raw.get("embedding_source", "") or "",
    }


def validate_article(article: dict) -> bool:
    """
    Validasi minimal sebelum disimpan ke Qdrant.
    Return False jika artikel tidak layak disimpan.
    """
    if not article.get("title", "").strip():
        return False
    if not article.get("url", "").strip():
        return False
    if not article.get("content", "").strip() and not article.get("summary", "").strip():
        return False
    return True


def build_embed_text(article: dict) -> str:
    """
    Bangun teks final yang akan di-encode jadi vector.
    Prioritaskan embedding_source jika sudah tersedia (sudah di-build di scraper).
    Fallback ke title + content jika embedding_source kosong.
    """
    embedding_source = article.get("embedding_source", "").strip()
    
    if embedding_source:
        # Sudah di-build oleh scraper, tinggal bersihkan noise-nya
        return clean_text(embedding_source)

    # Fallback manual
    title   = article.get("title", "")
    content = article.get("content", "") or article.get("summary", "")
    stocks  = ", ".join(article.get("related_stocks", []))
    commods = ", ".join(article.get("related_commodities", []))

    parts = [f"JUDUL: {title}."]
    if stocks:
        parts.append(f"EMITEN: {stocks}.")
    if commods:
        parts.append(f"KOMODITAS: {commods}.")
    parts.append(f"KONTEKS: {content[:300]}")

    return clean_text(" ".join(parts))


def generate_point_id(url: str) -> str:
    """
    Generate UUID deterministik dari URL.
    Idempotent: URL yang sama selalu menghasilkan ID yang sama,
    sehingga upsert aman dijalankan ulang tanpa duplikasi.
    """
    return str(uuid.UUID(hashlib.md5(url.encode()).hexdigest()))


def preprocess(raw: dict) -> Optional[dict]:
    """
    Full preprocessing pipeline untuk 1 artikel.
    Input : dict dari MacroCommodityNews.model_dump()
    Output: dict siap upsert, atau None jika tidak valid
    """
    article = parse_article(raw)

    # Bersihkan field teks
    article["title"]            = clean_text(article["title"]) or normalize_title(raw.get("title", ""))
    article["content"]          = clean_text(article["content"])
    article["summary"]          = clean_text(article["summary"])
    article["embedding_source"] = build_embed_text(article)

    if not validate_article(article):
        return None

    # Tambah ID untuk Qdrant
    article["point_id"] = generate_point_id(article["url"])

    return article

def chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> list[str]:
    """
    Potong teks panjang jadi beberapa chunk dengan overlap.
    overlap: jumlah karakter yang di-share antar chunk agar konteks tidak putus.
    """
    if len(text) <= max_chars:
        return [text]  # tidak perlu dichunk
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        # Potong di batas kalimat terdekat agar tidak putus di tengah kalimat
        if end < len(text):
            last_period = chunk.rfind(".")
            if last_period > max_chars * 0.6:  # minimal 60% chunk terisi
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1
        chunks.append(chunk.strip())
        start = end - overlap  # mundur overlap karakter untuk konteks
    return chunks


def preprocess_with_chunks(raw: dict) -> list[dict]:
    """
    Versi preprocess() yang mendukung chunking.
    Return list of dicts — 1 artikel bisa jadi beberapa chunk.
    """
    article = preprocess(raw)
    if article is None:
        return []

    content = article["content"]
    chunks = chunk_text(content)

    if len(chunks) == 1:
        return [article]  # tidak ada chunking

    result = []
    for i, chunk in enumerate(chunks):
        chunk_article = article.copy()
        chunk_article["content"]        = chunk
        chunk_article["chunk_index"]    = i          
        chunk_article["total_chunks"]   = len(chunks)
        chunk_article["embedding_source"] = build_embed_text({
            **chunk_article, "content": chunk
        })
        # ID unik per chunk: hash dari URL + index chunk
        chunk_url = f"{article['url']}#chunk{i}"
        chunk_article["point_id"] = generate_point_id(chunk_url)
        result.append(chunk_article)

    return result
