# Creating Graph Datasets

- [Creating Graph Datasets](#creating-graph-datasets)
  - [「In Memory Dataset」の作成](#in-memory-datasetの作成)
  - [「より大きな」Datasetの作成](#より大きなdatasetの作成)
  - [よくある質問](#よくある質問)
  - [演習問題](#演習問題)

---

PyG にはすでに多くの有用なデータセットが含まれているが，自分で記録したデータや非公開のデータを使って独自のデータセットを作成したい場合もあるだろう．

自分でデータセットを実装すること自体は難しくなく，既存の各データセットがどのように実装されているかソースコードを覗いてみるのもよい．ここでは，独自のデータセットをセットアップするために必要となる事柄を簡単に紹介する．

データセットのための抽象クラスとして，`torch_geometric.data.Dataset` と `torch_geometric.data.InMemoryDataset` の2つが提供されている．`torch_geometric.data.InMemoryDataset` は `torch_geometric.data.Dataset` を継承したクラスであり，データセット全体が CPU メモリに収まる場合に使用すべきものである．

`torchvision` の慣習に倣い，各データセットにはデータセットの保存場所を示す root フォルダを渡す．この root フォルダは，データセットのダウンロード先である `raw_dir` と，処理済みデータセットの保存先である `processed_dir` の2つに分割される．

さらに，各データセットには `transform`，`pre_transform`，`pre_filter` という関数を渡すことができ，デフォルトはいずれも `None` である．`transform` 関数はデータオブジェクトへアクセスする直前に動的に変換を行うものであり（データ拡張に最も適している），`pre_transform` 関数はデータオブジェクトをディスクへ保存する前に変換を適用するものであり（一度だけ実行すればよい重い前処理に最も適している），`pre_filter` 関数はデータオブジェクトを保存する前に手動でフィルタリングするために使用できる．

## 「In Memory Dataset」の作成

`InMemoryDataset` を作成するには，次の4つの基本メソッドを実装する必要がある．

- `raw_file_names()`：ダウンロードをスキップするために `raw_dir` 内に存在している必要があるファイルのリスト．
- `processed_file_names()`：処理をスキップするために `processed_dir` 内に存在している必要があるファイルのリスト．
- `download()`：生データを `raw_dir` へダウンロードする．
- `process()`：生データを処理し，`processed_dir` へ保存する．

本当の意味での中心的な処理は `process()` の本体で行われる．ここでは，`Data` オブジェクトのリストを読み込んで作成し，それを `processed_dir` へ保存する必要がある．巨大な python のリストをそのまま保存するのはかなり遅いため，保存前に `collate()` によってリストを1つの巨大な `Data` オブジェクトへと統合する．統合されたデータオブジェクトは，すべてのサンプルを1つの大きなデータオブジェクトへ連結したものであり，このオブジェクトから個々のサンプルを再構築するための `slices` 辞書を返す．

```python
import torch
from torch_geometric.data import InMemoryDataset, download_url


class MyOwnDataset(InMemoryDataset):
    def __init__(self, root, transform=None, pre_transform=None, pre_filter=None):
        super().__init__(root, transform, pre_transform, pre_filter)
        self.load(self.processed_paths[0])
        # For PyG<2.4:
        # self.data, self.slices = torch.load(self.processed_paths[0])

    @property
    def raw_file_names(self):
        return ['some_file_1', 'some_file_2', ...]

    @property
    def processed_file_names(self):
        return ['data.pt']

    def download(self):
        # Download to `self.raw_dir`.
        download_url(url, self.raw_dir)
        ...

    def process(self):
        # Read data into huge `Data` list.
        data_list = [...]

        if self.pre_filter is not None:
            data_list = [data for data in data_list if self.pre_filter(data)]

        if self.pre_transform is not None:
            data_list = [self.pre_transform(data) for data in data_list]

        self.save(data_list, self.processed_paths[0])
        # For PyG<2.4:
        # torch.save(self.collate(data_list), self.processed_paths[0])
```

## 「より大きな」Datasetの作成

メモリに収まらないデータセットを作成する場合は，`torch_geometric.data.Dataset` を使用できる．これは `torchvision` のデータセットの考え方に近く，加えて次のメソッドの実装が要求される．

- `len()`：データセット中のサンプル数を返す．
- `get()`：単一のグラフを読み込むロジックを実装する．

内部的には，`__getitem__()` が `get()` からデータオブジェクトを取得し，必要に応じて `transform` に従ってそれらを変換する．

```python
import os.path as osp

import torch
from torch_geometric.data import Dataset, download_url


class MyOwnDataset(Dataset):
    def __init__(self, root, transform=None, pre_transform=None, pre_filter=None):
        super().__init__(root, transform, pre_transform, pre_filter)

    @property
    def raw_file_names(self):
        return ['some_file_1', 'some_file_2', ...]

    @property
    def processed_file_names(self):
        return ['data_1.pt', 'data_2.pt', ...]

    def download(self):
        # Download to `self.raw_dir`.
        path = download_url(url, self.raw_dir)
        ...

    def process(self):
        idx = 0
        for raw_path in self.raw_paths:
            # Read data from `raw_path`.
            data = Data(...)

            if self.pre_filter is not None and not self.pre_filter(data):
                continue

            if self.pre_transform is not None:
                data = self.pre_transform(data)

            torch.save(data, osp.join(self.processed_dir, f'data_{idx}.pt'))
            idx += 1

    def len(self):
        return len(self.processed_file_names)

    def get(self, idx):
        data = torch.load(osp.join(self.processed_dir, f'data_{idx}.pt'))
        return data
```

ここでは，各グラフデータオブジェクトが `process()` 内で個別に保存され，`get()` 内で手動で読み込まれる．

## よくある質問

1. **`download()` や `process()` の実行をスキップするにはどうすればよいか？**
   > `download()` および `process()` メソッドをオーバーライドしないことで，ダウンロードや処理をスキップできる．
   >
   > ```python
   > class MyOwnDataset(Dataset):
   >     def __init__(self, transform=None, pre_transform=None):
   >         super().__init__(None, transform, pre_transform)
   > ```

2. **これらのデータセットインターフェースを本当に使う必要があるか？**
   > いいえ．通常の PyTorch と同様に，たとえば明示的にディスクへ保存せずにその場で合成データを作成したい場合など，データセットを使わなくてもよい．この場合，単に `Data` オブジェクトを保持する通常の python のリストを `DataLoader` に渡せばよい．
   >
   > ```python
   > from torch_geometric.data import Data
   > from torch_geometric.loader import DataLoader
   >
   > data_list = [Data(...), ..., Data(...)]
   > loader = DataLoader(data_list, batch_size=32)
   > ```

## 演習問題

`Data` オブジェクトのリストから構築された次の `InMemoryDataset` を考える．

```python
class MyDataset(InMemoryDataset):
    def __init__(self, root, data_list, transform=None):
        self.data_list = data_list
        super().__init__(root, transform)
        self.load(self.processed_paths[0])

    @property
    def processed_file_names(self):
        return 'data.pt'

    def process(self):
        self.save(self.data_list, self.processed_paths[0])
```

1. `self.processed_paths[0]` の出力は何か？
2. `save()` は何をしているか？
