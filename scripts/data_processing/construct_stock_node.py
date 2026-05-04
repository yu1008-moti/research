import pandas as pd
import numpy as np



def main():
    if __name__ == "__main__":
        df = pd.read_csv("data/edges.csv")
        df["source"] = df["source"].apply(lambda x: int(x.split("_")[1]))
        df["target"] = df["target"].apply(lambda x: int(x.split("_")[1]))
        df.to_csv("data/edges.csv", index=False)