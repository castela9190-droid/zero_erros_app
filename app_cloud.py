import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from fpdf import FPDF
import matplotlib.pyplot as plt
import io
from datetime import datetime
from PIL import Image
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Zero Erros EXPERT", page_icon="🏢")

# --- MEMÓRIA DE SESSÃO ---
if "dados_nrau" not in st.session_state: st.session_state.dados_nrau = None
if "res_ross" not in st.session_state: st.session_state.res_ross = None
if "res_comparativo" not in st.session_state: st.session_state.res_comparativo = None

# --- MÓDULO 1: CÁLCULO NRAU (Estado de Conservação) ---
# Baseado na Ficha de Avaliação NRAU (Portaria n.º 1192-B/2006)
def calcular_indice_nrau(pontuacoes):
    # Pesos (Ponderações) aproximados da Ficha NRAU
    pesos = {
        "Estrutura": 6, "Cobertura": 5, "Fachadas": 3,
        "Paredes Comuns": 3, "Caixilharia": 2, "Instalações": 3
    }
    soma_pond = 0
    soma_pontos = 0
    
    # Pontuação: 5 (Excelente) a 1 (Mau)
    for item, estado in pontuacoes.items():
        peso = pesos.get(item, 1)
        soma_pontos += estado * peso
        soma_pond += peso
        
    if soma_pond == 0: return 0, "N/A"
    
    indice = soma_pontos / soma_pond
    
    # Classificação Final NRAU
    if indice >= 4.5: classif = "Excelente"
    elif indice >= 3.5: classif = "Bom"
    elif indice >= 2.5: classif = "Médio"
    elif indice >= 1.5: classif = "Mau"
    else: classif = "Péssimo"
    
    return indice, classif

# --- MÓDULO 2: TABELA ROSS-HEIDECKE (Depreciação) ---
# Implementação simplificada da curva de depreciação baseada na tabela enviada
def calcular_ross_heidecke(idade, vida_util, estado_conservacao):
    # 1. Calcular % de Vida Consumida
    pct_vida = (idade / vida_util) * 100
    if pct_vida > 100: pct_vida = 100
    
    # 2. Fator de Heidecke (Estado) - Aproximação da tabela
    # Estados: A(Novo) a H(Sem valor)
    # Mapear NRAU (Excelente -> A/B, Bom -> C, etc.)
    mapa_estados = {
        "Excelente": ("A", 0.0),      # Novo
        "Bom": ("B", 2.5),            # Entre novo e regular
        "Médio": ("D", 8.0),          # Entre regular e reparações
        "Mau": ("F", 18.0),           # Reparações importantes
        "Péssimo": ("H", 30.0)        # Sem valor
    }
    
    codigo, penalizacao_estado = mapa_estados.get(estado_conservacao, ("C", 5.0))
    
    # 3. Fórmula de Ross (Depreciação pela Idade)
    # D = 0.5 * (Age/Life + (Age/Life)^2) * 100
    x = pct_vida / 100
    deprec_ross = 0.5 * (x + x**2) * 100
    
    # 4. Combinação (Depreciação Final)
    # A tabela Ross-Heidecke combina os dois. Vamos somar a penalização do estado de forma ponderada.
    depreciacao_final = deprec_ross + penalizacao_estado
    
    # Ajuste fino para não passar 100% nem ser menor que 0
    if depreciacao_final > 95: depreciacao_final = 95
    if depreciacao_final < 0: depreciacao_final = 0
    
    coeficiente_k = (100 - depreciacao_final) / 100
    
    return coeficiente_k, depreciacao_final, codigo

# --- MÓDULO 3: GERADOR DE RELATÓRIO PDF (PREMIUM) ---
class PDFReport(FPDF):
    def header(self):
        # Cabeçalho Profissional
        self.set_font('Arial', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'RELATÓRIO DE AVALIAÇÃO IMOBILIÁRIA | MÉTODO CIENTÍFICO', 0, 1, 'R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()} - Gerado por Zero Erros Expert', 0, 0, 'C')

def gerar_pdf_expert(cliente, imovel, nrau, ross, comparativo, user, foto):
    pdf = PDFReport()
    pdf.add_page()
    
    # --- CAPA ---
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(0, 0, 50)
    pdf.cell(0, 20, "RELATÓRIO DE AVALIAÇÃO", 0, 1, "C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Imóvel: {imovel['morada']}", 0, 1, "C")
    pdf.cell(0, 10, f"Data: {datetime.now().strftime('%d/%m/%Y')}", 0, 1, "C")
    
    if foto:
        try:
            with open("temp_img_report.jpg", "wb") as f: f.write(foto.getbuffer())
            pdf.image("temp_img_report.jpg", x=55, y=70, w=100)
        except: pass
        
    pdf.ln(120)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "SOLICITANTE / CLIENTE:", 0, 1)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, f"Nome: {cliente['nome']}\nNIF: {cliente['nif']}\nFinalidade: {cliente['finalidade']}")
    
    pdf.add_page()
    
    # --- 1. IDENTIFICAÇÃO E METODOLOGIA ---
    pdf.set_fill_color(230, 230, 240)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "1. OBJETIVO E METODOLOGIA", 0, 1, "L", fill=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    texto_metodologia = (
        "O presente relatório visa determinar o Valor de Mercado do imóvel identificado, "
        "utilizando critérios objetivos e fundamentados.\n\n"
        "Foram utilizados os seguintes métodos:\n"
        "a) Método Comparativo de Mercado: Estima o valor por comparação com transações recentes "
        "de imóveis semelhantes, homogeneizados por fatores corretivos.\n"
        "b) Método do Custo (Ross-Heidecke): Calcula o valor de reposição depreciado, "
        "considerando a idade e o estado de conservação (determinado via auditoria NRAU)."
    )
    pdf.multi_cell(0, 6, texto_metodologia)
    pdf.ln(5)
    
    # --- 2. CARACTERIZAÇÃO DO IMÓVEL ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "2. CARACTERIZAÇÃO DO IMÓVEL", 0, 1, "L", fill=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.cell(95, 6, f"Artigo Matricial: {imovel['artigo']}", 0, 0)
    pdf.cell(95, 6, f"Tipologia: {imovel['tipologia']}", 0, 1)
    pdf.cell(95, 6, f"Área Bruta Privativa (ABP): {imovel['abp']} m2", 0, 0)
    pdf.cell(95, 6, f"Área Útil Medida: {imovel['au']} m2", 0, 1)
    pdf.ln(5)
    
    # --- 3. DIAGNÓSTICO DE CONSERVAÇÃO (NRAU) ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "3. ESTADO DE CONSERVAÇÃO (NRAU)", 0, 1, "L", fill=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Índice de Anomalias Calculado: {nrau['indice']:.2f}", 0, 1)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, f"Classificação Final: {nrau['classif'].upper()}", 0, 1)
    pdf.set_font("Arial", "I", 9)
    pdf.multi_cell(0, 6, "Nota: Avaliação baseada na ponderação dos elementos construtivos (Estrutura, Cobertura, Fachadas, etc.) conforme ficha técnica anexa ao processo.")
    pdf.ln(5)
    
    # --- 4. CÁLCULO DO VALOR (ROSS-HEIDECKE) ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "4. AVALIAÇÃO PELO MÉTODO DO CUSTO", 0, 1, "L", fill=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    
    ross_txt = (
        f"Idade do Imóvel: {ross['idade']} anos | Vida Útil Estimada: {ross['vida']} anos\n"
        f"Depreciação Aplicada (Tabela Ross-Heidecke): {ross['deprec']:.2f}%\n"
        f"Coeficiente 'K' (Estado {ross['codigo']}): {ross['k']:.3f}\n"
    )
    pdf.multi_cell(0, 6, ross_txt)
    pdf.ln(2)
    # Fórmula Visual
    pdf.set_font("Courier", "B", 10)
    pdf.cell(0, 6, f"Valor Custo = Area x Valor Novo x K", 0, 1, "C")
    pdf.cell(0, 6, f"Valor Custo = {imovel['abp']} x {ross['valor_novo']} x {ross['k']:.3f} = {ross['valor_final']:,.2f} EUR", 0, 1, "C")
    pdf.ln(5)
    
    # --- 5. CÁLCULO COMPARATIVO ---
    pdf.set_font("Arial", "B", 12)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "5. AVALIAÇÃO PELO MÉTODO COMPARATIVO", 0, 1, "L", fill=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Valor Base de Referência (Zona): {comparativo['preco_base']:,.2f} EUR/m2", 0, 1)
    pdf.cell(0, 6, f"Fatores de Homogeneização: Loc({comparativo['c_loc']}) x Qual({comparativo['c_qual']}) x Est({comparativo['c_est']})", 0, 1)
    pdf.ln(2)
    pdf.set_font("Courier", "B", 10)
    pdf.cell(0, 6, f"Valor Mercado = {comparativo['valor_final']:,.2f} EUR", 0, 1, "C")
    
    # --- CONCLUSÃO ---
    pdf.ln(10)
    pdf.set_draw_color(0, 0, 0)
    pdf.rect(10, pdf.get_y(), 190, 25)
    pdf.set_xy(15, pdf.get_y() + 5)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"VALOR FINAL DE AVALIAÇÃO: {comparativo['valor_final']:,.2f} EUR", 0, 1, "C")
    
    # Assinatura
    pdf.set_y(-40)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, "O Perito Avaliador,", 0, 1, "R")
    pdf.cell(0, 6, f"{user}", 0, 1, "R")
    
    return bytes(pdf.output())

# --- LOGIN SIMPLES ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
def check_login():
    if st.session_state["u"] == "perito" and st.session_state["p"] == "123":
        st.session_state.logged_in = True
        st.session_state.username = "Perito Arquiteto"
    else: st.error("Credenciais Inválidas")

# --- INTERFACE PRINCIPAL ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Zero Erros EXPERT")
        st.text_input("User", key="u"); st.text_input("Pass", type="password", key="p")
        st.button("Entrar", on_click=check_login, type="primary")

else:
    # Sidebar
    st.sidebar.title("MENU")
    st.sidebar.info(f"👤 {st.session_state.username}")
    
    # DADOS DO CLIENTE (Persistentes na sessão)
    st.sidebar.header("📁 Dados do Processo")
    cl_nome = st.sidebar.text_input("Nome Cliente", "João Silva")
    cl_nif = st.sidebar.text_input("NIF", "123456789")
    cl_fin = st.sidebar.selectbox("Finalidade", ["Crédito Habitação", "Partilhas", "Compra/Venda", "Fiscal"])
    
    # ABAS PRINCIPAIS
    tab_imovel, tab_nrau, tab_valores, tab_relatorio = st.tabs([
        "🏠 1. Imóvel", "🔍 2. Vistoria (NRAU)", "🧮 3. Avaliação", "📄 4. Relatório"
    ])
    
    # --- ABA 1: IMÓVEL ---
    with tab_imovel:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.subheader("Localização e Identificação")
            busca = st.text_input("Pesquisar Morada", help="Ex: Av. Liberdade, Lisboa")
            
            lat_i, long_i = 38.736946, -9.142685
            if busca:
                try:
                    geo = Nominatim(user_agent="zero_erros_expert")
                    loc = geo.geocode(busca, timeout=5)
                    if loc: 
                        lat_i, long_i = loc.latitude, loc.longitude
                        st.success(f"📍 {loc.address}")
                    else: st.warning("Morada não encontrada.")
                except: st.warning("Serviço de mapas indisponível.")
                
            lat = st.number_input("Latitude", value=lat_i, format="%.6f")
            long = st.number_input("Longitude", value=long_i, format="%.6f")
            
            st.subheader("Carregamento de Foto")
            foto = st.file_uploader("Fachada Principal", type=['jpg', 'png'])
            if foto: st.session_state.foto = foto
            
        with c2:
            st.subheader("Dados Cadastrais")
            artigo = st.text_input("Artigo Matricial", "U-1234")
            tipologia = st.selectbox("Tipologia", ["T0", "T1", "T2", "T3", "T4", "Outro"])
            abp = st.number_input("Área Bruta Privativa (m2)", 100.0)
            au = st.number_input("Área Útil Medida (m2)", 90.0)
            ano_constr = st.number_input("Ano Construção", 2000, 2025, 2010)
            
            # Guardar na sessão
            st.session_state.imovel = {
                'morada': busca if busca else "Coordenadas manuais",
                'artigo': artigo, 'tipologia': tipologia, 'abp': abp, 'au': au, 'ano': ano_constr
            }

    # --- ABA 2: VISTORIA (NRAU) ---
    with tab_nrau:
        st.header("Auditoria Técnica (Método NRAU)")
        st.caption("Avalie o estado de cada componente (5=Excelente, 1=Muito Mau)")
        
        c_n1, c_n2 = st.columns(2)
        pontuacoes = {}
        
        with c_n1:
            pontuacoes["Estrutura"] = st.slider("1. Estrutura (Peso 6)", 1, 5, 4)
            pontuacoes["Cobertura"] = st.slider("2. Cobertura (Peso 5)", 1, 5, 4)
            pontuacoes["Fachadas"] = st.slider("3. Fachadas (Peso 3)", 1, 5, 3)
            
        with c_n2:
            pontuacoes["Caixilharia"] = st.slider("4. Caixilharia (Peso 2)", 1, 5, 3)
            pontuacoes["Paredes Comuns"] = st.slider("5. Áreas Comuns (Peso 3)", 1, 5, 3)
            pontuacoes["Instalações"] = st.slider("6. Água/Luz/Esgoto (Peso 3)", 1, 5, 4)
            
        if st.button("Calcular Estado de Conservação"):
            idx, classif = calcular_indice_nrau(pontuacoes)
            st.session_state.dados_nrau = {'indice': idx, 'classif': classif}
            st.success(f"Índice: {idx:.2f} | Classificação: {classif}")
        
        if st.session_state.dados_nrau:
            st.info(f"Estado Definido: {st.session_state.dados_nrau['classif']}")

    # --- ABA 3: AVALIAÇÃO (ROSS + COMPARATIVO) ---
    with tab_valores:
        st.header("Cálculo do Valor")
        
        col_ross, col_comp = st.columns(2)
        
        # MÉTODO 1: ROSS-HEIDECKE
        with col_ross:
            st.subheader("🔹 Método do Custo (Ross-Heidecke)")
            valor_novo_m2 = st.number_input("Valor de Construção Nova (€/m2)", 800.0, 3000.0, 1200.0)
            vida_util = st.number_input("Vida Útil Esperada (Anos)", 60, 100, 80)
