import argparse
import torch
from torch.nn import CrossEntropyLoss
from torch.optim import Adam
from datetime import datetime as dt

from model.model import MarketHGTModel
import scripts.datap.graph.const as c
from scripts.datap.graph.dataset import MarketDataset
from model.helper import EarlyStopping, RealTimePlot, get_loader


def train(
        model:MarketHGTModel, dataset: MarketDataset, optimizer:Adam, 
        early_stopping:EarlyStopping, criterion:CrossEntropyLoss, epoch:int, batch_size:int,
        plotter:RealTimePlot
        ) -> None:
    train_loader, valid_loader = get_loader(dataset, batch_size)
    start_time = dt.now()

    for e in range(epoch):
        epock_train_losses, epock_valid_losses = [], []
        epoch_time = dt.now()

        # Train loop
        optimizer.zero_grad()
        for batch in train_loader: # for debugging, only use 2856 to 2858 for training
            labels = torch.argmax(batch["stock"].labels.long(), dim=1).to(c.DEVICE)
            output = model(batch)
            loss = criterion(output, labels)
            epock_train_losses.append(float(loss.to('cpu').detach().numpy()))
            loss.backward()
        optimizer.step()

        # Valid loop
        for batch in valid_loader:
            labels = torch.argmax(batch["stock"].labels.long(), dim=1).to(c.DEVICE)
            output = model(batch)
            loss = criterion(output, labels)
            epock_valid_losses.append(float(loss.to('cpu').detach().numpy()))

        train_loss = sum(epock_train_losses)/batch_size
        valid_loss = sum(epock_valid_losses)/batch_size

        # Print epoch summary
        print(f'Epoch {e+1}/{epoch}')
        print(f'Train Loss: {train_loss:.4f}')
        print(f'Valid Loss: {valid_loss:.4f}')
        print(f'Time for epoch: {dt.now() - epoch_time}')

        # Early stopping and model saving based on validation loss
        early_stopping(valid_loss, model)
        if early_stopping.early_stop:
            print("Early stopping triggered. Stopping training.")
            break

        # Update real-time plot
        plotter.update(train_loss, valid_loss)
    
    plotter.close()
    print(f"Training completed in: {dt.now() - start_time}")
    return

def eval(model:MarketHGTModel, dataset: MarketDataset, criterion:CrossEntropyLoss):
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
    parser.add_argument("--patience"  , type=int  , default=10    , help="Number of epochs to stop training early.")
    parser.add_argument("--epochs"    , type=int  , default=10000 , help="Number of epochs to train.")
    parser.add_argument("--batch-size", type=int  , default=8    , help="Batch size for training.")
    parser.add_argument("--min-delta" , type=float, default=10e-5 , help="Number of epochs to stop training early.")
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
        bidirectional = args.bidirectional
    ).to(c.DEVICE)

    # Load the dataset by get-method with tfID
    dataset = MarketDataset(root="pt")
    if not dataset.graph_consecutive_check():  # Ensure that the graph data is consecutive and valid
        raise ValueError("The graph data is not consecutive or valid.")

    optimizer = Adam(model.parameters(), lr=args.lr)
    criterion = CrossEntropyLoss()
    early_stopping = EarlyStopping(patience=args.patience, min_delta=args.min_delta)
    plotter = RealTimePlot()
 
    model.train()
    train(
        model, dataset, optimizer=optimizer, 
        early_stopping=early_stopping, criterion=criterion, 
        epoch=args.epochs, batch_size=args.batch_size,
        plotter=plotter
    )

    model.eval()
    eval(model, dataset, criterion=criterion)