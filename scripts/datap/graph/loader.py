from dataset import MarketDataset

if __name__ == "__main__":
    ds = MarketDataset(root='./pt')
    ds.process()
    