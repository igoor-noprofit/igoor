import fasttext
import fasttext.util
import re

# Load model
model = fasttext.load_model('C:\TMP\IGOOR\MODELS\cc.fr.300.bin')

model_size=50
# Reduce dimensions
fasttext.util.reduce_model(model, model_size)
model.save_model(f'C:\\\\TMP\\\\IGOOR\\\\MODELS\\\\cc.fr.{model_size}.bin')