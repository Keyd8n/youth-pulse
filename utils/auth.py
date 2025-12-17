import streamlit as st
import hmac

def check_password():
    def password_entered():
        if hmac.compare_digest(st.session_state["password"], st.secrets["general"]["admin_password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔑 Введіть пароль адміністратора", type="password", on_change=password_entered, key="password")
        st.stop()
        return False
        
    elif not st.session_state["password_correct"]:
        st.text_input("🔑 Введіть пароль адміністратора", type="password", on_change=password_entered, key="password")
        st.error("😕 Невірний пароль")
        st.stop()
        return False

    return True