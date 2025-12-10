import streamlit as st
import pandas as pd
import plotly.express as px
import textwrap
from utils.db import get_survey_by_id, save_ai_result
from utils.ai_helper import get_ai_analysis, analyze_whole_survey

# --- НАЛАШТУВАННЯ ---
st.set_page_config(page_title="Dashboard", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>[data-testid="stSidebar"] {display: none;}</style>""", unsafe_allow_html=True)

# --- ДОПОМІЖНІ ФУНКЦІЇ ---
def extract_rating_number(series):
    return series.astype(str).apply(lambda x: int(x.split()[0]) if x.split()[0].isdigit() else 0)

def shorten_label(text, width=40):
    return textwrap.shorten(str(text), width=width, placeholder="...")

def generate_insight(df, question_type):
    if df.empty: return "Немає даних", "error", "-", 0
    if question_type == 'text': return f"Отримано {len(df)} відповідей.", "info", str(len(df)), 0
    if question_type == 'matrix': return "Матричне питання.", "info", "Matrix", 0

    sorted_df = df.sort_values(by='Кількість', ascending=False)
    winner = sorted_df.iloc[0]
    total = df['Кількість'].sum()
    if total == 0: return "Err", "error", "-", 0
    
    percent = (winner['Кількість'] / total) * 100
    
    if question_type == 'rating':
        try:
            vals = extract_rating_number(df['Відповідь'])
            avg = (vals * df['Кількість']).sum() / total
            status = "success" if avg >= 4 else "warning"
            return f"Середня: **{avg:.1f}**", status, f"{avg:.1f}", avg*20
        except: return "Помилка", "warning", "-", 0
        
    return f"Лідер: **{winner['Відповідь'][:20]}...**", "success", str(winner['Кількість']), percent

# --- ГОЛОВНА ЛОГІКА ---

if st.button("⬅️ Назад до стрічки"):
    st.switch_page("main.py")

survey_id = st.session_state.get("selected_survey_id")
if not survey_id: st.stop()
survey = get_survey_by_id(survey_id)

st.title(survey.get('title'))
st.caption(survey.get('description'))

# === БЛОК ПАКЕТНОГО АНАЛІЗУ (BATCH) ===
# Перевіряємо, чи є хоча б одне питання без аналізу
questions = survey.get('questions', [])
missing_analysis = any(not q.get('ai_analysis') for q in questions)

if missing_analysis:
    with st.container(border=True):
        c_text, c_btn = st.columns([3, 1])
        c_text.info("💡 Ви можете згенерувати висновки для всього опитування одним кліком (Batch Processing).")
        if c_btn.button("⚡ Проаналізувати ВСЕ", type="primary", width='stretch'):
            with st.spinner("Gemini аналізує все опитування (1 запит)..."):
                batch_results = analyze_whole_survey(survey.get('title'), questions)
                
                if batch_results:
                    bar = st.progress(0)
                    for idx, text in batch_results.items():
                        # idx вже є число, тому не потрібно конвертувати
                        save_ai_result(survey.get('id'), idx, text)
                        bar.progress((idx + 1) / len(batch_results))
                    st.success("Готово!")
                    st.rerun()
                else:
                    st.error("Помилка генерації.")

st.divider()

# === ЦИКЛ ПО ПИТАННЯХ ===
for i, q in enumerate(questions):
    q_text = q.get('text', 'Питання')
    q_type = q.get('type', 'single_choice')
    q_data = q.get('data', {})
    
    if not q_data: continue

    # DataFrame підготовка
    if q_type == 'text':
        data_list = q_data.get("answers", []) if isinstance(q_data, dict) else []
        df = pd.DataFrame(data_list, columns=['Text'])
    elif q_type == 'matrix':
        df = pd.DataFrame() 
    else:
        df = pd.DataFrame(list(q_data.items()), columns=['Відповідь', 'Кількість'])
        df['Label'] = df['Відповідь'].apply(lambda x: shorten_label(x, 50))

    with st.container(border=True):
        st.subheader(f"{i+1}. {q_text}")
        
        if q_type == 'matrix': col_viz = st.container(); col_info = None
        else: col_viz, col_info = st.columns([2, 1])
        
        # ВІЗУАЛІЗАЦІЯ
        with col_viz:
            if q_type == 'text':
                st.markdown("##### 💬 Відгуки")
                if not df.empty:
                    with st.container(height=300):
                        for txt in df['Text']:
                            if len(str(txt)) > 1:
                                with st.container(border=True): st.write(txt)
                else: st.caption("Пусто.")

            elif q_type == 'matrix':
                matrix_rows = []
                for sub_q, sub_votes in q_data.items():
                    tot = sum(sub_votes.values())
                    for ans, cnt in sub_votes.items():
                        pct = (cnt / tot * 100) if tot > 0 else 0
                        matrix_rows.append({"Питання": sub_q, "Відповідь": ans, "Кількість": cnt, "Відсоток": pct})
                df_m = pd.DataFrame(matrix_rows)
                if not df_m.empty:
                    fig = px.bar(df_m, x="Відсоток", y="Питання", color="Відповідь", orientation='h', text_auto='.0f')
                    fig.update_layout(height=300 + (len(q_data)*30))
                    st.plotly_chart(fig, width='stretch', key=f"chart_matrix_{i}")

            elif q_type == 'multiple_choice':
                df = df.sort_values('Кількість')
                fig = px.bar(df, x='Кількість', y='Label', orientation='h', text='Кількість')
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch', key=f"chart_multi_{i}")

            elif q_type in ['single_choice', 'rating']:
                fig = px.pie(df, values='Кількість', names='Label', hole=0.4) if q_type == 'single_choice' \
                 else px.bar(df, x='Label', y='Кількість', color='Кількість')
                st.plotly_chart(fig, width='stretch', key=f"chart_q{i}")

        # СТАТИСТИКА
        if col_info:
            with col_info:
                txt, status, val, pct = generate_insight(df, q_type)
                st.markdown("##### Статистика")
                if status == 'success': st.success(txt)
                elif status == 'warning': st.warning(txt)
                else: st.info(txt)
                if q_type != 'text':
                    st.metric("Показник", val)
                    if q_type != 'rating': st.progress(min(int(pct), 100))

        # AI ВИСНОВОК (Збережений або Кнопка)
        st.divider()
        existing_ai = q.get('ai_analysis')
        
        if existing_ai:
            st.markdown("##### 🤖 Висновок AI:")
            st.info(existing_ai, icon="💡")
        else:
            if st.button(f"✨ Аналізувати питання", key=f"btn_{i}"):
                with st.spinner("Аналіз..."):
                    # Підготовка даних для поодинокого запиту
                    if q_type == 'text': d = df['Text'].tolist(); dt = 'text'
                    elif q_type == 'matrix': d = str(q_data); dt = 'matrix'
                    else: d = dict(zip(df['Відповідь'], df['Кількість'])); dt = q_type
                    
                    res = get_ai_analysis(q_text, d, dt)
                    save_ai_result(survey.get('id'), i, res)
                    st.rerun()