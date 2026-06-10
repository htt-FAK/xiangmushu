"""Compare MarkItDown vs pypdf PDF extraction quality."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.kb_extract import _extract_pdf_blocks_markitdown, _extract_pdf_blocks_pypdf

PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/historical/项目计划书.pdf"

def evaluate(label: str, blocks):
    total_chars = sum(len(b.text) for b in blocks)
    total_blocks = len(blocks)
    has_table = any("table" in b.block_type or "|" in b.text[:200] for b in blocks)
    chapters = [b.chapter for b in blocks if b.chapter]
    print(f"\n{'='*50}")
    print(f"[{label}]")
    print(f"  Blocks:      {total_blocks}")
    print(f"  Total chars: {total_chars:,}")
    print(f"  Has table:   {has_table}")
    print(f"  Chapters:    {chapters[:8]}{'...' if len(chapters)>8 else ''}")
    # Show first 300 chars of first block as sample
    if blocks:
        sample = blocks[0].text[:300].replace('\n', '\\n')
        print(f"  Sample:      {sample}...")
    print(f"{'='*50}")
    return total_chars

print(f"Testing PDF: {PDF_PATH}")
print(f"File size: {os.path.getsize(PDF_PATH):,} bytes")

# Test pypdf
t0 = time.time()
pypdf_blocks = _extract_pdf_blocks_pypdf(PDF_PATH)
pypdf_time = time.time() - t0
pypdf_chars = evaluate(f"pypdf ({pypdf_time:.2f}s)", pypdf_blocks)

# Test MarkItDown
t0 = time.time()
md_blocks = _extract_pdf_blocks_markitdown(PDF_PATH)
md_time = time.time() - t0
md_chars = evaluate(f"MarkItDown ({md_time:.2f}s)", md_blocks)

# Summary
print(f"\n{'='*50}")
print("COMPARISON SUMMARY")
print(f"{'='*50}")
char_diff = md_chars - pypdf_chars
pct = (char_diff / max(pypdf_chars, 1)) * 100
print(f"  pypdf:      {pypdf_chars:>8,} chars | {pypdf_time:.2f}s | {len(pypdf_blocks)} blocks")
print(f"  MarkItDown: {md_chars:>8,} chars | {md_time:.2f}s | {len(md_blocks)} blocks")
print(f"  Char diff:  {char_diff:+,} ({pct:+.1f}%)")
winner = "MarkItDown" if md_chars > pypdf_chars else "pypdf" if pypdf_chars > md_chars else "Tie"
print(f"  Winner:     {winner}")
print(f"{'='*50}")
