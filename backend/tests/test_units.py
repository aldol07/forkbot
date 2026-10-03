from app.services.chunking import chunk_text
from app.services.embeddings import HashEmbedder
from app.services.retrieval import rrf


def test_chunking_respects_size_and_overlap():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(20))
    chunks = chunk_text(text, size=400, overlap=50)
    assert len(chunks) > 5
    assert all(len(c) <= 460 for c in chunks)


def test_rrf_prefers_items_ranked_by_both():
    s = rrf([[1, 2, 3], [3, 4, 1]])
    assert max(s, key=s.get) in (1, 3) and s[1] > s[2] and s[3] > s[4]


def test_hash_embedder_similarity():
    e = HashEmbedder(384)
    a, b, c = e.embed_query("refund policy days"), e.embed_query("refund policy within days"), e.embed_query("express shipping cost")
    dot = lambda x, y: sum(i * j for i, j in zip(x, y))
    assert dot(a, b) > dot(a, c)


def test_gpt_oss_citations_normalised_across_deltas():
    from app.llm.providers import clean_citations
    parts = ["cannot be enrolled【", "1†L1", "-L3】 and [2", "†source] ok [3] fine 5% [see note", " below]"]
    assert "".join(clean_citations(iter(parts))) == "cannot be enrolled[1] and [2] ok [3] fine 5% [see note below]"
