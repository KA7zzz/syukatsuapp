from flask import Flask, render_template, request, redirect, url_for, session
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' # ★ここを任意の文字列に変更してください。前回と同じものにしてください。

USERS = {
    "user1": "pass1",
    "admin": "adminpass"
}

# --- データファイルのパス設定と操作関数 ---
DATA_DIR = "data"
COMPANIES_FILE = os.path.join(DATA_DIR, "companies.txt")
INTERVIEWS_FILE = os.path.join(DATA_DIR, "interviews.txt")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.txt")
DOCUMENTS_FILE = os.path.join(DATA_DIR, "documents.txt")
MEMOS_FILE = os.path.join(DATA_DIR, "memos.txt")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def save_data(filepath, data_list):
    """
    指定されたファイルパスにデータを書き込む。
    各要素は新しい行として書き込まれる。
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            for item in data_list:
                f.write(item + '\n')
        print(f"データが {filepath} に保存されました。")
    except IOError as e:
        print(f"エラー: データファイル {filepath} への書き込みに失敗しました。{e}")

def load_data(filepath):
    """
    指定されたファイルパスからデータを読み込む。
    各行はリストの要素として返される。
    """
    data_list = []
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    data_list.append(line.strip()) # 末尾の改行を削除
        return data_list
    except IOError as e:
        print(f"エラー: データファイル {filepath} の読み込みに失敗しました。{e}")
        return []

# 汎用的なデータパース関数
def parse_data_string(data_string, keys):
    """
    'キー: 値, キー: 値' 形式の文字列を辞書にパースする。
    """
    parsed_data = {}
    parts = data_string.split(', ')
    for part in parts:
        if ': ' in part:
            key, value = part.split(': ', 1)
            # キーの日本語名を辞書のキーとして使いやすい英語名やスネークケースに変換
            # 例: "企業名" -> "company_name"
            # ここは、各機能のデータに合わせて調整が必要です
            # 汎用的にするために、単純に元のキーをそのまま使うか、
            # もしくは引数でマッピングを渡すこともできますが、今回はシンプルに元のキーを使います。
            # 例外的に日本語キーを扱うため、今回はそのままキーとして使う形にします。
            parsed_data[key] = value.strip()
    
    # 期待するキーが存在しない場合に備えてデフォルト値を設定
    for key in keys:
        if key not in parsed_data:
            parsed_data[key] = '不明' # または適切なデフォルト値
    return parsed_data

# --- アプリケーションルート ---

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in USERS and USERS[username] == password:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            error = '無効なユーザー名またはパスワードです。'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

# --- 応募企業情報 (既存) ---
@app.route('/companies')
def companies():
    if 'username' not in session:
        return redirect(url_for('login'))

    raw_companies = load_data(COMPANIES_FILE)
    parsed_companies = []
    # 期待するキーをリストで定義
    expected_keys = ["企業名", "応募日", "選考段階", "結果"]
    for company_str in raw_companies:
        # パース関数を呼び出す際に、各フィールド名を適切にマッピングして渡す
        company_data = parse_data_string(company_str, expected_keys)
        parsed_companies.append({
            'name': company_data.get('企業名', '不明'),
            'application_date': company_data.get('応募日', '不明'),
            'selection_stage': company_data.get('選考段階', '不明'),
            'result': company_data.get('結果', '未定')
        })
    return render_template('companies.html', companies=parsed_companies)

@app.route('/add_company', methods=['POST'])
def add_company():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        company_name = request.form['company_name']
        application_date = request.form.get('application_date', '未入力')
        selection_stage = request.form.get('selection_stage', '未入力')
        result = request.form.get('result', '未定')

        new_company_entry = (
            f"企業名: {company_name}, "
            f"応募日: {application_date}, "
            f"選考段階: {selection_stage}, "
            f"結果: {result}"
        )

        companies_list = load_data(COMPANIES_FILE)
        companies_list.append(new_company_entry)
        save_data(COMPANIES_FILE, companies_list)

    return redirect(url_for('companies'))

# --- ★ここから新しい機能を追加します★ ---

# 面接スケジュール
@app.route('/interviews')
def interviews():
    if 'username' not in session:
        return redirect(url_for('login'))

    raw_interviews = load_data(INTERVIEWS_FILE)
    parsed_interviews = []
    expected_keys = ["企業名", "日時", "場所", "担当者"]
    for interview_str in raw_interviews:
        interview_data = parse_data_string(interview_str, expected_keys)
        parsed_interviews.append({
            'company_name': interview_data.get('企業名', '不明'),
            'date_time': interview_data.get('日時', '不明'),
            'location': interview_data.get('場所', '不明'),
            'person': interview_data.get('担当者', '不明')
        })
    return render_template('interviews.html', interviews=parsed_interviews)

@app.route('/add_interview', methods=['POST'])
def add_interview():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        company_name = request.form['company_name']
        date_time = request.form.get('date_time', '未入力')
        location = request.form.get('location', '未入力')
        person = request.form.get('person', '未入力')

        new_interview_entry = (
            f"企業名: {company_name}, "
            f"日時: {date_time}, "
            f"場所: {location}, "
            f"担当者: {person}"
        )

        interviews_list = load_data(INTERVIEWS_FILE)
        interviews_list.append(new_interview_entry)
        save_data(INTERVIEWS_FILE, interviews_list)

    return redirect(url_for('interviews'))

# タスク管理
@app.route('/tasks')
def tasks():
    if 'username' not in session:
        return redirect(url_for('login'))

    raw_tasks = load_data(TASKS_FILE)
    parsed_tasks = []
    expected_keys = ["タスク内容", "期限", "状態"]
    for task_str in raw_tasks:
        task_data = parse_data_string(task_str, expected_keys)
        parsed_tasks.append({
            'content': task_data.get('タスク内容', '不明'),
            'deadline': task_data.get('期限', '不明'),
            'status': task_data.get('状態', '未完了')
        })
    return render_template('tasks.html', tasks=parsed_tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        content = request.form['content']
        deadline = request.form.get('deadline', '未入力')
        status = '未完了' # 新規タスクはデフォルトで未完了

        new_task_entry = (
            f"タスク内容: {content}, "
            f"期限: {deadline}, "
            f"状態: {status}"
        )

        tasks_list = load_data(TASKS_FILE)
        tasks_list.append(new_task_entry)
        save_data(TASKS_FILE, tasks_list)

    return redirect(url_for('tasks'))

@app.route('/complete_task', methods=['POST'])
def complete_task():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        task_index = int(request.form['task_index'])
        
        tasks_list = load_data(TASKS_FILE)
        if 0 <= task_index < len(tasks_list):
            task_str = tasks_list[task_index]
            # 状態を '完了' に更新
            if "状態: 未完了" in task_str:
                tasks_list[task_index] = task_str.replace("状態: 未完了", "状態: 完了")
                save_data(TASKS_FILE, tasks_list)
        
    return redirect(url_for('tasks'))


# 応募書類管理
@app.route('/documents')
def documents():
    if 'username' not in session:
        return redirect(url_for('login'))

    raw_documents = load_data(DOCUMENTS_FILE)
    parsed_documents = []
    expected_keys = ["書類名", "企業名", "提出日", "状況"]
    for doc_str in raw_documents:
        doc_data = parse_data_string(doc_str, expected_keys)
        parsed_documents.append({
            'document_name': doc_data.get('書類名', '不明'),
            'company_name': doc_data.get('企業名', '不明'),
            'submission_date': doc_data.get('提出日', '不明'),
            'status': doc_data.get('状況', '不明')
        })
    return render_template('documents.html', documents=parsed_documents)

@app.route('/add_document', methods=['POST'])
def add_document():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        document_name = request.form['document_name']
        company_name = request.form.get('company_name', '未入力')
        submission_date = request.form.get('submission_date', '未入力')
        status = request.form.get('status', '未入力')

        new_document_entry = (
            f"書類名: {document_name}, "
            f"企業名: {company_name}, "
            f"提出日: {submission_date}, "
            f"状況: {status}"
        )

        documents_list = load_data(DOCUMENTS_FILE)
        documents_list.append(new_document_entry)
        save_data(DOCUMENTS_FILE, documents_list)

    return redirect(url_for('documents'))

# メモ
@app.route('/memos')
def memos():
    if 'username' not in session:
        return redirect(url_for('login'))

    raw_memos = load_data(MEMOS_FILE)
    parsed_memos = []
    expected_keys = ["タイトル", "内容"]
    for memo_str in raw_memos:
        memo_data = parse_data_string(memo_str, expected_keys)
        parsed_memos.append({
            'title': memo_data.get('タイトル', '不明'),
            'content': memo_data.get('内容', '不明')
        })
    return render_template('memos.html', memos=parsed_memos)

@app.route('/add_memo', methods=['POST'])
def add_memo():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form.get('content', '未入力')

        new_memo_entry = (
            f"タイトル: {title}, "
            f"内容: {content}"
        )

        memos_list = load_data(MEMOS_FILE)
        memos_list.append(new_memo_entry)
        save_data(MEMOS_FILE, memos_list)

    return redirect(url_for('memos'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')