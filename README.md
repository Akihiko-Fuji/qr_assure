# qr_assure

# QRコード照合プログラム

このプログラムは、QRコードを読み取り、それぞれのQRコードを照合し、結果をログに記録するシステムです。
ドキュメントは日本語しかありません。

## 機能

このプログラムは以下の機能を持っています：

1. それぞれが桁数の異なるQRコードに対して、どちらにも含まれる値を部分一致として読み取る。
2. 読み取ったQRコードのデータを抽出する。
3. 照合結果に基づいて一致、不一致の結果をLEDとブザーで通知する。
4. 照合結果をログファイル（CSV形式）に記録する。

## 動作環境

- Python 3.x
- `config.ini`ファイルで各種設定を指定します。

## インストール

このプログラムを動作させるために、下記の手順に従ってください：

1. リポジトリをクローンまたはダウンロードします。
    ```shell
    git clone https://github.com/Akihiko-Fuji/qr_assure.git
    cd your-repository-directory
    ```

2. 必要なPythonパッケージをインストールします。
    ```shell
    pip install pyserial
    ```

3. `config.ini`ファイルを設定します。以下は`config.ini`の例です：
    ```ini
    [Settings]
    port = /dev/ttyUSB0
    baudrate=9600
    bytesize=8
    parity=N
    stopbits=1
    timeout=1
    write_timeout=0
    inter_byte_timeout=0.5
    tanmatsu_ID = TERM001
    green_led_pin =  5
    red_led_pin   =  6
    buzzer_pin    = 13
    led_blink_interval   =  500
    success_led_duration = 2000
    error_beep_duration  =  100
    error_beep_interval  =  100
    qr_timeout = 60
    manual_qr_length = 11
    manual_qr_data_length = 8
    process_qr_length = 300
    process_qr_candidates = 199:207,219:227,239:247
    process_qr_seisakusho_code_start = 15
    process_qr_seisakusho_code_end = 20
    process_qr_order_no_start = 81
    process_qr_order_no_end = 92
    process_qr_sstehai_no_start = 0
    process_qr_sstehai_no_end = 12
    ```

## 使用方法

1. プログラムを実行します：
    ```shell
    python qr_assure.py
    ```

2. 最初のQRコードを読み取ります。デフォルトは11桁のコードと300桁のコードを使用します。読み取り条件の変更はコードを修正して下さい。
3. 2つ目のQRコードを読み取ります。プログラムは自動的に照合を行います。
4. 照合結果がLEDとブザーで通知されます。また、ログファイルに結果が記録されます。

## ファイル構成

```plaintext
.
├── config.ini         # 設定ファイル
├── main.py            # メインプログラム
├── README.md          # このファイル
└── log/               # ログファイルディレクトリ（自動的に作成されます）
```

## エラーハンドリング

シリアルポートの設定や読み込みでエラーが発生した場合は、エラーメッセージが表示され、適切に処理が終了します。
QRコードのフォーマットが無効な場合は、ValueErrorがスローされ、プログラムが停止します。

## ハードウェア

YHE12-03という 2-5Vで動作するブザーを利用しました。
```
[GPIO 13] --- [330Ω抵抗] --- +[ブザー]- --- [GND]
```
逆起電力による損傷を抑えるため、1N4148やIN4001などの汎用スイッチングダイオードをブザーと並列に接続し、保護をおこなうと安全です。
LEDは特に指定はありません。

## その他

このプログラムはRaspberry PiのGPIOを使用していますが、GPIOが使用できない環境のためのモッククラスも含まれています。GPIOが利用できない環境でも動作を確認することが可能です。

## ライセンス
Apache License 2.0にて公開します。
