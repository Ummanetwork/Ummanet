from pathlib import Path
text = Path('backend/app/main.py').read_text(errors='ignore')
start = text.index('LANGUAGE_LABELS = {')
end = text.index('}', start) + 1
print(repr(text[start:end]))
