import json
import csv
from pathlib import Path
import time
from tqdm import tqdm

def load_words_from_csv(csv_path: str):
    """
    Loads words from the CSV file, ignoring definitions
    """
    words = []
    # First count lines for the progress bar
    with open(csv_path, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f) - 1  # Subtract 1 for header
    
    # Now load words with progress bar
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in tqdm(reader, total=total_lines, desc="Loading words"):
            word = row['Mot'].strip().lower()
            # Only keep pure alphabetic words and words longer than 1 character
            if word.isalpha() and len(word) > 1:
                words.append(word)
    
    return sorted(words)

def create_prefix_dictionary(words):
    """
    Creates a prefix-based dictionary from a list of words
    """
    prefix_dict = {}
    for word in tqdm(words, desc="Creating prefix dictionary"):
        # Create prefixes
        for i in range(1, len(word) + 1):
            prefix = word[:i]
            if prefix not in prefix_dict:
                prefix_dict[prefix] = []
            if word not in prefix_dict[prefix]:
                prefix_dict[prefix].append(word)
    
    return prefix_dict

def main():
    # Input and output paths
    csv_path = r"c:\TMP\IGOOR\MODELS\dico.csv"
    output_dir = Path("dictionary")
    output_dir.mkdir(exist_ok=True)
    
    # Load words
    print("Starting dictionary creation...")
    words = load_words_from_csv(csv_path)
    print(f"Loaded {len(words)} words")
    
    # Save simple format
    print("Saving simple dictionary format...")
    simple_dict = {"words": words}
    with open(output_dir / "french_dictionary_simple.json", 'w', encoding='utf-8') as f:
        json.dump(simple_dict, f, ensure_ascii=False, indent=2)
    
    # Create and save prefix format
    start_time = time.time()
    prefix_dict = create_prefix_dictionary(words)
    creation_time = time.time() - start_time
    print(f"Created prefix dictionary in {creation_time:.2f} seconds")
    
    print("Saving prefix dictionary...")
    with open(output_dir / "french_dictionary_prefix.json", 'w', encoding='utf-8') as f:
        json.dump(prefix_dict, f, ensure_ascii=False, indent=2)
    
    # Test the dictionary
    test_prefix = "acc"
    matches = prefix_dict.get(test_prefix, [])
    print(f"\nTest predictions for '{test_prefix}': {matches[:5]}")
    
    # Print some statistics
    print("\nDictionary Statistics:")
    print(f"Total words: {len(words)}")
    print(f"Total prefixes: {len(prefix_dict)}")
    print(f"Average prefixes per word: {len(prefix_dict)/len(words):.1f}")

if __name__ == "__main__":
    main()