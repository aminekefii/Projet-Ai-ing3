"""Unit test for the Markdown→PDF helper. No API key required."""
from agent.export_pdf import markdown_to_pdf_bytes


SAMPLE_PAPER = """# Transformer Attention Mechanisms

## Introduction

This paper reviews attention in transformers [src-1].

## Background

Self-attention was introduced by Vaswani et al. [src-2].

## References

- **[src-1]** Smith, J. (2020). Attention is great. https://example.com/a
- **[src-2]** Vaswani et al. (2017). Attention is all you need. https://arxiv.org/abs/1706.03762
"""


def test_returns_pdf_bytes():
    pdf_bytes = markdown_to_pdf_bytes(SAMPLE_PAPER)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-"), "Output must start with the PDF magic number"
    assert len(pdf_bytes) > 1024, "A real PDF for this content should be at least 1KB"
