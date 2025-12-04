#!/usr/bin/env python3
"""
CloudHealth Perspective Schema Parser
Reads a CloudHealth Perspective schema JSON file and generates human-readable output.

Requirements:
    - Python 3.6+
    - requests library (install via: pip install -r requirements.txt)
"""

import json
import re
import argparse
import sys
import requests
import getpass


def camel_to_readable(text):
    """Convert CamelCase to human-readable format with spaces."""
    # Insert space before uppercase letters
    result = re.sub(r'(?<!^)(?=[A-Z])', ' ', text)
    return result


def format_condition_clause(clause):
    """Format a condition clause into SQL-like syntax."""
    op = clause.get('op', '=')
    val = clause.get('val', '')

    # Determine if this is a tag field or regular field
    if 'tag_field' in clause:
        field_list = clause.get('tag_field', [])
        field_name = field_list[0] if field_list else ''
        field_prefix = 'tag '
    else:
        field_list = clause.get('field', [])
        field_name = field_list[0] if field_list else ''
        field_prefix = ''

    # Format based on operator
    if op == '=':
        return f"{field_prefix}{field_name} = '{val}'"
    elif op == '!=':
        return f"{field_prefix}{field_name} != '{val}'"
    elif op == 'Contains':
        return f"{field_prefix}{field_name} CONTAINS '{val}'"
    elif op.lower() == 'does not contain':
        return f"{field_prefix}{field_name} DOES NOT CONTAIN '{val}'"
    elif op.lower() == 'is null':
        return f"{field_prefix}{field_name} IS NULL"
    elif op.lower() == 'is not null':
        return f"{field_prefix}{field_name} IS NOT NULL"
    else:
        # Fallback for any unknown operators
        return f"{field_prefix}{field_name} {op} '{val}'"


def parse_perspective_schema(schema_data):
    """Parse the perspective schema and generate human-readable output."""
    schema = schema_data.get('schema', {})

    output_lines = []

    # Perspective name
    perspective_name = schema.get('name', 'Unknown')
    output_lines.append(f"Perspective: {perspective_name}\n")

    # Get rules, constants, merges
    rules = schema.get('rules', [])
    constants = schema.get('constants', [])
    merges = schema.get('merges', [])

    # Build lookup dictionaries
    group_blocks = {}  # ref_id -> block info
    dynamic_groups = {}  # ref_id -> group info
    static_groups = {}  # ref_id -> group info

    for constant in constants:
        const_type = constant.get('type')

        if const_type == 'Dynamic Group Block':
            for block in constant.get('list', []):
                group_blocks[block['ref_id']] = block

        elif const_type == 'Dynamic Group':
            for group in constant.get('list', []):
                dynamic_groups[group['ref_id']] = group

        elif const_type == 'Static Group':
            for group in constant.get('list', []):
                static_groups[group['ref_id']] = group

    # Build merge mappings
    merge_targets = {}  # target ref_id -> list of source ref_ids
    merged_sources = set()  # set of source ref_ids that are merged into others

    for merge in merges:
        if merge.get('type') == 'Group':
            to_ref = merge.get('to')
            from_refs = merge.get('from', [])

            if to_ref not in merge_targets:
                merge_targets[to_ref] = []

            merge_targets[to_ref].extend(from_refs)
            merged_sources.update(from_refs)

    # Collect filter rules for static groups
    static_group_filters = {}  # ref_id -> list of filter rules

    for rule in rules:
        if rule.get('type') == 'filter':
            to_ref = rule.get('to')
            # Only process if not being forwarded (fwd_to means it's going to another group)
            if to_ref and 'fwd_to' not in rule:
                if to_ref not in static_group_filters:
                    static_group_filters[to_ref] = []

                asset_type = rule.get('asset', '')
                condition = rule.get('condition', {})
                clauses = condition.get('clauses', [])

                # Each filter rule is stored separately - they will be OR'd together
                # Clauses within a single rule will be AND'd together
                static_group_filters[to_ref].append({
                    'asset': asset_type,
                    'clauses': clauses
                })

    # Process categorize rules (dynamic groups)
    for rule in rules:
        rule_type = rule.get('type')

        if rule_type == 'categorize':
            # Get rule details
            asset_type = rule.get('asset', '')
            readable_asset = camel_to_readable(asset_type)
            ref_id = rule.get('ref_id')
            block_name = rule.get('name', '')
            tag_fields = rule.get('tag_field', [])
            tag_field = tag_fields[0] if tag_fields else ''

            # Show group block header
            output_lines.append(f"Group Block: {block_name}\n")

            # Find all dynamic groups belonging to this block
            block_groups = [
                group for group in dynamic_groups.values()
                if group.get('blk_id') == ref_id
            ]

            # Output each group
            for group in block_groups:
                group_ref_id = group.get('ref_id')

                # Skip groups that are merged into others
                if group_ref_id in merged_sources:
                    continue

                group_name = group.get('name', '')
                group_val = group.get('val', '')

                output_lines.append("-" * 76)
                output_lines.append("")
                output_lines.append(f"Group:  {group_name}")
                output_lines.append("")
                output_lines.append(f"Filter: {readable_asset}")
                output_lines.append(f"        WHERE tag {tag_field} = '{group_val}'")

                # If this group has others merged into it, add OR conditions
                if group_ref_id in merge_targets:
                    for merged_ref_id in merge_targets[group_ref_id]:
                        merged_group = dynamic_groups.get(merged_ref_id)
                        if merged_group:
                            merged_val = merged_group.get('val', '')
                            output_lines.append(f"        OR tag {tag_field} = '{merged_val}'")

                output_lines.append("")  # Empty line after each group

    # Process static groups
    if static_groups:
        output_lines.append("Static Groups:\n")

        for ref_id, group in static_groups.items():
            group_name = group.get('name', '')
            is_other = group.get('is_other') == 'true'

            output_lines.append("-" * 76)
            output_lines.append("")
            output_lines.append(f"Group:  {group_name}")

            # Special handling for "Other" group
            if is_other:
                output_lines.append("")
                output_lines.append("Note: Catches all assets not matched by other groups")
                output_lines.append("")
                continue

            # Get all filter rules for this static group
            filters = static_group_filters.get(ref_id, [])

            if filters:
                # Group filters by asset type to organize output
                filters_by_asset = {}
                for filter_info in filters:
                    asset = filter_info['asset']
                    if asset not in filters_by_asset:
                        filters_by_asset[asset] = []
                    filters_by_asset[asset].append(filter_info['clauses'])

                # Output each asset type's filters
                first_filter_for_asset = True
                for asset_type, clause_groups in filters_by_asset.items():
                    readable_asset = camel_to_readable(asset_type)
                    output_lines.append("")
                    output_lines.append(f"Filter: {readable_asset}")

                    # Each clause_group represents one filter rule
                    # Multiple clause_groups are OR'd together
                    for group_idx, clauses in enumerate(clause_groups):
                        if not clauses:
                            continue

                        # Within a clause group, conditions are AND'd
                        if group_idx == 0:
                            # First rule for this asset type
                            for clause_idx, clause in enumerate(clauses):
                                condition_str = format_condition_clause(clause)
                                if clause_idx == 0:
                                    output_lines.append(f"        WHERE {condition_str}")
                                else:
                                    output_lines.append(f"        AND {condition_str}")
                        else:
                            # Subsequent rules - OR'd with previous rules
                            # If multiple clauses in this rule, wrap them logically
                            if len(clauses) == 1:
                                condition_str = format_condition_clause(clauses[0])
                                output_lines.append(f"        OR {condition_str}")
                            else:
                                # Multiple clauses AND'd together, but OR'd with previous rules
                                for clause_idx, clause in enumerate(clauses):
                                    condition_str = format_condition_clause(clause)
                                    if clause_idx == 0:
                                        output_lines.append(f"        OR ({condition_str}")
                                    elif clause_idx == len(clauses) - 1:
                                        output_lines.append(f"            AND {condition_str})")
                                    else:
                                        output_lines.append(f"            AND {condition_str}")
            else:
                # Empty group - no filter rules
                output_lines.append("")
                output_lines.append("        EMPTY GROUP")

            output_lines.append("")  # Empty line after each group

    output_lines.append("Done")

    return '\n'.join(output_lines)


def fetch_perspective_from_api(api_key, perspective_id):
    """Fetch perspective schema from CloudHealth API."""
    url = f"https://chapi.cloudhealthtech.com/v1/perspective_schemas/{perspective_id}"
    params = {'api_key': api_key}

    try:
        response = requests.get(url, params=params, timeout=30)

        # Handle specific HTTP errors with helpful messages
        if response.status_code == 401:
            print("Error: Invalid API key. Please check your CloudHealth API key.", file=sys.stderr)
            sys.exit(1)
        elif response.status_code == 403:
            print("Error: Permission denied. You may not have access to this Perspective.", file=sys.stderr)
            sys.exit(1)
        elif response.status_code == 404:
            print(f"Error: Perspective ID '{perspective_id}' not found.", file=sys.stderr)
            sys.exit(1)

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from API: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON response from API: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Parse CloudHealth Perspective schema and generate human-readable output',
        epilog='See https://apidocs.cloudhealthtech.com/#perspectives_retrieve-perspective-schema for help downloading a schema manually.'
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        help='Path to the JSON schema file (if not provided, will prompt for API credentials)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Optional output file (default: print to screen)',
        default=None
    )
    parser.add_argument(
        '--api-key',
        help='CloudHealth API key (if not provided, will prompt)',
        default=None
    )
    parser.add_argument(
        '--perspective-id',
        help='CloudHealth Perspective ID (if not provided, will prompt)',
        default=None
    )

    args = parser.parse_args()

    # Determine if we're reading from file or API
    if args.input_file:
        # Read from file
        try:
            with open(args.input_file, 'r') as f:
                schema_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: File '{args.input_file}' not found", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Fetch from API
        api_key = args.api_key
        perspective_id = args.perspective_id

        # Prompt for API key if not provided
        if not api_key:
            api_key = input("CloudHealth API Key: ")

        # Prompt for Perspective ID if not provided
        if not perspective_id:
            perspective_id = input("Perspective ID: ")

        print("Fetching perspective schema from CloudHealth API...")
        schema_data = fetch_perspective_from_api(api_key, perspective_id)

    # Parse and generate output
    output = parse_perspective_schema(schema_data)

    # Write to file or print to screen
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Output written to {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
