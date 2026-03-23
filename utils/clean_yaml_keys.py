#!/usr/bin/env python3

import argparse
import yaml

def remove_keys(data, keys_to_remove):
    """Recursively remove specified keys from nested dicts and lists."""
    if isinstance(data, dict):
        return {k: remove_keys(v, keys_to_remove) for k, v in data.items() if k not in keys_to_remove}
    elif isinstance(data, list):
        return [remove_keys(item, keys_to_remove) for item in data]
    else:
        return data

def clean_yaml(input_path, output_path, keys):
    with open(input_path, "r", encoding="utf-8") as infile:
        data = yaml.safe_load(infile)

    cleaned_data = remove_keys(data, keys)

    with open(output_path, "w", encoding="utf-8") as outfile:
        yaml.dump(cleaned_data, outfile, allow_unicode=True, sort_keys=False)

def main():
    parser = argparse.ArgumentParser(description="Remove specified keys from a YAML file recursively.")
    parser.add_argument("input", help="Path to the input YAML file")
    parser.add_argument("output", help="Path to save the cleaned YAML file")
    parser.add_argument("--keys", nargs="+", default=["example", "gloss"], help="Keys to remove (default: example gloss)")
    args = parser.parse_args()

    clean_yaml(args.input, args.output, set(args.keys))

if __name__ == "__main__":
    main()
