"""Découpage structurel : respecte titres/paragraphes, taille et chevauchement configurables.
(Ce n'est pas un découpage sémantique par embeddings ; il évite de couper au milieu d'un paragraphe.)"""
import re


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    if chunk_size < 100 or not 0 <= overlap < chunk_size:
        raise ValueError("invalid chunk configuration")
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= chunk_size:
            units.append(para)
        else:  # paragraphe trop long : découpe par phrases
            units.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip())
    chunks: list[str] = []
    current = ""
    for u in units:
        while len(u) > chunk_size:  # phrase géante : découpe dure
            if current:
                chunks.append(current); current = ""
            chunks.append(u[:chunk_size]); u = u[chunk_size - overlap:]
        if current and len(current) + 2 + len(u) > chunk_size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            tail = tail[tail.find(" ") + 1:] if tail and " " in tail else tail  # ne pas commencer au milieu d'un mot
            current = (tail + "\n\n" + u).strip() if tail else u
        else:
            current = f"{current}\n\n{u}" if current else u
    if current:
        chunks.append(current)
    return chunks
