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

# --- データ読み込み関数 ---
@st.cache_data(show_spinner="問題を読み込み中...") # データキャッシュで高速化
def load_questions_from_csv(filename):
    """
    CSVファイルから4択問題を読み込む関数。
    問題データの検証も行う。
    """
    questions = []
    # ファイルが存在しない場合、ヘッダーのみのファイルを作成する
    if not os.path.exists(filename):
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(CSV_HEADERS)
            st.info(f"'{filename}'が見つからなかったため、新しく作成しました。サイドバーから問題を追加してください。")
            return []
        except Exception as e:
            st.error(f"'{filename}'の作成中にエラーが発生しました: {e}")
            return []
    
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # ヘッダーの検証（ステータス列は任意とするため、必須ヘッダーから除外してチェック）
            required_headers = [h for h in CSV_HEADERS if h != 'ステータス']
            if not all(header in reader.fieldnames for header in required_headers):
                st.error("CSVファイルのヘッダーが正しくありません。必要なヘッダー: " + ", ".join(required_headers))
                return []

            for row_num, row in enumerate(reader, 2): # 2行目からカウント開始
                # ステータスが「無効」の問題をスキップする
                # .get()を使い、ステータス列がない場合や空の場合は「有効」と見なす
                if row.get('ステータス', '有効').strip() == '無効':
                    continue # この問題は警告なしでスキップ

                try:
                    # 空の行をスキップ
                    if not any(row.values()):
                        continue

                    choices = [row[f'選択肢{i}'] for i in range(1, 5) if row.get(f'選択肢{i}')]
                    
                    # 以降のバリデーションは「有効」な問題に対してのみ実行される
                    if len(choices) < 4:
                         st.warning(f"問題No.{row.get('問題No', '不明')} (CSVの{row_num}行目): 選択肢が4つ未満です。この問題をスキップします。")
                         continue
                         
                    correct_idx_str = row.get('正解')
                    if not correct_idx_str:
                        st.warning(f"問題No.{row.get('問題No', '不明')} (CSVの{row_num}行目): '正解'が空欄です。この問題をスキップします。")
                        continue
                    
                    correct_idx = int(correct_idx_str) - 1 # 0-indexedに変換
                    
                    if not (0 <= correct_idx < len(choices)):
                        st.warning(f"問題No.{row.get('問題No', '不明')} (CSVの{row_num}行目): '正解'が選択肢の範囲外です ({correct_idx_str})。この問題をスキップします。")
                        continue

                    questions.append({
                        'id': row.get('問題No', str(len(questions) + 1)),
                        'difficulty': row.get('難易度', 'N/A'),
                        'question_text': row.get('問題', '問題文がありません'),
                        'choices': choices,
                        'correct_answer_index': correct_idx,
                        'comment': row.get('コメント', '')
                    })
                except ValueError:
                    st.warning(f"問題No.{row.get('問題No', '不明')} (CSVの{row_num}行目): '正解'が数字ではありません。この問題をスキップします。")
                except KeyError as e:
                    st.warning(f"問題No.{row.get('問題No', '不明')} (CSVの{row_num}行目): 必須の列が見つかりません ({e})。この問題をスキップします。")
                except Exception as e:
                    st.warning(f"問題No.{row.get('問題No', '不明')} (CSVの{row_num}行目): 問題の解析中に予期せぬエラーが発生しました: {e}。この問題をスキップします。")

    except FileNotFoundError:
        st.error(f"エラー: ファイル '{filename}' が見つかりません。")
        return []
    except Exception as e:
        st.error(f"ファイルの読み込み中に予期せぬエラーが発生しました: {e}")
        return []
    
    if not questions and os.path.exists(filename):
        st.warning("CSVファイルから有効な問題が読み込まれませんでした。ファイルの内容を確認してください。")

    return questions

def add_question_to_csv(new_question_data):
    """
    新しい問題のデータをCSVファイルに追記する関数
    """
    try:
        file_exists = os.path.isfile(QUESTIONS_FILE)
        is_empty = os.path.getsize(QUESTIONS_FILE) == 0 if file_exists else True
        
        with open(QUESTIONS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            if not file_exists or is_empty:
                writer.writeheader()
            writer.writerow(new_question_data)
        
        st.sidebar.success("問題が追加されました！")
        st.cache_data.clear() # キャッシュをクリアして変更を即時反映

    except Exception as e:
        st.sidebar.error(f"問題の追加中にエラーが発生しました: {e}")


def display_add_question_form():
    """
    サイドバーに問題追加フォームを表示する関数
    """
    st.sidebar.header("新しい問題を追加")

    with st.sidebar.form(key='add_question_form', clear_on_submit=True):
        st.write("以下の情報を入力してください。")
        
        q_no = st.text_input("問題No", help="例: Q001")
        q_difficulty = st.selectbox("難易度", ["SS", "S", "A","B","C"])
        q_text = st.text_area("問題文")
        q_choice1 = st.text_input("選択肢1")
        q_choice2 = st.text_input("選択肢2")
        q_choice3 = st.text_input("選択肢3")
        q_choice4 = st.text_input("選択肢4")
        q_correct = st.number_input("正解の選択肢番号", min_value=1, max_value=4, step=1)
        q_comment = st.text_area("コメント（任意）")
        
        q_status = st.selectbox("ステータス", ["有効", "無効"], help="「無効」に設定した問題はクイズに出題されません。")

        submitted = st.form_submit_button("この問題を追加する")

        if submitted:
            required_fields = [q_no, q_text, q_choice1, q_choice2, q_choice3, q_choice4]
            if not all(required_fields):
                st.sidebar.warning("必須項目（問題No, 問題文, 4つの選択肢）をすべて入力してください。")
            else:
                new_question = {
                    "問題No": q_no,
                    "難易度": q_difficulty,
                    "問題": q_text,
                    "選択肢1": q_choice1,
                    "選択肢2": q_choice2,
                    "選択肢3": q_choice3,
                    "選択肢4": q_choice4,
                    "正解": q_correct,
                    "コメント": q_comment,
                    "ステータス": q_status
                }
                add_question_to_csv(new_question)


# --- クイズ管理関数 ---
### 変更 ###: 引数を受け取り、渡された問題リストでクイズを開始するように変更
def start_quiz(available_questions, num_questions_to_ask):
    """
    選択された設定に基づいてクイズを開始・リセットする関数。
    引数として、出題候補の問題リストと出題数を受け取ります。
    """
    if not available_questions:
        st.session_state.quiz_started = False
        st.warning("クイズを開始できません。条件に合う有効な問題が見つかりません。")
        return

    # 問題をシャッフル
    random.shuffle(available_questions)
    
    # 指定された数の問題を選択
    st.session_state.questions = available_questions[:num_questions_to_ask]

    # セッション状態を初期化
    st.session_state.current_question_index = 0
    st.session_state.score = 0
    st.session_state.answered_details = []
    st.session_state.quiz_started = True
    st.session_state.last_answer_correct = None
    st.session_state.last_answer_comment = ""
    st.session_state.show_feedback = False
    st.rerun() 

def reset_quiz_state():
    """クイズの状態を初期値にリセットする関数"""
    st.session_state.quiz_started = False
    st.session_state.questions = [] 
    st.session_state.current_question_index = 0
    st.session_state.score = 0
    st.session_state.answered_details = []
    st.session_state.last_answer_correct = None
    st.session_state.last_answer_comment = ""
    st.session_state.show_feedback = False

# --- UI表示関数 ---
### 変更 ###: クイズの設定（難易度、問題数）UIを追加
def display_start_screen():
    """クイズの開始画面を表示し、設定を受け付ける"""
    st.header("クイズ設定")
    
    # 問題を一度読み込み、利用可能な難易度と問題数を取得
    all_questions = load_questions_from_csv(QUESTIONS_FILE)
    
    if not all_questions:
        st.warning("クイズを開始できません。有効な問題が1問も登録されていません。")
        st.info("💡 サイドバーから新しい問題を追加できます。")
        return

    # 利用可能な難易度のリストを作成 (重複を除きソート)
    available_difficulties = sorted(list(set(q['difficulty'] for q in all_questions)))

    # --- 設定フォーム ---
    with st.form(key='quiz_settings_form'):
        st.write("挑戦するクイズの条件を設定してください。")
        
        # 難易度選択
        selected_difficulties = st.multiselect(
            label="難易度（複数選択可）",
            options=available_difficulties,
            default=available_difficulties, # デフォルトで全て選択
        )

        # 選択された難易度で問題をフィルタリング
        if not selected_difficulties:
            # ユーザーが意図的にクリアした場合、全難易度を対象とする
            filtered_questions = all_questions
        else:
            filtered_questions = [q for q in all_questions if q['difficulty'] in selected_difficulties]

        # 出題数選択
        max_questions = len(filtered_questions)
        
        if max_questions > 0:
            num_questions = st.slider(
                label="出題数",
                min_value=1,
                max_value=max_questions,
                value=min(10, max_questions), # デフォルトは10問 or 最大数
                step=1
            )
            st.info(f"選択中の難易度では、最大 {max_questions} 問出題できます。")
        else:
            num_questions = 0
            st.warning("選択された難易度の問題がありません。別の難易度を選んでください。")

        # フォームの送信ボタン
        submitted = st.form_submit_button("クイズ開始！", type="primary", disabled=(max_questions == 0))

        if submitted:
            # start_quizにフィルタリング済みの問題リストと出題数を渡す
            start_quiz(filtered_questions, num_questions)


def display_question():
    """現在の問題を表示し、ユーザーの回答を受け付ける"""
    total_questions = len(st.session_state.questions)
    current_idx = st.session_state.current_question_index

    if current_idx >= total_questions:
        display_results()
        return

    question_data = st.session_state.questions[current_idx]

    st.subheader(f"問題 {current_idx + 1} / {total_questions}")
    st.markdown(f"**難易度:** <span style='background-color:#E0F7FA; padding: 4px 8px; border-radius: 5px;'>{question_data['difficulty']}</span>", unsafe_allow_html=True)
    st.write("")
    st.markdown(f"### {question_data['question_text']}") 

    if st.session_state.show_feedback:
        st.write("---")
        if st.session_state.last_answer_correct:
            st.success("🎉 正解！")
        else:
            st.error("残念、不正解...")
        
        if st.session_state.last_answer_comment:
            st.info(f"**コメント:** {st.session_state.last_answer_comment}")
        st.write("---")
        st.session_state.show_feedback = False

    with st.form(key=f"question_form_{question_data['id']}_{current_idx}"):
        user_choice_label = "選択肢を選んでください:"
        user_choice_text = st.radio(
            user_choice_label,
            question_data['choices'],
            index=None, 
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
    st.session_state.last_answer_correct = is_correct
    st.session_state.last_answer_comment = question_data['comment']
    st.session_state.show_feedback = True

    st.session_state.current_question_index += 1
    st.rerun()

def display_results():
    """クイズの結果を表示する"""
    st.header("クイズ終了！")
    total_questions = len(st.session_state.questions)
    
    if total_questions > 0:
        accuracy = (st.session_state.score / total_questions) * 100
        st.markdown(f"あなたのスコア: **{st.session_state.score} / {total_questions}**")
        st.markdown(f"正答率: **{accuracy:.2f}%**")
    else:
        st.warning("問題がありませんでした。")

    st.subheader("回答詳細")
    for i, detail in enumerate(st.session_state.answered_details):
        st.markdown(f"---")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**問題 {i + 1}:** {detail['question_text']}")
            user_answer_color = "green" if detail['is_correct'] else "red"
            st.markdown(f"あなたの回答: <span style='color:{user_answer_color};'>**{detail['user_choice_text']}**</span>", unsafe_allow_html=True)
            
            if not detail['is_correct']:
                st.markdown(f"正解: <span style='color:green;'>**{detail['correct_answer_text']}**</span>", unsafe_allow_html=True)
            
            if detail['comment']:
                st.markdown(f"<small>コメント: _{detail['comment']}_</small>", unsafe_allow_html=True)
        with col2:
            if detail['is_correct']:
                st.markdown("<span style='font-size: 3em;'>✅</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='font-size: 3em;'>❌</span>", unsafe_allow_html=True)
                
    st.markdown("---")
    if st.button("もう一度クイズを始める"):
        reset_quiz_state()
        st.rerun()

# --- メイン関数 ---
def main():
    st.set_page_config(page_title="4択クイズアプリ", layout="centered", initial_sidebar_state="expanded")
    st.title("4択クイズ‼️")

    # サイドバーに問題追加フォームを常に表示
    display_add_question_form()

    if not st.session_state.quiz_started:
        # クイズ開始前は設定画面を表示
        display_start_screen()
    else:
        # クイズ開始後は問題を表示
        display_question()

# --- アプリケーションのエントリーポイント ---
if __name__ == '__main__':
    main()
