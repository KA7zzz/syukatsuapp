from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import json
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-secure-default-key-for-development')

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    companies = db.relationship('Company', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    industry = db.Column(db.String(100))
    url = db.Column(db.String(200))
    notes = db.Column(db.Text)
    application_date = db.Column(db.String(20))
    selection_stage = db.Column(db.String(50))
    result = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('ログインに成功しました！', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('無効なユーザー名またはパスワードです。', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
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
    
    calendar_events = []
    
    companies = Company.query.filter_by(user_id=current_user.id).all()
    for company in companies:
        if company.application_date:
            calendar_events.append({
                'title': f"応募: {company.name}",
                'start': company.application_date,
                'url': url_for('company_detail', company_id=company.id),
                'backgroundColor': '#28a745',
                'borderColor': '#28a745',
                'textColor': 'black'
            })

    interviews = Interview.query.filter_by(user_id=current_user.id).all()
    for interview in interviews:
        if interview.date_time:
            calendar_events.append({
                'title': f"面接: {interview.company.name}",
                'start': interview.date_time,
                'url': url_for('company_detail', company_id=interview.company_id),
                'backgroundColor': '#dc3545',
                'borderColor': '#dc3545',
                'textColor': 'black'
            })

    tasks = Task.query.filter_by(user_id=current_user.id, status='未完了').all()
    for task in tasks:
        if task.deadline:
            calendar_events.append({
                'title': f"タスク〆: {task.content[:10]}",
                'start': task.deadline,
                'url': url_for('company_detail', company_id=task.company_id) if task.company_id else '#',
                'backgroundColor': '#ffc107',
                'borderColor': '#ffc107',
                'textColor': 'black'
            })
            
    documents = Document.query.filter_by(user_id=current_user.id).all()
    for doc in documents:
        if doc.submission_date:
            calendar_events.append({
                'title': f"書類提出: {doc.document_name}",
                'start': doc.submission_date,
                'url': url_for('company_detail', company_id=doc.company_id) if doc.company_id else '#',
                'backgroundColor': '#17a2b8',
                'borderColor': '#17a2b8',
                'textColor': 'black'
            })

    return render_template(
        'dashboard.html', 
        companies=companies, 
        calendar_events=json.dumps(calendar_events)
    )

@app.route('/company/<int:company_id>')
@login_required
def company_detail(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    
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

# --- 面接スケジュール関連のルート ---
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

@app.route('/interview/<int:interview_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_interview(interview_id):
    interview = Interview.query.filter_by(id=interview_id, user_id=current_user.id).first_or_404()
    company = Company.query.filter_by(id=interview.company_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        interview.date_time = request.form.get('date_time')
        interview.location = request.form.get('location')
        interview.person = request.form.get('person')
        interview.url = request.form.get('url')
        interview.notes = request.form.get('notes')
        db.session.commit()
        flash('面接情報を更新しました', 'success')
        return redirect(url_for('company_detail', company_id=company.id))
    return render_template('edit_interview.html', interview=interview, company=company)

@app.route('/interview/<int:interview_id>/delete', methods=['POST'])
@login_required
def delete_interview(interview_id):
    interview = Interview.query.filter_by(id=interview_id, user_id=current_user.id).first_or_404()
    company_id = interview.company_id
    db.session.delete(interview)
    db.session.commit()
    flash('面接情報を削除しました', 'success')
    return redirect(url_for('company_detail', company_id=company_id))

# --- タスク関連のルート ---
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

@app.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    company_id = task.company_id
    task.status = '完了' if task.status == '未完了' else '未完了'
    db.session.commit()
    flash('タスクの状態を更新しました', 'success')
    return redirect(url_for('company_detail', company_id=company_id))

@app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    company = Company.query.filter_by(id=task.company_id, user_id=current_user.id).first_or_404() if task.company_id else None
    if request.method == 'POST':
        task.content = request.form.get('content')
        task.deadline = request.form.get('deadline')
        task.status = request.form.get('status')
        db.session.commit()
        flash('タスクを更新しました', 'success')
        return redirect(url_for('company_detail', company_id=company.id) if company else url_for('dashboard')) # タスクが企業に紐付いていない場合も考慮
    return render_template('edit_task.html', task=task, company=company)

@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    company_id = task.company_id
    db.session.delete(task)
    db.session.commit()
    flash('タスクを削除しました', 'success')
    return redirect(url_for('company_detail', company_id=company_id) if company_id else url_for('dashboard'))

# --- 書類関連のルート ---
@app.route('/company/<int:company_id>/document/add', methods=['POST'])
@login_required
def add_document(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first_or_404()
    new_document = Document(
        user_id=current_user.id,
        company_id=company.id,
        document_name=request.form.get('document_name'),
        submission_date=request.form.get('submission_date'),
        status=request.form.get('status'),
        file_path=request.form.get('file_path')
    )
    db.session.add(new_document)
    db.session.commit()
    flash('書類情報を追加しました', 'success')
    return redirect(url_for('company_detail', company_id=company.id))

@app.route('/document/<int:document_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_document(document_id):
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()
    company = Company.query.filter_by(id=document.company_id, user_id=current_user.id).first_or_404() if document.company_id else None
    if request.method == 'POST':
        document.document_name = request.form.get('document_name')
        document.submission_date = request.form.get('submission_date')
        document.status = request.form.get('status')
        document.file_path = request.form.get('file_path')
        db.session.commit()
        flash('書類情報を更新しました', 'success')
        return redirect(url_for('company_detail', company_id=company.id) if company else url_for('dashboard'))
    return render_template('edit_document.html', document=document, company=company)

@app.route('/document/<int:document_id>/delete', methods=['POST'])
@login_required
def delete_document(document_id):
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()
    company_id = document.company_id
    db.session.delete(document)
    db.session.commit()
    flash('書類情報を削除しました', 'success')
    return redirect(url_for('company_detail', company_id=company_id) if company_id else url_for('dashboard'))

# --- メモ関連のルート ---
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

@app.route('/memo/<int:memo_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_memo(memo_id):
    memo = Memo.query.filter_by(id=memo_id, user_id=current_user.id).first_or_404()
    company = Company.query.filter_by(id=memo.company_id, user_id=current_user.id).first_or_404() if memo.company_id else None
    if request.method == 'POST':
        memo.title = request.form.get('title')
        memo.content = request.form.get('content')
        db.session.commit()
        flash('メモを更新しました', 'success')
        return redirect(url_for('company_detail', company_id=company.id) if company else url_for('dashboard'))
    return render_template('edit_memo.html', memo=memo, company=company)

@app.route('/memo/<int:memo_id>/delete', methods=['POST'])
@login_required
def delete_memo(memo_id):
    memo = Memo.query.filter_by(id=memo_id, user_id=current_user.id).first_or_404()
    company_id = memo.company_id
    db.session.delete(memo)
    db.session.commit()
    flash('メモを削除しました', 'success')
    return redirect(url_for('company_detail', company_id=company_id) if company_id else url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)