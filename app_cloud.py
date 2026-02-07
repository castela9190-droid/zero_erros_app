import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from fpdf import FPDF
import matplotlib.pyplot as plt
import io
from datetime import datetime
from PIL import Image

# Novas ferramentas de Nível 2
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# --- BASE DE DADOS VOLÁTIL (CLOUD) ---
# Nota: Na versão Cloud gratuita, isto reseta ocasionalmente.
# Para persistência real, na Fase 3 ligaremos ao Google Sheets.
if "historico_local" not in st.session_state:
    st.session_state.historico_local = []

# --- LÓGICA DE NEGÓCIO (CÁLCULOS AVANÇADOS) ---
def calcular_valor_homogeneizado(abp, au, preco_base, c_loc, c_qual, c_est):
    # 1. Validação de Áreas (Gatekeeper)
    if au > (abp * 1.15):
        return None, f"ERRO CRÍTICO: Área Útil ({au}) excede ABP ({abp}) em mais de 15%. Verifique medições."
    
    # 2. Cálculo dos Coeficientes
    # Fórmula: Valor Unitário Final = Preço Base * (C1 * C2 * C3)
    fator_global = c_loc * c_qual * c_est
    valor_unitario_final = preco_base * fator_global
    
    # 3. Valor de Mercado
    valor_final = abp * valor_unitario_final
    
    return {
        "valor_final": valor_final,
        "valor_unitario": valor_unitario_final,
        "fator_global": fator_global
    }, None

# --- GERADOR DE PDF PRO (COM FOTO) ---
def gerar_relatorio_pro(dados, inputs, user, foto_bytes=None):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Relatorio de Avaliacao Imobiliaria", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 10, f"Perito Avaliador: {user} | Data: {datetime.now().strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    
    # --- BLOCO 1: IDENTIFICAÇÃO E FOTO ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 10, "1. Identificacao do Imovel", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(2)
    
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Morada: {inputs['morada']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Artigo: {inputs['artigo']} | Tipologia: {inputs['tipologia']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Estado: {inputs['estado']} | Norma: {inputs['norma']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Inserir Foto se existir
    if foto_bytes:
        try:
            # Guardar imagem temporária para o PDF ler
            with open("temp_img.jpg", "wb") as f:
                f.write(foto_bytes.getbuffer())
            pdf.image("temp_img.jpg", x=120, y=45, w=70) # Posição à direita
        except:
            pass
    
    # --- BLOCO 2: DADOS TÉCNICOS ---
    pdf.set_y(90) # Forçar cursor para baixo da foto
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "2. Analise Tecnica e Areas", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Area Bruta Privativa (Registo): {inputs['abp']} m2", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Area Util Medida (Laser): {inputs['au']} m2", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.cell(0, 6, f"Preco Base de Referencia (Zona): {inputs['preco_base']:,.2f} EUR/m2", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Fatores: Loc({inputs['c_loc']}) x Qual({inputs['c_qual']}) x Est({inputs['c_est']}) = {dados['fator_global']:.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # --- BLOCO 3: VALOR E PROVA MATEMÁTICA ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "3. Valor de Mercado (Metodo Comparativo)", new_x="LMARGIN", new_y="NEXT", fill=True)
    
    # Imagem da Fórmula
    fig = plt.figure(figsize=(8, 2))
    valor_fmt = f"{dados['valor_final']:,.0f}"
    
    # Fórmula LaTeX Visual
    texto = f"$VM = ABP \\times Pb \\times Fator = {inputs['abp']} \\times {inputs['preco_base']} \\times {dados['fator_global']:.2f} = \\mathbf{{{valor_fmt} EUR}}$"
    
    plt.text(0.5, 0.5, texto, fontsize=14, ha='center', va='center')
    plt.axis('off')
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
    img_buffer.seek(0)
    pdf.image(img_buffer, x=10, w=190)
    
    return bytes(pdf.output())

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(layout="wide", page_title="Zero Erros PRO")

# --- LOGIN ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""

def check_login():
    if st.session_state["u"] == "perito" and st.session_state["p"] == "123":
        st.session_state.logged_in = True
        st.session_state.username = "Perito Arquiteto"
    else:
        st.error("Credenciais Inválidas")

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Zero Erros PRO")
        st.text_input("User", key="u")
        st.text_input("Pass", type="password", key="p")
        st.button("Entrar", on_click=check_login, type="primary")

else:
    # --- APLICAÇÃO PRINCIPAL ---
    st.sidebar.title(f"👤 {st.session_state.username}")
    if st.sidebar.button("Sair"):
        st.session_state.logged_in = False
        st.rerun()
    
    tab1, tab2 = st.tabs(["📝 Nova Avaliação", "📂 Histórico da Sessão"])
    
    with tab1:
        col_dados, col_mapa = st.columns([1.2, 1])
        
        with col_dados:
            st.subheader("1. Localização e Imagem")
            
            # GEOLOCALIZAÇÃO AUTOMÁTICA
            busca_morada = st.text_input("🔍 Pesquisar Morada (Ex: Rua do Ouro, Lisboa)")
            
            lat_inicial, long_inicial = 38.736946, -9.142685 # Lisboa padrão
            
            if busca_morada:
                geolocator = Nominatim(user_agent="zero_erros_app")
                location = geolocator.geocode(busca_morada)
                if location:
                    lat_inicial = location.latitude
                    long_inicial = location.longitude
                    st.success(f"📍 Encontrado: {location.address}")
                else:
                    st.warning("Morada não encontrada. Tente ser mais específico.")

            # Coordenadas (Editáveis)
            c1, c2 = st.columns(2)
            lat = c1.number_input("Latitude", value=lat_inicial, format="%.6f")
            long = c2.number_input("Longitude", value=long_inicial, format="%.6f")
            
            # FOTO
            foto_upload = st.file_uploader("📸 Carregar Foto da Fachada", type=['jpg', 'png'])

            st.divider()
            st.subheader("2. Caracterização e Áreas")
            
            c_art, c_tip = st.columns(2)
            artigo = c_art.text_input("Artigo Matricial", "U-12345")
            tipologia = c_tip.selectbox("Tipologia", ["T0", "T1", "T2", "T3", "T4", "T5+", "Comércio"])
            
            c_est, c_norm = st.columns(2)
            estado = c_est.selectbox("Estado", ["Novo", "Usado (Bom)", "Usado (Médio)", "Para Obras", "Ruína"])
            norma = c_norm.selectbox("Norma", ["RICS", "IVS"])
            
            c_abp, c_au = st.columns(2)
            abp = c_abp.number_input("ABP (Registo)", value=100.0)
            au = c_au.number_input("AU (Medida)", value=95.0)

            st.divider()
            st.subheader("3. Homogeneização (Cálculo)")
            
            preco_base = st.number_input("💶 Preço Base de Referência (€/m2)", value=3500.0, step=50.0, help="Valor médio de venda na zona para imóveis novos")
            
            # COEFICIENTES
            col_c1, col_c2, col_c3 = st.columns(3)
            c_loc = col_c1.slider("Localização", 0.8, 1.2, 1.0, 0.05, help="0.8=Pior, 1.0=Igual, 1.2=Melhor")
            c_qual = col_c2.slider("Qualidade Constr.", 0.8, 1.2, 1.0, 0.05)
            
            # Estado define o slider automaticamente, mas permite ajuste
            mapa_estado = {"Novo": 1.0, "Usado (Bom)": 0.9, "Usado (Médio)": 0.8, "Para Obras": 0.6, "Ruína": 0.4}
            val_est_default = mapa_estado.get(estado, 0.8)
            c_est = col_c3.slider("Estado Conserv.", 0.3, 1.0, val_est_default, 0.05)

            # BOTÃO DE AÇÃO
            if st.button("🚀 Calcular Valor PRO", type="primary"):
                res, erro = calcular_valor_homogeneizado(abp, au, preco_base, c_loc, c_qual, c_est)
                
                if erro:
                    st.error(erro)
                else:
                    st.session_state.resultado_pro = res
                    st.session_state.inputs_pro = {
                        'morada': busca_morada if busca_morada else "Coordenadas manuais",
                        'artigo': artigo, 'tipologia': tipologia, 'estado': estado, 'norma': norma,
                        'abp': abp, 'au': au, 'preco_base': preco_base,
                        'c_loc': c_loc, 'c_qual': c_qual, 'c_est': c_est
                    }
                    st.session_state.foto_atual = foto_upload
                    
                    # Gravar no histórico local
                    registo = {
                        "Data": datetime.now().strftime("%H:%M:%S"),
                        "Artigo": artigo,
                        "Valor": res['valor_final']
                    }
                    st.session_state.historico_local.append(registo)
                    
                    st.success("✅ Avaliação Calculada com Sucesso!")

        with col_mapa:
            st.subheader("🗺️ Mapa")
            m = folium.Map([lat, long], zoom_start=18) # Zoom maior para ver o telhado
            folium.Marker([lat, long], popup=artigo, tooltip="Imóvel").add_to(m)
            st_folium(m, height=500, use_container_width=True)
            
            # MOSTRAR RESULTADOS
            if "resultado_pro" in st.session_state:
                res = st.session_state.resultado_pro
                st.divider()
                st.metric("💰 Valor de Mercado", f"{res['valor_final']:,.2f} €", delta=f"{res['valor_unitario']:.2f} €/m2")
                
                # BOTÃO PDF
                pdf_bytes = gerar_relatorio_pro(
                    res, 
                    st.session_state.inputs_pro, 
                    st.session_state.username,
                    st.session_state.foto_atual
                )
                
                st.download_button(
                    label="📄 Baixar Relatório PRO (Com Foto)",
                    data=pdf_bytes,
                    file_name=f"Avaliacao_{artigo}.pdf",
                    mime="application/pdf",
                    type="primary"
                )

    with tab2:
        st.subheader("📂 Histórico da Sessão Atual")
        st.caption("Atenção: Estes dados apagam-se ao fechar o browser na versão gratuita.")
        if st.session_state.historico_local:
            st.dataframe(pd.DataFrame(st.session_state.historico_local), use_container_width=True)
        else:
            st.info("Ainda sem registos.")
