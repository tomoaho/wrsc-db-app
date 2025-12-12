from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'secret_key'

# データベース設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shooting.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------------------------------------------------------
# モデル定義
# ---------------------------------------------------------
class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    gender = db.Column(db.String(10))
    entry_year = db.Column(db.Integer)
    scores = db.relationship('Score', backref='player', lazy=True, cascade="all, delete-orphan")

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    match_name = db.Column(db.String(100))
    category = db.Column(db.String(50))
    event_name = db.Column(db.String(50))
    s1 = db.Column(db.Float, default=0.0)
    s2 = db.Column(db.Float, default=0.0)
    s3 = db.Column(db.Float, default=0.0)
    s4 = db.Column(db.Float, default=0.0)
    s5 = db.Column(db.Float, default=0.0)
    s6 = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)

# ★追加: チーム目標テーブル
class TeamGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    target_score = db.Column(db.Float, default=0.0)

# ---------------------------------------------------------
# フィルター定義
# ---------------------------------------------------------
@app.template_filter('sort_events')
def sort_events_filter(events):
    order = ['AR60', 'SB3x20', 'P60', 'AP60', 'BP']
    def get_rank(e):
        if e in order: return order.index(e)
        return 999
    return sorted(events, key=lambda x: (get_rank(x), x))

# ---------------------------------------------------------
# ルーティング
# ---------------------------------------------------------

@app.route('/')
def index():
    target_events = ['AR60', 'SB3x20', 'P60']
    
    # チーム目標取得 (前回までのコードと同じ)
    team_goals = {}
    for event in target_events:
        team_goals[event] = {}
        for gender in ['男', '女']:
            goal = TeamGoal.query.filter_by(event_name=event, gender=gender).first()
            if not goal:
                default_score = 600.0
                if event == 'AR60': default_score = 620.0
                elif event == 'SB3x20': default_score = 570.0
                elif event == 'P60': default_score = 560.0
                goal = TeamGoal(event_name=event, gender=gender, target_score=default_score)
                db.session.add(goal)
                db.session.commit()
            team_goals[event][gender] = goal.target_score

    # 1. ダッシュボード集計 (全期間の平均・最高)
    # ※ここは期間制限しない方が「歴代最高」などが分かって良いかと思いますが、
    # もしここも4年間にしたい場合は filter を追加してください。今回は全期間のままにします。
    dashboard_data = {e: {'男': {'avg':0,'max':0}, '女': {'avg':0,'max':0}} for e in target_events}
    stats_query = db.session.query(Score.event_name, Player.gender, func.avg(Score.total), func.max(Score.total)).join(Player).group_by(Score.event_name, Player.gender).all()
    for e, g, avg, mx in stats_query:
        if e in dashboard_data and g in ['男','女']:
            dashboard_data[e][g] = {'avg': round(avg,1), 'max': round(mx,1)}

    # --- 2. グラフ用データ (★修正: 最新から4年間に限定) ---
    chart_data = {e: {'labels':[], 'male':[], 'female':[]} for e in target_events}
    
    # 最新の日付を取得して期間を決める
    last_score = Score.query.order_by(Score.date.desc()).first()
    if last_score:
        latest_date = last_score.date
        try:
            # 4年前を計算 (うるう年対応)
            start_date = latest_date.replace(year=latest_date.year - 4)
        except ValueError:
            start_date = latest_date.replace(year=latest_date.year - 4, day=28)
    else:
        # データがない場合のダミー日付
        start_date = datetime(2000, 1, 1).date()

    # フィルタリング付きでデータ取得
    monthly = db.session.query(
        Score.event_name, 
        Player.gender, 
        func.strftime('%Y/%m', Score.date).label('m'), 
        func.avg(Score.total)
    ).join(Player).filter(
        Score.date >= start_date  # ★ここで期間を制限
    ).group_by(
        Score.event_name, Player.gender, 'm'
    ).order_by('m').all()

    temp = {e:{} for e in target_events}
    months = set()
    for e, g, m, avg in monthly:
        if e in target_events and g in ['男','女']:
            if m not in temp[e]: temp[e][m] = {'男':None,'女':None}
            temp[e][m][g] = round(avg,1)
            months.add(m)
    sorted_months = sorted(list(months))
    
    for e in target_events:
        chart_data[e]['labels'] = sorted_months
        for m in sorted_months:
            val = temp[e].get(m, {})
            chart_data[e]['male'].append(val.get('男'))
            chart_data[e]['female'].append(val.get('女'))

    # 3. 選手一覧 (検索・絞り込み)
    q_name = request.args.get('name', '')
    q_year = request.args.get('year', '')
    q_gender = request.args.get('gender', '')
    q_match = request.args.get('match', '')
    q_event = request.args.get('event', '')

    query = Player.query
    if q_year: query = query.filter(Player.entry_year == int(q_year))
    if q_gender: query = query.filter(Player.gender == q_gender)
    if q_match or q_event:
        query = query.join(Score)
        if q_match: query = query.filter(Score.match_name == q_match)
        if q_event: query = query.filter(Score.event_name == q_event)
    
    players = query.distinct().order_by(Player.entry_year.desc(), Player.name).all()

    if q_name:
        clean = q_name.replace(' ','').replace('　','')
        filtered = []
        for p in players:
            if clean in p.name.replace(' ','').replace('　',''): filtered.append(p)
        players = filtered

    years = [y[0] for y in db.session.query(Player.entry_year).distinct().filter(Player.entry_year!=None).order_by(Player.entry_year.desc()).all()]
    # matchesクエリ修正: 大会名のリストを正しく取得
    # (前回 main.py を修正した際に、matches変数の作り方も変えたため、ここも合わせます)
    matches_res = db.session.query(Score.match_name).distinct().all()
    unique_matches = [m[0] for m in matches_res]
    # 必要ならここでソートしても良いですが、indexページのプルダウン順序なので一旦このままで

    events_list = [e[0] for e in db.session.query(Score.event_name).distinct().order_by(Score.event_name).all()]
    recent = Score.query.order_by(Score.date.desc()).limit(10).all()

    return render_template('index.html', players=players, recent_scores=recent,
                           unique_years=years, unique_matches=unique_matches, unique_events=events_list,
                           dashboard_data=dashboard_data, chart_data=chart_data, team_goals=team_goals,
                           q_name=q_name, q_year=q_year, q_gender=q_gender, q_match=q_match, q_event=q_event)

@app.route('/update_goals', methods=['POST'])
def update_goals():
    target_events = ['AR60', 'SB3x20', 'P60']
    for event in target_events:
        for gender in ['男', '女']:
            # inputのname属性は "goal_AR60_男" のような形にする予定
            key = f"goal_{event}_{gender}"
            val = request.form.get(key)
            if val:
                goal = TeamGoal.query.filter_by(event_name=event, gender=gender).first()
                if goal:
                    goal.target_score = float(val)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
def upload_csv():
    if 'file' not in request.files: return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '': return redirect(url_for('index'))
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        try: df = pd.read_csv(filepath, encoding='cp932')
        except: df = pd.read_csv(filepath, encoding='utf-8')
        for _, row in df.iterrows():
            try:
                pname = row['選手名']
                player = Player.query.filter_by(name=pname).first()
                if not player:
                    player = Player(name=pname, gender=row.get('性別',''), entry_year=row.get('入部年度',2024))
                    db.session.add(player)
                    db.session.commit()
                d_str = str(row['日付'])
                try: dobj = datetime.strptime(d_str, '%Y/%m/%d').date()
                except: dobj = datetime.now().date()
                
                s_vals = [float(row.get(f'S{i}',0)) for i in range(1,7)]
                total = row.get('合計点')
                if pd.isna(total): total = row.get('合計')
                if pd.isna(total) or total==0: total = sum(s_vals)
                else: total = float(total)

                ns = Score(player_id=player.id, date=dobj, match_name=row.get('大会名',''),
                           category=row.get('識別',''), event_name=row.get('種目',''),
                           s1=s_vals[0], s2=s_vals[1], s3=s_vals[2], s4=s_vals[3], s5=s_vals[4], s6=s_vals[5], total=total)
                db.session.add(ns)
            except: continue
        db.session.commit()
        return redirect(url_for('index'))

@app.route('/player/<int:player_id>')
def player_detail(player_id):
    player = Player.query.get_or_404(player_id)
    scores = Score.query.filter_by(player_id=player.id).order_by(Score.date).all()
    
    # 1. 本人の要約データ (Max, Avg)
    temp_stats = {}
    for s in scores:
        if s.event_name not in temp_stats: temp_stats[s.event_name] = []
        temp_stats[s.event_name].append(s.total)
    
    summary_data = {}
    for event, val_list in temp_stats.items():
        if val_list:
            summary_data[event] = {
                'max': max(val_list),
                'avg': round(sum(val_list) / len(val_list), 1),
                'count': len(val_list),
                'rank_best': '-',  # ベスト順位
                'rank_avg': '-',   # ★追加: 平均順位
                'total_players': '-'
            }
    
    # --- A. ベストスコアの順位計算 ---
    all_bests = db.session.query(Score.event_name, Score.player_id, func.max(Score.total)).group_by(Score.event_name, Score.player_id).all()
    best_map = {}
    for event, pid, val in all_bests:
        if event not in best_map: best_map[event] = []
        best_map[event].append(val)
    
    for event in best_map:
        best_map[event].sort(reverse=True)

    # --- B. 平均点の順位計算 (★追加) ---
    all_avgs = db.session.query(Score.event_name, Score.player_id, func.avg(Score.total)).group_by(Score.event_name, Score.player_id).all()
    avg_map = {}
    for event, pid, val in all_avgs:
        if event not in avg_map: avg_map[event] = []
        # 平均点は計算誤差で桁が多くなることがあるので丸める
        avg_map[event].append(round(val, 1))
    
    for event in avg_map:
        avg_map[event].sort(reverse=True)

    # --- C. 本人の順位を埋め込む ---
    for event, data in summary_data.items():
        # ベスト順位
        if event in best_map:
            try:
                # indexは0始まりなので+1
                data['rank_best'] = best_map[event].index(data['max']) + 1
                data['total_players'] = len(best_map[event])
            except ValueError: pass
        
        # 平均順位 (★追加)
        if event in avg_map:
            try:
                data['rank_avg'] = avg_map[event].index(data['avg']) + 1
                # 参加人数はベストと同じはずだが念のため
                if data['total_players'] == '-':
                    data['total_players'] = len(avg_map[event])
            except ValueError: pass

    # 2. グラフ用データ
    unique_dates = sorted(list(set([s.date.strftime('%Y/%m/%d') for s in scores])))
    event_map = {}
    for s in scores:
        d = s.date.strftime('%Y/%m/%d')
        if s.event_name not in event_map: event_map[s.event_name] = {}
        event_map[s.event_name][d] = s.total
    
    graph_datasets = []
    
    event_colors = {
        'AR60':   'rgba(218, 165, 32, 1)',
        'SB3x20': 'rgba(0, 100, 0, 1)',
        'P60':    'rgba(184, 0, 163, 1)',
        'AP60':   'rgba(13, 0, 255, 1)',
        'BP':     'rgba(108, 92, 231, 1)'
    }
    fallback_colors = ['rgba(54, 162, 235, 1)', 'rgba(255, 99, 132, 1)', 'rgba(75, 192, 192, 1)']

    for i, (event_name, date_score_map) in enumerate(event_map.items()):
        data_list = []
        for d in unique_dates:
            data_list.append(date_score_map.get(d, None))
        color = event_colors.get(event_name, fallback_colors[i % len(fallback_colors)])
        graph_datasets.append({
            'label': event_name, 'data': data_list,
            'borderColor': color, 'backgroundColor': color.replace('1)', '0.1)'),
            'tension': 0, 'spanGaps': True
        })

    # 3. チーム目標
    goals_query = TeamGoal.query.filter_by(gender=player.gender).all()
    player_goals = {g.event_name: g.target_score for g in goals_query}

    return render_template('player.html', 
                           player=player, scores=scores, summary_data=summary_data, 
                           graph_labels=unique_dates, graph_datasets=graph_datasets, 
                           player_goals=player_goals)

@app.route('/edit/<int:score_id>', methods=['GET', 'POST'])
def edit_score(score_id):
    score = Score.query.get_or_404(score_id)
    if request.method == 'POST':
        s = [float(request.form.get(f's{i}',0)) for i in range(1,7)]
        score.s1, score.s2, score.s3, score.s4, score.s5, score.s6 = s
        score.total = sum(s)
        db.session.commit()
        return redirect(url_for('player_detail', player_id=score.player_id))
    return render_template('edit.html', score=score)

@app.route('/delete/<int:score_id>', methods=['POST'])
def delete_score(score_id):
    score = Score.query.get_or_404(score_id)
    pid = score.player_id
    db.session.delete(score)
    db.session.commit()
    return redirect(url_for('player_detail', player_id=pid))

@app.route('/ranking')
def ranking():
    target_events = ['AR60', 'SB3x20', 'P60']
    today = datetime.now().date()
    start_year = today.year - 1 if today.month < 4 else today.year
    current_start = datetime(start_year, 4, 1).date()

    def get_rank_data(start_date=None):
        # 1. 集計クエリ (平均と最大を取得)
        q = db.session.query(
            Player.name, Player.gender, Player.entry_year, Player.id, Score.event_name, 
            func.avg(Score.total), func.max(Score.total), func.count(Score.id)
        ).join(Player)
        
        if start_date:
            q = q.filter(Score.date >= start_date)
            
        rows = q.group_by(Player.id, Score.event_name).all()

        # 2. データの箱を用意
        # data[種目][性別]['avg'] = [平均順リスト]
        # data[種目][性別]['max'] = [最高順リスト]
        data = {e: {'男': {'avg': [], 'max': []}, '女': {'avg': [], 'max': []}} for e in target_events}
        
        # 一旦リストにまとめる
        temp_list = {e: {'男': [], '女': []} for e in target_events}
        
        for n, g, y, pid, e, avg, mx, c in rows:
            if e in target_events and g in ['男', '女']:
                stat = {
                    'name': n, 
                    'id': pid, 
                    'year': y, 
                    'avg': round(avg, 1), 
                    'max': round(mx, 1), 
                    'count': c
                }
                temp_list[e][g].append(stat)
        
        # 3. ソートして格納
        for e in target_events:
            for g in ['男', '女']:
                # 平均点順 (降順)
                data[e][g]['avg'] = sorted(temp_list[e][g], key=lambda x: x['avg'], reverse=True)
                # 最高点順 (降順)
                data[e][g]['max'] = sorted(temp_list[e][g], key=lambda x: x['max'], reverse=True)
                
        return data

    return render_template('ranking.html', 
                           rankings_current=get_rank_data(current_start), 
                           rankings_all=get_rank_data(None), 
                           current_year=start_year)

@app.route('/matches')
def matches():
    # 1. 大会名の一覧を取得 (重複なし)
    results = db.session.query(Score.match_name).distinct().all()
    unique_names = [r[0] for r in results]

    # 2. 指定された順番で並び替え
    custom_order = [
        '春季関東大会', '選抜', '東京六大学（春）', '新人BR大会', '東日本学生', 
        '秋季関東大会', '東京六大学（秋）', '東西六大学', '全日本', '新人戦', '早慶戦'
    ]

    def get_rank(name):
        for i, keyword in enumerate(custom_order):
            if keyword in name: return i
        return 999 # リストにない大会は後ろへ

    sorted_names = sorted(unique_names, key=get_rank)

    return render_template('matches.html', match_names=sorted_names)

@app.route('/match/<path:match_name>/years')
def match_years(match_name):
    scores = Score.query.filter_by(match_name=match_name).order_by(Score.date.desc()).all()
    
    # 1. テーブル表示用データ (既存ロジック)
    years_data = {}
    is_sokeisen = '早慶戦' in match_name
    
    # 2. グラフ用データ集計箱 { 2024: {'AR60 男': 1850.5, ...}, 2023: ... }
    history_data = {} 
    
    for s in scores:
        ay = s.date.year if s.date.month >= 4 else s.date.year - 1
        
        # --- テーブル用 ---
        if ay not in years_data:
            years_data[ay] = {'start_date': s.date, 'end_date': s.date, 'regulars': {}}
        if s.date < years_data[ay]['start_date']: years_data[ay]['start_date'] = s.date
        if s.date > years_data[ay]['end_date']: years_data[ay]['end_date'] = s.date
        
        # --- グラフ & テーブル用 (Regular集計) ---
        if s.category == 'Regular':
            if is_sokeisen:
                key = s.event_name # 例: AR60
            else:
                key = f"{s.event_name} {s.player.gender}" # 例: AR60 男
            
            # テーブル用リスト作成
            if key not in years_data[ay]['regulars']:
                years_data[ay]['regulars'][key] = []
            if s.player.name not in years_data[ay]['regulars'][key]:
                years_data[ay]['regulars'][key].append(s.player.name)
            
            # グラフ用合計点計算
            if ay not in history_data: history_data[ay] = {}
            if key not in history_data[ay]: history_data[ay][key] = 0.0
            
            history_data[ay][key] += s.total
            history_data[ay][key] = round(history_data[ay][key], 1)

    # テーブル用: 年度の降順
    sorted_years_table = sorted(years_data.items(), key=lambda x: x[0], reverse=True)
    
    # --- 3. グラフ用データセットの作成 ---
    # 年度の昇順 (グラフは左から右へ時系列)
    sorted_years_graph = sorted(history_data.keys())
    
    # 全てのキー(種目+性別)を抽出
    all_keys = set()
    for y in history_data:
        for k in history_data[y]:
            all_keys.add(k)
    sorted_keys = sorted(list(all_keys)) # AR60 女, AR60 男... の順
    
    chart_datasets = []
    
    for key in sorted_keys:
        # データ配列作成 (該当年になければ null)
        data_list = []
        for y in sorted_years_graph:
            data_list.append(history_data[y].get(key, None))
        
        # 色設定
        color = '#636e72'
        if 'AR60' in key: color = 'rgba(218, 165, 32, 1)' # Gold
        elif 'SB3x20' in key: color = 'rgba(0, 100, 0, 1)' # DarkGreen
        elif 'P60' in key: color = 'rgba(184, 0, 163, 1)' # Purple
        
        # 線種設定 (女子は点線)
        border_dash = []
        if '女' in key:
            border_dash = [5, 5] # 5px線, 5px空白 の繰り返し
            
        chart_datasets.append({
            'label': key,
            'data': data_list,
            'borderColor': color,
            'backgroundColor': color, # 点の色
            'borderDash': border_dash, # ★ここで点線を指定
            'fill': False,
            'tension': 0, # 直線
            'spanGaps': True
        })

    return render_template('match_years.html', 
                           match_name=match_name, 
                           years_data=sorted_years_table,
                           chart_labels=sorted_years_graph, # グラフ横軸(年度)
                           chart_datasets=chart_datasets)   # グラフデータ

@app.route('/match/<path:match_name>/<int:year>')
def match_result(match_name, year):
    start_date = datetime(year, 4, 1).date()
    end_date = datetime(year + 1, 3, 31).date()
    
    scores = Score.query.filter(
        Score.match_name == match_name,
        Score.date >= start_date,
        Score.date <= end_date
    ).join(Player).all()
    
    # データを格納する箱
    # 早慶戦以外は男女で分ける
    team_results_male = {}   # 男子用
    team_results_female = {} # 女子用
    team_results_mixed = {}  # 早慶戦(混合)用
    
    individual_results = {}
    
    is_sokeisen = '早慶戦' in match_name

    for s in scores:
        # 個人戦リストへ追加
        if s.event_name not in individual_results:
            individual_results[s.event_name] = []
        individual_results[s.event_name].append(s)
        
        # 団体戦集計
        if s.category == 'Regular':
            if is_sokeisen:
                # 早慶戦: 混合
                key = s.event_name # "AR60" など
                target_dict = team_results_mixed
            else:
                # 通常: 男女別
                # キーは競技名だけにする (表示側で「男子」「女子」と分けるため)
                key = s.event_name
                if s.player.gender == '男':
                    target_dict = team_results_male
                else:
                    target_dict = team_results_female
            
            if key not in target_dict:
                target_dict[key] = {'total': 0.0, 'members': []}
            
            target_dict[key]['total'] += s.total
            target_dict[key]['total'] = round(target_dict[key]['total'], 1)
            target_dict[key]['members'].append(s)

    # 絞り込み処理
    if is_sokeisen:
        target_keys = ['AR60', 'SB3x20', 'P60']
        team_results_mixed = {k: v for k, v in team_results_mixed.items() if k in target_keys}
        # 混合の場合は mixed だけを使う
        display_mode = 'mixed'
    else:
        # 通常: AR60, SB3x20
        target_keys = ['AR60', 'SB3x20']
        team_results_male = {k: v for k, v in team_results_male.items() if k in target_keys}
        team_results_female = {k: v for k, v in team_results_female.items() if k in target_keys}
        display_mode = 'separate'

    # 個人戦ソート
    for event in individual_results:
        individual_results[event].sort(key=lambda x: x.total, reverse=True)

    return render_template('match_result.html', 
                           match_name=match_name, 
                           year=year,
                           team_results_male=team_results_male,     # 男子データ
                           team_results_female=team_results_female, # 女子データ
                           team_results_mixed=team_results_mixed,   # 混合データ
                           display_mode=display_mode,               # 表示モード
                           individual_results=individual_results)

# --- バックアップ用ルート ---
@app.route('/download_db')
def download_db():
    # 1. まず「instance」フォルダの中を探す (最近のFlaskの標準的な場所)
    db_path_in_instance = os.path.join(app.instance_path, 'shooting.db')
    
    if os.path.exists(db_path_in_instance):
        return send_file(db_path_in_instance, as_attachment=True)
    
    # 2. なければ、main.py と同じ場所を探す
    db_path_local = os.path.join(os.path.dirname(__file__), 'shooting.db')
    
    if os.path.exists(db_path_local):
        return send_file(db_path_local, as_attachment=True)

    # 3. どちらにもない場合
    return "エラー: データベースファイルが見つかりませんでした。(shooting.db)", 404

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5001)