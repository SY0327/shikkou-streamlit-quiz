import streamlit as st
import csv
import random
import os

# --- 定数 ---
QUESTIONS_FILE = 'questions.csv'
# CSVのヘッダーを定数として定義
CSV_HEADERS = ["問題No", "難易度", "問題", "選択肢1", "選択肢2", "選択肢3", "選択肢4", "正解", "コメント", "ステータス"]


# --- セッション状態の初期化 ---
# アプリが初めてロードされたとき、またはブラウザのキャッシュがクリアされたときにのみ実行
def initialize_session_state():
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False
    if 'questions' not in st.session_state:
        st.session_state.questions = []
    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0
    if 'score' not in st.session_state:
        st.session_state.score = 0
    if 'answered_details' not in st.session_state:
        st.session_state.answered_details = []
    if 'last_answer_correct' not in st.session_state: # 前回回答の正誤を保持
        st.session_state.last_answer_correct = None
    if 'last_answer_comment' not in st.session_state: # 前回回答のコメントを保持
        st.session_state.last_answer_comment = ""
    if 'show_feedback' not in st.session_state: # フィードバック表示フラグ
        st.session_state.show_feedback = False

initialize_session_state()

# --- データ読み込み/書き込み関数 ---

### 変更 ###: CSVから問題を読み込む機能を実装
@st.cache_data(show_spinner="問題を読み込み中...") # データキャッシュで高速化
def load_questions_from_csv(filename):
    """CSVファイルから問題を読み込み、辞書のリストとして返す"""
    if not os.path.exists(filename):
        return []
    
    questions = []
    try:
        with open(filename, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                try:
                    # 正解の選択肢番号を0ベースのインデックスに変換
                    correct_answer_index = int(row["正解"]) - 1
                    if not (0 <= correct_answer_index < 4):
                        st.warning(f"問題No {row.get('問題No', i+1)} の正解番号 '{row['正解']}' が無効です。スキップします。")
                        continue

                    questions.append({
                        'id': row.get("問題No", f"q{i}"),
                        'difficulty': row["難易度"],
                        'question_text': row["問題"],
                        'choices': [row["選択肢1"], row["選択肢2"], row["選択肢3"], row["選択肢4"]],
                        'correct_answer_index': correct_answer_index,
                        'comment': row["コメント"]
                    })
                except (ValueError, KeyError) as e:
                    st.warning(f"CSVファイルの行 {i+2} のフォーマットが不正です: {e}。スキップします。")
                    continue
    except Exception as e:
        st.error(f"ファイル '{filename}' の読み込み中にエラーが発生しました: {e}")
        return []
        
    return questions

### 変更 ###: CSVに新しい問題データを書き込む機能を実装
def add_question_to_csv(new_question_data):
    """新しい問題データをCSVファイルに追記する"""
    try:
        file_exists = os.path.exists(QUESTIONS_FILE)
        with open(QUESTIONS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            if not file_exists:
                writer.writeheader() # ファイルがなければヘッダーを書き込む
            writer.writerow(new_question_data)
        
        # データキャッシュをクリアして、新しい問題を即座に反映させる
        st.cache_data.clear()
        st.sidebar.success("問題が追加されました！")

    except Exception as e:
        st.sidebar.error(f"問題の追加中にエラーが発生しました: {e}")

### 変更 ###: サイドバーに問題追加フォームを表示する機能を実装
def display_add_question_form():
    """サイドバーに新しい問題を追加するフォームを表示する"""
    st.sidebar.header("新しい問題を追加")
    with st.sidebar.form(key='add_question_form', clear_on_submit=True):
        # 既存の問題数を読み込み、新しい問題Noを提案
        try:
            with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                # ヘッダー行を除いた行数をカウント
                num_existing_questions = max(0, len(f.readlines()) - 1)
        except FileNotFoundError:
            num_existing_questions = 0
        
        question_no = st.text_input("問題No", value=str(num_existing_questions + 1))
        difficulty = st.selectbox("難易度", options=["SS", "S", "A", "B", "C", "D"])
        question_text = st.text_area("問題文", height=100)
        choice1 = st.text_input("選択肢1")
        choice2 = st.text_input("選択肢2")
        choice3 = st.text_input("選択肢3")
        choice4 = st.text_input("選択肢4")
        correct_answer = st.radio("正解の選択肢番号", options=[1, 2, 3, 4], index=0, horizontal=True)
        comment = st.text_area("コメント（解説）", height=100)

        submitted = st.form_submit_button("問題を追加する")
        
        if submitted:
            # 簡単な入力値チェック
            if not all([question_no, difficulty, question_text, choice1, choice2, choice3, choice4, correct_answer]):
                st.sidebar.warning("すべての必須項目を入力してください。")
            else:
                new_question = {
                    "問題No": question_no,
                    "難易度": difficulty,
                    "問題": question_text,
                    "選択肢1": choice1,
                    "選択肢2": choice2,
                    "選択肢3": choice3,
                    "選択肢4": choice4,
                    "正解": correct_answer,
                    "コメント": comment,
                    "ステータス": "未回答" # 固定値
                }
                add_question_to_csv(new_question)


# --- クイズ管理関数 ---
### 変更 ###: クイズを開始するためのセッション状態設定処理を実装
def start_quiz(available_questions, num_questions_to_ask):
    """クイズを開始するためにセッション状態をセットアップする"""
    # 既存のクイズ状態をリセット
    reset_quiz_state(start_new=False) # 画面をリロードしないようにリセット

    st.session_state.quiz_started = True

    # 指定された数の問題をランダムに選択
    num_to_sample = min(num_questions_to_ask, len(available_questions))
    st.session_state.questions = random.sample(available_questions, num_to_sample)
    
    st.rerun() 

### 変更 ###: クイズの状態を完全にリセットする機能を実装
def reset_quiz_state(start_new=True):
    """セッション状態を初期値に戻す"""
    st.session_state.quiz_started = False
    st.session_state.questions = []
    st.session_state.current_question_index = 0
    st.session_state.score = 0
    st.session_state.answered_details = []
    st.session_state.last_answer_correct = None
    st.session_state.last_answer_comment = ""
    st.session_state.show_feedback = False
    
    # 「もう一度」ボタンから呼ばれた場合のみリロードする
    if start_new:
        st.rerun()

# --- UI表示関数 ---
def display_start_screen():
    """クイズの開始画面を表示し、設定を受け付ける"""
    st.header("クイズ設定")
    
    all_questions = load_questions_from_csv(QUESTIONS_FILE)
    
    if not all_questions:
        st.warning("クイズを開始できません。有効な問題が1問も登録されていません。")
        st.info("💡 サイドバーから新しい問題を追加できます。")
        return

    available_difficulties = sorted(list(set(q['difficulty'] for q in all_questions)))

    with st.form(key='quiz_settings_form'):
        st.write("挑戦するクイズの条件を設定してください。")
        
        selected_difficulties = st.multiselect(
            label="難易度（複数選択可）",
            options=available_difficulties,
            default=available_difficulties,
        )

        filtered_questions = [q for q in all_questions if q['difficulty'] in selected_difficulties]

        max_questions = len(filtered_questions)
        
        if max_questions > 0:
            num_questions = st.slider(
                label="出題数",
                min_value=1,
                max_value=max_questions,
                value=min(10, max_questions),
                step=1
            )
            st.info(f"選択中の難易度では、最大 {max_questions} 問出題できます。")
        else:
            num_questions = 0
            st.warning("選択された難易度の問題がありません。別の難易度を選んでください。")

        submitted = st.form_submit_button("クイズ開始！", type="primary", disabled=(max_questions == 0))

        if submitted:
            start_quiz(filtered_questions, num_questions)


def display_question():
    """現在の問題を表示し、ユーザーの回答を受け付ける"""
    total_questions = len(st.session_state.questions)
    current_idx = st.session_state.current_question_index

    if current_idx >= total_questions:
        display_results()
        return

    question_data = st.session_state.questions[current_idx]

    # 直前の問題のフィードバックを表示
    if st.session_state.show_feedback:
        if st.session_state.last_answer_correct:
            st.success("🎉 正解！")
        else:
            st.error("残念、不正解...")
        
        if st.session_state.last_answer_comment:
            st.info(f"**解説:** {st.session_state.last_answer_comment}")
        st.markdown("---")
        # フィードバック表示後はフラグをリセット
        st.session_state.show_feedback = False

    st.subheader(f"問題 {current_idx + 1} / {total_questions}")
    st.markdown(f"**難易度:** <span style='background-color:#E0F7FA; padding: 4px 8px; border-radius: 5px;'>{question_data['difficulty']}</span>", unsafe_allow_html=True)
    st.write("")
    st.markdown(f"### {question_data['question_text']}") 

    # フォームを使って回答を受け付ける
    # keyをユニークにすることで、毎回新しいフォームとして描画される
    with st.form(key=f"question_form_{question_data['id']}_{current_idx}"):
        user_choice_text = st.radio(
            "選択肢を選んでください:",
            question_data['choices'],
            index=None, # デフォルトで何も選択しない
            key=f"radio_{question_data['id']}_{current_idx}"
        )
        submitted = st.form_submit_button("回答する")

        if submitted:
            if user_choice_text is None:
                st.warning("回答を選択してください。")
            else:
                process_answer(question_data, user_choice_text)

def process_answer(question_data, user_choice_text):
    """ユーザーの回答を処理し、次の問題へ進む準備をする"""
    user_choice_index = question_data['choices'].index(user_choice_text)
    is_correct = (user_choice_index == question_data['correct_answer_index'])

    if is_correct:
        st.session_state.score += 1

    st.session_state.answered_details.append({
        'question_id': question_data['id'],
        'question_text': question_data['question_text'],
        'user_choice_text': user_choice_text,
        'correct_answer_text': question_data['choices'][question_data['correct_answer_index']],
        'is_correct': is_correct,
        'comment': question_data['comment']
    })
    
    # 次の問題表示の際にフィードバックを表示するための情報を保存
    st.session_state.last_answer_correct = is_correct
    st.session_state.last_answer_comment = question_data['comment']
    st.session_state.show_feedback = True

    # 次の問題へ
    st.session_state.current_question_index += 1
    st.rerun()

def display_results():
    """クイズの結果を表示する"""
    st.header("クイズ終了！")
    total_questions = len(st.session_state.questions)
    
    if total_questions > 0:
        accuracy = (st.session_state.score / total_questions) * 100
        st.markdown(f"### あなたのスコア: **{st.session_state.score} / {total_questions}**")
        st.progress(accuracy / 100)
        st.markdown(f"正答率: **{accuracy:.1f}%**")
    else:
        st.warning("問題がありませんでした。")

    st.subheader("回答詳細")
    for i, detail in enumerate(st.session_state.answered_details):
        with st.expander(f"問題 {i + 1}: {detail['question_text'][:30]}..."):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**問題文:** {detail['question_text']}")
                user_answer_color = "green" if detail['is_correct'] else "red"
                st.markdown(f"あなたの回答: <span style='color:{user_answer_color};'>**{detail['user_choice_text']}**</span>", unsafe_allow_html=True)
                
                if not detail['is_correct']:
                    st.markdown(f"正解: <span style='color:green;'>**{detail['correct_answer_text']}**</span>", unsafe_allow_html=True)
                
                if detail['comment']:
                    st.info(f"**解説:** {detail['comment']}")
            with col2:
                if detail['is_correct']:
                    st.markdown("<p style='font-size: 3em; text-align: center;'>✅</p>", unsafe_allow_html=True)
                else:
                    st.markdown("<p style='font-size: 3em; text-align: center;'>❌</p>", unsafe_allow_html=True)
                
    st.markdown("---")
    if st.button("もう一度クイズを始める", type="primary"):
        reset_quiz_state() # 引数なしで呼び出し、リロードして開始画面に戻る

# --- メイン関数 ---
def main():
    st.set_page_config(page_title="4択クイズ", layout="wide", initial_sidebar_state="expanded")
    st.title("4択クイズ")

    # サイドバーに問題追加フォームを常に表示
    display_add_question_form()

    # メインエリアの表示をクイズの進行状況に応じて切り替える
    if not st.session_state.quiz_started:
        display_start_screen()
    else:
        display_question()

# --- アプリケーションのエントリーポイント ---
if __name__ == '__main__':
    main()
