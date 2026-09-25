# CPU Affinity for PyG Workloads

- [CPU Affinity for PyG Workloads](#cpu-affinity-for-pyg-workloads)
  - [Using CPU affinity](#using-cpu-affinity)
  - [Binding processes to physical cores](#binding-processes-to-physical-cores)
  - [Isolating the `DataLoader` process](#isolating-the-dataloader-process)
    - [Dual socket CPU separation](#dual-socket-cpu-separation)
  - [Improving memory bounds](#improving-memory-bounds)
  - [Quick start guidelines](#quick-start-guidelines)
  - [Example results](#example-results)

---

CPU を使用する PyG ワークロードのパフォーマンスは，適切なアフィニティマスクを設定することで大幅に改善できる．
プロセッサアフィニティ（コアバインディング）とは，OS本来のキュースケジューリングアルゴリズムを変更し，アプリケーションが実行中に起動するプロセスやスレッドに対して特定のコア群を割り当てられるようにする仕組みである．
その結果，コアのストール（停止）やメモリバウンドを最小化することで，ハードウェア全体の実効利用率を高めることができる．
また，システムに高い負荷がかかっている場合でも，重要なプロセスやスレッドに対して CPU リソースを確保できる．

CPU アフィニティは，パフォーマンス上重要な次の2つの領域を対象とする．

- **Execution bind（実行バインド）：** プロセス／スレッドが実行されるコアを指定する．
- **Memory bind（メモリバインド）：** メモリページがバインドされる優先メモリ領域（NUMA マシンにおけるローカル領域）を指定する．

以下では，Intel CPU 上で PyG のパフォーマンスを最大化するために利用できる，すぐに使えるツールや環境設定について説明する．

> **Note**
>
> 全体として，CPU アフィニティはある種のアプリケーションのパフォーマンスと予測可能性を向上させる有用な手段となり得るが，あらゆるケースに当てはまる唯一の設定というものは存在しない．CPU アフィニティが自分のユースケースに適しているかどうかを慎重に検討し，変更を加えた場合はその効果を実際にテスト・測定することが重要である．

## Using CPU affinity

各 PyG ワークロードは，PyTorch のイテレータクラスである `MultiProcessingDataLoaderIter` を用いて並列化できる．このクラスは，[`torch.utils.data.DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) に `num_workers > 0` が渡された場合に自動的に有効化される．
内部的には，メインプロセスと並列に動作する `num_workers` 個のサブプロセスが生成される．
データ読み込みプロセスに対して CPU アフィニティマスクを設定すると，[`DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) のワーカースレッドが特定の CPU コアに配置される．
これにより，プリフェッチしたバッチをローカルメモリに配置できるようになり，より効率的なデータバッチ準備が可能になる．
プロセスやスレッドがあるコアから別のコアへ移動するたびに，レジスタやキャッシュのフラッシュ・再読み込みが必要になる．
これが頻繁に発生すると非常にコストが高くなる可能性があり，また，スレッドが自身のデータに近い場所に留まれなくなったり，キャッシュ上でデータを共有できなくなったりすることもある．

PyG（バージョン2.3以降）では，[`NodeLoader`](../modules/loader.html#torch_geometric.loader.NodeLoader) と [`LinkLoader`](../modules/loader.html#torch_geometric.loader.LinkLoader) クラスが，[`torch_geometric.loader.AffinityMixin`](../modules/loader.html#torch_geometric.loader.AffinityMixin) コンテキストマネージャを用いた CPU アフィニティのネイティブサポートを正式に提供している．
CPU アフィニティは，`num_workers > 0` のユースケースにおいて [`enable_cpu_affinity()`](../modules/loader.html#torch_geometric.loader.AffinityMixin.enable_cpu_affinity) メソッドを介して有効化でき，初期化時に各ワーカーへ個別のコアが割り当てられることが保証される．
`loader_cores` 引数を使うことで，ユーザーが定義したコア ID のリストを割り当てることも可能である．
指定しない場合，コア ID 0 から自動的に割り当てられる．
現時点では，1つのワーカーには単一のコアしか割り当てられないため，ワーカーのプロセスではデフォルトでマルチスレッドが無効化されている．
まず試すべきワーカー数の目安は `[2, 4]` の範囲であり，最適な値はワークロードの特性によって変わる．

```python
loader = NeigborLoader(
    data,
    num_workers=3,
    ...,
)

with loader.enable_cpu_affinity(loader_cores=[0, 1, 2]):
    for batch in loader:
        pass
```

マルチプロセスの CPU ワークロードでは，一般的に `filter_per_worker=True`（デフォルトで [`True`](https://docs.python.org/3/library/constants.html#True)）を使用することが推奨される．
各ワーカーは，まず事前定義されたサンプラーを用いてノードのインデックスをサンプリングし，次にサンプリングされたノード・エッジに応じてノード・エッジ特徴をフィルタリングすることで，各ミニバッチを準備する．
このフィルタリング関数は，DRAM にロードされた入力 [`Data`](../generated/torch_geometric.data.Data.html#torch_geometric.data.Data) テンソル全体からノード特徴ベクトルを選択する．
`filter_per_worker` を `True` に設定すると，各ワーカーのサブプロセスが自身の CPU リソース内でフィルタリングを実行する．
これにより，メインプロセスのリソースが解放され，GNN の計算のためだけに確保できるようになる．

## Binding processes to physical cores

一般的なパフォーマンスチューニングの原則に従い，深層学習ワークロードには物理コアのみを使用することが望ましい．
例えば，2つの論理スレッドが同時に `GEMM` を実行する場合，両者は同じコアリソースを共有することになり，フロントエンドバウンドが発生する．このフロントエンドバウンドによるオーバーヘッドは，2つの論理スレッドを同時に実行することによる利得を上回ってしまう．
これは，OpenMP スレッドが同一の `GEMM` 実行ユニットを奪い合うために起こる（[こちら](https://pytorch.org/tutorials/intermediate/torchserve_with_ipex.html)を参照）．

このバインディングには様々な方法があるが，最も一般的なツールは次の通りである．

- `numactl`（Linux のみ）：

```console
--physcpubind=<cpus>, -C <cpus>  or --cpunodebind=<nodes>, -N <nodes>
```

- [Intel OMP](https://www.intel.com/content/www/us/en/developer/articles/technical/how-to-get-better-performance-on-pytorchcaffe2-with-intel-acceleration.html) `libiomp`：

```console
export KMP_AFFINITY=granularity=fine,proclist=[0-<physical_cores_num-1>],explicit
```

- GNU `libgomp`：

```console
export GOMP_CPU_AFFINITY="0-<physical_cores_num-1>"
```

## Isolating the `DataLoader` process

最良のパフォーマンスを得るためには，上記で挙げたツールを用いたメインプロセスのアフィニティ設定と，マルチプロセスの [`DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) のアフィニティ設定を組み合わせる必要がある．
並列化された各 PyG ワークロードの実行において，メインプロセスは GNN 層にわたるメッセージパッシングの更新を行い，[`DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) のワーカーサブプロセスは GNN モデルへ渡すデータの取得・前処理を担う．
最良の結果を得るためには，これら2つのプロセスに割り当てる CPU リソースを分離することが望ましい．
そのためには，それぞれのアフィニティマスクに割り当てる CPU が互いに排他的（重複しない）になるようにする必要がある．
例えば，4つの [`DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) ワーカーが CPU `[0, 1, 2, 3]` に割り当てられている場合，メインプロセスは残りの利用可能なコアを使用すべきであり，具体的には次のように呼び出す．

```console
numactl -C 4-(N-1) --localalloc python …
```

ここで `N` は物理コアの総数であり，最後の CPU のコア ID は `N-1` である．
`--localalloc` を追加すると，ローカルメモリへの割り当てが改善され，キャッシュをアクティブなコアの近くに保つことができる．

### Dual socket CPU separation

デュアルソケット CPU の場合，ソケット間でプロセスをさらに分離することが有益な場合がある．
これにより，メインプロセスにおけるリモートメモリ呼び出しの頻度が減少する．
その目的は，[ローカルメモリ上の高速キャッシュを活用し，NUMA ノード間でキャッシュデータを移動させることによって生じるメモリバウンドを削減すること](https://pytorch.org/tutorials/intermediate/torchserve_with_ipex.html)である．
これは，[`DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) のアフィニティを使用し，メインプロセスを第2ソケットのコア上で起動することで実現できる．具体的には次の通りである．

```console
numactl -C M-(N-1) -m 1 python …
```

ここで `M` は，第2の CPU ソケットの最初のコアの `cpuid` である．
補完的なメモリ割り当てフラグ `-m 1` を追加すると，メインプロセスが実行されているのと同じ NUMA ノード上でのキャッシュ割り当てが優先される（より緩やかなメモリ割り当てにしたい場合は，代わりに `--preferred 1` を使用する）．
これにより，計算が行われるのと同じソケット上でデータをすぐに利用できるようになる．
この設定はワークロードに強く依存するため，ある程度のチューニングが必要になる場合がある．より多くの OMP スレッドを使用することと，リモートメモリ呼び出しの数を制限することとの間のトレードオフを管理する必要があるためである．

## Improving memory bounds

PyTorch の CPU パフォーマンス最適化ガイドラインに従い，PyG でも `jemalloc` または `TCMalloc` を使用することが推奨される．
これらは一般に，デフォルトの PyTorch [メモリアロケータ](https://pytorch.org/tutorials/intermediate/torchserve_with_ipex_2.html)である `PTMalloc` よりも優れたメモリ使用効率を達成できる．
[デフォルト以外のメモリアロケータ](https://pytorch.org/tutorials/recipes/recipes/tuning_guide.html)は，スクリプト実行前に `LD_PRELOAD` を用いて指定できる．

## Quick start guidelines

CPU アフィニティを用いて最良のパフォーマンスを達成するための一般的なガイドラインは，次のステップにまとめられる．

1. データローダーを並列化することでデータセットが恩恵を受けるかどうかをテストする．
   データセットによっては，特に入力 [`Data`](../generated/torch_geometric.data.Data.html#torch_geometric.data.Data) の次元が比較的小さい場合，単純な逐次データローダーを使用する方が有利なこともある．

2. `num_workers > 0` を設定してマルチプロセスのデータローダーを有効化する．
   `num_workers` の目安としては `[2, 4]` の範囲が適切である．
   ただし，より複雑なデータセットの場合は，より多くのワーカー数を試してみるとよい．
   [`DataLoader`](https://docs.pytorch.org/docs/main/data.html#torch.utils.data.DataLoader) のコアをアフィニティ化するには，[`enable_cpu_affinity()`](../modules/loader.html#torch_geometric.loader.AffinityMixin.enable_cpu_affinity) 機能を使用する．

3. 実行を物理コアにバインドする．
   代替手段として，システムレベルでハイパースレッディングを完全に無効化することもできる．

4. `numactl`，`libiomp5` ライブラリの `KMP_AFFINITY`，または `libgomp` ライブラリの `GOMP_CPU_AFFINITY` を用いて，メインプロセスに使用するコアとデータローダーワーカーに使用するコアを分離する．

5. 自身のワークロードに最適な OMP スレッド数を見つける．
   出発点としては `N - num_workers` が適切である．
   一般に，十分に並列化されたモデルは多数の OMP スレッドから恩恵を受ける．
   しかし，モデルの計算フローに並列領域と逐次領域が入り組んでいる場合，並列領域間でスレッドを生成・維持するためのリソース割り当てが必要になるため，パフォーマンスが低下する．

6. デュアルソケット CPU を使用する場合，データ読み込みを一方のソケットに割り当て，メインプロセスをもう一方のソケットに割り当てたうえで，メインプロセスが実行されているのと同じソケット上でメモリを割り当てる（`numactl -m`）という設定を試してみるとよい．
   これにより最良のキャッシュ割り当てが得られることが多く，多くの場合，より多くの OMP スレッドを使用することによる利点を上回る．

7. `jemalloc` や `TCMalloc` のようなデフォルト以外のメモリアロケータを使用することで，さらなるパフォーマンスの向上を得られる場合がある．

8. CPU アフィニティマスクの最適な設定を見つけることは，各イテレーションにおいてデータの読み込み・準備に費やされる CPU 時間の割合と，GNN の実行に費やされる時間の割合とのバランスを管理する問題である．
   バッチサイズ，サンプリングする近傍数，レイヤー数といったモデルのハイパーパラメータを変更することで，異なる結果が得られることがある．
   一般的な原則として，複雑なグラフのサンプリングを必要とするワークロードほど，データ準備ステップのために CPU リソースの一部を確保しておくことから，より多くの恩恵を受けられる．

## Example results

以下の図は，`benchmark/training/training_benchmark.py` に対して CPU アフィニティマスクを適用した結果を示している．
測定はワーカー数を変化させながら行われ，各ベンチマークにおいてその他のハイパーパラメータは次のように一定に保たれている：`--warmup 0 --use-sparse-tensor --num-layers 3 --num-hidden-channels 128 --batch-sizes 2048`．
次の3種類のアフィニティ構成が示されている．

- **Baseline** — `OMP_NUM_THREADS` のみを変更：

```console
OMP_NUM_THREADS=(N-num_workers) python training_benchmark.py --num-workers …
```

- **Aff** — データローダープロセスは第1ソケット，メインプロセスは第1・第2ソケットの両方（98〜110スレッド）：

```console
LD_PRELOAD=(path)/libjemalloc.so (path)/libiomp5.so MALLOC_CONF=oversize_threshold:1,background_thread:true,metadata_thp:auto OMP_NUM_THREADS=(N-num_workers) KMP_AFFINITY=granularity=fine,compact,1,0 KMP_BLOCKTIME=0 numactl -C <num_workers-(N-1)> --localalloc python training_benchmark.py --cpu-affinity --num-workers …
```

- **Aff+SocketSep** — データローダープロセスは第1ソケット，メインプロセスは第2ソケット（60スレッド）：

```console
LD_PRELOAD=(path)/libjemalloc.so (path)/libiomp5.so MALLOC_CONF=oversize_threshold:1,background_thread:true,metadata_thp:auto OMP_NUM_THREADS=(N-M) KMP_AFFINITY=granularity=fine,compact,1,0 KMP_BLOCKTIME=0 numactl -C <M-(N-1)> -m 1 python training_benchmark.py --cpu-affinity --num-workers ...
```

各モデル／データセットの組み合わせに対する学習時間は，ベースラインについてはワーカー数 `[0, 2, 4, 8, 16]`，各アフィニティ構成についてはワーカー数 `[2, 4, 8, 16]` における結果の平均を取ることで得られている．
その後，アフィニティ構成の平均値をベースラインの平均測定値に対して正規化している．
この値は $y$ 軸上に示されている．
各結果の上に付されたラベルは，該当の構成を使用した場合のエンドツーエンドのパフォーマンス向上を示している．
全モデル／データセットのサンプルにおいて，平均学習時間はプレーンなアフィニティ設定で **1.53倍**，ソケット分離を伴うアフィニティ設定で **1.85倍** 短縮されている．

![](../_images/training_affinity.png)

*量産前のデュアルソケット Intel(R) Xeon(R) Platinum 8481C @ 2.0Ghz（56コア×2）CPU．*
