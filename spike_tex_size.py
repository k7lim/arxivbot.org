#!/usr/bin/env python3
"""Spike: Download arXiv TeX sources and measure token counts."""

import io
import tarfile
import gzip
import asyncio
import aiohttp
from pathlib import Path

# Papers to analyze
PAPERS = {
    "Ling 2.0": "2510.22115",
    "Minimax 01": "2501.08313",
    "Minimax M1": "2506.13585",
    "Deepseek V3": "2412.19437",
    "Deepseek R1": "2501.12948",
    "Longcat Flash": "2509.01322",
    "Kimi K2": "2507.20534",
    "MiniCPM 4": "2506.07900",
    "Cohere Command A": "2504.00698",
    "Olmo 3": "2512.13961",
}


def count_tokens_approx(text: str) -> int:
    """
    Approximate token count using cl100k_base tokenizer rules.
    Falls back to character-based estimate if tiktoken not available.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Rough estimate: ~4 chars per token for English, ~3 for LaTeX (more symbols)
        return len(text) // 3


def extract_tex_from_tar(data: bytes) -> str:
    """Extract and concatenate all .tex files from a tar.gz archive."""
    tex_contents = []

    try:
        # Try as tar.gz first
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".tex") and member.isfile():
                    f = tar.extractfile(member)
                    if f:
                        content = f.read().decode("utf-8", errors="replace")
                        tex_contents.append(f"% === {member.name} ===\n{content}")
    except tarfile.ReadError:
        try:
            # Maybe it's just gzipped (single file)
            content = gzip.decompress(data).decode("utf-8", errors="replace")
            tex_contents.append(content)
        except Exception:
            # Maybe it's a plain .tex file
            try:
                content = data.decode("utf-8", errors="replace")
                if "\\documentclass" in content or "\\begin{document}" in content:
                    tex_contents.append(content)
            except Exception:
                pass

    return "\n\n".join(tex_contents)


async def fetch_tex_source(session: aiohttp.ClientSession, paper_id: str) -> tuple[str, int, str]:
    """Fetch TeX source and return (content, token_count, status)."""
    url = f"https://arxiv.org/src/{paper_id}"

    try:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status == 404:
                return "", 0, "NO_SOURCE"
            if resp.status != 200:
                return "", 0, f"HTTP_{resp.status}"

            data = await resp.read()
            tex_content = extract_tex_from_tar(data)

            if not tex_content:
                return "", 0, "NO_TEX_FILES"

            token_count = count_tokens_approx(tex_content)
            return tex_content, token_count, "OK"

    except Exception as e:
        return "", 0, f"ERROR: {e}"


async def main():
    print("Fetching arXiv TeX sources and counting tokens...\n")
    print(f"{'Paper':<20} {'Tokens':>10} {'Chars':>12} {'Status':<15}")
    print("-" * 60)

    results = []

    async with aiohttp.ClientSession() as session:
        for name, paper_id in PAPERS.items():
            content, tokens, status = await fetch_tex_source(session, paper_id)
            chars = len(content)
            results.append((name, paper_id, tokens, chars, status))

            # Format token count with color hints
            if status != "OK":
                token_str = "-"
                char_str = "-"
            else:
                token_str = f"{tokens:,}"
                char_str = f"{chars:,}"

            # Status indicator
            if tokens > 250_000:
                indicator = "OVER HARD LIMIT"
            elif tokens > 100_000:
                indicator = "over soft"
            elif status == "OK":
                indicator = "OK"
            else:
                indicator = status

            print(f"{name:<20} {token_str:>10} {char_str:>12} {indicator:<15}")

    # Summary
    print("\n" + "=" * 60)
    ok_results = [(n, t) for n, _, t, _, s in results if s == "OK"]
    if ok_results:
        tokens_list = [t for _, t in ok_results]
        print(f"Papers with source: {len(ok_results)}/{len(PAPERS)}")
        print(f"Token range: {min(tokens_list):,} - {max(tokens_list):,}")
        print(f"Average tokens: {sum(tokens_list) // len(tokens_list):,}")

        under_100k = sum(1 for t in tokens_list if t <= 100_000)
        under_250k = sum(1 for t in tokens_list if t <= 250_000)
        print(f"\nUnder 100k (soft limit): {under_100k}/{len(ok_results)}")
        print(f"Under 250k (hard limit): {under_250k}/{len(ok_results)}")


if __name__ == "__main__":
    asyncio.run(main())
