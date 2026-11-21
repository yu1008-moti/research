import os
import json
import random

# os.environ['CUDA_LAUNCH_BLOCKING'] = "1"

import argparse
import torch
from torch.nn import CrossEntropyLoss
from torch.optim import Adam
import duckdb as db
from datetime import datetime as dt

from model.model import MarketHGTModel
import scripts.datap.graph.const as c
from scripts.datap.graph.dataset import MarketDataset
from model.helper import EarlyStopping, RealTimePlot, SampledMarketDataLoader, Evaluation, get_model_dir

def train(
        model:MarketHGTModel, optimizer:Adam, smdl:SampledMarketDataLoader,
        early_stopping:EarlyStopping, criterion:CrossEntropyLoss, epoch:int, batch_size:int,
        plotter:RealTimePlot
        ) -> None:
    
    start_time = dt.now()
    train_loader, valid_loader = smdl.get_loader()
    

    for e in range(epoch):
        # train_loader, valid_loader = smdl.get_loader()
        epock_train_losses, epock_valid_losses = [], []
        epoch_time = dt.now()

        # Train loop
        model.train()
        for batch in train_loader:
            optimizer.zero_grad()
            labels = torch.argmax(batch["stock"].labels.long(), dim=1).to(c.DEVICE)
            output = model(batch)
            loss = criterion(output, labels)
            epock_train_losses.append(float(loss.to('cpu').detach().numpy()))
            loss.backward()
            optimizer.step()

        # Valid loop
        model.eval()
        with torch.no_grad():
            for batch in valid_loader:
                labels = torch.argmax(batch["stock"].labels.long(), dim=1).to(c.DEVICE)
                output = model(batch)
                loss = criterion(output, labels)
                epock_valid_losses.append(float(loss.to('cpu').detach().numpy()))

        train_loss = sum(epock_train_losses)/len(epock_train_losses)
        valid_loss = sum(epock_valid_losses)/len(epock_valid_losses)

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

def eval(model:MarketHGTModel, dataset: MarketDataset, criterion:CrossEntropyLoss, eval_split: tuple):
    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    conn = db.connect(database=":memory:", read_only=False)
    conn.execute(f"attach '{c.ACT_DB_PATH}' as act;")
    conn.execute(f"attach '{c.DEV_DB_PATH}' as dev;")
    df = conn.execute("SELECT * from dev.tool.risk_free;").df()[['tID', 'r_f']]
    conn.close()

    r_p = []
    r_f = db.connect(database=":memory:", read_only=False)

    model.eval()
    with torch.no_grad():
        for tID in range(eval_split[0], eval_split[1]):
            data = dataset.get(tID)
            labels  = torch.argmax(data["stock"].labels.long(), dim=1).to(c.DEVICE)
            returns = data["stock"].returns.to(c.DEVICE)
            
            output = model(data)

            r_p.append((returns, output))

            loss = criterion(output, labels)
            total_loss += float(loss.to('cpu').detach().numpy())
            total_correct += (output.argmax(dim=1) == labels).sum().item()
            total_samples += labels.size(0)

    avg_loss = total_loss / (eval_split[1] - eval_split[0] + 1)
    accuracy = total_correct / total_samples if total_samples > 0 else 0.0

    print(f'Evaluation Loss: {avg_loss:.4f}, Accuracy: {accuracy:.4f}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the MarketHGTModel.")
    parser.add_argument("--in-hid"    , type=int  , default=128   , help="Input hidden dimension.")
    parser.add_argument("--out-hid"   , type=int  , default=128   , help="Output hidden dimension.")
    parser.add_argument("--num-head"  , type=int  , default=4     , help="Number of attention heads.")
    parser.add_argument("--dropout"   , type=float, default=0.1   , help="Dropout rate.")
    parser.add_argument("--patience"  , type=int  , default=25    , help="Number of epochs to stop training early.")
    parser.add_argument("--epochs"    , type=int  , default=10000 , help="Number of epochs to train.")
    parser.add_argument("--batch-size", type=int  , default=4     , help="Batch size for training.")
    parser.add_argument("--min-delta" , type=float, default=10e-5 , help="Number of epochs to stop training early.")
    parser.add_argument("--num-layer" , type=int  , default=2     , help="Number of GNN layers.")
    parser.add_argument("--lr"        , type=float, default=0.001 , help="Learning rate.")
    parser.add_argument('--k'         , type=int  , default=20    , help="Number of random samples to draw for each epoch.")
    parser.add_argument("--train-id"  , type=int  , default=0     , help="Training ID for splitted training range.")
    parser.add_argument('--model-id'  , type=str  , default=None  , help="Model ID; outputs go to save_models/<model_id>/ (default: timestamp).")

    parser.add_argument('--top-k'     , type=int  , default=20    , help="Number of stocks for long/short portfolio in evaluation.")

    parser.add_argument('--eval'         , action='store_true', help="Run evaluation only (requires --model_id).")
    parser.add_argument('--bidirectional', action='store_true', help="Use bidirectional GRU.")

    args = parser.parse_args()

    if args.model_id is None:
        if args.eval:
            parser.error("--eval requires --model-id.")
        args.model_id = dt.now().strftime('%Y%m%d_%H%M%S')
    model_dir = get_model_dir(args.model_id)
    print(f"model_dir: {model_dir}")

    if args.eval:
        eval_split = c.EVAL_SPLIT
        dataset = MarketDataset(root="pt")
        model = MarketHGTModel(
            in_hid=args.in_hid, out_hid=args.out_hid, num_head=args.num_head,
            num_layers=args.num_layer, dropout=args.dropout,
            bidirectional=args.bidirectional,
        ).to(c.DEVICE)
        model.load_state_dict(torch.load(os.path.join(model_dir, "best_model.pt"), map_location=c.DEVICE))
        criterion = CrossEntropyLoss()
        evaluation = Evaluation(model, dataset, criterion=criterion, eval_split=eval_split,
                                model_dir=model_dir, top_k=args.top_k)
        evaluation.evaluate()
        print(f"Saved daily results: {evaluation.save()}")
        exit(0)


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
    # if not dataset.graph_consecutive_check():  # Ensure that the graph data is consecutive and valid
    #     raise ValueError("The graph data is not consecutive or valid.")

    optimizer = Adam(model.parameters(), lr=args.lr)
    criterion = CrossEntropyLoss()
    early_stopping = EarlyStopping(model_dir=model_dir, patience=args.patience, min_delta=args.min_delta)
    plotter = RealTimePlot(model_dir=model_dir)
    with open(os.path.join(model_dir, "params.json"), "w", encoding="utf-8") as f:
        json.dump(vars(args), f, indent=2, ensure_ascii=False)
    smdl = SampledMarketDataLoader(
        dataset, 
        batch_size=args.batch_size,
        train_ds_range=c.TRAIN_SPLIT[args.train_id],
        valid_ds_range=c.VALID_SPLIT[args.train_id],
        k=args.k
    )

    eval_split = c.EVAL_SPLIT
    
    train(
        model, optimizer=optimizer, smdl=smdl,
        early_stopping=early_stopping, criterion=criterion, 
        epoch=args.epochs, batch_size=args.batch_size,
        plotter=plotter
    )