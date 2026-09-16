# TX802 SysEx Knowledge（実機検証版）
Yamaha TX802 が受信できる SysEx 形式、および DX7 Single‑Voice Dump の扱いについて、  
実機検証に基づく正確な挙動をまとめる。

---

## 1. TX802 が受信できる SysEx フォーマットは 2 種類

TX802 は以下の 2 種類の SysEx を正しく受信できる。

### ① 32 ボイス一括転送（WMEM / Format 09）

```
F0 43 0n 09 20 00 [128 bytes × 32 voices] cs F7
```

- TX802 / DX7II / TX816 互換の **128 バイト × 32 ボイス**形式  
- 総サイズ：**4104 bytes**  
- **INT バンク（I01〜I64）を書き換える唯一の方法**  
- STORE 操作不要（受信した時点で書き換わる）

---

### ② DX7 Single‑Voice Bulk Dump（163 bytes / Format 00 01 1B）

Dexed が送信する形式と完全互換。

```
F0 43 0n 00 01 1B [155 bytes payload] cc F7
```

- DX7 / TX7 / TX816 互換  
- TX802 はこれを **Edit Buffer（編集中の1音色）にロードする**  
- INT バンクは書き換わらない（STORE が必要）

---

## 2. DX7 Single‑Voice Dump（163 bytes）の構造

### ヘッダ
```
F0 43 0n 00 01 1B
```

### ペイロード（155 bytes）
Dexed は **128 bytes packed → 155 bytes に展開**して送信する。  
vgm2tx802 では以下の構造で生成する：

| 範囲 | 内容 |
|------|------|
| 0–127 | TX802 packed（128 bytes） |
| 128–144 | 予約領域（0 埋め） |
| 145–154 | ボイス名（ASCII 10 bytes） |

### チェックサム
```
(-sum(payload)) & 0x7F
```

### 終端
```
F7
```

---

## 3. TX802 の DX7 Single‑Voice Dump 受信挙動（実機検証）

TX802 の挙動は **VOICE EDIT に入っているかどうか**で変わる。

---

### ● VOICE EDIT に入っている場合

例：I39 を選択 → VOICE EDIT に入る → SysEx 受信

- 受信した Single‑Voice Dump は **現在編集しているスロットの Edit Buffer にロードされる**
- 受信直後の音は「I39 の Edit Buffer 版」として鳴る
- **STORE を押すと I39 が書き換わる**

つまり：

> **DX7 Single Dump のターゲットは「VOICE EDIT で開いているスロット」。**

---

### ● VOICE EDIT に入っていない場合

例：I39 を選択 → VOVOICE EDIT に入らず SysEx 受信

- 一時的に受信した音が鳴ることがある  
- しかし **INT バンクは書き換わらない**
- 別のボイスを選択 → 再度 I39 に戻ると  
  → **受信前の音色に戻る**

つまり：

> **VOICE EDIT に入っていない状態で受信した Single Dump は  
> 永続的には保存されない（Edit Buffer の一時領域扱い）。**

---

## 4. TX802 の Edit Buffer と INT バンクの関係

TX802 には 2 種類の音色領域がある：

| 領域 | 内容 | 書き換え方法 |
|------|------|--------------|
| **Edit Buffer** | 編集中の 1 音色 | DX7 Single Dump（163 bytes） |
| **INT バンク（I01〜I64）** | 永続保存領域 | WMEM（4104 bytes）または STORE |

DX7 Single Dump は **Edit Buffer 専用**であり、  
INT バンクを直接書き換えることはできない。

---

## 5. OPLL と OPS（DX7/TX802）のオペレータ割り当ての違い

OPLL（YM2413）と OPS（DX7/TX802）はオペレータの役割が逆。

| チップ | OP1 | OP2 |
|--------|-----|-----|
| **OPLL** | Modulator | Carrier |
| **OPS（DX7/TX802）** | Carrier | Modulator |

そのため、OPLL → TX802 変換では：

- オペレータの順序を反転  
- TL / EG / KSL / MULTI などの意味も逆転  
- ALG の構造も変わる

---

## 6. vgm2tx802 が生成する SysEx の種類

| 種類 | 用途 | TX802 の挙動 |
|------|------|--------------|
| **WMEM（32 voices bulk dump）** | INT バンク書き換え | 受信時に即書き換え |
| **DX7 Single‑Voice Dump（163 bytes）** | Edit Buffer にロード | STORE で選択中のスロットに保存 |

---

## 7. 実機検証で得られた重要ポイントまとめ

- TX802 は DX7 Single Dump を **Edit Buffer にロードするだけ**  
- INT バンクを書き換えるには WMEM が必要  
- VOICE EDIT に入っているかどうかで挙動が変わる  
- 名前はペイロード末尾 10 バイトで正しく読まれる  
- OPLL → TX802 のオペレータ割り当ては逆転が必須