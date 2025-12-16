import streamlit as st
import hmac

def check_password():
    """
    Повертає `True`, якщо користувач ввід правильний пароль.
    В іншому випадку показує поле введення пароля і зупиняє виконання скрипта.
    """
    def password_entered():
        """Перевіряє, чи введений пароль збігається з секретним."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["general"]["admin_password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Не зберігаємо пароль у стані
        else:
            st.session_state["password_correct"] = False

    # Якщо пароль ще не перевірено або він неправильний
    if "password_correct" not in st.session_state:
        # Перший запуск, показуємо поле вводу
        st.text_input("🔑 Введіть пароль адміністратора", type="password", on_change=password_entered, key="password")
        st.stop()  # Зупиняємо виконання, нічого нижче не покажеться
        return False
        
    elif not st.session_state["password_correct"]:
        # Пароль введено неправильно
        st.text_input("🔑 Введіть пароль адміністратора", type="password", on_change=password_entered, key="password")
        st.error("😕 Невірний пароль")
        st.stop()  # Зупиняємо виконання
        return False
        
    # Пароль вірний
    return True