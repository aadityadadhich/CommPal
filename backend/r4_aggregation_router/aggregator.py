import os
from channel3_sdk import Channel3
from dotenv import load_dotenv
load_dotenv(dotenv_path="keys.env")

api_key = os.getenv("CHANNEL3_API_KEY")
client = Channel3(api_key=api_key)

results = client.products.search(query="nike", limit = 10)
actual = [product for _, product in zip(range(10), results)]

for products in actual:
    print(f'Title: {products}')
    description = products.description or "no description"
    print(f"Description: {description[:160]}..." if len(description) > 160 else f"Description: {description}")

    