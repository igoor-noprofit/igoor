import json
import time
from typing import List
from pathlib import Path

class WordPredictor:
    def __init__(self):
        self.prefix_dict = None
        
    def load_model(self, dict_path: str) -> float:
        """
        Loads the prefix dictionary model and returns loading time
        
        Returns:
            float: Time taken to load the model in seconds
        """
        start_time = time.time()
        
        with open(dict_path, 'r', encoding='utf-8') as f:
            self.prefix_dict = json.load(f)
            
        load_time = time.time() - start_time
        print(f"Model loaded in {load_time*1000:.2f}ms")
        print(f"Model contains {len(self.prefix_dict)} prefixes")
        
        return load_time
        
    def predict(self, prefix: str, max_suggestions: int = 5) -> tuple[List[str], float]:
        """
        Predicts words based on prefix
        
        Returns:
            tuple: (list of predictions, time taken in seconds)
        """
        if not self.prefix_dict:
            raise RuntimeError("Model not loaded. Call load_model first.")
            
        if not prefix or len(prefix) < 2:
            return [], 0
            
        start_time = time.time()
        prefix = prefix.lower()
        matches = self.prefix_dict.get(prefix, [])
        predictions = matches[:max_suggestions]
        predict_time = time.time() - start_time
        
        return predictions, predict_time

def main():
    # Initialize predictor
    predictor = WordPredictor()
    
    # Load model
    dict_path = Path("dictionary/french_dictionary_prefix.json")
    load_time = predictor.load_model(str(dict_path))
    
    # Test some predictions
    test_prefixes = ["bonj", "acc", "mai", "pre"]
    
    print("\nPrediction tests:")
    print("-" * 50)
    for prefix in test_prefixes:
        predictions, predict_time = predictor.predict(prefix)
        print(f"\nPrefix '{prefix}':")
        print(f"Predictions: {predictions}")
        print(f"Prediction time: {predict_time*1000:.2f}ms")

if __name__ == "__main__":
    main()