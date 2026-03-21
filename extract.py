import os
import re

html_path = r"c:\Users\HP\Downloads\rxai-ghana.html"
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

# Extract styles
style_match = re.search(r"<style>(.*?)</style>", content, flags=re.DOTALL)
css_content = style_match.group(1) if style_match else ""

# Extract script
script_match = re.search(r"<script>(.*?)</script>", content, flags=re.DOTALL)
js_content = script_match.group(1) if script_match else ""

# Replace in HTML
html_content = re.sub(r"<style>.*?</style>", '<link rel="stylesheet" href="css/styles.css">', content, flags=re.DOTALL)
html_content = re.sub(r"<script>.*?</script>", '<script src="js/app.js"></script>', html_content, flags=re.DOTALL)

os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

with open("static/css/styles.css", "w", encoding="utf-8") as f:
    f.write(css_content.strip())

with open("static/js/app.js", "w", encoding="utf-8") as f:
    f.write(js_content.strip())

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(html_content.strip())

print("Extraction complete.")
