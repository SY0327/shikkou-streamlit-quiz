import streamlit as st
import csv
import random

# --- 定数 ---
QUESTIONS_FILE = 'questions.csv'

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
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            required_headers = ["問題No", "難易度", "問題", "選択肢1", "選択肢2", "選択肢3", "選択肢4", "正解"]
            if not all(header in reader.fieldnames for header in required_headers):
                st.error("CSVファイルのヘッダーが不足しています。以下のヘッダーが必要です: " + ", ".join(required_headers))
                return []

            for row_num, row in enumerate(reader, 2): # 2行目からカウント開始
                try:
                    choices = [row[f'選択肢{i}'] for i in range(1, 5) if row.get(f'選択肢{i}')]
                    
                    # 正解インデックスの検証
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
        st.error(f"エラー: ファイル '{filename}' が見つかりません。'{filename}' が '{st.secrets['PWD'] if 'PWD' in st.secrets else '現在実行中のディレクトリ'}' に存在するか確認してください。")
        return []
    except Exception as e:
        st.error(f"ファイルの読み込み中に予期せぬエラーが発生しました: {e}")
        return []
    
    if not questions:
        st.warning("CSVファイルから有効な問題が読み込まれませんでした。ファイルの内容を確認してください。")

    return questions

# --- クイズ管理関数 ---
def start_quiz():
    """クイズを開始・リセットする関数"""
    st.session_state.questions = load_questions_from_csv(QUESTIONS_FILE)
    if not st.session_state.questions:
        st.session_state.quiz_started = False # 問題がないのでクイズを開始しない
        return

    random.shuffle(st.session_state.questions) # 問題をシャッフル
    st.session_state.current_question_index = 0
    st.session_state.score = 0
    st.session_state.answered_details = []
    st.session_state.quiz_started = True
    st.session_state.last_answer_correct = None
    st.session_state.last_answer_comment = ""
    st.session_state.show_feedback = False
    st.rerun() # クイズ開始後、画面を更新して最初の問題を表示

def reset_quiz_state():
    """クイズの状態を初期値にリセットする関数"""
    st.session_state.quiz_started = False
    st.session_state.questions = [] # 問題リストもクリア
    st.session_state.current_question_index = 0
    st.session_state.score = 0
    st.session_state.answered_details = []
    st.session_state.last_answer_correct = None
    st.session_state.last_answer_comment = ""
    st.session_state.show_feedback = False

# --- UI表示関数 ---
def display_start_screen():
    """クイズの開始画面を表示する"""
    st.write("下のボタンを押してクイズを開始してください。")
    if st.button("クイズ開始"):
        start_quiz()

def display_question():
    """現在の問題を表示し、ユーザーの回答を受け付ける"""
    total_questions = len(st.session_state.questions)
    current_idx = st.session_state.current_question_index

    # 全問終了した場合
    if current_idx >= total_questions:
        display_results()
        return

    question_data = st.session_state.questions[current_idx]

    st.subheader(f"問題 {current_idx + 1} / {total_questions}")
    st.markdown(f"**難易度:** <span style='background-color:#E0F7FA; padding: 4px 8px; border-radius: 5px;'>{question_data['difficulty']}</span>", unsafe_allow_html=True)
    st.write("") # スペース
    st.markdown(f"### {question_data['question_text']}") # 問題文を大きく

    # 前回回答のフィードバックを表示
    if st.session_state.show_feedback:
        st.write("---")
        if st.session_state.last_answer_correct:
            st.success("🎉 正解！")
        else:
            st.error("残念、不正解...")
        
        if st.session_state.last_answer_comment:
            st.info(f"**コメント:** {st.session_state.last_answer_comment}")
        st.write("---")
        st.session_state.show_feedback = False # フィードバック表示後リセット

    # 回答選択フォーム
    with st.form(key=f"question_form_{question_data['id']}_{current_idx}"):
        user_choice_label = "選択肢を選んでください:"
        # ラジオボタンのキーをユニークに設定
        user_choice_text = st.radio(
            user_choice_label,
            question_data['choices'],
            index=None, # 初期選択なし
            key=f"radio_{question_data['id']}_{current_idx}"
        )
        submitted = st.form_submit_button("回答する")

        if submitted:
            if user_choice_text is None:
                st.warning("回答を選択してください。")
                # st.rerun() # warningを出すだけなのでrerunは不要
            else:
                process_answer(question_data, user_choice_text)
                # process_answer内でst.rerun()されるため、ここでは何もしない

def process_answer(question_data, user_choice_text):
    """ユーザーの回答を処理し、次の問題へ進む準備をする"""
    user_choice_index = question_data['choices'].index(user_choice_text)
    is_correct = (user_choice_index == question_data['correct_answer_index'])

    if is_correct:
        st.session_state.score += 1

    # 回答詳細とフィードバック情報を保存
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
    st.session_state.show_feedback = True # 次の描画でフィードバックを表示する

    st.session_state.current_question_index += 1
    st.rerun() # 画面を再描画して次の問題（または結果）へ

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
        reset_quiz_state() # 全ての状態をリセット
        st.rerun() # アプリをリフレッシュしてスタート画面へ

# --- メイン関数 ---
def main():
    st.set_page_config(page_title="4択クイズアプリ", layout="centered")
    st.title("💡 4択クイズアプリ")

    if not st.session_state.quiz_started:
        display_start_screen()
    else:
        display_question()

# --- アプリケーションのエントリーポイント ---
if __name__ == '__main__':
    main()