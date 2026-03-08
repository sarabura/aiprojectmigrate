# aiprojectmigrate

Scripts and prompts for migrating ChatGPT projects to Claude.

## The Problem

ChatGPT's data export does not include project membership. Your conversations are all present in the export JSON, but the information about which project each conversation belongs to has been silently omitted. There is no project field to filter on — you cannot write a simple script to extract conversations by project name.

This repository provides a workaround: capture the conversation titles from the ChatGPT interface directly, then use those titles to extract the matching conversations from the export.

For a full explanation of the approach, see the accompanying article on Medium.

---

## Requirements

- Python 3.7 or later
- No third-party packages required — standard library only

---

## Repository Contents

```
scripts/
    merge_conversations.py    Merge multiple ChatGPT export JSON files into one
    extract_project.py        Extract and reconstruct conversations by title list

prompts/
    extract_titles_prompt.txt Paste into Claude with screenshots to generate a titles file
    project_summary_prompt.txt Upload your conversations file to Claude to generate a project summary
```

---

## Workflow

### Step 1 — Capture conversation titles from ChatGPT

Do this before cancelling your ChatGPT subscription. Once you lose access, this information is gone.

Navigate to each project in ChatGPT and take screenshots of the conversation list. Paste the screenshots into a Claude conversation along with the contents of `prompts/extract_titles_prompt.txt`. Claude will return a plain text list of titles and provide it as a downloadable `titles.txt` file.

Save a separate titles file for each project you want to migrate. For the second and subsequent project you can use the prompt *Same instructions as before* to save yourself some time.

### Step 2 — Merge the export files

If your ChatGPT export contains multiple `conversations-00x.json` files, merge them first:

```bash
python3 scripts/merge_conversations.py
```

This produces `conversations_merged.json` in the current directory.

Options:

```
--output    Output filename (default: conversations_merged.json)
--dir       Directory containing the export files (default: current directory)
```

### Step 3 — Extract conversations by project

Run the extraction script with your titles file:

```bash
python3 scripts/extract_project.py \
    --input conversations_merged.json \
    --titles titles.txt \
    --claude-project "Your Project Name"
```

This produces two output files:

- `Your_Project_Name-conversations.md` — all matched conversations in readable markdown, with timestamps
- `Your_Project_Name-files.md` — a deduplicated inventory of every file uploaded in those conversations, showing only the most recent upload of each filename

Options:

```
--input           Path to conversations_merged.json (required)
--titles          Path to titles file, one title per line (required)
--claude-project  Name to use for output files and headings (required)
--diagnose        Print structure of first conversation and exit
```

If some titles produce no match, the script will list them and exit with a warning. Re-check the screenshots and regenerate the titles file if needed.

### Step 4 — Generate a project summary

Upload `Your_Project_Name-conversations.md` to a Claude conversation along with the contents of `prompts/project_summary_prompt.txt`. Claude will produce a structured summary document and provide it as a downloadable `project-summary.md` file.

The summary covers: project overview, key facts and numbers, decisions made, work completed, open items, people and organizations mentioned, important context for future conversations, and a suggested project instructions block ready to paste into Claude.

### Step 5 — Set up the Claude project

1. In Claude, click **New Project** in the left sidebar
2. Upload `project-summary.md` to the project knowledge base
3. Paste the suggested project instructions block from the summary into the project instructions field

If your ChatGPT project had existing custom instructions, merge them with the generated block — the generated version captures project context, but your existing instructions may contain behavioral preferences (tone, formatting, things to avoid) that the summary will not.

---

## Known Limitations

- Title matching is exact. Titles must match the export exactly as shown in the ChatGPT interface. If a title in your screenshots differs from what is stored in the export JSON, it will not match. Run `--diagnose` to inspect the raw export structure if you have unexpected misses.
- The ChatGPT export format may change without notice. If the scripts stop working after a new export, please open an issue.

---

## Issues and Improvement Requests

Please use [GitHub Issues](https://github.com/sarabura/aiprojectmigrate/issues) to report problems or suggest improvements.

---

## License

MIT. See [LICENSE](LICENSE) for details.

## Author

Martin Sarabura — martin.sarabura@gmail.com
