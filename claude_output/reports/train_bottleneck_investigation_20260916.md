# model/baseline/train.py 学習速度調査（Adam.stepプロファイリング〜方針決定）

実施日: 2026-09-16。`uv run python -m model.baseline.train --serial-id 9999 --profile --profile-batches 20`
で取得した `torch.profiler` の出力（テーブル・Chrome trace `trace.json`）を中心に、
「Optimizer.step#Adam.step が学習のボトルネックか」という仮説を検証したセッションの記録。

## 今回やったこと

1. `model/baseline/train.py` / `model/baseline/model.py` のコードレビュー（モデル構造、
   ハイパーパラメータ、`NeighborLoader` の使い方を確認）。
2. `torch.profiler` のテーブル出力を `sort_by="cuda_time"` → `sort_by="cpu_time_total"`、
   `row_limit` を増やして再取得し、Adam.step の内訳を子オペレータ単位で確認。
3. Chrome trace（`trace.json`、67MB・173,046イベント）を Python で直接パースし、
   `"Optimizer.step#Adam.step"` という同名イベントを thread id 別に分離して集計。
4. `batch_size` を32→64にした場合のGPUメモリ余裕について検討（ユーザー報告
   「6GBのうち5.5GB消費中」という前提での評価）。
5. 対策として提案した勾配累積（gradient accumulation）のデメリットを洗い出し。
6. 「訓練データ数38,716件」という数字が指す対象（バッチ数 vs 実サンプル数）を確認・訂正。
7. 同日作成済みの既存レポート [`baseline_training_resource_analysis.md`](../baseline_training_resource_analysis.md)
   の実測値との整合性を確認。
8. 「GPUメモリ6GBのうち5.5GB消費中」という報告の実体をタスクマネージャーで調査
   （`nvidia-smi` はWDDM環境でプロセス名が `N/A` になったため、タスクマネージャーの
   「詳細」タブ／「パフォーマンス」タブに切り替えて特定）。

## 得られた事実

### A. 「Optimizer.step#Adam.step が Self CUDA 37%」は表示上のアーティファクトだった

`trace.json` を直接解析した結果、`"Optimizer.step#Adam.step"` という同名イベントが
**CPUスレッド（tid=26020, `user_annotation`）** と **GPUストリーム（tid=7, `user_annotation`）**
の両方に存在することを確認した。

- プロファイラのテーブルで「Self CUDA 136.79ms（37.34%）」と出ていた行は、GPUストリーム側に
  投影された「CPU上でこのスコープが開いていた区間の幅」をそのまま合計した値であり、
  実際のカーネル計算時間ではない。
- 20回の呼び出しのうち **初回1回だけで69.05ms（全体の50.5%）** を占めていた。これはCUDA初期化
  （cuBLAS/cuDNNハンドル生成・初回カーネルのJITロード等）の一回限りのウォームアップコストと
  ほぼ確実に判断できる。ウォームアップを除くと 136.79ms → 67.75ms（平均3.57ms/batch）。
- 子オペレータに正しく紐付けられた「本物のAdam計算」（`aten::_foreach_addcdiv_` /
  `_foreach_lerp_` / `_foreach_mul_` / `_foreach_addcmul_` / `_foreach_sqrt` / `_foreach_div_`
  の合計）は約22〜24ms（20バッチ）＝**1.2ms/batch** に過ぎない。

### B. 明確に紐づいた実コストの最大は `aten::mm`、次点は Embedding backward

| Op | Self CUDA | 割合 | 呼び出し数 |
|---|---:|---:|---:|
| `aten::mm`（+`ampere_sgemm_*`カーネル群） | 109.356ms | 29.85% | 2,160 |
| `aten::embedding_dense_backward` | 35.198ms | 9.61% | 220 |
| Adam本体（`_foreach_*`合計） | 〜24ms | 〜6.5% | 20 |

`HeteroConv` が edge_type ごとに独立した `GraphConv` を持つ設計（[model.py:99-107](../../model/baseline/model.py#L99-L107)）
のため、1バッチあたり108回程度の `mm` 呼び出しが発生している。

さらに **Self CPU time total（1.933s / 20batch ≒ 96.7ms/batch）が Self CUDA time total
（366.327ms / 20batch ≒ 18.3ms/batch）の5倍以上**あり、GPU計算そのものよりCPU側の
op dispatch（多数の小さなテンソル演算をPythonから発行するオーバーヘッド）が支配的な
可能性が高い。

### C. 既存レポートとの食い違い（解決済み: ユーザー側の誤解と確認）

同日作成済みの [`baseline_training_resource_analysis.md`](../baseline_training_resource_analysis.md)
では、既定ハイパーパラメータ（`batch_size=32, hidden_dim=64, num_layers=2, hops=2, 近傍10`）での
学習中GPUメモリ使用量を実測しており、以下の通り**非常に小さい**：

| 指標 | 実測値 |
|---|---:|
| `torch.cuda.max_memory_allocated` | 25.0 MB |
| `torch.cuda.max_memory_reserved` | 30.0 MB |
| `nvidia-smi` 実測（CUDAコンテキスト込み） | 141 MiB / 6,144 MiB |

一方、本セッション中にユーザーから「GPUメモリ6GBのうち現時点で5.5GBほど消費」という報告が
あった。この2つの数値の食い違いをタスクマネージャーで調査した結果、以下が判明した。

- タスクマネージャー「詳細」タブでGPU専用メモリの多い順にソートしたところ、`python.exe`
  （直前の学習プロセスの残骸）の専用GPUメモリは **146,136 KB（約146MB）** であり、既存
  レポートの実測値（141MiB）とほぼ一致した。**`train.py` 自体は5.5GBの原因ではない**ことが
  確定した。
- 「5.5GB消費中」という認識は、タスクマネージャーの「GPUエンジン」列で **「3D」の使用率が
  85〜88%で高止まりしていたこと**を、GPUメモリの大量消費と誤って結び付けたことが原因だった
  （ユーザー本人が事後に報告・確認）。
- この2つは本来無関係な指標である: 「3D」使用率（%）はそのエンジンにGPU側の作業（カーネル
  実行）が入っていた時間の割合であり、専用GPUメモリ（MB/GB）はVRAM上の確保量。小さな
  データを高頻度に処理し続けている場合、メモリはほぼゼロでも使用率だけ高く出ることがある。
- 実際、この高使用率・低メモリという組み合わせは、A・B節で判明した「1バッチあたり `mm` が
  108回、`embedding_dense_backward` が11回、Adamのforeach系カーネルが6種類など、小さな
  カーネルを高頻度に発行し続けている」という構造と整合的であり、「小さなカーネルの発行
  頻度がボトルネック」という結論を補強する追加の観測事実として扱える。

**結論**: GPUメモリの余裕についての懸念は解消された。`batch_size` を32→64に上げても
メモリ面のリスクは実質ないと判断できる（ただし本セッションでは実際の変更・実測は
見送り、方針として記録するのみに留めた）。

### D. 「訓練データ数38,716件」はバッチ数であり、実サンプル数ではない

`NeighborLoader` の `len(loader)` は `ceil(input_nodes数 / batch_size)` を返す。ユーザーが
`len(loader)` から取得した「38,716」（前回計測では「38,706」）は `batch_size=32` 時点での
**バッチ数/epoch** であり、実際の訓練サンプル数ではない。

既存レポートの実測によると、実際の訓練サンプル数（`is_target` かつ `y_valid` な
(銘柄,週) の件数）は：

| split | サンプル数 | `batch_size=32`時のバッチ数 |
|---|---:|---:|
| train | 1,238,577 | 38,706 |
| val | 273,868 | 8,558 |
| test | 205,956 | 6,436 |

見た目の「38,716」の**約32倍**が実際のサンプル数である。

### E. 勾配累積（gradient accumulation）は今回の主要ボトルネックには効かない（前回提案の訂正）

`batch_size` を上げる代わりにメモリを増やさず勾配累積を使う案を提案したが、これは
`optimizer.step()`/`zero_grad()` の呼び出し頻度だけを下げる手法であり、以下は変わらない：

- `NeighborLoader` のバッチ構築回数（既存レポートで判明している最大のボトルネック）
- forward/backward の呼び出し回数（`aten::mm` 29.85%、`embedding_dense_backward` 9.61% など）

本物のAdam計算コストは1.2ms/batch程度しかないため、勾配累積で得られる高速化効果は小さく、
`batch_size` そのものを増やして `NeighborLoader` の反復回数を減らす効果とは別物である。
実装上も損失・勾配のスケーリングを正しく行う必要があり、バグ混入リスクがある。

### F. 訓練データ量そのものについて（一般論）

- 週次パネルデータは同週内の銘柄間相関・同一銘柄の時系列自己相関を持つため、見た目の件数
  （約124万件）ほどの独立した情報量はない。
- 長期間（東証・大証統合 2013/07/16 を含む）のデータを均等に扱うと、レジーム変化により
  古いデータが現在の関係性を歪める可能性がある。
- 「データが多すぎて精度が落ちる」という直接的な懸念は一般には薄いが、計算コスト・
  レジームの観点では開発中は期間を絞る判断に合理性がある。

## 今後の方針

1. **［解決済み］** GPUメモリ5.5GBの謎はC節の通り解決済み（`train.py` 自体は原因ではなく、
   タスクマネージャーの「3D」使用率とメモリ消費の混同だった）。追加調査は不要。
2. `NeighborLoader` のサンプリングコスト削減が引き続き最優先課題（既存レポートで判明済み）。
   `num_workers`（既定2、実測2.5倍高速化）は導入済みなので、次は `num_hops` / 
   `num_neighbors_per_hop` の削減、`batch_size` 引き上げ（`NeighborLoader` の反復回数削減）
   を試す。
3. `batch_size=64`（または48など段階的に）を実際に試し、`ms/batch`・epoch時間・GPU/CPU
   メモリを実測する（メモリ面のリスクは解消済みだが、本セッションでは変更・実測は
   見送った。次回着手する）。
4. 開発イテレーションを速くするため、直近の一部期間に絞ったサブサンプルでの
   ハイパーパラメータ探索を導入する（本番学習ではフル期間を使用する）。
5. `torch.profiler` を再度使う場合は、初回バッチ（CUDAウォームアップ）を除外して集計する
   （`torch.profiler.schedule(wait=1, warmup=1, active=N)` 等の利用、または単純に1回目を無視）。
6. `aten::mm`（29.85%）がGPU計算の中で最大の実コストであることが判明したため、
   `HeteroConv` が edge_type ごとに個別の `GraphConv` を持つ設計による `mm` 呼び出し数の削減
   （共有可能な変換の統合など）を将来的な最適化候補として検討する。
7. Adamの `fused=True` は試す価値はあるが、真因（CPU側dispatch/`NeighborLoader` オーバーヘッド）
   への効果は限定的と予想されるため優先度は低い。
