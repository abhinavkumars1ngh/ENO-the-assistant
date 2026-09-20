import time
class DummyTokenizer:
    def decode(self, tokens, skip_special_tokens=False):
        return "".join(map(str, tokens))

tokenizer = DummyTokenizer()
tokens = ["a"] * 5000

t0 = time.time()
for i in range(1, 5000):
    text = tokenizer.decode(tokens[:i])
print("List slice & decode:", time.time() - t0)
