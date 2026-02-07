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
st.set_page_config(layout="wide", page_title="Zero Erros: Compliance", page_icon="⚖️")

# --- FUNÇÃO DE LIMPEZA DE TEXTO (CORREÇÃO DE ERROS PDF) ---
def limpar_texto(texto):
    """
    Remove caracteres especiais que crasham o PDF (como hífens longos do Word/Maps).
    """
    if not isinstance(texto, str):
        return str(texto)
    
    substituicoes = {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", 
        "\u2014": "-", "\u2015": "-", "–": "-", "€": "EUR", 
        "º": ".", "ª": "."
    }
    
    for char_ruim, char_bom in substituicoes.items():
        texto = texto.replace(char_ruim, char_bom)
    
    # Força compatibilidade Latin-1
    return texto.encode('latin-1', 'replace').decode('latin-1')

# --- MEMÓRIA DE SESSÃO ---
if "dados_nrau" not in st.session_state: st.session_state.dados_nrau = None
if "res_ross" not in st.session_state: st.session_state.res_ross = None
if "res_comparativo" not in st.session_state: st.session_state.res_comparativo = None
if "res_rendimento" not in st.session_state: st.session_state.res_rendimento = None

# --- LÓGICA DE MÉTODOS ---
def sugerir_metodos(tipo_imovel, finalidade):
    sugestao = []
    msg = ""
    if tipo_imovel == "Urbano":
        sugestao = ["Comparativo", "Custo (Ross-Heidecke)"]
        msg = "Urbano: Comparativo é preferencial. Custo como controlo."
    elif tipo_imovel == "Rústico":
        sugestao = ["Rendimento (Capitalização)", "Comparativo"]
        msg = "Rústico: Valor de Rendimento (Produção) é o standard."
    elif tipo_imovel == "Misto":
        sugestao = ["Comparativo", "Custo (Ross-Heidecke)", "Rendimento (Capitalização)"]
        msg = "Misto: Requer análise separada (Parte Urbana + Parte Rústica)."
    elif tipo_imovel == "Jazigo/Campa":
        sugestao = ["Custo (Ross-Heidecke)", "Comparativo"]
        msg = "Jazigo: Avaliação pelo custo de construção/concessão."
    return sugestao, msg

# --- CÁLCULO NRAU ---
def calcular_indice_nrau(pontuacoes):
    pesos = {"Estrutura": 6, "Cobertura": 5, "Fachadas": 3, "Paredes Comuns": 3, "Caixilharia": 2, "Instalações": 3}
    soma_pond = 0; soma_pontos = 0
    for item, estado in pontuacoes.items():
        peso = pesos.get(item, 1)
        soma_pontos += estado * peso
        soma_pond += peso
    if soma_pond == 0: return 0, "N/A"
    indice = soma_pontos / soma_pond
    if indice >= 4.5: classif = "Excelente"
    elif indice >= 3.5: classif = "Bom"
    elif indice >= 2.5: classif = "Médio"
    elif indice >= 1.5: classif = "Mau"
    else: classif = "Péssimo"
    return indice, classif

# --- CÁLCULO ROSS-HEIDECKE ---
def calcular_ross_heidecke(idade, vida_util, estado_conservacao):
    pct_vida = (idade / vida_util) * 100
    if pct_vida > 100: pct_vida = 100
    mapa_estados = {"Excelente": ("A", 0.0), "Bom": ("B", 2.5), "Médio": ("D", 8.0), "Mau": ("F", 18.0), "Péssimo": ("H", 30.0)}
    codigo, penalizacao_estado = mapa_estados.get(estado_conservacao, ("C", 5.0))
    x = pct_vida / 100
    deprec_ross = 0.5 * (x + x**2) * 100
    depreciacao_final = min(95, max(0, deprec_ross + penalizacao_estado))
    coeficiente_k = (100 - depreciacao_final) / 100
    return coeficiente_k, depreciacao_final, codigo

# --- RELATÓRIO PDF ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, limpar_texto('RELATÓRIO DE AVALIAÇÃO PERICIAL'), 0, 1, 'R')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, limpar_texto(f'Página {self.page_no()} - Zero Erros Compliance'), 0, 0, 'C')

def gerar_pdf_compliance(meta, imovel, nrau, ross, comparativo, rendimento, user, foto):
    pdf = PDFReport()
    pdf.add_page()
    
    # CAPA
    pdf.set_font("Arial", "B", 24); pdf.set_text_color(0, 0, 50)
    pdf.cell(0, 20, limpar_texto("RELATÓRIO DE AVALIAÇÃO"), 0, 1, "C")
    
    pdf.set_font("Arial", "B", 14); pdf.set_text_color(100, 0, 0)
    pdf.cell(0, 10, limpar_texto(f"Âmbito: {meta['finalidade'].upper()}"), 0, 1, "C")
    
    pdf.set_font("Arial", "", 12); pdf.set_text_color(0)
    pdf.cell(0, 10, limpar_texto(f"Imóvel: {imovel['morada']}"), 0, 1, "C")
    pdf.cell(0, 10, limpar_texto(f"Data: {datetime.now().strftime('%d/%m/%Y')}"), 0, 1, "C")
    
    if foto:
        try:
            with open("temp.jpg", "wb") as f: f.write(foto.getbuffer())
            pdf.image("temp.jpg", x=55, y=90, w=100)
        except: pass
    
    pdf.ln(110)
    
    # DOCUMENTAÇÃO
    pdf.set_font("Arial", "B", 11); pdf.set_fill_color(220, 220, 220)
    pdf.cell(0, 8, limpar_texto("1. DOCUMENTAÇÃO E PRESSUPOSTOS"), 0, 1, "L", fill=True)
    pdf.set_font("Arial", "", 10); pdf.ln(2)
    
    docs_str = ", ".join(meta['documentos']) if meta['documentos'] else "Nenhuma documentação fornecida."
    pdf.multi_cell(0, 6, limpar_texto(f"Documentação analisada: {docs_str}"))
    pdf.ln(2)
    pdf.multi_cell(0, 6, limpar_texto(f"Tipo: {meta['tipo']} | Finalidade: {meta['finalidade']}"))
    pdf.ln(2)
    pdf.multi_cell(0, 6, limpar_texto(f"Métodos: {', '.join(meta['metodos_escolhidos'])}"))
    
    # CARACTERIZAÇÃO
    pdf.ln(5); pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, limpar_texto("2. CARACTERIZAÇÃO"), 0, 1, "L", fill=True)
    pdf.set_font("Arial", "", 10); pdf.ln(2)
    
    # CORREÇÃO AQUI: Imprimir o ano corretamente
    pdf.cell(0, 6, limpar_texto(f"Artigo: {imovel['artigo']} | Tipologia: {imovel['tipologia']}"), 0, 1)
    pdf.cell(0, 6, limpar_texto(f"Ano Matriz/Construção: {imovel['ano']}"), 0, 1)
    pdf.cell(0, 6, limpar_texto(f"ABP: {imovel['abp']} m2 | AU: {imovel['au']} m2"), 0, 1)
    
    if nrau:
        pdf.cell(0, 6, limpar_texto(f"Estado NRAU: {nrau['classif']} (Índice {nrau['indice']:.2f})"), 0, 1)
    
    # CÁLCULOS
    pdf.ln(5); pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, limpar_texto("3. CÁLCULO DO VALOR"), 0, 1, "L", fill=True)
    pdf.ln(2)
    
    valor_final_conclusao = 0
    
    if "Comparativo" in meta['metodos_escolhidos'] and comparativo:
        pdf.set_font("Arial", "B", 10); pdf.cell(0, 6, limpar_texto("A. Método Comparativo de Mercado"), 0, 1)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, limpar_texto(f"Valor Base: {comparativo['preco_base']:,.2f} EUR/m2"), 0, 1)
        pdf.cell(0, 6, limpar_texto(f"Valor Mercado Estimado: {comparativo['valor_final']:,.2f} EUR"), 0, 1)
        pdf.ln(2)
        valor_final_conclusao = comparativo['valor_final']
        
    if "Custo (Ross-Heidecke)" in meta['metodos_escolhidos'] and ross:
        pdf.set_font("Arial", "B", 10); pdf.cell(0, 6, limpar_texto("B. Método do Custo (Ross-Heidecke)"), 0, 1)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, limpar_texto(f"Custo Novo: {ross['valor_novo']:,.2f} EUR/m2 | Depreciação: {ross['deprec']:.2f}%"), 0, 1)
        pdf.cell(0, 6, limpar_texto(f"Valor Depreciado: {ross['valor_final']:,.2f} EUR"), 0, 1)
        pdf.ln(2)
        if valor_final_conclusao == 0: valor_final_conclusao = ross['valor_final']

    if "Rendimento (Capitalização)" in meta['metodos_escolhidos'] and rendimento:
        pdf.set_font("Arial", "B", 10); pdf.cell(0, 6, limpar_texto("C. Método do Rendimento"), 0, 1)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, limpar_texto(f"Renda Anual: {rendimento['renda_anual']:,.2f} EUR | Yield: {rendimento['yield']*100:.2f}%"), 0, 1)
        pdf.cell(0, 6, limpar_texto(f"Valor Capitalizado: {rendimento['valor_final']:,.2f} EUR"), 0, 1)
        pdf.ln(2)
        if meta['tipo'] == "Rústico": valor_final_conclusao = rendimento['valor_final']

    # CONCLUSÃO
    pdf.ln(10); pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, limpar_texto(f"VALOR FINAL: {valor_final_conclusao:,.2f} EUR"), 0, 1, "C")
    
    pdf.set_y(-40); pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, limpar_texto("O Perito Avaliador,"), 0, 1, "R")
    pdf.cell(0, 6, limpar_texto(f"{user}"), 0, 1, "R")
    
    return bytes(pdf.output())

# --- LOGIN ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
def check_login():
    if st.session_state["u"] == "perito" and st.session_state["p"] == "123":
        st.session_state.logged_in = True; st.session_state.username = "Perito Arquiteto"
    else: st.error("Erro no Login")

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("⚖️ Zero Erros Compliance")
        st.text_input("User", key="u"); st.text_input("Pass", type="password", key="p")
        st.button("Entrar", on_click=check_login, type="primary")

else:
    # --- SIDEBAR ---
    st.sidebar.title("🛠️ Configuração")
    st.sidebar.info(f"👤 {st.session_state.username}")
    
    st.sidebar.subheader("1. Âmbito")
    tipo_imovel = st.sidebar.selectbox("Tipo de Artigo", ["Urbano", "Rústico", "Misto", "Jazigo/Campa"])
    
    finalidade_cat = st.sidebar.selectbox("Categoria", ["Judicial", "Financeira", "Transação", "Fiscal", "Seguros"])
    if finalidade_cat == "Judicial":
        sub_fin = st.sidebar.selectbox("Sub-tipo", ["Insolvência", "Execução", "Partilhas (Divórcio/Herança)", "Inventário"])
    elif finalidade_cat == "Financeira":
        sub_fin = st.sidebar.selectbox("Sub-tipo", ["Hipoteca (Crédito Habitação)", "Fundo Imobiliário", "Garantia"])
    else:
        sub_fin = st.sidebar.text_input("Especificar", "Avaliação Particular")
    finalidade_completa = f"{finalidade_cat} - {sub_fin}"
    
    st.sidebar.subheader("2. Documentação")
    docs_opcoes = ["Caderneta Predial (CPU)", "Certidão Permanente (CRP)", "Licença Utilização", "Plantas", "Certificado Energético", "Título Concessão", "Contratos Arrendamento"]
    docs_selecionados = st.sidebar.multiselect("Checklist", docs_opcoes)
    
    sugestao, msg_sugestao = sugerir_metodos(tipo_imovel, finalidade_completa)
    st.sidebar.subheader("3. Metodologia")
    st.sidebar.caption(f"🤖 Sugestão: {msg_sugestao}")
    metodos_ativos = st.sidebar.multiselect("Métodos", ["Comparativo", "Custo (Ross-Heidecke)", "Rendimento (Capitalização)"], default=sugestao)

    # --- TABS ---
    tab_imovel, tab_nrau, tab_calculo, tab_relatorio = st.tabs(["🏠 Imóvel", "🔍 Vistoria", "🧮 Cálculos", "📄 Relatório"])
    
    with tab_imovel:
        c1, c2 = st.columns(2)
        with c1:
            busca = st.text_input("Morada", help="Ex: Rua da Prata, Lisboa")
            lat_i, long_i = 38.73, -9.14
            if busca:
                try:
                    geo = Nominatim(user_agent="zero_erros_compliance")
                    loc = geo.geocode(busca, timeout=5)
                    if loc: lat_i, long_i = loc.latitude, loc.longitude
                except: st.warning("Mapa indisponível")
            lat = st.number_input("Lat", value=lat_i, format="%.6f")
            long = st.number_input("Long", value=long_i, format="%.6f")
            foto = st.file_uploader("Foto", type=['jpg', 'png'])
        with c2:
            artigo = st.text_input("Artigo", "U-1234")
            tipologia = st.text_input("Tipologia/Descrição", "T3")
            abp = st.number_input("Área Principal (m2)", 100.0)
            au = st.number_input("Área Secundária/Útil (m2)", 90.0)
            
            # --- CORREÇÃO DO ANO (Livre inserção) ---
            ano = st.number_input("Ano Matriz/Construção", value=2000, min_value=1000, max_value=2100, step=1, help="Insira o ano livremente")

    with tab_nrau:
        st.subheader("Estado de Conservação (NRAU)")
        if tipo_imovel in ["Urbano", "Misto", "Jazigo/Campa"]:
            c_n1, c_n2 = st.columns(2)
            pontos = {}
            with c_n1:
                pontos["Estrutura"] = st.slider("Estrutura", 1, 5, 4)
                pontos["Cobertura"] = st.slider("Cobertura", 1, 5, 4)
                pontos["Fachadas"] = st.slider("Fachadas", 1, 5, 3)
            with c_n2:
                pontos["Caixilharia"] = st.slider("Caixilharia", 1, 5, 3)
                pontos["Paredes Comuns"] = st.slider("Paredes", 1, 5, 3)
                pontos["Instalações"] = st.slider("Instalações", 1, 5, 4)
            idx, classif = calcular_indice_nrau(pontos)
            st.info(f"Classificação: {classif} (Índice {idx:.2f})")
            st.session_state.dados_nrau = {'indice': idx, 'classif': classif}
        else:
            st.info("NRAU não aplicável a Rústicos.")
            st.session_state.dados_nrau = None

    with tab_calculo:
        st.subheader("Cálculos")
        
        if "Comparativo" in metodos_ativos:
            with st.expander("🔹 Comparativo", expanded=True):
                col_c1, col_c2 = st.columns(2)
                pb = col_c1.number_input("Preço Base (€/m2)", 100.0, 20000.0, 2500.0)
                f_loc = col_c2.slider("Fator Loc", 0.5, 1.5, 1.0)
                f_qual = col_c2.slider("Fator Qual", 0.5, 1.5, 1.0)
                val_comp = abp * pb * f_loc * f_qual
                st.metric("Valor Comparativo", f"{val_comp:,.2f} €")
                st.session_state.res_comparativo = {'valor_final': val_comp, 'preco_base': pb}

        if "Custo (Ross-Heidecke)" in metodos_ativos:
            with st.expander("🔹 Custo (Ross-Heidecke)", expanded=True):
                est_cons = st.session_state.dados_nrau['classif'] if st.session_state.dados_nrau else st.selectbox("Estado", ["Novo", "Bom", "Médio", "Mau", "Péssimo"])
                v_novo = st.number_input("Custo Novo (€/m2)", 500.0, 5000.0, 1000.0)
                vida = st.number_input("Vida Útil", 10, 200, 80)
                
                # Cálculo Idade Robusto
                idade_calc = max(0, datetime.now().year - ano)
                
                k, deprec, cod = calcular_ross_heidecke(idade_calc, vida, est_cons)
                val_ross = abp * v_novo * k
                st.metric("Valor Custo", f"{val_ross:,.2f} €", delta=f"Idade: {idade_calc} anos | Deprec: -{deprec:.1f}%")
                st.session_state.res_ross = {'valor_final': val_ross, 'valor_novo': v_novo, 'deprec': deprec}

        if "Rendimento (Capitalização)" in metodos_ativos:
            with st.expander("🔹 Rendimento", expanded=True):
                renda_mensal = st.number_input("Renda Mensal (€)", 0.0, 100000.0, 500.0)
                yield_cap = st.number_input("Yield (%)", 1.0, 20.0, 5.0) / 100
                renda_anual = renda_mensal * 12
                val_rend = renda_anual / yield_cap
                st.metric("Valor Rendimento", f"{val_rend:,.2f} €")
                st.session_state.res_rendimento = {'valor_final': val_rend, 'renda_anual': renda_anual, 'yield': yield_cap}

    with tab_relatorio:
        st.header("Conclusão")
        meta = {'tipo': tipo_imovel, 'finalidade': finalidade_completa, 'documentos': docs_selecionados, 'metodos_escolhidos': metodos_ativos}
        imovel = {'morada': busca if busca else "S/ Morada", 'artigo': artigo, 'tipologia': tipologia, 'abp': abp, 'au': au, 'ano': ano}
        
        if st.button("Gerar Relatório Final", type="primary"):
            pdf = gerar_pdf_compliance(meta, imovel, st.session_state.dados_nrau, st.session_state.res_ross, st.session_state.res_comparativo, st.session_state.res_rendimento, st.session_state.username, foto)
            st.download_button("📥 Download PDF", data=pdf, file_name=f"Relatorio_{artigo}.pdf", mime="application/pdf")
