<p align="center">
  <img src="docs/images/Ham_Body_UV.png" alt="Hamzzi UV Toolkit" width="240">
</p>

<h1 align="center">Hamzzi UV Toolkit</h1>

<p align="center">展開済みのUVを整えるBlenderアドオン</p>

<p align="center"><a href="README.md">한국어</a> | <a href="README.en.md">English</a> | <b>日本語</b></p>

すでに展開してあるUVを手直しするためのツール集です。アイランドの整列とタイルへの配置、シームの縫い合わせ、伸びたUVのほぐし、テクセル密度の統一を、サイドバーのボタンで行えます。UVを新しく展開する機能はありません。

- Blender 4.2以降(5.2でテストしており、それより前のバージョンでは実行していません)
- 制作: StudyingHamzzi
- 詳しい使い方: [使い方ガイド](docs/GUIDE.ja.md) ([한국어](docs/GUIDE.md), [English](docs/GUIDE.en.md))

## 画面

メッシュをEdit Modeにすると、3DビューポートとUVエディターのサイドバー(Nキー)に **Hamzzi UV Toolkit** タブが現れます。

<table>
  <tr>
    <td valign="top"><img src="docs/images/sidebar.png" alt="Hamzzi UV Toolkit サイドバー" width="250"></td>
    <td valign="top"><img src="docs/images/pack.png" alt="Pack into Tile の前後" width="620"><br><sub>Pack into Tile を一度押すだけで、散らばったアイランドがタイルにまとまった様子</sub></td>
  </tr>
</table>

## 機能

| パネル | できること |
|---|---|
| Align Islands | アイランドを端や中央に揃える(基準: 選択範囲または0–1タイル) |
| Distribute / Sort | 間隔を均等に配分、3D上の位置順に一列(または一行)に並べる |
| Tile / Pack | UDIMタイルへ移動、タイルの中に行を揃えて自動配置(Margin、Scale to Fit) |
| Transform | 回転(90°、180°、任意の角度)、反転、自動の向き合わせ、選択エッジを軸に揃える、U・Vの倍率調整、UVが裏返った面を赤で表示 |
| Texel Density | 密度の計測、目標値の適用、平均への統一、アクティブな面の密度に合わせる |
| UV Vertices | 選択したUV頂点の整列と均等配分、エッジ一列をまっすぐに伸ばす(Straighten) |
| Stitch | 選択したUVエッジを隣のアイランドの同じエッジに縫い合わせる。二つのエッジの形が違っても端点を合わせて接続する。Detach Selected は逆に、選択したエッジに沿ってアイランドを切り分ける |
| Unstretch | 伸びたUVを3D表面の比率に近づけて再計算、ストレッチ表示のオン・オフ |
| Connected Edges | 選択した点・辺・面が他のアイランドのどこにつながるかを青で表示 |

## インストール

1. リポジトリの **Releases** から `HamzziUVToolkit.zip` をダウンロードします。解凍はしません。
2. Blenderで Edit → Preferences → Get Extensions を開きます。
3. 右上の矢印メニューから **Install from Disk** を選び、ダウンロードしたzipを指定します。
4. インストールが終わったら、アドオンが有効になっているか確認します。

> 緑色のCodeボタンにある Download ZIP はリポジトリ全体なので、そのままではインストールできません。アドオン本体は `HamzziUVToolkit/` フォルダーです。

<table>
  <tr>
    <td><img src="docs/images/Ham_Body_UV_UP.png" alt="UPDATE" width="130"></td>
    <td valign="middle"><b>アップデート</b>するときは、新しいzipを同じ方法でインストールします。パネルが古いままなら、Blenderを再起動してください。</td>
  </tr>
</table>

## クイックスタート

1. メッシュを選び、Tabキーで Edit Mode に入ります。
2. UVエディターを開き、Nキーでサイドバーを出して **Hamzzi UV Toolkit** タブをクリックします。
3. アイランド系のツールは選択したアイランドに、何も選んでいなければ見えているアイランド全体に適用されます。実行したツールは Ctrl+Z で取り消せます。

たとえば散らばったアイランドをまとめるには、**Tile / Pack** で U 0、V 0 を確認して **Pack into Tile** を押します。ほかのツールの使い方と作業例は [使い方ガイド](docs/GUIDE.ja.md) にまとめてあります。

## 既知の制限

- Stitch は選択したエッジにだけ働き、近くのエッジを自動で探して縫うことはありません。
- Unstretch はブラシではなく、選択範囲に一度で適用されます。
- 球のように平らに開けない形を無理に開く機能はありません。
- Pack into Tile はアイランドの境界ボックスを基準に配置し、回転はしません。複雑な形を隙間なく詰めたいときは、BlenderのPack Islandsのほうが密に配置できます。
- Connected Edges は、Edit Modeの面がFace Limit(既定は1万)を超えると表示をスキップし、UVエディターに案内を出します。
- パネルのボタン名は英語です。

## バグとお問い合わせ

質問、バグ、ほしい機能は [Issues](https://github.com/STmagi20/HamzziUVWs/issues) に書き込んでください。バグの場合は、Blenderのバージョン、どのボタンを押したか、画面に出た警告文を添えていただくと確認しやすくなります。詳しくは [使い方ガイド](docs/GUIDE.ja.md#バグとお問い合わせ) にあります。

## 開発

アドオンに使うファイルはすべて `HamzziUVToolkit/` フォルダーにあります。

| パス | 内容 |
|---|---|
| `HamzziUVToolkit/__init__.py` | 登録・解除 |
| `HamzziUVToolkit/blender_manifest.toml` | 拡張機能の情報とバージョン |
| `HamzziUVToolkit/info.py` | 名前、制作者、バージョン |
| `HamzziUVToolkit/icons.py`, `HamzziUVToolkit/images/` | パネル名の前の小さなロゴ(`logo.png`)とAboutの全身イラスト(`mascot.png`)。なくてもアドオンは動作します |
| `HamzziUVToolkit/core.py` | UVデータへのアクセス: 編集オブジェクト、選択判定、アイランド |
| `HamzziUVToolkit/properties.py` | パネルに表示される設定値 |
| `HamzziUVToolkit/operators/` | ツールごとのオペレーター(`islands`, `density`, `elements`, `stitch`, `relax`) |
| `HamzziUVToolkit/overlay.py` | UVエディターの接続エッジと裏返った面の表示 |
| `HamzziUVToolkit/ui.py` | サイドバーのパネル |
| `HamzziUVToolkit/menus.py` | UVメニューの項目と、StitchとDetachの空のショートカット枠 |
| `README.en.md`, `README.ja.md` | このREADMEの英語版と日本語版 |
| `docs/GUIDE.md`, `docs/GUIDE.en.md`, `docs/GUIDE.ja.md`, `docs/images/` | 使い方ガイドと画像(インストール用zipには含まれません) |
| `tests/` | 自動テスト(インストール用zipには含まれません) |

バージョンは `blender_manifest.toml` にだけ書きます。パネルに表示されるバージョンはこのファイルから読み込みます。

テストはバックグラウンドのBlenderで実行します。すべて通ると終了コードは0です。`--` の後にファイル名の一部(例: `orient`)を書くと、そのテストだけ実行します。

```bash
blender --background --factory-startup --python tests/run_tests.py
```

バックグラウンドにはUVエディターがないため、Relaxの実際の動作と画面表示はテストでは確認できません。この二つはUVエディターを開いたBlenderで直接確かめてください。

インストール用zipはコミットしたあと、次のコマンドで作ります。zipの最上位に `blender_manifest.toml` が来るよう、フォルダーの中身だけをまとめます。

```bash
git archive --format=zip -o HamzziUVToolkit.zip HEAD:HamzziUVToolkit
```

## ライセンス

GPL-3.0-or-later。全文は [LICENSE](LICENSE) にあります。

Copyright (C) 2026 StudyingHamzzi
