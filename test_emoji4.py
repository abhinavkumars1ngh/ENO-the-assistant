import mlx_lm
import mlx.core as mx
from mlx_lm.utils import generate_step

model, tokenizer = mlx_lm.load("/Users/abhinavkumarsingh/ENO/qwen_local_weights")
prompt = tokenizer.encode("Output a single fire emoji and nothing else: ", return_tensors="np")
prompt_tokens = mx.array(prompt[0])

all_ids = []
for token, prob in generate_step(prompt_tokens, model, temp=0.0):
    token_id = token if isinstance(token, int) else token.item()
    all_ids.append(token_id)
    print("Tokens:", all_ids, "Decoded so far:", repr(tokenizer.decode(all_ids)))
    if len(all_ids) > 10:
        break
