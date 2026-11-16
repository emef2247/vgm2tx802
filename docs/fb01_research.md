# FB-01対応に向けた仕様調査

調査日:2026-11-16。今回は仕様と検証順序の整理。FB-01用の本番変換や音色探索は未実装。
既存TX802出力は変更しない。

## 構成とデータの境界

目標は、IKAOPLL-verilator-devが出すOPLLの音を参照し、FB-01用の4オペレータ音色を探索すること。
OPLLの音色表を抽出したり、TX802用の6オペレータCSVをそのまま読み替える経路にはしない。

```text
入力VGM -> NativePerformance -> FB-01向け演奏・割当
                                  |
探索したFB-01用CSV -> 64byte音色 -> SysEx / 演奏MIDI
                         |
                  明示したレジスタ変換 -> OPPレンダ -> 参照音との比較
```

次の3つの順序を別々に定義する。

1. 音色データ上のoperator blockの並び。
2. アルゴリズム図・変換プログラム内のoperator識別名。
3. YM2164のレジスタアドレスとスロット。

FB-01は8音・8instrument、4operator・8algorithm。音色メモリは48音色×7bankで、
RAMが2bank、ROMが5bank。wire番号はbank0–6、voice0–47、instrument0–7。
画面上の番号との変換は境界で明示する。音色と、受信ch・発音数などのconfigurationは別。
[Yamaha Owner's Manual、printed pp.1,6,47–57](https://www.opl3.com/wp-content/uploads/2018/11/FB01E.pdf)

## SysExの基本

以下は全て16進数。`s`はsystem channelの0–15、`i`はinstrumentの0–7。

| 用途 | 構造 |
| --- | --- |
| instrument音色の要求 | `F0 43 75 s (28+i) 00 00 F7` |
| instrument音色のダンプ | `F0 43 75 s (08+i) 00 00` + packet + `F7` |
| 音色parameter変更 | `F0 43 75 s (18+i) p low high F7` |
| bank要求 | `F0 43 75 s 20 00 bank F7` |
| bankダンプ | `F0 43 75 s 00 00 bank` + packets + `F7` |

音色parameter番号`p`は音色内offset+40。configurationの変更は別の1byteデータ形式。
要求の`28+i`とダンプの`08+i`は役割の違いであり、同じcommandではない。
Owner's Manual printed p.57とService Manual PDF p.16の図を照合した。

1音色の転送先は指定instrumentの**voice buffer**で、永続bankへの保存ではない。
bank保存は別の操作として扱う。ROM bankを読み出せることは書き込めることを意味せず、
Service ManualにはROM領域への保存やmemory protectによるcancelも記載されている。

音色の各8bit値を**下位nibble、上位nibble**の順に送る。
packetは`count-high count-low encoded-data checksum`。
countはnibble展開後の送信データ数、checksumはそのデータだけの和に対する
`(-sum(data)) & 7F`。header/countはchecksumに含めない。

- 1音色64byte ->128nibble、count=`01 00`、全体139byte。
- 例:値`AB` ->`0B 0A`。他が0の64byteテストデータならchecksum=`6B`。
- Owner's Manualのbank形式は32byteのbank先頭情報と48音色の49packet。
  その区切り方なら拡張形式は6363byte。TX802の32音色4104byte形式とは別。
- Service Manualには大きなchunkで分割する記述もある。受信parserは6363byte固定長だけで判定しない。
- 分割bulkのpacket間には100msを超える間隔を設ける記述がある。送信側のペーシングも必要。

既存SMF encoderは完全な`F0...F7`メッセージを前提としている。
1つのbank SysEx内部のpacket間隔を保存するなら、SMF continuationへの対応か、
bank転送を演奏MIDIと分けた送信手順が必要。最初は単音色bufferの139byte形式を検証する。
[Yamaha Service Manual、PDF pp.15–16,20](https://www.synfo.nl/servicemanuals/Yamaha/YAMAHA_FB-01_SERVICE_MANUAL.pdf)

## 音色データとレジスタへの対応

64byteの音色は、name/user code、LFO/algorithm等、4個の8byte operator block、
voice function/reserved領域に分かれる。operator block先頭offsetは`10,18,20,28`。

operator内の要点を以下に記す。これはレジスタへのmemcpyの仕様ではない。

| 相対offset | 保持するフィールド |
| --- | --- |
| 0 | TL、7bit、0が最大音量 |
| 1 | level scaling typeの一部、TL velocity sensitivity |
| 2 | level scaling depth、TL adjust |
| 3 | scaling typeの残り、DT1、MUL |
| 4 | rate scaling、AR |
| 5 | modulator/carrier flag、AR velocity sensitivity、D1R |
| 6 | DT2、D2R |
| 7 | SL、RR |

特にoffset5は、FB-01ではcarrier/modulator関連のflagとvelocity項目を含む。
OPMのAM-enable/D1R byteとして機械的にコピーしない。アルゴリズムによる接続、
FB-01側のflag処理、chip側のAM動作を分けて確認する。
また音色offset0Cの出力enableはFB-01では無視するとService Manualにあり、
実際のlevel/pan設定はinstrument側を別に持つ。

FB-01の番号と、他のeditorのOP1–OP4表記を同一視しない。
DXconvert3.2.4の作者実装`vopm.py`では、次の対応でFB-01音色をVOPMへ変換している。

| FB-01 block offset | この変換での名前 | OPM register offset/ch |
| --- | --- | --- |
| 10 | M1 | 00 |
| 18 | C1 | 10 |
| 20 | M2 | 08 |
| 28 | C2 | 18 |

従ってこの表現では、音色順`M1,C1,M2,C2`に対しレジスタ順は`M1,M2,C1,C2`。
変換表は実装の照合結果であり、FB-01実機で検証済みという意味ではない。
M/Cの識別名だけから全algorithmの実際のcarrierを決めない。
ALG7で1operatorずつ、それから2operatorの接続を鳴らして、この対応を検証する。
[DXconvert作者配布元](https://www.martintarenskeen.nl/dxconvert/index.html)、
[ymfmのoperator mapping](https://github.com/aaronsgiles/ymfm/blob/main/src/ymfm_opm.cpp)

## OPPとOPM

Nuked-OPMのYM2164分岐を調べると、基本のoperator register群は共通する一方、
次の差が実装されている。これはYamahaが公開した完全なOPP仕様表とは区別する。

| 項目 | YM2151 / OPM | YM2164 / OPP |
| --- | --- | --- |
| TEST/LFO reset関連address | 01 | 09 |
| Timer B | 基準周期 | 同clockなら周期2倍 |
| 00–07 | 通常の音色設定には使わない | channel別TL ramp divisor |
| TL bit7 | 通常TLでは使わない | TL rampの制御に使用 |
| TL変化 | 通常のTL更新 | ramp有効時に内部で段階的に更新 |

KC/KF、DT1/MUL、KS/AR、DT2/D2R等の基本addressの共通性と、FB-01音色の並べ替えは
別の話になる。OPP固有の書込みpipeline、TL ramp、TEST/Timer差を無視したOPM再生を、
FB-01の最終的な音の証明には使わない。
[Nuked-OPM、確認したrevision f209e6ed3712032b641d53ce8fb24824eae6adc3](https://github.com/nukeykt/Nuked-OPM/blob/f209e6ed3712032b641d53ce8fb24824eae6adc3/opm.c)

FB-01用のclockも独立して持つ。MAMEのFB-01 machine構成はOPPを4MHzで動かしている。
OPLL側のclockを流用すると、pitchだけでなくEG/LFO/rampの比較条件も変わる。
[MAME FB-01 machine構成](https://github.com/mamedev/mame/blob/master/src/mame/yamaha/fb01.cpp)

オーナーから、用途分離・転用防止を意図した設計変更という背景の説明がある。
今回の資料では、その動機を示すYamahaの一次記述までは確認していない。
実装の対応表は、設計意図の推測ではなく、上記のfield/addressと発音検証で確定させる。

## 音合わせを始めるための手順

1. FB-01専用CSV/schema、nibble/packet codec、64byteとの往復確認を作る。
   TX802のserializer/level lawを流用する前に、FB-01側の意味を確認する。
2. OPP対応の外部rendererを固定revisionで準備する。Nuked-OPMのOPP modeを第一候補とし、
   SysEx解釈・FB-01のlevel/velocity/割当処理と、chip単体の音生成を分ける。
3. 単carrier・operator接続・pitch・TL/velocity・LFO・TL rampを順に検証する。
   MIDI受理、parameter往復、chip音、FB-01実機の一致を別の証拠として残す。
4. IKAOPLL-verilator-devの出力を参照音にして、まず15メロディ、その後リズムを探索する。
   複数音高・音量・gateの別条件を予約し、tail/partialを含めて比較する。

参照側の指定checkoutは`../IKAOPLL-verilator-dev`、調査時HEADは`8a7467b`。
そのworking treeに既存変更4件があり、`build/obj_dir/ikaopll_sim`と`rtl/`は未配置だった。
今回は変更・buildを行っていない。音合わせ開始時にはcheckout/RTL/hash/clock/gainを記録し、
従来の別checkoutの結果と混同しない。

ターゲット側の候補として[FB-02](https://fullbucket.de/music/fb02.html)もある。
作者がFB-01音生成のsimulation、SysEx import/exportを提供しているが、
追加波形等の拡張を持つ。使用するならFB-01相当の条件を固定し、実機同等と自動認定しない。
現在のIKAOPM-verilator-devはREADMEでYM2164入力を拒否すると明記しており、
現状のままOPP rendererとして扱わない。

未確定:FB-01 firmwareによるTL adjust/velocity/scalingの正確な変換、共有LFOの扱い、
carrier/modulator flagの動作、feedback上限表記の差、実機でのpacketペーシングとACK。
本調査の算術確認は139/6363byteと256値nibble往復までで、実機送信や音声検証は未実施。

今後のCSVは、FB-01のblock番号・bit fieldと、bank/voiceの人間向け番号を明示する案。
`OP1`だけで異なるeditorの番号を兼用しない。送信時の0-based番号への変換も別にする。
Service Manualの説明文にはbank1–7も現れるが、wireはOwner's Manual p.55の0–6を採る。
今回まだ新しいschema/APIやexportコマンドを確定・実装したわけではない。
