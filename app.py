from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime # 日付を扱うために追加
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required

# --- Flaskアプリケーションの基本設定 ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super_secret_dev_key')

# --- データベース設定 (PostgreSQL - Neon) ---
# ★ここを大幅に修正します★
# Renderで環境変数として設定する接続文字列
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
if not app.config['SQLALCHEMY_DATABASE_URI']:
    # ローカル開発用のデフォルト値（Neonの接続文字列に置き換える）
    # YOUR_NEON_CONNECTION_STRING をステップ1でコピーした接続文字列に置き換えてください
    app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://user:password@host/dbname?sslmode=require" # <-- ここをあなたのNeon接続文字列に置き換え！
    print("警告: DATABASE_URL 環境変数が設定されていません。ローカルのデフォルト接続文字列を使用します。")


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# データベースの初期化
db = SQLAlchemy(app)

# --- ここから追加 ---
# Flask-Loginの設定
login_manager = LoginManager()
login_manager.init_app(app)
# ログインしていないユーザーがログイン必須ページにアクセスしたときに
# リダイレクトされるページ（ログインページのルート名）を指定
login_manager.login_view = 'login' 

@login_manager.user_loader
def load_user(user_id):
    # sessionに保存されたユーザーIDを使って、実際のユーザーオブジェクトを返す
    # これにより、どのページでもcurrent_userでログイン中のユーザー情報を取得できる
    return User.query.get(int(user_id))
# --- ここまで追加 ---

# データベースモデルの定義
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    # このユーザーが登録した企業情報を参照できるようにリレーションを追加
    companies = db.relationship('Company', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ★ここからCompanyモデルを追加★
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    application_date = db.Column(db.String(20)) # 日付形式で保存する文字列
    selection_stage = db.Column(db.String(50))
    result = db.Column(db.String(50))
    # どのユーザーがこの企業情報を登録したかを識別するための外部キー
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Company {self.name}>'
# ... (User, Company モデルの定義の続き) ...

# Interviewモデル (面接情報を保存するテーブル)
class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False) # 企業と紐付け
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # ユーザーと紐付け
    date_time = db.Column(db.String(50)) # 日時 (例: 2025/06/15 14:00)
    location = db.Column(db.String(100))
    person = db.Column(db.String(100))
    url = db.Column(db.String(200)) # ★イベント詳細URL追加★
    notes = db.Column(db.Text) # ★メモ追加★

    # CompanyモデルとInterviewモデルのリレーション
    company = db.relationship('Company', backref=db.backref('interviews', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<Interview {self.company.name} - {self.date_time}>'

# Taskモデル (タスク情報を保存するテーブル)
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # ユーザーと紐付け
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # 特定の企業に関連するタスクの場合
    content = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.String(20)) # 期限
    status = db.Column(db.String(20), default='未完了') # 未完了, 完了

    # CompanyモデルとTaskモデルのリレーション (Company IDは任意)
    company = db.relationship('Company', backref=db.backref('tasks', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<Task {self.content}>'

# Documentモデル (応募書類情報を保存するテーブル)
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # ユーザーと紐付け
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # 特定の企業に関連する書類の場合
    document_name = db.Column(db.String(100), nullable=False)
    submission_date = db.Column(db.String(20))
    status = db.Column(db.String(50))
    file_path = db.Column(db.String(200)) # ★ファイルパスやURL追加 (実際にはS3などのストレージへのリンク) ★

    # CompanyモデルとDocumentモデルのリレーション (Company IDは任意)
    company = db.relationship('Company', backref=db.backref('documents', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<Document {self.document_name} for {self.company_id}>'

# Memoモデル (メモ情報を保存するテーブル)
class Memo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # ユーザーと紐付け
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # 特定の企業に関連するメモの場合
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False) # ★内容の文字数制限なし★

    # CompanyモデルとMemoモデルのリレーション (Company IDは任意)
    company = db.relationship('Company', backref=db.backref('memos', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<Memo {self.title}>'
# --- 既存のテキストファイル操作関数 (データベース移行が完了したら削除します) ---


@app.before_request
def create_tables():
    # データベーステーブルが存在しない場合のみ作成
    # PostgreSQLの場合、db.create_all()は接続先のデータベースにテーブルを作成します。
    # 警告: 開発段階でテーブル構造を頻繁に変える場合、Alembicなどのマイグレーションツールを導入するのが理想ですが、
    # 今回はシンプルさのため db.create_all() を使用します。
    # 本番環境(Render)では初回デプロイ時にのみ有効になるようにしておくのが安全です。
    # Renderでは環境変数 DATABASE_URL が存在するかどうかで本番環境と見なし、
    # そうでない場合はローカル環境と見なすことが多いです。
    # ここでは、db.session.query(User).first() でテーブルの存在をチェックします。
    try:
        with app.app_context():
            db.session.query(User).first() # Userテーブルにアクセスを試みる
    except Exception as e:
        # テーブルが存在しないなどのエラーが発生したら作成
        print(f"データベーステーブルが見つからないか、アクセスできませんでした: {e}")
        with app.app_context():
            db.create_all()
            print("データベーステーブルが作成されました。")

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['username'] = user.username
            session['user_id'] = user.id # ★ユーザーIDをセッションに保存★
            flash('ログインに成功しました！', 'success')
            return redirect(url_for('dashboard'))
        else:
            error = '無効なユーザー名またはパスワードです。'
            flash(error, 'danger')
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None) # ★ユーザーIDもセッションから削除★
    flash('ログアウトしました。', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('パスワードが一致しません。', 'danger')
            return render_template('register.html', username=username)

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('このユーザー名は既に存在します。別のユーザー名をお試しください。', 'danger')
            return render_template('register.html', username=username)

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('ユーザー登録が完了しました！ログインしてください。', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# 元々あった /dashboard と /companies のルートは削除してください

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # POSTリクエスト（企業情報の入力フォームが送信された時）の処理
    if request.method == 'POST':
        name = request.form.get('name')
        industry = request.form.get('industry')
        url = request.form.get('url')
        notes = request.form.get('notes')

        if name: # 会社名が入力されていれば
            new_company = Company(
                name=name,
                industry=industry,
                url=url,
                notes=notes,
                user_id=current_user.id
            )
            db.session.add(new_company)
            db.session.commit()
            flash('企業が追加されました', 'success')
        return redirect(url_for('dashboard'))

    # GETリクエスト（ページを普通に表示した時）の処理
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    return render_template('dashboard.html', companies=companies)

# --- 企業詳細ページ ---
@app.route('/company/<int:company_id>')
def company_detail(company_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')

    # ログイン中のユーザーが所有する企業情報を取得
    company = Company.query.filter_by(id=company_id, user_id=user_id).first_or_404()
    
    # その企業に関連する面接、タスク、書類、メモを取得
    interviews = Interview.query.filter_by(company_id=company_id, user_id=user_id).order_by(Interview.date_time).all()
    tasks = Task.query.filter_by(company_id=company_id, user_id=user_id).order_by(Task.deadline).all()
    documents = Document.query.filter_by(company_id=company_id, user_id=user_id).order_by(Document.document_name).all()
    memos = Memo.query.filter_by(company_id=company_id, user_id=user_id).order_by(Memo.title).all()

    return render_template(
        'company_detail.html',
        company=company,
        interviews=interviews,
        tasks=tasks,
        documents=documents,
        memos=memos
    )

# --- 面接スケジュール (DB化) ---
# --- 面接スケジュール (データベース化) ---
@app.route('/interviews')
def interviews():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    # ログインユーザーの面接情報と、関連する企業名も一緒に取得
    interviews = Interview.query.filter_by(user_id=user_id).join(Company).order_by(Interview.date_time).all()
    
    # 面接登録フォームで企業選択を可能にするため、ユーザーが登録した企業リストも渡す
    companies = Company.query.filter_by(user_id=user_id).order_by(Company.name).all()

    return render_template('interviews.html', interviews=interviews, companies=companies)

@app.route('/add_interview', methods=['POST'])
def add_interview():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    if user_id is None:
        flash('セッションエラー：ユーザーIDが見つかりません。再ログインしてください。', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        company_id = request.form['company_id'] # selectボックスから取得
        date_time = request.form.get('date_time', '')
        location = request.form.get('location', '')
        person = request.form.get('person', '')
        url = request.form.get('url', '') # ★URL追加★
        notes = request.form.get('notes', '') # ★メモ追加★

        new_interview = Interview(
            company_id=company_id,
            user_id=user_id,
            date_time=date_time,
            location=location,
            person=person,
            url=url, # ★URL設定★
            notes=notes # ★メモ設定★
        )
        db.session.add(new_interview)
        db.session.commit()

        flash(f'面接情報を追加しました。', 'success')

    return redirect(url_for('interviews'))

# --- タスク管理 (後でDB化します) ---
# --- タスク管理 (データベース化) ---
@app.route('/tasks')
def tasks():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    # ログインユーザーのタスクと、関連する企業名も一緒に取得
    # Companyを左結合することで、company_idがNULLでもタスクは表示される
    tasks = db.session.query(Task, Company.name).outerjoin(Company).filter(Task.user_id==user_id).order_by(Task.deadline).all()

    # タスク登録フォームで企業選択を可能にするため、ユーザーが登録した企業リストも渡す
    companies = Company.query.filter_by(user_id=user_id).order_by(Company.name).all()

    return render_template('tasks.html', tasks=tasks, companies=companies)

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    if user_id is None:
        flash('セッションエラー：ユーザーIDが見つかりません。再ログインしてください。', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        content = request.form['content']
        deadline = request.form.get('deadline', '')
        company_id = request.form.get('company_id') # 企業IDは任意
        
        # company_id が空文字の場合、None に変換してデータベースにNULLとして保存
        company_id_val = int(company_id) if company_id else None


        new_task = Task(
            user_id=user_id,
            company_id=company_id_val,
            content=content,
            deadline=deadline,
            status='未完了'
        )
        db.session.add(new_task)
        db.session.commit()

        flash(f'タスク「{content}」を追加しました。', 'success')

    return redirect(url_for('tasks'))

@app.route('/complete_task', methods=['POST'])
def complete_task():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    if user_id is None:
        flash('セッションエラー：ユーザーIDが見つかりません。再ログインしてください。', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        task_id = request.form['task_id'] # タスクIDで更新

        # ログイン中のユーザーが所有するタスクのみを更新
        task_to_update = Task.query.filter_by(id=task_id, user_id=user_id).first()
        if task_to_update:
            task_to_update.status = '完了'
            db.session.commit()
            flash(f'タスク「{task_to_update.content}」を完了しました。', 'success')
        else:
            flash('指定されたタスクが見つからないか、更新できませんでした。', 'danger')

    return redirect(url_for('tasks'))

# --- 応募書類管理 (後でDB化します) ---
# --- 応募書類管理 (データベース化) ---
@app.route('/documents')
def documents():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    # ログインユーザーの書類情報と、関連する企業名も一緒に取得
    documents = db.session.query(Document, Company.name).outerjoin(Company).filter(Document.user_id==user_id).order_by(Document.document_name).all()

    # 書類登録フォームで企業選択を可能にするため、ユーザーが登録した企業リストも渡す
    companies = Company.query.filter_by(user_id=user_id).order_by(Company.name).all()

    return render_template('documents.html', documents=documents, companies=companies)

@app.route('/add_document', methods=['POST'])
def add_document():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    if user_id is None:
        flash('セッションエラー：ユーザーIDが見つかりません。再ログインしてください。', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        document_name = request.form['document_name']
        company_id = request.form.get('company_id') # 企業IDは任意
        submission_date = request.form.get('submission_date', '')
        status = request.form.get('status', '')
        file_path = request.form.get('file_path', '') # ★ファイルパス/URL追加★
        
        # company_id が空文字の場合、None に変換してデータベースにNULLとして保存
        company_id_val = int(company_id) if company_id else None

        new_document = Document(
            user_id=user_id,
            company_id=company_id_val,
            document_name=document_name,
            submission_date=submission_date,
            status=status,
            file_path=file_path # ★ファイルパス/URL設定★
        )
        db.session.add(new_document)
        db.session.commit()

        flash(f'書類「{document_name}」を追加しました。', 'success')

    return redirect(url_for('documents'))

# --- メモ (後でDB化します) ---
# --- メモ (データベース化) ---
@app.route('/memos')
def memos():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    # ログインユーザーのメモ情報と、関連する企業名も一緒に取得
    memos = db.session.query(Memo, Company.name).outerjoin(Company).filter(Memo.user_id==user_id).order_by(Memo.title).all()

    # メモ登録フォームで企業選択を可能にするため、ユーザーが登録した企業リストも渡す
    companies = Company.query.filter_by(user_id=user_id).order_by(Company.name).all()

    return render_template('memos.html', memos=memos, companies=companies)

@app.route('/add_memo', methods=['POST'])
def add_memo():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    if user_id is None:
        flash('セッションエラー：ユーザーIDが見つかりません。再ログインしてください。', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form.get('content', '')
        company_id = request.form.get('company_id') # 企業IDは任意
        
        # company_id が空文字の場合、None に変換してデータベースにNULLとして保存
        company_id_val = int(company_id) if company_id else None

        new_memo = Memo(
            user_id=user_id,
            company_id=company_id_val,
            title=title,
            content=content
        )
        db.session.add(new_memo)
        db.session.commit()

        flash(f'メモ「{title}」を追加しました。', 'success')

    return redirect(url_for('memos'))

# ... (app.run の部分) ...
if __name__ == '__main__':
    # ローカル開発時にデータベースを初期化したい場合、以下のブロックを一度実行します。
    # すでにdb.create_all()は@app.before_requestデコレータで初回リクエスト時に実行されるため、
    # 基本的にはコメントアウトしたままで大丈夫です。
    # ただし、DBファイルを削除して一からやり直したい場合はコメントアウトを外して実行してください。
    # with app.app_context():
    #     db.create_all()
    app.run(debug=True, host='0.0.0.0')
