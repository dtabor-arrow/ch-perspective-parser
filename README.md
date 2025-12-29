# CloudHealth Perspective Parser
[![AI Assisted](https://img.shields.io/badge/AI-Claude%20Code-AAAAAA.svg)](https://claude.ai/code)

Converts CloudHealth Perspective schema JSON files into human-readable SQL-like output.

## Requirements

- Python 3.6+
- `requests` library: `pip install requests`

## Usage

### Parse from local JSON file

```bash
python3 parse_perspective.py example.json
```

### Parse from local file and save output

```bash
python3 parse_perspective.py example.json -o output.txt
```

### Fetch directly from CloudHealth API

```bash
python3 parse_perspective.py --api-key YOUR_API_KEY --perspective-id PERSPECTIVE_ID
```

Or run without arguments for interactive prompts:

```bash
python3 parse_perspective.py
```

## Output Format

The tool generates SQL-like WHERE/AND/OR clauses that show how assets are categorized:

```
Group Block: owners

Group:  Marketing
Filter: Azure Taggable Asset
        WHERE tag cht_owner = 'Marketing'

Group:  Engineering
Filter: Azure Taggable Asset
        WHERE tag cht_owner = 'Engineering'
        OR tag cht_owner = 'DevOps'
```

## API Documentation

See CloudHealth API docs for downloading schemas manually:
https://apidocs.cloudhealthtech.com/#perspectives_retrieve-perspective-schema
