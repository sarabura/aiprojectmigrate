#!/usr/bin/env python3
# Author: Martin Sarabura (martin.sarabura@gmail.com)
# License: MIT
# Repository: https://github.com/sarabura/aiprojectmigrate
# Issues and improvement requests: https://github.com/sarabura/aiprojectmigrate/issues
"""
extract_project.py

Extracts conversations from a ChatGPT data export (conversations_merged.json)
by matching a list of known conversation titles, reconstructs the message tree
in chronological order, and writes two output files:

  <claude_project>-conversations.md   -- all matched conversations, formatted
  <claude_project>-files.md           -- deduplicated file attachment inventory

Usage:
    python3 extract_project.py \
        --input conversations_merged.json \
        --titles titles.txt \
        --claude-project "Identifying Trees"

titles.txt is a plain text file with one conversation title per line,
generated from the extract_titles_prompt.txt prompt in the prompts/ folder.

Options:
    --input           Path to conversations_merged.json (required)
    --titles          Path to titles file, one title per line (required)
    --claude-project  Name to use for output files and headings (required)
    --diagnose        Print structure of first conversation and exit
"""

import json
import argparse
import os
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Extract ChatGPT project conversations by title.")
    p.add_argument("--input",          required=True,  help="Path to conversations_merged.json")
    p.add_argument("--titles",         required=True,  help="Path to titles file (one per line)")
    p.add_argument("--claude-project", required=True,  help="Claude project name (used in output filenames)")
    p.add_argument("--diagnose",       action="store_true", help="Print structure of first conversation and exit")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def epoch_to_str(epoch):
    """Convert a float epoch timestamp to a readable UTC string."""
    if epoch is None:
        return "unknown time"
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(epoch)


def safe_filename(name):
    """Convert a project name to a safe filename prefix."""
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip().replace(" ", "_")


def load_titles(path):
    """Load conversation titles from a text file, one per line."""
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def title_matches(conv_title, target_titles):
    """Return True if conv_title exactly matches any target title."""
    return conv_title in target_titles


# ---------------------------------------------------------------------------
# Message tree reconstruction
# ---------------------------------------------------------------------------

def get_linear_messages(mapping, current_node_id):
    """
    Walk the message tree from root to current_node, returning messages
    in chronological (parent -> child) order.

    ChatGPT stores conversations as a tree where each node has a parent
    and children. We follow the path from root down to current_node.
    """
    if not mapping or not current_node_id:
        return []

    # Build child->parent and id->node maps
    nodes = {node_id: node for node_id, node in mapping.items()}

    # Find root: node with no parent or null parent
    root_id = None
    for node_id, node in nodes.items():
        if node.get("parent") is None:
            root_id = node_id
            break

    if root_id is None:
        return []

    # Trace path from current_node back to root, then reverse
    path = []
    current = current_node_id
    visited = set()
    while current is not None and current not in visited:
        visited.add(current)
        path.append(current)
        node = nodes.get(current)
        if node is None:
            break
        current = node.get("parent")

    path.reverse()  # root -> current_node order

    # Extract messages from path nodes
    messages = []
    for node_id in path:
        node = nodes.get(node_id)
        if node is None:
            continue
        msg = node.get("message")
        if msg is None:
            continue

        author = msg.get("author", {})
        role = author.get("role", "unknown")

        # Skip system messages and empty/hidden messages
        if role == "system":
            continue
        metadata = msg.get("metadata", {})
        if metadata.get("is_visually_hidden_from_conversation"):
            continue

        # Extract text content
        content = msg.get("content", {})
        content_type = content.get("content_type", "")
        text = ""

        if content_type == "text":
            parts = content.get("parts", [])
            text = "\n".join(str(p) for p in parts if p and str(p).strip())
        elif content_type == "multimodal_text":
            parts = content.get("parts", [])
            text_parts = []
            for p in parts:
                if isinstance(p, str) and p.strip():
                    text_parts.append(p)
                elif isinstance(p, dict):
                    # Image or file reference
                    if p.get("content_type") in ("image_asset_pointer", "file_attachment"):
                        fname = p.get("asset_pointer") or p.get("name") or "[attached file]"
                        text_parts.append(f"[Attachment: {fname}]")
            text = "\n".join(text_parts)
        elif content_type == "tether_browsing_display":
            # Web browsing results - skip or summarise
            continue

        if not text.strip():
            continue

        create_time = msg.get("create_time")
        messages.append({
            "role": role,
            "text": text.strip(),
            "time": create_time,
        })

    return messages


# ---------------------------------------------------------------------------
# File attachment extraction
# ---------------------------------------------------------------------------

def extract_file_attachments(mapping):
    """
    Scan all message nodes for file attachments.
    Returns list of (filename, epoch_timestamp) tuples.
    """
    attachments = []
    for node_id, node in mapping.items():
        msg = node.get("message")
        if not msg:
            continue
        content = msg.get("content", {})
        parts = content.get("parts", [])
        create_time = msg.get("create_time")
        for part in parts:
            if isinstance(part, dict):
                ct = part.get("content_type", "")
                if ct == "file_attachment":
                    fname = part.get("name") or part.get("asset_pointer") or "unknown_file"
                    attachments.append((fname, create_time))
                elif ct == "image_asset_pointer":
                    fname = part.get("asset_pointer") or "image"
                    attachments.append((fname, create_time))
    return attachments


# ---------------------------------------------------------------------------
# Diagnose mode
# ---------------------------------------------------------------------------

def diagnose(data):
    conv = data[0]
    print("=== DIAGNOSE: First conversation ===")
    print("Top-level keys:", list(conv.keys()))
    print("Title:", conv.get("title"))
    print("Create time:", conv.get("create_time"))
    print("Current node:", conv.get("current_node"))
    mapping = conv.get("mapping", {})
    print(f"Mapping node count: {len(mapping)}")
    if mapping:
        sample_node = next(iter(mapping.values()))
        print("Sample mapping node keys:", list(sample_node.keys()))
        msg = sample_node.get("message")
        if msg:
            print("Sample message keys:", list(msg.keys()))
            print("Sample content type:", msg.get("content", {}).get("content_type"))
            print("Sample role:", msg.get("author", {}).get("role"))
    print()
    # Show reconstructed messages for first conversation
    messages = get_linear_messages(mapping, conv.get("current_node"))
    print(f"Reconstructed {len(messages)} messages:")
    for m in messages[:4]:
        preview = m["text"][:120].replace("\n", " ")
        print(f"  [{m['role']}] {preview}")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------

def format_conversation(conv, messages, index):
    title = conv.get("title") or "(untitled)"
    create_time = epoch_to_str(conv.get("create_time"))
    lines = []
    lines.append(f"## {index}. {title}")
    lines.append(f"*{create_time}*")
    lines.append("")
    for msg in messages:
        role_label = "**You**" if msg["role"] == "user" else f"**{msg['role'].capitalize()}**"
        lines.append(f"{role_label}:")
        lines.append("")
        # Indent each line of the message slightly for readability
        for line in msg["text"].split("\n"):
            lines.append(line)
        lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Load conversations
    print(f"Loading {args.input} ...")
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    print(f"  {len(data)} conversations loaded.")

    if args.diagnose:
        diagnose(data)

    # Load target titles
    target_titles = load_titles(args.titles)
    print(f"  {len(target_titles)} target titles loaded.")

    # Output file paths
    prefix = safe_filename(args.claude_project)
    conv_file  = f"{prefix}-conversations.md"
    files_file = f"{prefix}-files.md"

    # Match conversations and extract
    matched = []
    unmatched_titles = set(target_titles)
    file_inventory = {}  # filename -> (epoch, human_str)

    for conv in data:
        conv_title = conv.get("title", "")
        if not title_matches(conv_title, target_titles):
            continue

        mapping = conv.get("mapping", {})
        current_node = conv.get("current_node")
        messages = get_linear_messages(mapping, current_node)

        # Collect file attachments
        for fname, epoch in extract_file_attachments(mapping):
            if epoch is not None:
                existing = file_inventory.get(fname)
                if existing is None or epoch > existing[0]:
                    file_inventory[fname] = (epoch, epoch_to_str(epoch))

        matched.append((conv, messages))

        # Track which titles were found
        for t in list(unmatched_titles):
            if title_matches(conv_title, [t]):
                unmatched_titles.discard(t)

    print(f"  {len(matched)} conversation(s) matched.")

    if not matched:
        print("WARNING: No conversations matched.")
        print("  Check that your titles file was generated from the correct project screenshots.")
        print("  Run with --diagnose to inspect the export structure.")
        sys.exit(1)

    # Sort matched conversations by create_time
    matched.sort(key=lambda x: x[0].get("create_time") or 0)

    # Write conversations file
    with open(conv_file, "w", encoding="utf-8") as f:
        f.write(f"# ChatGPT Project Conversations\n")
        f.write(f"# Claude Project: {args.claude_project}\n")
        f.write(f"# Exported: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")
        for i, (conv, messages) in enumerate(matched, 1):
            f.write(format_conversation(conv, messages, i))

    print(f"  Written: {conv_file}")

    # Write file inventory
    with open(files_file, "w", encoding="utf-8") as f:
        f.write(f"# File Attachments: {args.claude_project}\n")
        f.write(f"# Most recent upload only, deduplicated\n\n")
        if file_inventory:
            f.write("| File | Last Uploaded |\n")
            f.write("|------|---------------|\n")
            for fname, (epoch, time_str) in sorted(file_inventory.items(),
                                                     key=lambda x: x[1][0], reverse=True):
                f.write(f"| {fname} | {time_str} |\n")
        else:
            f.write("No file attachments found in these conversations.\n")

    print(f"  Written: {files_file}")

    # Warn about any titles that had no match
    if unmatched_titles:
        print()
        print("WARNING: The following titles had no match in the export:")
        for t in sorted(unmatched_titles):
            print(f"  - {t}")
        print("  Verify these titles appear in the ChatGPT project and re-run the titles extraction prompt.")


if __name__ == "__main__":
    main()
