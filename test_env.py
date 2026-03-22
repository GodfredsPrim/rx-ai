import os
from pathlib import Path
from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent
env_path = base_dir / '.env'
print(f"Checking for .env at: {env_path}")
print(f"Exists: {env_path.exists()}")

loaded = load_dotenv(env_path, verbose=True)
print(f"load_dotenv returned: {loaded}")

key = os.getenv("DEEPSEEK_API_KEY")
if key:
    print(f"Found DEEPSEEK_API_KEY starting with: {key[:10]}...")
else:
    print("DEEPSEEK_API_KEY NOT FOUND")
