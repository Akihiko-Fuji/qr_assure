#!/usr/bin/python3
# -*- coding: utf-8 -*-

###########################################################################
# Filename      :qr_assure.py
# Description   :QR-Assure (Quality Relationship Assurance )
# Author        :Akihiko Fujita
# Update        :2025/3/24
Version =       "0.9.1"
# A professional QR code matching system for manufacturing processes.
# Ensures accurate pairing between production instructions and product manuals.
############################################################################

import time
import configparser
import csv
import os
import glob
import serial

# Config読み込み
config = configparser.ConfigParser()
config.read('config.ini')

# GPIOポートの指定:設定ファイル
QR_TIMEOUT    = int(config['Settings']['qr_timeout'])
GREEN_LED_PIN = int(config['Settings']['green_led_pin'])
RED_LED_PIN   = int(config['Settings']['red_led_pin'])
BUZZER_PIN    = int(config['Settings']['buzzer_pin'])

# LEDをの点灯点滅条件:設定ファイル　秒→ミリ秒変換が入る
LED_BLINK_INTERVAL   = int(config['Settings']['led_blink_interval'])   / 1000.0
SUCCESS_LED_DURATION = int(config['Settings']['success_led_duration']) / 1000.0
ERROR_BEEP_DURATION  = int(config['Settings']['error_beep_duration'])  / 1000.0
ERROR_BEEP_INTERVAL  = int(config['Settings']['error_beep_interval'])  / 1000.0

# シリアル通信条件の指定:設定ファイル
SERIAL_PORT          = config['Settings']['port']
BAUDRATE             = int(config['Settings']['baudrate'])
BYTESIZE             = int(config['Settings']['bytesize'])
PARITY               = config['Settings']['parity']
STOPBITS             = int(config['Settings']['stopbits'])
TIMEOUT              = int(config['Settings']['timeout'])
WRITE_TIMEOUT        = float(config['Settings']['write_timeout'])      # WRITE_TIMEOUT は float で扱う
INTER_BYTE_TIMEOUT   = float(config['Settings']['inter_byte_timeout'])

# QRコード読取位置の指定:設定ファイル
MANUAL_QR_LENGTH      = int(config['Settings']['manual_qr_length'])
MANUAL_QR_DATA_LENGTH = int(config['Settings']['manual_qr_data_length'])
PROCESS_QR_LENGTH     = int(config['Settings']['process_qr_length'])
PROCESS_QR_CANDIDATES = [
    (int(r.split(":")[0]), int(r.split(":")[1]))
    for r in config['Settings']['process_qr_candidates'].split(',')
]
PROCESS_QR_SEISAKUSHO_CODE_START = int(config['Settings']['process_qr_SEISAKUSHO_CODE_start'])
PROCESS_QR_SEISAKUSHO_CODE_END   = int(config['Settings']['process_qr_SEISAKUSHO_CODE_end'])
PROCESS_QR_ORDER_NO_START        = int(config['Settings']['process_qr_order_no_start'])
PROCESS_QR_ORDER_NO_END          = int(config['Settings']['process_qr_order_no_end'])
PROCESS_QR_SSTEHAI_NO_START      = int(config['Settings']['process_qr_SSTEHAI_NO_start'])
PROCESS_QR_SSTEHAI_NO_END        = int(config['Settings']['process_qr_SSTEHAI_NO_end'])

# 端末IDなどの指定:設定ファイル
TANMATSU_ID          = config['Settings']['tanmatsu_ID']
LOG_DIR              = 'log'

# GPIOが無い環境のためのモックGPIOクラス
class MockGPIO:
    OUT = True
    IN = False

    @staticmethod
    def setup(pin, state):
        print(f"GPIO setup: Pin {pin}, State {state}")

    @staticmethod
    def output(pin, state):
        print(f"GPIO output: Pin {pin}, State {state}")

    @staticmethod
    def cleanup():
        print("GPIO cleanup")

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO = MockGPIO
    GPIO_AVAILABLE = False

# GPIOを利用したハードウェア制御
def setup_hardware():
    # ハードウェアのセットアップ
    GPIO.setup(GREEN_LED_PIN,   GPIO.OUT)
    GPIO.setup(RED_LED_PIN,     GPIO.OUT)
    GPIO.setup(BUZZER_PIN,      GPIO.OUT)

def activate_success():
    # 照合が一致時のLED動作
    GPIO.output(GREEN_LED_PIN,  True)
    GPIO.output(BUZZER_PIN,     True)
    time.sleep(SUCCESS_LED_DURATION)
    GPIO.output(GREEN_LED_PIN,  False)
    GPIO.output(BUZZER_PIN,     False)

def activate_error():
    # 照合が不一致時のLED動作、同じデータ型のQRコードを読み込んだ際のLED動作
    GPIO.output(RED_LED_PIN,    True)
    for _ in range(3):
        GPIO.output(BUZZER_PIN, True)
        time.sleep(ERROR_BEEP_DURATION)
        GPIO.output(BUZZER_PIN, False)
        time.sleep(ERROR_BEEP_INTERVAL)
    GPIO.output(RED_LED_PIN,    False)

def cleanup_gpio():
    # GPIOのクリーンアップ
    GPIO.cleanup()

def blink_leds():
    # 1個目のQRコードを読み待機時のLED動作
    GPIO.output(GREEN_LED_PIN,  True)
    GPIO.output(RED_LED_PIN,    False)
    time.sleep(LED_BLINK_INTERVAL)
    GPIO.output(GREEN_LED_PIN,  False)
    GPIO.output(RED_LED_PIN,    True)
    time.sleep(LED_BLINK_INTERVAL)

# QRコード処理
def check_qr_codes(qr1_data, qr2_data_candidates):
    # QRコードの照合
    return any(qr1_data == candidate for candidate in qr2_data_candidates)

def extract_data_from_manual_qr(qr1_code):
    # 取説中QRコードからデータを抽出
    if len(qr1_code) != MANUAL_QR_LENGTH or not qr1_code.isdigit():
        raise ValueError("Invalid Torisetsu QR code format")
    return qr1_code[:MANUAL_QR_DATA_LENGTH]

def extract_data_from_process_qr(qr2_code):
    # 加工指示書QRコードからデータを抽出
    if len(qr2_code) != PROCESS_QR_LENGTH:
        raise ValueError("Invalid Kakoshiji QR code format")
    candidates      = [qr2_code[start:end] for start, end in PROCESS_QR_CANDIDATES]             # 加工指示書QRコード参照位置、複数指定可能
    seisakusho_code = qr2_code[PROCESS_QR_SEISAKUSHO_CODE_START:PROCESS_QR_SEISAKUSHO_CODE_END] # 製作所コード
    order_no        = qr2_code[PROCESS_QR_ORDER_NO_START:PROCESS_QR_ORDER_NO_END]               # 受注No
    sstehai_no      = qr2_code[PROCESS_QR_SSTEHAI_NO_START:PROCESS_QR_SSTEHAI_NO_END]           # 生産手配No
    return candidates, seisakusho_code, order_no, sstehai_no

# シリアル通信
def setup_serial():
    # シリアルポートのセットアップ
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=TIMEOUT,
            write_timeout=WRITE_TIMEOUT,
            inter_byte_timeout=INTER_BYTE_TIMEOUT
        )
        return ser
    except serial.SerialException as e:
        # シリアルポートの設定中にエラーが発生しました: 
        # (linux terminal環境では日本語メッセージが通らないので英文対応)
        print(f"An error occurred while configuring the serial port: {e}")
        return None

def read_qr_code(ser):
    # QRコードの読み込み
    try:
        qr_code = ser.readline().decode('shift_jis').strip()
        return qr_code
    except serial.SerialException as e:
        # シリアルポート読込み中にエラーが発生しました:
        # (linux terminal環境では日本語メッセージが通らないので英文対応)
        print(f"Error while reading serial port: {e}")
        return None

# ログ機能
def log_match_result(timestamp, seisakusho_code, tanmatsu_id, order_no, sstehai_no, result):
    # 照合結果のログを記録
    try:
        # LOG_DIR ディレクトリを作成。ディレクトリが既に存在する場合は何もしない
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError as e:
        # ディレクトリ作成中にエラーが発生した場合、エラーメッセージを表示して終了する
        print(f"Error creating log directory {LOG_DIR}: {e}")
        return

    # ログファイルパスを生成。'YYYYMM.csv'形式で生成する(日別から月別に変更,日別にしたければ%dをファイル名に追加してください)
    log_file = os.path.join(LOG_DIR, time.strftime('%Y%m') + '.csv')

    try:
        # CSVファイルを追記モードで開き、UTF-8エンコーディングで書き込みを行う
        with open(log_file, 'a', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            # タイムスタンプ、製作所コード、端末ID、受注No、生産手配No、照合結果をログに記録する
            csv_writer.writerow([timestamp, seisakusho_code, tanmatsu_id, order_no, sstehai_no, result])
    except IOError as e:
        # ログファイルの書き込み中にエラーが発生した場合、エラーメッセージを表示して終了する
        print(f"Error writing to log file {log_file}: {e}")
        return

    try:
        # LOG_DIR 内の全てのCSVファイルを取得し、作成日時順にソートする
        log_files = sorted(glob.glob(os.path.join(LOG_DIR, '*.csv')), key=os.path.getmtime)
        if len(log_files) > 12:
            # もしログファイルが12以上ある場合、最も古いログファイルを削除する
            os.remove(log_files[0])
    except Exception as e:
        # ログファイルの管理中にエラーが発生した場合、エラーメッセージを表示する
        print(f"Error managing log files in directory {LOG_DIR}: {e}")
        return

# メインルーチン
def main():
    ser = setup_serial()
    if not ser:
        # シリアルポートが設定できませんでした。プログラムを終了します
        # (linux terminal環境では日本語メッセージが通らないので英文対応)
        print("Serial port could not be configured. Exit the program.")
        return

    setup_hardware()

    state = 'WAITING_FIRST_QR'  # 最初のQRコードを待機
    first_qr_data = None        # 最初のQRコードデータを保持する変数
    first_qr_type = None        # 最初のQRコードの種類を保持する変数

    while True:
        # 1つ目のQRコードを読み取る際の処理
        if state == 'WAITING_FIRST_QR':
            qr_code = read_qr_code(ser)                               # シリアルポートからQRコード読み取り
            if len(qr_code) == 11:
                first_qr_data = extract_data_from_manual_qr(qr_code)  # 桁数を判定し取扱説明書QRコードからデータ抽出
                first_qr_type = 'manual'
                state = 'WAITING_SECOND_QR'                           # 次のQRコードを待機状態に変更
                start_time = time.time()
            elif len(qr_code) == 300:
                first_qr_data, seisakusho_code, order_no, sstehai_no = extract_data_from_process_qr(qr_code)
                                                                      # 桁数を判定し加工指示書QRコードからデータ抽出
                first_qr_type = 'process'
                state = 'WAITING_SECOND_QR'                           # 次のQRコードを待機状態に変更
                start_time = time.time()

        # 2つ目のQRコードを読み取る際の処理
        elif state == 'WAITING_SECOND_QR':
            if time.time() - start_time > QR_TIMEOUT:                 # QRコード読取りのタイムアウト:設定ファイル
                state = 'WAITING_FIRST_QR'
                continue
            blink_leds()                                              # LEDの点滅動作
            qr_code = read_qr_code(ser)                               # シリアルポートからQRコード読み取り

            if len(qr_code) == 11:
                second_qr_data = extract_data_from_manual_qr(qr_code) # 桁数を判定し取扱説明書QRコードからデータ抽出
                if first_qr_type == 'manual':
                    activate_error()                                  # 二回目も取扱説明書QRコードだった場合エラービープを鳴らす。ログは残さない
                else:
                  # 加工指示書QRとの照合チェック
                    match_found = check_qr_codes(second_qr_data, first_qr_data)
                    timestamp = time.strftime('%Y/%m/%d %H:%M:%S')
                    if match_found:
                        activate_success()                            # 照合が一致した場合
                        log_match_result(timestamp, seisakusho_code, TANMATSU_ID, order_no, sstehai_no, '一致')
                    else:
                        activate_error()                              # 照合が不一致だった場合
                        log_match_result(timestamp, seisakusho_code, TANMATSU_ID, order_no, sstehai_no, '不一致')
                state = 'WAITING_FIRST_QR'

            elif len(qr_code) == 300:
                second_qr_data, seisakusho_code, order_no, sstehai_no = extract_data_from_process_qr(qr_code)
                                                                      # 桁数を判定し加工指示書QRコードからデータ抽出
                if first_qr_type == 'process':
                    activate_error()                                  # 二回目も加工指示書QRコードだった場合エラービープを鳴らす。ログは残さない
                else:
                  # 取扱説明書QRとの照合チェック
                    match_found = check_qr_codes(first_qr_data, second_qr_data)
                    timestamp = time.strftime('%Y/%m/%d %H:%M:%S')
                    if match_found:
                        activate_success()                            # 照合が一致した場合
                        log_match_result(timestamp, seisakusho_code, TANMATSU_ID, order_no, sstehai_no, '一致')
                    else:
                        activate_error()                              # 照合が不一致だった場合
                        log_match_result(timestamp, seisakusho_code, TANMATSU_ID, order_no, sstehai_no, '不一致')
                state = 'WAITING_FIRST_QR'

            else:
              # 不明なQRコードの場合
                timestamp = time.strftime('%Y/%m/%d %H:%M:%S')
                log_match_result(timestamp, 'N/A', TANMATSU_ID, 'N/A', 'N/A', qr_code)
                state = 'WAITING_FIRST_QR'

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        cleanup_gpio()
