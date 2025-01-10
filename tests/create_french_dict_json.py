import json
import csv
from pathlib import Path
import time
from tqdm import tqdm

def load_words_from_csv(csv_path: str):
    """
    Loads words from CSV and sorts them by frequency
    Returns list of words already sorted by frequency
    Handles duplicate lemmas by keeping the highest frequency occurrence
    """
    word_freq = {}
    # First count lines for the progress bar
    with open(csv_path, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f) - 1  # Subtract 1 for header
    
    # Load words with progress bar
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in tqdm(reader, total=total_lines, desc="Loading words"):
            try:
                # Convert frequency from "81,36" format to float
                freq_str = row['freq'].replace(',', '.')
                freq = float(freq_str)  # Now handling decimal numbers
                
                word = row['lemme'].strip().lower()
                # Only keep pure alphabetic words and words longer than 1 character
                if word.isalpha() and len(word) > 1:
                    # If word exists, keep the highest frequency
                    if word not in word_freq or freq > word_freq[word]:
                        word_freq[word] = freq
            except ValueError:
                continue
    
    # Convert dictionary to list and sort by frequency (descending)
    word_freq_list = [(freq, word) for word, freq in word_freq.items()]
    word_freq_list.sort(reverse=True)  # Higher frequency first
    
    # Print first few words to verify ordering
    print("\nTop 10 most frequent words:")
    for freq, word in word_freq_list[:10]:
        print(f"freq {freq:.2f}: {word}")
    
    print(f"\nTotal unique words: {len(word_freq_list)}")
        
    return [word for _, word in word_freq_list]

def create_prefix_dictionary(words):
    """
    Creates a prefix-based dictionary from a list of words
    Words must already be sorted by frequency
    """
    prefix_dict = {}
    
    # First, create all possible prefixes for each word
    for word in tqdm(words, desc="Creating prefix dictionary"):
        # Generate all prefixes of length 2 or more
        for prefix_length in range(2, len(word) + 1):
            prefix = word[:prefix_length]
            
            # Initialize prefix entry if it doesn't exist
            if prefix not in prefix_dict:
                prefix_dict[prefix] = []
            
            # Add word to this prefix's list if not already present
            if word not in prefix_dict[prefix]:
                prefix_dict[prefix].append(word)
    
    return prefix_dict

def main():
    # Input and output paths
    csv_path = r"C:\TMP\IGOOR\MODELS\140kwords.csv"
    output_dir = Path("dictionary")
    output_dir.mkdir(exist_ok=True)
    
    # Load words (they come pre-sorted by frequency)
    print("Starting dictionary creation...")
    words = load_words_from_csv(csv_path)
    print(f"Loaded {len(words)} words")
    
    # Create and save prefix format
    start_time = time.time()
    prefix_dict = create_prefix_dictionary(words)
    creation_time = time.time() - start_time
    print(f"Created prefix dictionary in {creation_time:.2f} seconds")
    
    # Test a few prefixes before saving
    test_prefixes = ["êt", "je", "av"]
    print("\nTesting some prefixes:")
    for prefix in test_prefixes:
        if prefix in prefix_dict:
            print(f"\nPrefix '{prefix}': {prefix_dict[prefix][:5]}")
    
    print("\nSaving prefix dictionary...")
    with open(output_dir / "french_dictionary_prefix.json", 'w', encoding='utf-8') as f:
        json.dump(prefix_dict, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()