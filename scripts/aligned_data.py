import pandas as pd
import os
import re

def process_zambian_stories(directory_path):
    all_data = []
    target_langs = ['bem', 'toi', 'lun', 'lue', 'ny', 'tum', 'kqn', 'loz-zm', 'en']
    
    for filename in os.listdir(directory_path):
        if filename.endswith(".csv"):
            df = pd.read_csv(os.path.join(directory_path, filename))
            df.columns = df.columns.str.strip()
            
            # Filter out untitled and extract the ID
            df = df[df['story_title'].str.lower() != 'untitled'].copy()
            df['story_id'] = df['story_url'].str.extract(r'/(\d+)/')
            
            all_data.append(df)

    if not all_data: return None
    combined_df = pd.concat(all_data, ignore_index=True)

    # Detect which language columns actually exist
    available_langs = [l for l in target_langs if l in combined_df.columns]

    # --- THE CRITICAL CHANGE ---
    # We pivot ONLY on story_id and page_number.
    # We add 'story_title' to the values so we can pick one title for the final row.
    aligned_df = combined_df.pivot_table(
        index=['story_id', 'page_number'],
        values=available_langs + ['story_title'],
        aggfunc='first' # Takes the first non-null title and first non-null sentence
    ).reset_index()

    # Create a generic story_url by stripping the language code (e.g., /toi/ -> /all/)
    # Or simply keep the ID as the reference.
    aligned_df['story_url_ref'] = "https://storybookszambia.net/stories/" + aligned_df['story_id'] + "/"

    # Reorder columns: Metadata first, then languages
    metadata_cols = ['story_title', 'story_id', 'page_number', 'story_url_ref']
    final_df = aligned_df[metadata_cols + available_langs]

    # Stats
    print("\n--- Summary Statistics ---")
    print(final_df[available_langs].count())

    return final_df

if __name__ == "__main__":
    df_final = process_zambian_stories('./data')
    if df_final is not None:
        df_final.to_csv('all_zambian_sents.csv', index=False)
        print(f"\nSuccess! Aligned into {len(df_final)} unique story-page rows.")
    # Usage
#df_final = process_zambian_stories('./data')
#df_final.to_csv('aligned_zambian_stories.csv', index=False)
