import firebase_admin
from firebase_admin import credentials, db
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time
from googleapiclient.errors import HttpError

# Firebase アプリ初期化
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase-service-account.json')
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://test-51ebc-default-rtdb.firebaseio.com/'
    })

# データ取得
data = db.reference().get()
print(data)

# Google Sheets APIのサービス初期化
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service-account.json'

# サービスアカウントから資格情報取得
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# Google SheetsとDriveのサービスを作成
sheets_service = build('sheets', 'v4', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

def create_spreadsheet():
    # スプレッドシートを作成
    spreadsheet = {
        'properties': {'title': 'New Spreadsheet'}
    }
    spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
    sheet_id = spreadsheet.get('spreadsheetId')
    print(f'Spreadsheet ID: {sheet_id}')

    # データをスプレッドシートに追加
    values = []
    # ヘッダー行を追加
    headers = ['student_id']
    values.append(headers)

    # データ行を追加
    for student_id, student_data in data['Students'].items():
        row = [student_id]
        for i in range(1, 11):  # 1から10までのセッションをチェック
            start_key = f'start{i}'
            finish_key = f'finish{i}'
            start_value = student_data.get(start_key)
            finish_value = student_data.get(finish_key)

            if start_value:
                if len(values[0]) < len(row) + 1:
                    headers.append(start_key)
                row.append(start_value)
            if finish_value:
                if len(values[0]) < len(row) + 1:
                    headers.append(finish_key)
                row.append(finish_value)

        if len(row) > 1:  # 学生ID以外のデータがある場合のみ追加
            values.append(row)

    # ヘッダーの更新
    values[0] = headers

    body = {'values': values}
    sheets_service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range='Sheet1!A1',
        valueInputOption='RAW',
        body=body
    ).execute()

    # Google Driveでの共有設定 with exponential backoff
    permission = {
        'type': 'user',
        'role': 'reader',
        'emailAddress': 'e19139@denki.numazu-ct.ac.jp'
    }

    retries = 0
    max_retries = 3
    wait_time = 1

    while retries < max_retries:
        try:
            drive_service.permissions().create(fileId=sheet_id, body=permission).execute()
            print(f'Spreadsheet shared with e19139@denki.numazu-ct.ac.jp with ID: {sheet_id}')
            break
        except HttpError as error:
            if error.resp.status == 403 and "sharingRateLimitExceeded" in str(error):
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                wait_time *= 2
                retries += 1
            else:
                raise
    else:
        print("Failed to share spreadsheet after multiple retries.")

# スプレッドシートを作成して共有
create_spreadsheet()
