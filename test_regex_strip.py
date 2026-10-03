import re
new_strip = r'\[(?:.*?MOOD:\s*[^\|\]\n]+|.*?NAME:\s*[^\]\n]+)(?:\|[^\]]+)?\]\s*'
print(re.sub(new_strip, '', '[NAME: ABHINAV] hello'))
print(re.sub(new_strip, '', '[MOOD: Angry | NAME: ABHINAV] hello'))
print(re.sub(new_strip, '', '[MOOD: Angry] hello'))
