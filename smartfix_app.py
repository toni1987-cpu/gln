
import streamlit as st
import sqlite3
import pandas as pd
import tensorflow as tf
import numpy as np
from PIL import Image
from datetime import datetime
import os
import tempfile

DB_PATH = "smartfix.db"
IMG_DIR = "imagens_upload"
os.makedirs(IMG_DIR, exist_ok=True)

def criar_bd():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS operadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operador TEXT,
            molde TEXT,
            cavidade TEXT,
            defeito TEXT,
            turno TEXT,
            solucao TEXT,
            tipo_equipamento TEXT,
            resultado TEXT,
            confianca REAL,
            data TEXT,
            imagem_nome TEXT
        )
    ''')
    conn.commit()
    conn.close()

@st.cache_resource
def carregar_modelo(modelo_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as tmp_file:
        tmp_file.write(modelo_file.read())
        modelo_path = tmp_file.name
    return tf.keras.models.load_model(modelo_path)

def classificar_imagem(img_path, modelo):
    img = Image.open(img_path).convert("RGB").resize((224, 224))
    img_array = np.expand_dims(np.array(img) / 255.0, axis=0)
    pred = modelo.predict(img_array)[0][0]
    conf = pred if pred >= 0.5 else 1 - pred
    resultado = "NOK" if pred >= 0.5 else "OK"
    return resultado, conf

criar_bd()
st.title("GLN SmartFix")

if "user" not in st.session_state:
    st.subheader("Login")
    nome = st.text_input("Operador")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM operadores WHERE nome=? AND senha=?", (nome, senha))
        resultado = c.fetchone()
        conn.close()
        if resultado:
            st.session_state.user = nome
            st.experimental_rerun()
        else:
            st.error("Credenciais inválidas")
else:
    st.success(f"Bem-vindo, {st.session_state.user}")
    st.sidebar.button("Logout", on_click=lambda: st.session_state.pop("user"))

    st.sidebar.subheader("🔁 Carregar modelo .h5")
    modelo_file = st.sidebar.file_uploader("Modelo (.h5)", type=["h5"])
    if modelo_file:
        try:
            modelo = carregar_modelo(modelo_file)
            st.sidebar.success("Modelo carregado com sucesso!")
            st.session_state.modelo = modelo
        except Exception as e:
            st.sidebar.error(f"Erro ao carregar modelo: {e}")

    if "modelo" in st.session_state:
        st.subheader("📷 Classificar e Registar Defeito")
        molde = st.text_input("Código do molde")
        cavidade = st.text_input("Cavidade")
        defeito = st.text_input("Defeito observado")
        turno = st.selectbox("Turno", ["Turno A", "Turno B", "Turno C"])
        solucao = st.text_area("Solução aplicada")
        tipo_eq = st.selectbox("Tipo de equipamento", ["Máquina", "Molde", "Periférico"])
        imagem = st.file_uploader("Imagem", type=["jpg", "jpeg", "png"])

        if st.button("Classificar e Guardar") and all([molde, cavidade, defeito, solucao, tipo_eq, imagem]):
            nome_ficheiro = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{imagem.name}"
            img_path = os.path.join(IMG_DIR, nome_ficheiro)
            with open(img_path, "wb") as f:
                f.write(imagem.read())
            resultado, conf = classificar_imagem(img_path, st.session_state.modelo)
            st.image(img_path, caption=f"Resultado: {resultado} ({conf:.2%})")

            conn = sqlite3.connect(DB_PATH)
            conn.execute('''
                INSERT INTO historico (operador, molde, cavidade, defeito, turno, solucao, tipo_equipamento, resultado, confianca, data, imagem_nome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (st.session_state.user, molde, cavidade, defeito, turno, solucao, tipo_eq, resultado, conf, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nome_ficheiro))
            conn.commit()
            conn.close()
            st.success("Registado com sucesso!")

        st.subheader("📊 Histórico")
        conn = sqlite3.connect(DB_PATH)
        historico = pd.read_sql_query("SELECT * FROM historico ORDER BY data DESC", conn)
        conn.close()
        st.dataframe(historico)
        st.download_button("📥 Exportar CSV", data=historico.to_csv(index=False), file_name="historico_smartfix.csv", mime="text/csv")
    else:
        st.warning("Por favor, carregue um modelo .h5 no menu lateral.")
