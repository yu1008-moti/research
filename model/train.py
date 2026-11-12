import argparse
import torch
from torch.nn import CrossEntropyLoss
from torch.optim import Adam
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt 
from datetime import datetime as dt
from torch_geometric.data import HeteroData
import random

from model.model import MarketHGTModel
# import scripts.datap.graph.loader as loader
import scripts.datap.graph.const as c
from scripts.datap.graph.dataset import MarketDataset


def train(
        model:MarketHGTModel, dataset: MarketDataset, optimizer:Adam, 
        criterion:CrossEntropyLoss, epoch:int, early_stop:float, train_size:int
        ):

    train_losses = []
    valid_losses = []

    best_valid_loss = float('inf')

    start_time = dt.now()

    for e in range(epoch):

        epock_train_losses = []
        epock_valid_losses = []

        epoch_time = dt.now()
        train_extracted_data = [
            dataset.get(idx) for idx in [
                random.randint(c.TRAIN_RANGE_TID[0], c.TRAIN_RANGE_TID[1] + 1) 
                for _ in range(train_size)
            ]
        ]

        valid_data = [dataset.get(idx) for idx in range(c.VALID_RANGE_TID[0], c.VALID_RANGE_TID[1] + 1)]

        optimizer.zero_grad()

        # for idx in range(c.TRAIN_RANGE_TID[0], c.TRAIN_RANGE_TID[1] + 1):
        for data in train_extracted_data: # for debugging, only use 2856 to 2858 for training0

            labels = torch.argmax(data["stock"].labels.long(), dim=1).to(c.DEVICE)
            output = model(data)

            loss = criterion(output, labels)
            epock_train_losses.append(float(loss.to('cpu').detach().numpy()))
            loss.backward()
        
        optimizer.step()

        for data in valid_data:
            labels = torch.argmax(data["stock"].labels.long(), dim=1).to(c.DEVICE)
            output = model(data)

            loss = criterion(output, labels)
            epock_valid_losses.append(float(loss.to('cpu').detach().numpy()))

        print(f'Epoch {e+1}/{epoch}')
        print(f'Train Loss: {sum(epock_train_losses)/train_size:.4f}')
        print(f'Valid Loss: {sum(epock_valid_losses)/len(valid_data):.4f}')
        print(f'Time for epoch: {dt.now() - epoch_time}')
        train_losses.append(sum(epock_train_losses))
        valid_losses.append(sum(epock_valid_losses))

        # Early stopping and model saving based on validation loss
        if sum(epock_valid_losses) < best_valid_loss:
            best_valid_loss = sum(epock_valid_losses)
            if best_valid_loss < early_stop:  # Save the model only if the validation loss is below a certain threshold
                torch.save(model.state_dict(), f"best_market_hgt_model_{dt.now().strftime('%Y%m%d_%H%M%S')}.pt")
                print(f"Model saved at epoch {e+1} with validation loss {best_valid_loss:.4f}")
                break  # Stop training if the model is saved


    plt.plot(range(1, epoch+1), train_losses, label='Train Loss')    
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('Training Loss')
    plt.legend()
    plt.show()
    print(f"Training completed in: {dt.now() - start_time}")
    torch.save(model.state_dict(), f"market_hgt_model_{dt.now().strftime('%Y%m%d_%H%M%S')}.pt")
    return

def evaluate(model:MarketHGTModel, dataset: MarketDataset, criterion:CrossEntropyLoss):
    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    with torch.no_grad():
        for tID in range(c.EVAL_RANGE_TID[0], c.EVAL_RANGE_TID[1] + 1):
            data = dataset.get(tID)
            labels = torch.argmax(data["stock"].labels.long(), dim=1).to(c.DEVICE)
            output = model(data)

            loss = criterion(output, labels)
            total_loss += float(loss.to('cpu').detach().numpy())
            total_correct += (output.argmax(dim=1) == labels).sum().item()
            total_samples += labels.size(0)

    avg_loss = total_loss / (c.EVAL_LENGTH)
    accuracy = total_correct / total_samples if total_samples > 0 else 0.0

    print(f'Evaluation Loss: {avg_loss:.4f}, Accuracy: {accuracy:.4f}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the MarketHGTModel.")
    parser.add_argument("--in-hid"    , type=int  , default=128   , help="Input hidden dimension.")
    parser.add_argument("--out-hid"   , type=int  , default=128   , help="Output hidden dimension.")
    parser.add_argument("--num-head"  , type=int  , default=4     , help="Number of attention heads.")
    parser.add_argument("--dropout"   , type=float, default=0.1   , help="Dropout rate.")
    parser.add_argument("--epochs"    , type=int  , default=10e+5 , help="Number of epochs to train.")
    parser.add_argument("--train-size", type=int  , default=32    , help="Batch size for training.")
    parser.add_argument("--early-stop", type=int  , default=10e-5 , help="Number of epochs to stop training early.")
    parser.add_argument("--num-layer" , type=int  , default=2     , help="Number of GNN layers.")
    parser.add_argument("--lr"        , type=float, default=0.001 , help="Learning rate.")
    parser.add_argument('--bidirectional', action='store_true', help="Use bidirectional GRU.")
    args = parser.parse_args()

    model = MarketHGTModel(
        in_hid        = args.in_hid, 
        out_hid       = args.out_hid, 
        num_head      = args.num_head, 
        num_layers    = args.num_layer,
        dropout       = args.dropout,
        bidirectional  = False
    ).to(c.DEVICE)

    # Load the dataset by get-method with tfID
    dataset = MarketDataset(root="pt")

    optimizer = Adam(model.parameters(), lr=args.lr)
    criterion = CrossEntropyLoss()

    model.train()
    train(model, dataset, optimizer=optimizer, criterion=criterion, epoch=args.epochs, early_stop=args.early_stop, train_size=args.train_size)

    model.eval()
    evaluate(model, dataset, criterion=criterion)