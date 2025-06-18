from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

# ★変更点: Flask-Loginから必要な機能をすべてインポート
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required

# --- Flaskアプリケーションの基本設定 ---
app = Flask(__name__)
# SECRET_KEYは環境変数から読み込むのが安全です
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-secure-default-key-for-development')

# --- データベース設定 ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
# ★変更点: postgres:// を postgresql:// に置換する処理を追加
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ★変更点: Flask-Loginの初期設定を追加
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # 未ログイン時にリダイレクトするページを指定

# --- データベースモデルの定義 ---

# ★変更点: Userモデルに UserMixin を継承させる
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # password_hashの長さを256に修正
    companies = db.relationship('Company', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 他のモデル定義 (Company, Interview, Task, Document, Memo) はそのまま...
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    industry = db.Column(db.String(100))  # ★追加
    url = db.Column(db.String(200))      # ★追加
    notes = db.Column(db.Text)           # ★追加
    application_date = db.Column(db.String(20))
    selection_stage = db.Column(db.String(50))
    result = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # ... (以下、Company, Interview, Task, Document, Memoのモデル定義は変更なし) ...
    def __repr__(self):
        return f'<Company {self.name}>'
class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False) 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_time = db.Column(db.String(50)) 
    location = db.Column(db.String(100))
    person = db.Column(db.String(100))
    url = db.Column(db.String(200))
    notes = db.Column(db.Text)
    company = db.relationship('Company', backref=db.backref('interviews', lazy=True, cascade="all, delete-orphan"))
    def __repr__(self):
        return f'<Interview {self.company.name} - {self.date_time}>'
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.String(20))
    status = db.Column(db.String(20), default='未完了')
    company = db.relationship('Company', backref=db.backref('tasks', lazy=True, cascade="all, delete-orphan"))
    def __repr__(self):
        return f'<Task {self.content}>'
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    document_name = db.Column(db.String(100), nullable=False)
    submission_date = db.Column(db.String(20))
    status = db.Column(db.String(50))
    file_path = db.Column(db.String(200))
    company = db.relationship('Company', backref=db.backref('documents', lazy=True, cascade="all, delete-orphan"))
    def __repr__(self):
        return f'<Document {self.document_name} for {self.company_id}>'
class Memo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    company = db.relationship('Company', backref=db.backref('memos', lazy=True, cascade="all, delete-orphan"))
    def __repr__(self):
        return f'<Memo {self.title}>'


# ★変更点: Flask-Loginに必須の user_loader を定義
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ★変更点: 不要で非効率なため、@app.before_request を削除


# ★変更点: ルートの "/" を簡潔に
@app.route('/')
def index():
    # ログインしていればダッシュボードへ、していなければログインページへ
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    # ★変更点: Flask-Loginのcurrent_userでログイン状態をチェック
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # ★変更点: login_user() でログイン処理を行う
            login_user(user)
            flash('ログインに成功しました！', 'success')
            # 次にアクセスしようとしていたページがあれば、そちらにリダイレクト
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('無効なユーザー名またはパスワードです。', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required # ★変更点: ログイン必須にする
def logout():
    # ★変更点: logout_user() でログアウト処理を行う
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # ... (registerのロジックはほぼ変更なし) ...
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

# ★変更点: 以前の改造を反映し、@login_requiredで保護
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required 
def dashboard():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            new_company = Company(name=name, industry=request.form.get('industry'), url=request.form.get('url'), notes=request.form.get('notes'), user_id=current_user.id)
            db.session.add(new_company)
            db.session.commit()
            flash('企業が追加されました', 'success')
        return redirect(url_for('dashboard'))
    
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    return render_template('dashboard.html', companies=companies)

# --- この下のルートをすべて置き換えてください ---

@app.route('/company/<int:company_id>')
@login_required
def company_detail(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    
    # その企業に関連する情報を取得
    interviews = Interview.query.filter_by(company_id=company.id).order_by(Interview.date_time.desc()).all()
    tasks = Task.query.filter_by(company_id=company.id).order_by(Task.deadline).all()
    documents = Document.query.filter_by(company_id=company.id).order_by(Document.document_name).all()
    memos = Memo.query.filter_by(company_id=company.id).order_by(Memo.title).all()

    return render_template(
        'company_detail.html',
        company=company,
        interviews=interviews,
        tasks=tasks,
        documents=documents,
        memos=memos
    )

# --- 企業情報の編集・削除 ---
@app.route('/company/<int:company_id>/edit', methods=['POST'])
@login_required
def edit_company(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    company.name = request.form.get('name')
    company.industry = request.form.get('industry')
    company.url = request.form.get('url')
    company.notes = request.form.get('notes')
    company.application_date = request.form.get('application_date')
    company.selection_stage = request.form.get('selection_stage')
    company.result = request.form.get('result')
    db.session.commit()
    flash('企業情報が更新されました', 'success')
    return redirect(url_for('company_detail', company_id=company.id))

@app.route('/company/<int:company_id>/delete', methods=['POST'])
@login_required
def delete_company(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    db.session.delete(company)
    db.session.commit()
    flash('企業情報を削除しました', 'success')
    return redirect(url_for('dashboard'))


# --- 各機能の追加・削除ルート ---

# 面接の追加
@app.route('/company/<int:company_id>/interview/add', methods=['POST'])
@login_required
def add_interview(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    new_interview = Interview(
        company_id=company.id,
        user_id=current_user.id,
        date_time=request.form.get('date_time'),
        location=request.form.get('location'),
        person=request.form.get('person'),
        url=request.form.get('url'),
        notes=request.form.get('notes')
    )
    db.session.add(new_interview)
    db.session.commit()
    flash('面接情報を追加しました', 'success')
    return redirect(url_for('company_detail', company_id=company.id))

# タスクの追加
@app.route('/company/<int:company_id>/task/add', methods=['POST'])
@login_required
def add_task(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    content = request.form.get('content')
    if content:
        new_task = Task(
            user_id=current_user.id,
            company_id=company.id,
            content=content,
            deadline=request.form.get('deadline'),
            status='未完了'
        )
        db.session.add(new_task)
        db.session.commit()
        flash('タスクを追加しました', 'success')
    return redirect(url_for('company_detail', company_id=company.id))

# タスクの完了/未完了 トグル
@app.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    company_id = task.company_id
    task.status = '完了' if task.status == '未完了' else '未完了'
    db.session.commit()
    flash('タスクの状態を更新しました', 'success')
    return redirect(url_for('company_detail', company_id=company_id))

# 書類の追加
@app.route('/company/<int:company_id>/document/add', methods=['POST'])
@login_required
def add_document(company_id):
    # (ファイルアップロードのロジックは複雑なので、ここでは情報の保存のみ)
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    new_document = Document(
        user_id=current_user.id,
        company_id=company.id,
        document_name=request.form.get('document_name'),
        submission_date=request.form.get('submission_date'),
        status=request.form.get('status'),
        file_path=request.form.get('file_path') # URLやメモとして使う
    )
    db.session.add(new_document)
    db.session.commit()
    flash('書類情報を追加しました', 'success')
    return redirect(url_for('company_detail', company_id=company.id))

# メモの追加
@app.route('/company/<int:company_id>/memo/add', methods=['POST'])
@login_required
def add_memo(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    title = request.form.get('title')
    if title:
        new_memo = Memo(
            user_id=current_user.id,
            company_id=company.id,
            title=title,
            content=request.form.get('content')
        )
        db.session.add(new_memo)
        db.session.commit()
        flash('メモを追加しました', 'success')
    return redirect(url_for('company_detail', company_id=company.id))

# --- この下に、各アイテムの削除ルートを追加可能 (例: /interview/<id>/delete) ---


# --- この下の、/companies, /interviews, /tasks, /documents, /memos のような
# --- 一覧表示用のルートは、新しい設計では不要になる可能性があります。
# --- 一旦、エラー解決のためにコメントアウトするか、@login_required を付けてください。


if __name__ == '__main__':
    app.run(debug=True)