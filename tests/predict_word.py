import fasttext
import fasttext.util
import time
start_time = time.time()
model_size = 300
model = fasttext.load_model(f'C:\\\\TMP\\\\IGOOR\\\\MODELS\\\\cc.fr.{model_size}.bin')
end_time = time.time()
print(f"Time to load model: {end_time - start_time} seconds")
# Test the model
start_time = time.time()
similar_words = model.get_nearest_neighbors('bonj', k=5)
end_time = time.time()
print(f"Time to get prediction: {end_time - start_time} seconds")
print(similar_words)