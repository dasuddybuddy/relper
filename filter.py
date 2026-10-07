import pandas as pd

df = pd.read_csv("writes/corpus.csv")
print(f"Total rows: {len(df)}")
print(f"Rows with text: {df['text'].notna().sum()}")

df_clean = df[df["text"].notna() & (df["text"].str.strip() != "")]
df_clean.to_csv("ragproject/input/gt_cs_papers.csv", index=False)
print(f"Wrote {len(df_clean)} usable rows")
