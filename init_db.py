from app import app, db

# アプリケーションコンテキスト内でデータベース操作を実行する
with app.app_context():
    print("データベースのテーブルを初期化します...")
    
    # app.pyで定義されている全てのモデル（User, Company, Taskなど）に基づいて
    # テーブルを作成します。すでにテーブルが存在する場合は、作成されません。
    db.create_all()
    
    print("データベースのテーブル初期化が完了しました。")