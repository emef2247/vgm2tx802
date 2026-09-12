# Domino 音源定義ファイル仕様（概要まとめ）
**Source:** [https://hans5958.github.io/Domino-English-Translation/jp/module.html](https://hans5958.github.io/Domino-English-Translation/jp/module.html)

## 音源定義ファイルとは
Domino が外部音源を扱う際に、  
**音源固有の情報（パラメータ、コントロールチェンジ、プログラムリストなど）を定義する XML ファイル**。

これにより Domino は：

- 音源のパラメータを正しく表示  
- コントロールチェンジを意味のある項目として扱う  
- 音色名やバンク情報を正しく解釈  
- モジュール処理（復元など）を音源仕様に合わせて行う  

といった動作が可能になる。

---

## 音源定義ファイルの構造
音源定義ファイルは XML 形式で構成され、  
主に以下の要素を含む。

### ● `Module`
音源定義の最上位要素。  
音源名やバージョンなどのメタ情報を持つ。

### ● `ControlChangeMacro`
コントロールチェンジを「意味のあるパラメータ」として扱うための辞書。

例：

- CC1 → Modulation  
- CC7 → Volume  
- CC10 → Pan  
- CC11 → Expression  
- CC64 → Sustain  
- CC32 → Bank Select LSB（TX802 で重要）

Domino の「復元」機能は、このマクロを使って音源状態を再構築する。

### ● `ProgramList`
音源の音色リスト。  
バンクやプログラム番号と音色名を対応付ける。

TX802 の場合：

- Bank A / Bank B  
- 1〜64 のプリセット  
- Performance と Voice の区別

などをここで定義する。

### ● `Parameter`
音源の編集可能なパラメータを定義する。

例：

- EG  
- Pitch  
- LFO  
- Operator  
- Algorithm  
- Output Level  
- Detune  
- Frequency Ratio  

Domino の音色編集画面で表示される内容はここから生成される。

---

## Control Change Macro の役割
ページ内で特に重要な項目。

- CC をただの数値ではなく「意味のある音源パラメータ」として扱う  
- Domino の復元機能がこの辞書を使って音源状態を再構築する  
- Bank Select、Volume、Pan、Modulation などの初期化に必須  
- TX802 のような特殊音源では、正しいマクロ定義が演奏品質に直結する

---

## 音源定義ファイルの目的
- 音源固有の仕様を Domino に伝える  
- コントロールチェンジの意味付け  
- 音色名の表示  
- バンク構造の定義  
- パラメータ編集画面の生成  
- モジュール処理（復元など）の正しい動作

---

## 音源定義ファイルを使うメリット
- 音源の挙動が Domino と完全同期  
- CC の意味が正しく解釈される  
- 音色名が正しく表示される  
- バンク切替が正しく行われる  
- モジュール処理が音源仕様に合わせて動作  
- 演奏の安定性が向上する（TX802 で顕著）

---

# まとめ
このページは Domino の **音源定義ファイル（XML）仕様**を説明しており、  
特に **Control Change Macro** が音源状態の復元に重要であることが記載されている。


