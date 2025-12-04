# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CloudHealth Perspective Schema Parser - A Python utility that converts CloudHealth Perspective schema JSON files into human-readable, SQL-like output. The tool can read from local JSON files or fetch directly from the CloudHealth API.

## Running the Tool

### From Local File
```bash
python3 parse_perspective.py <json_file> [-o output.txt]
```

### From CloudHealth API
```bash
# Interactive prompts for credentials
python3 parse_perspective.py

# With command-line arguments
python3 parse_perspective.py --api-key <key> --perspective-id <id> [-o output.txt]
```

### Dependencies
The tool requires Python 3.6+ and the `requests` library. Install dependencies with:
```bash
pip install requests
```

## Architecture

### Core Components

**parse_perspective_schema()** - Main parsing engine (lines 59-259)
- Processes the JSON schema data structure
- Builds lookup dictionaries for group blocks, dynamic groups, and static groups
- Handles merge logic to combine groups
- Outputs SQL-like WHERE/AND/OR clauses

**Key Data Structures:**
- `group_blocks`: Maps ref_id to group block definitions
- `dynamic_groups`: Maps ref_id to dynamic group definitions (tag-based categorization)
- `static_groups`: Maps ref_id to static group definitions (explicit filter rules)
- `merge_targets`: Maps target ref_id to list of source ref_ids being merged
- `static_group_filters`: Maps static group ref_id to its filter rules

### Rule Processing Logic

**Dynamic Groups (categorize rules):**
- Defined by tag field matching (e.g., WHERE tag cht_owner = 'value')
- Groups can be merged together using OR conditions
- Groups that are merged into others are skipped in output

**Static Groups (filter rules):**
- Multiple filter rules for the same group are OR'd together
- Clauses within a single rule are AND'd together
- Special handling for "Other" group (catches unmatched assets)
- Empty groups are explicitly labeled

**Merge Logic:**
- When groups are merged, the target group includes OR conditions for all merged source groups
- Source groups that are merged into others are excluded from output (lines 158-159)
- Merges are only processed for type 'Group' (line 99)

### Output Format

The parser generates SQL-like syntax:
- `WHERE` - First condition in a filter
- `AND` - Additional conditions within same rule (all must match)
- `OR` - Alternative conditions or merged groups (any can match)
- Tag fields prefixed with "tag" (e.g., "tag Business Unit")
- CamelCase asset types converted to readable format (e.g., "AzureTaggableAsset" becomes "Azure Taggable Asset")

### Supported Operators

The `format_condition_clause()` function (lines 26-56) handles:
- Equality: `=`, `!=`
- String matching: `Contains`, `Does not contain`
- Null checks: `Is null`, `Is not null`

## Example Data Files

- `example.json` - Simple perspective with dynamic groups based on cht_owner tag
- `example2.json` / `example2.txt` - Complex perspective with both dynamic and static groups, including merges
- `example3.json` - Minimal test case
- `example4.json` - Large-scale production example
- `example1.txt`, `example2.txt` - Parsed output examples

## Important Implementation Details

**Filter Rule Processing (lines 109-129):**
- Only processes filter rules without `fwd_to` field (forwarding rules are skipped)
- Each filter rule is stored separately and will be OR'd in output
- Clauses within each rule are AND'd together

**Static Group Output Logic (lines 213-249):**
- First rule uses WHERE/AND structure
- Subsequent rules use OR (with parentheses for multi-clause rules)
- This creates proper precedence: `WHERE (a AND b) OR (c AND d)`

**API Integration:**
- Base URL: `https://chapi.cloudhealthtech.com/v1/perspective_schemas/{id}`
- Requires valid CloudHealth API key
- Handles 401 (invalid key), 403 (permission denied), 404 (not found) errors
- 30-second timeout on API requests
