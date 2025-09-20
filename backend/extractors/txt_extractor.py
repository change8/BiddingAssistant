from typing import Optional


def extract_text_from_txt(path: str, encoding: Optional[str] = None) -> str:
    encodings = [encoding] if encoding else ["utf-8", "gbk", "gb18030", "latin1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    with open(path, "rb") as f:
        return f.read().decode(errors="ignore")

