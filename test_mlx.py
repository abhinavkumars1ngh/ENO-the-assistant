from mlx_lm import load
from mlx_lm.utils import generate_step
import mlx.core as mx
import time

m, t = load("/Users/abhinavkumarsingh/ENO/mlx_models/gemma-2-2b-it-4bit")
prompt = "user\nExplain probability.\nmodel\n"
tokens = t.encode(prompt, return_tensors="np")
prompt_tokens = mx.array(tokens[0])

t0 = time.time()
gen = generate_step(prompt_tokens, m, temp=0.7)
count = 0
for (token, prob) in gen:
    token_id = token if isinstance(token, int) else token.item()
    count += 1
    if count >= 20:
        break
t1 = time.time()
print(f"Generated {count} tokens in {t1 - t0:.2f}s ({(count)/(t1-t0):.2f} tok/s)")
