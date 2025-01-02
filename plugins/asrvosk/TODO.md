# LOADING MODELS
function that checks in self.plugin_folder if the model corresponding to the language/model_size exists,
otherwise it loads it, unzips it in folder named as in json file (big, small) 

- FIX: should not start listening when still in onboarding mode
- remove blocking using threads