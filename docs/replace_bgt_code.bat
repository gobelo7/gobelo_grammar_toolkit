# Preview what would change (dry run)
grep -r "gobelo_grammar_toolkit" . --include="*.py" --include="*.yaml" --include="*.yml" --include="*.md"

# Do the replacement across all relevant files
find . -type f \( -name "*.py" -o -name "*.yaml" -o -name "*.yml" -o -name "*.md" \) \
  -exec sed -i 's/gobelo_grammar_toolkit/ggt/g' {} +