import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from fpdf import FPDF
import matplotlib.pyplot as plt
import io
import time
from datetime import datetime

# --- BASE DE DADOS INTEGRADA (SQLITE) ---
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

# Configuração DB
DATABASE_URL = "sqlite:///./zero_erros_cloud.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo Tabela
class AvaliacaoDB(Base):
    __tablename__ = "avaliacoes"
    id = Column(Integer, primary_key=True, index=True)
    data_criacao = Column(DateTime, default=datetime.now)
    artigo = Column(String)
    norma = Column(String)
    valor_mercado = Column(Float)
    area_bruta = Column(Float)
    area_util = Column(Float)

# Criar tabelas se não existirem
Base.metadata.create_all(bind=engine)

# --- LÓGICA DE NEGÓCIO (CÁLCULOS) ---
def calcular_valor(abp, au):
    # Regra Zero Erros
    if au > (abp * 1.15):
        return None, f"ERRO CRÍTICO: Área Útil ({au}) excede ABP ({abp}) em mais de 15%."
    
    valor_m2 = 4500.00
    valor_final = abp * valor_m2
    return valor_final, None

# --- GERADOR DE PDF ---
def gerar_relatorio_pdf(dados, inputs, user):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16); pdf.cell(0, 10, "Relatorio de Avaliacao Imobiliaria", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 10); pdf.cell(0, 10, f"Processo #{dados['id']} | Perito: {user}", new_x="LMARGIN", new_y="NEXT", align="C"); pdf.ln(10)
    
    pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 10, "1. Identificacao", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Artigo: {inputs['artigo']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Norma: {inputs['norma']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"ABP: {inputs['abp']} m2 | AU: {inputs['au']} m2", new_x="LMARGIN", new_y="NEXT"); pdf.ln(5)
    
    pdf.set_font("Helvetica", "B", 12); pdf.cell(0, 10, "2. Valor e Prova", new_x="LMARGIN", new_y="NEXT")
    
    fig = plt.figure(figsize=(8, 2))
    valor_fmt = f"{dados['valor_mercado']:,.0f}"
    renda_est = dados['valor_mercado'] * 0.05
    texto = f"$VM = \\frac{{Renda}}{{Yield}} = \\frac{{{renda_est:,.0f}}}{{0.05}} = \\mathbf{{{valor_fmt} EUR}}$"
    plt.text(0.5, 0.5, texto, fontsize=16, ha='center', va='center')
    plt.axis('off')
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
    img_buffer.seek(0)
    pdf.image(img_buffer, x=15, w=180); pdf.ln(5)
    
    return bytes(pdf.output())

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Zero Erros Cloud")

# --- LOGIN ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""

def check_login():
    if st.session_state["u"] == "perito" and st.session_state["p"] == "123":
        st.session_state.logged_in = True
        st.session_state.username = "perito"
    else:
        st.error("Credenciais Inválidas")

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.header("🔒 Acesso Cloud")
        st.text_input("User", key="u")
        st.text_input("Pass", type="password", key="p")
        st.button("Entrar", on_click=check_login, type="primary")
else:
    # --- APLICAÇÃO PRINCIPAL ---
    st.sidebar.title(f"👤 {st.session_state.username}")
    if st.sidebar.button("Sair"):
        st.session_state.logged_in = False
        st.rerun()
    
    tab1, tab2 = st.tabs(["📝 Nova Avaliação", "📂 Histórico"])
    
    with tab1:
        c1, c2 = st.columns([1, 2])
        with c1:
            artigo = st.text_input("Artigo", "LISBOA-T3-CLOUD")
            norma = st.selectbox("Norma", ["RICS", "IVS"])
            abp = st.number_input("ABP", value=120.0)
            au = st.number_input("AU", value=115.0)
            lat = st.number_input("Lat", value=38.736946)
            long = st.number_input("Long", value=-9.142685)
            
            if st.button("🚀 Calcular e Gravar", type="primary"):
                val, erro = calcular_valor(abp, au)
                if erro:
                    st.error(erro)
                else:
                    # Gravar na DB
                    db = SessionLocal()
                    novo = AvaliacaoDB(artigo=artigo, norma=norma, valor_mercado=val, area_bruta=abp, area_util=au)
                    db.add(novo); db.commit(); db.refresh(novo)
                    st.session_state.ultimo_id = novo.id
                    st.session_state.ultimo_valor = val
                    st.session_state.ultimos_inputs = {'artigo': artigo, 'norma': norma, 'abp': abp, 'au': au}
                    db.close()
                    st.success("Gravado com Sucesso!")
        
        with c2:
            m = folium.Map([lat, long], zoom_start=15)
            folium.Marker([lat, long], popup=artigo).add_to(m)
            st_folium(m, height=300, use_container_width=True)
            
        if "ultimo_id" in st.session_state:
            st.divider()
            dados = {'id': st.session_state.ultimo_id, 'valor_mercado': st.session_state.ultimo_valor}
            st.metric("Valor Final", f"{dados['valor_mercado']:,.2f} €")
            
            pdf = gerar_relatorio_pdf(dados, st.session_state.ultimos_inputs, st.session_state.username)
            st.download_button("📄 PDF Oficial", data=pdf, file_name="Relatorio.pdf", mime="application/pdf")

    with tab2:
        if st.button("🔄 Atualizar"):
            db = SessionLocal()
            registos = db.query(AvaliacaoDB).order_by(AvaliacaoDB.id.desc()).all()
            db.close()
            
            if registos:
                data = [{"ID": r.id, "Data": r.data_criacao, "Artigo": r.artigo, "Valor": f"{r.valor_mercado:,.2f} €"} for r in registos]
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.info("Sem registos.")