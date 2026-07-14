import pandas as pd
import pickle
from sentence_transformers import SentenceTransformer

# -----------------------------
# Load Dataset
# -----------------------------
print("Loading dataset...")

df = pd.read_csv("data/tmdb_Preprocessed_dataset.csv")

print(f"Dataset Loaded Successfully ({len(df)} movies)")

# -----------------------------
# Check required column
# -----------------------------
if "tags" not in df.columns:
    raise Exception(
        "The dataset does not contain a 'tags' column.\n"
        f"Available columns:\n{list(df.columns)}"
    )

# Fill missing values
df["tags"] = df["tags"].fillna("")

# -----------------------------
# Load Sentence Transformer
# -----------------------------
print("Loading SentenceTransformer model...")

model = SentenceTransformer("all-MiniLM-L6-v2")

# -----------------------------
# Generate Embeddings
# -----------------------------
print("Generating embeddings...")

embeddings = model.encode(
    df["tags"].tolist(),
    show_progress_bar=True,
    convert_to_numpy=True
)

print("Embeddings generated successfully!")

# -----------------------------
# Save Embeddings
# -----------------------------
output_path = "models/movie_embeddings.pkl"

with open(output_path, "wb") as file:
    pickle.dump(embeddings, file)

print(f"\nEmbeddings saved to: {output_path}")
print("Total Embeddings:", len(embeddings))
print("Embedding Shape :", embeddings.shape)
print("\nDone!")