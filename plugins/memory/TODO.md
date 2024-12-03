BUG: MULTIPLE TRIGGER HOOKS ???

TTP Request: POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 200 OK"
TYPE = <class 'plugins.memory.memory.Facts'>, MEMORIES: facts=['Igor aime la Jaguar']
TYPE = <class 'dict'>, MEMORIES: {'facts': ['Igor aime la Jaguar']}
storing Igor aime la Jaguar
Hook triggered: store_memory
Executing hook store_memory with kwargs: {'memory': 'Igor aime la Jaguar'}
True
Hook triggered: save_index
TYPE = <class 'dict'>, MEMORIES: {'facts': ['Igor aime la Jaguar']}
storing Igor aime la Jaguar
Hook triggered: store_memory
Executing hook store_memory with kwargs: {'memory': 'Igor aime la Jaguar'}
True
Hook triggered: save_index
storing Igor aime la Jaguar
Hook triggered: store_memory
Executing hook store_memory with kwargs: {'memory': 'Igor aime la Jaguar'}
True
Hook triggered: save_index
Hook triggered: store_memory
Executing hook store_memory with kwargs: {'memory': 'Igor aime la Jaguar'}
True
Hook triggered: save_index
Executing hook store_memory with kwargs: {'memory': 'Igor aime la Jaguar'}
True
Hook triggered: save_index
Executing hook save_index with kwargs: {}
Index saved successfully.
True
Time taken for processing: 0.6663181781768799 seconds
None
Hook triggered: save_index
Executing hook save_index with kwargs: {}
Index saved successfully.
True
Time taken for processing: 0.6663181781768799 seconds
None
Executing hook save_index with kwargs: {}
Index saved successfully.

TAG with metadata appropriately, for example: 

- summary: summary of the conversation (ex. "Igor and Claire discuss about their children")
- TAG the conversation
- re-rank with metadata
- 
- differentiate DAILY memories