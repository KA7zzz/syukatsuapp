from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

# --- Flaskアプリケーションの基本設定 ---
app = Flask(__name__)
# セッションを暗号化するための秘密鍵
# 環境変数から読み込むように変更。デプロイ時はRenderの環境変数に設定したFLASK_SECRET_KEYが使われます。
# ローカル開発用にデフォルト値を設定
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super_secret_dev_key')

# --- データベース設定 (SQLite) ---
# SQLiteデータベースファイルのパス。dataフォルダ内に配置します。
# Renderでは永続ディスクのパスと合わせる必要があります。
# '/opt/render/project/src/data' はRenderのWebサービスで設定した永続ディスクのマウントパスです。
# ローカル環境では 'data/site.db' になります。
base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, 'data', 'site.db')
render_db_folder_path = os.path.join('/opt', 'render', 'project', 'src', 'data') # Renderの永続ディスクパス
render_db_file_path = os.path.join(render_db_folder_path, 'site.db') # RenderでのDBファイル絶対パス

# Render環境で実行されているかどうかの判定 (RENDER_EXTERNAL_HOSTNAME はRenderで自動設定される環境変数)
if os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{render_db_file_path}'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # 警告を抑制

db = SQLAlchemy(app)

# --- データベースモデルの定義 ---

# Userモデル (ユーザー情報を保存するテーブル)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # user_id と関連付けるフィールド (後で他のモデルに追加します)
    # 例えば、companies = db.relationship('Company', backref='owner', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

    # パスワードを設定するメソッド (ハッシュ化して保存)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # パスワードを検証するメソッド
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- 既存のテキストファイル操作関数 (後でデータベース操作に置き換えられます) ---
# ※これらは後で削除しますので、一時的に存在しているだけです。
DATA_DIR = "data"
COMPANIES_FILE = os.path.join(DATA_DIR, "companies.txt")
INTERVIEWS_FILE = os.path.join(DATA_DIR, "interviews.txt")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.txt")
DOCUMENTS_FILE = os.path.join(DATA_DIR, "documents.txt")
MEMOS_FILE = os.path.join(DATA_DIR, "memos.txt")

# ローカル環境でdataディレクトリが存在しない場合は作成
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Render環境でのdataディレクトリ作成確認 (永続ディスクがマウントされるパス)
if os.environ.get('RENDER_EXTERNAL_HOSTNAME') and not os.path.exists(render_db_folder_path):
    os.makedirs(render_db_folder_path)


def save_data(filepath, data_list):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            for item in data_list:
                f.write(item + '\n')
        # print(f"データが {filepath} に保存されました。") # デバッグ用
    except IOError as e:
        print(f"エラー: データファイル {filepath} への書き込みに失敗しました。{e}")

def load_data(filepath):
    data_list = []
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    data_list.append(line.strip())
        return data_list
    except IOError as e:
        print(f"エラー: データファイル {filepath} の読み込みに失敗しました。{e}")
        return []

def parse_data_string(data_string, keys):
    parsed_data = {}
    parts = data_string.split(', ')
    for part in parts:
        if ': ' in part:
            key, value = part.split(': ', 1)
            parsed_data[key] = value.strip()
    for key in keys:
        if key not in parsed_data:
            parsed_data[key] = '不明'
    return parsed_data

# --- アプリケーションルート ---

# アプリケーション起動時にデータベースを作成 (初回のみ)
@app.before_request
def create_tables():
    # データベースファイルが存在しない場合のみ作成
    # Render環境かローカル環境かでパスを適切に判断
    if os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
        db_file_exists = os.path.exists(render_db_file_path)
    else:
        db_file_exists = os.path.exists(db_path)

    if not db_file_exists:
        with app.app_context():
            db.create_all()
            print("データベーステーブルが作成されました。")
            # デバッグ用に最初のユーザーをここで作成することも可能ですが、
            # ユーザー登録機能ができたのでコメントアウト推奨
            # admin_user = User.query.filter_by(username='admin').first()
            # if not admin_user:
            #     admin = User(username='admin')
            #     admin.set_password('adminpass')
            #     db.session.add(admin)
            #     db.session.commit()
            #     print("初期ユーザー 'admin' が作成されました。")


@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# ログインルート (データベース認証)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: # 既にログインしている場合はダッシュボードへ
        return redirect(url_for('dashboard'))

    error = None # エラーメッセージ用 (flashメッセージと併用)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first() # データベースからユーザーを取得
        if user and user.check_password(password): # パスワードを検証
            session['username'] = user.username # ログイン成功したらセッションにユーザー名を保存
            flash('ログインに成功しました！', 'success')
            return redirect(url_for('dashboard'))
        else:
            error = '無効なユーザー名またはパスワードです。'
            flash(error, 'danger') # flashメッセージとしても表示
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('ログアウトしました。', 'info')
    return redirect(url_for('login'))

# 新規ユーザー登録ルート
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session: # 既にログインしている場合はダッシュボードへ
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('パスワードが一致しません。', 'danger')
            return render_template('register.html', username=username) # 入力値を保持するためにusernameを渡す

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('このユーザー名は既に存在します。別のユーザー名をお試しください。', 'danger')
            return render_template('register.html', username=username)

        new_user = User(username=username)
        new_user.set_password(password) # パスワードをハッシュ化して設定
        db.session.add(new_user)
        db.session.commit() # データベースに保存

        flash('ユーザー登録が完了しました！ログインしてください。', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

# --- 既存の企業情報関連のルート (後でDB化します) ---
@app.route('/companies')
def companies():
    if 'username' not in session:
        return redirect(url_for('login'))

    raw_companies = load_data(COMPANIES_FILE)
    parsed_companies = []
    expected_keys = ["企業名", "応募日", "選考段階", "結果"]
    for company_str in raw_companies:
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

# --- 面接スケジュール (後でDB化します) ---
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

# --- タスク管理 (後でDB化します) ---
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
        status = '未完了'

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
            if "状態: 未完了" in task_str:
                tasks_list[task_index] = task_str.replace("状態: 未完了", "状態: 完了")
                save_data(TASKS_FILE, tasks_list)

    return redirect(url_for('tasks'))

# --- 応募書類管理 (後でDB化します) ---
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

# --- メモ (後でDB化します) ---
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
    # ローカル開発時にデータベースを初期化したい場合、以下のブロックを一度実行します。
    # すでにdb.create_all()は@app.before_requestデコレータで初回リクエスト時に実行されるため、
    # 基本的にはコメントアウトしたままで大丈夫です。
    # ただし、DBファイルを削除して一からやり直したい場合はコメントアウトを外して実行してください。
    # with app.app_context():
    #     db.create_all()
    app.run(debug=True, host='0.0.0.0')