BUG:
- Fallback does not work because of an unhandled exception in elevenlabslib:

  File "C:\AIKU\experiments\igoor\venv\lib\site-packages\elevenlabslib\helpers.py", line 730, in _ap  File "C:\AIKU\experiments\igoor\venv\lib\site-packages\elevenlabslib\helpers.py", line 730, in _api_tts_with_concurrency
    response_json = e.response.json()
AttributeError: 'NoneType' object has no attribute 'json'

This is the function:

def _api_tts_with_concurrency(requestFunction:callable, generationID:str, generationQueue:_PeekQueue) -> requests.Response:
    #Just a helper function which does all the concurrency stuff for TTS calls.
    waitMultiplier = 1
    response = None
    try:
        response = requestFunction()
        response.raise_for_status() #Just in case the callable isn't a function that already does this.
    except requests.exceptions.RequestException as e:
        response_json = e.response.json()
        response_handled = False

Maybe go back to elevenlabs original lib?

- generate_audio is slower, stream_audio is faster but has buffer errors 

FEATURE:
- enqueue phrases