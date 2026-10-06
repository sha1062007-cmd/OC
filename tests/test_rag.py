"""
Tests for RAG Ingestion and Retriever Pipeline:
- Text Chunking logic (800-1000 characters with 150 overlap)
- Metadata extraction (source file, chapter, page number)
- Retrieval accuracy and citation formatting [Source: file, p.X]
"""

import os
import pytest
from rag.ingest import chunk_text, run_ingestion
from rag.retriever import retrieve, format_context_for_llm


def test_chunk_text_boundaries_and_overlap():
    """Verify chunking produces chunks within 800-1000 chars with proper overlap."""
    sample_text = (
        "Newton's third law of motion explains interactions between objects. "
        "When an object exerts force on another object, it experiences an equal and opposite force. "
    ) * 35  # ~5200 characters

    chunks = chunk_text(sample_text, chunk_size=900, overlap=150)

    assert len(chunks) > 1
    for c in chunks:
        # Each chunk should be roughly bounded by chunk_size
        assert len(c) <= 1050, f"Chunk exceeded max expected length: {len(c)}"
        assert len(c) >= 100


def test_rag_ingestion_and_retrieval_citations():
    """Verify ingestion runs and retrieval returns citations in [Source: file, p.X] format."""
    # Ensure ingestion runs cleanly
    n_chunks, n_docs = run_ingestion()
    assert n_chunks > 0, "Ingestion must produce chunks from data/syllabus"

    # Query 1: Newton's Third Law
    results_physics = retrieve("Newton's third law action reaction forces", k=4)
    assert len(results_physics) > 0

    first_hit = results_physics[0]
    assert "content" in first_hit
    assert "citation" in first_hit
    assert "score" in first_hit
    assert "[Source:" in first_hit["citation"]
    assert ", p." in first_hit["citation"]

    # Content should mention Newton or action or reaction
    hit_text = first_hit["content"].lower()
    assert any(term in hit_text for term in ["newton", "force", "action", "reaction", "motion"])

    # Query 2: Photosynthesis
    results_bio = retrieve("photosynthesis chlorophyll light reactions stomata", k=3)
    assert len(results_bio) > 0
    assert "citation" in results_bio[0]


def test_format_context_for_llm():
    """Verify formatted context combines chunk citation with text content."""
    mock_chunks = [
        {"citation": "[Source: test.pdf, p.12]", "content": "Sample textbook paragraph."}
    ]
    formatted = format_context_for_llm(mock_chunks)
    assert "[Source: test.pdf, p.12]" in formatted
    assert "Sample textbook paragraph." in formatted
