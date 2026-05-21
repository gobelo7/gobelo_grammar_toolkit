import pandas as pd
import glob
from pathlib import Path

def align_sentences(csv_files):
    """
    Align sentences across multiple languages based on story_url and page_number.
    Excludes untitled booklets.
    
    Args:
        csv_files: List of CSV file paths or directory path containing CSV files
    
    Returns:
        DataFrame with aligned sentences across all languages
    """
    
    # If csv_files is a directory, get all CSV files
    if isinstance(csv_files, str) and Path(csv_files).is_dir():
        csv_files = glob.glob(f"{csv_files}/*.csv")
    
    # Read all CSV files
    all_data = []
    for file in csv_files:
        df = pd.read_csv(file)
        all_data.append(df)
    
    # Combine all dataframes
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Filter out untitled booklets (case-insensitive)
    combined_df = combined_df[
        combined_df['story_title'].str.lower() != 'untitled'
    ].copy()
    
    # Get all language columns (excluding metadata columns)
    metadata_cols = ['language_code', 'language_name', 'story_title', 
                     'story_url', 'page_number']
    language_cols = [col for col in combined_df.columns if col not in metadata_cols]
    
    # Create alignment key
    combined_df['align_key'] = (
        combined_df['story_url'].astype(str) + '_' + 
        combined_df['page_number'].astype(str)
    )
    
    # Pivot to create aligned structure
    aligned_data = {}
    
    # Add metadata columns
    for key in combined_df['align_key'].unique():
        subset = combined_df[combined_df['align_key'] == key]
        if len(subset) > 0:
            aligned_data[key] = {
                'story_url': subset['story_url'].iloc[0],
                'page_number': subset['page_number'].iloc[0],
                'story_title': subset['story_title'].iloc[0]
            }
    
    # Add language columns
    for lang_col in language_cols:
        for key in combined_df['align_key'].unique():
            subset = combined_df[combined_df['align_key'] == key]
            # Get the value for this language (may be NaN if not present)
            lang_values = subset[lang_col].dropna()
            if len(lang_values) > 0:
                aligned_data[key][lang_col] = lang_values.iloc[0]
            else:
                aligned_data[key][lang_col] = None
    
    # Convert to DataFrame
    aligned_df = pd.DataFrame.from_dict(aligned_data, orient='index')
    aligned_df = aligned_df.reset_index(drop=True)
    
    # Sort by story_url and page_number
    aligned_df = aligned_df.sort_values(['story_url', 'page_number'])
    
    # Reorder columns: metadata first, then languages
    column_order = ['story_title', 'story_url', 'page_number'] + language_cols
    aligned_df = aligned_df[column_order]
    
    return aligned_df


# Example usage
if __name__ == "__main__":
    # Method 1: Using a list of CSV files
    csv_files = ['sample_kqn.csv', 'sample_lue.csv']  # Add all your CSV files
    
    # Method 2: Using a directory containing all CSV files
    # csv_files = './csv_data_directory'
    
    # Align sentences
    aligned_df = align_sentences(csv_files)
    
    # Display results
    print(f"Total aligned sentences: {len(aligned_df)}")
    print(f"\nFirst few rows:")
    print(aligned_df.head(10))
    
    # Save to CSV
    aligned_df.to_csv('aligned_sentences.csv', index=False)
    print("\nAligned data saved to 'aligned_sentences.csv'")
    
    # Optional: Display summary statistics
    print(f"\nStories included:")
    for title in aligned_df['story_title'].unique():
        count = len(aligned_df[aligned_df['story_title'] == title])
        print(f"  - {title}: {count} pages")
    
    print(f"\nLanguages included:")
    for col in aligned_df.columns:
        if col not in ['story_title', 'story_url', 'page_number']:
            non_null = aligned_df[col].notna().sum()
            print(f"  - {col}: {non_null} sentences")