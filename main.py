import streamlit as st
import pandas as pd
import plotly.express as px
import os
from supabase import create_client
import locale
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'portuguese')
    except:
        pass
# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Bithelp - GearTech Solutions",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "**Bithelp - GearTech Solutions**\n\nSistema de Help Desk e BI\n\nDesenvolvido para TCC\n\nVersão 1.0"
    }
)

# --- CONFIGURAÇÕES SUPABASE ---
URL_SUPABASE = "https://rttcmxsvhjhcfrzbhwtm.supabase.co"
KEY_SUPABASE = "sb_publishable_Pss3H5MunB_Ioc2t8y66pg_WKVFxRyP"

# --- 2. SISTEMA DE LOGIN DINÂMICO ---
def sistema_login():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.perfil = None
        st.session_state.usuario_nome = None

    if not st.session_state.autenticado:
        col_side_l, col_login, col_side_r = st.columns([0.2, 3, 0.2])
        with col_login:
            st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>Acesso Bithelp</h1>", unsafe_allow_html=True)
            with st.container(border=True):
                with st.form("login_form", clear_on_submit=False):
                    usuario_input = st.text_input("Usuário ou E-mail")
                    senha_input = st.text_input("Senha", type="password")
                    btn_entrar = st.form_submit_button("Entrar", use_container_width=True)

                    if btn_entrar:
                        if usuario_input and senha_input:
                            try:
                                client_auth = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
                                termo = usuario_input.strip().lower()
                                response = client_auth.table("usuarios").select("*").eq("senha", senha_input.strip()).execute()
                                
                                usuario_valido = None
                                if response.data:
                                    for user in response.data:
                                        if user["email"].strip().lower() == termo or user["nome"].strip().lower() == termo:
                                            usuario_valido = user
                                            break
                                        
                                if usuario_valido:
                                    st.session_state.autenticado = True
                                    st.session_state.perfil = usuario_valido["perfil"]
                                    st.session_state.usuario_nome = usuario_valido["nome"]
                                    st.toast(f"Bem-vindo, {usuario_valido['nome']}!", icon='✨')
                                    st.rerun()
                                else:
                                    st.error("Usuário/E-mail ou senha incorretos.")
                            except Exception as e:
                                st.error(f"Erro ao autenticar: {e}")
                        else:
                            st.error("Por favor, preencha todos os campos.")
        return False
    return True

if sistema_login():

    # --- 3. CONEXÃO E CARREGAMENTO DE DADOS ---
    @st.cache_resource
    def init_connection():
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)

    supabase = init_connection()

    # ===== FUNÇÃO DE HISTÓRICO (VERSÃO ENXUTA) =====
    def registrar_historico(acao, detalhes=""):
        # Só registra ações realmente importantes
        acoes_importantes = [
            "ABERTURA DE CHAMADO", "FINALIZAR CHAMADO",
            "CADASTRAR USUÁRIO", "REMOVER USUÁRIO",
            "CADASTRO DE ATIVO", "EDIÇÃO DE ATIVO", "REMOVER ATIVO"
        ]
        
        if acao not in acoes_importantes:
            return  # Ignora ações desnecessárias
        
        try:
            payload_hist = {
                "usuario": st.session_state.usuario_nome,
                "perfil": st.session_state.perfil,
                "acao": acao,
                "detalhes": detalhes
            }
            supabase.table("historico").insert(payload_hist).execute()
        except:
            pass
    # ===== FIM DA FUNÇÃO =====

    def carregar_dados():
        try:
            response = supabase.table("maquinas").select("*").execute()
            df = pd.DataFrame(response.data)
            df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
            return df
        except Exception as e:
            st.error(f"Erro ao conectar ao Supabase: {e}")
            return None

    def carregar_chamados():
        try:
            response = supabase.table("chamados").select("*, maquinas(identificacao)").eq("finalizado", False).execute()
            return pd.DataFrame(response.data)
        except:
            return pd.DataFrame()
        
    def carregar_todos_chamados():
        try:
            response = supabase.table("chamados").select("*, maquinas(identificacao)").execute()
            return pd.DataFrame(response.data)
        except:
            return pd.DataFrame()
        
        # --- FUNÇÃO PARA GERAR RELATÓRIO PDF ---
    def gerar_relatorio_pdf(ano, mes):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        import tempfile
        from datetime import datetime
        import locale
        import re
        
        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'portuguese')
            except:
                pass
        
        # CARREGA TODOS OS CHAMADOS (SEM FILTRO DE FINALIZADO)
        df_chamados = carregar_todos_chamados()
        if df_chamados.empty:
            return None
        
        df_chamados['created_at'] = pd.to_datetime(df_chamados['created_at'])
        
        # FILTRA CHAMADOS DO MÊS
        df_mes = df_chamados[
            (df_chamados['created_at'].dt.year == ano) & 
            (df_chamados['created_at'].dt.month == mes)
        ]
        
        # SE NÃO HOUVER CHAMADOS NO MÊS, RETORNA NONE
        if df_mes.empty:
            return None
        
        # CARREGA O HISTÓRICO
        df_hist = carregar_historico()
        
        # CHAMADOS RESOLVIDOS (APENAS DO MÊS)
        chamados_resolvidos = 0
        if not df_hist.empty:
            df_hist['created_at'] = pd.to_datetime(df_hist['created_at'])
            
            ids_finalizados = []
            df_hist_mes = df_hist[
                (df_hist['acao'] == 'FINALIZAR CHAMADO') &
                (df_hist['created_at'].dt.year == ano) &
                (df_hist['created_at'].dt.month == mes)
            ]
            
            for _, row in df_hist_mes.iterrows():
                detalhes = row.get('detalhes', '')
                match = re.search(r'Chamado (\d+)', str(detalhes))
                if match:
                    ids_finalizados.append(int(match.group(1)))
            
            chamados_resolvidos = len(df_mes[df_mes['id'].isin(ids_finalizados)])
        
        # MÉTRICAS
        total_chamados = len(df_mes)
        taxa_resolucao = (chamados_resolvidos / total_chamados * 100) if total_chamados > 0 else 0
        
        # RANKING (APENAS DO MÊS)
        ranking_aberturas = {}
        if not df_hist.empty:
            df_hist_aberturas = df_hist[
                (df_hist['acao'] == 'ABERTURA DE CHAMADO') &
                (df_hist['created_at'].dt.year == ano) &
                (df_hist['created_at'].dt.month == mes)
            ]
            for _, row in df_hist_aberturas.iterrows():
                usuario = row.get('usuario', 'Desconhecido')
                ranking_aberturas[usuario] = ranking_aberturas.get(usuario, 0) + 1
        
        ranking_ordenado = sorted(ranking_aberturas.items(), key=lambda x: x[1], reverse=True)[:5] if ranking_aberturas else []
        
        # PRIORIDADES (APENAS DO MÊS)
        prioridades = df_mes['prioridade'].value_counts()
        
        # CRIA O PDF
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = temp_file.name
        temp_file.close()
        
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        elementos = []
        
        # Título
        titulo_style = ParagraphStyle(
            'Titulo',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1E40AF'),
            alignment=1,
            spaceAfter=20
        )
        subtitulo_style = ParagraphStyle(
            'Subtitulo',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.grey,
            alignment=1,
            spaceAfter=30
        )
        
        # ===== CABEÇALHO =====
        titulo = Paragraph("BITHELP <br/>GEARTECH SOLUTIONS", titulo_style)
        subtitulo = Paragraph(f"RELATÓRIO GERENCIAL DE CHAMADOS", subtitulo_style)
        
        logo_path = "bithelplogo.png"
        logo_elemento = ""
        try:
            if os.path.exists(logo_path):
                from reportlab.platypus import Image
                logo_elemento = Image(logo_path, width=70, height=60)
        except:
            logo_elemento = ""
        
        dados_cabecalho = [
            [titulo, logo_elemento],
            [subtitulo, ""]
        ]
        cabecalho_tabela = Table(dados_cabecalho, colWidths=[400, 100])
        cabecalho_tabela.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 1), 'LEFT'),
            ('ALIGN', (1, 0), (1, 1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elementos.append(cabecalho_tabela)
        elementos.append(Spacer(1, 10))
        
        nome_mes = datetime(ano, mes, 1).strftime('%B/%Y').capitalize()
        elementos.append(Paragraph(f"<b>Mês de Referência:</b> {nome_mes}", styles['Normal']))
        elementos.append(Paragraph(f"<b>Data de Geração:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elementos.append(Spacer(1, 20))
        
        # ===== RESUMO GERAL =====
        elementos.append(Paragraph("<b><font size=14>📊 RESUMO GERAL</font></b>", styles['Heading3']))
        elementos.append(Spacer(1, 10))
        
        dados_resumo = [
            ['Chamados Registrados', str(total_chamados)],
            ['Chamados Resolvidos', str(chamados_resolvidos)],
            ['Taxa de Resolução', f"{taxa_resolucao:.1f}%"],
        ]
        
        # TEMPO MÉDIO DE RESOLUÇÃO (se houver chamados resolvidos)
        if chamados_resolvidos > 0:
            tempo_medio_resolucao = None
            if not df_hist.empty:
                # Pega os IDs dos chamados finalizados no mês
                ids_finalizados = []
                df_hist_mes = df_hist[
                    (df_hist['acao'] == 'FINALIZAR CHAMADO') &
                    (df_hist['created_at'].dt.year == ano) &
                    (df_hist['created_at'].dt.month == mes)
                ]
                
                for _, row in df_hist_mes.iterrows():
                    detalhes = row.get('detalhes', '')
                    match = re.search(r'Chamado (\d+)', str(detalhes))
                    if match:
                        ids_finalizados.append(int(match.group(1)))
                
                # Calcular o tempo de cada chamado
                tempos = []
                for chamado_id in ids_finalizados:
                    chamado = df_mes[df_mes['id'] == chamado_id]
                    if not chamado.empty:
                        data_abertura = chamado.iloc[0]['created_at']
                        data_finalizacao = df_hist_mes[df_hist_mes['detalhes'].str.contains(str(chamado_id))].iloc[0]['created_at']
                        tempo = (data_finalizacao - data_abertura).total_seconds() / 3600
                        tempos.append(tempo)
                
                if tempos:
                    tempo_medio_resolucao = sum(tempos) / len(tempos)
            
            if tempo_medio_resolucao is not None:
                # Formatar o tempo
                if tempo_medio_resolucao < 1:
                    minutos = int(tempo_medio_resolucao * 60)
                    tempo_formatado = f"{minutos} min"
                elif tempo_medio_resolucao < 24:
                    horas = int(tempo_medio_resolucao)
                    minutos = int((tempo_medio_resolucao - horas) * 60)
                    if minutos > 0:
                        tempo_formatado = f"{horas}h {minutos}min"
                    else:
                        tempo_formatado = f"{horas}h"
                else:
                    dias = int(tempo_medio_resolucao / 24)
                    horas = int(tempo_medio_resolucao % 24)
                    if horas > 0:
                        tempo_formatado = f"{dias}d {horas}h"
                    else:
                        tempo_formatado = f"{dias}d"
                
                dados_resumo.append(['Tempo Médio de Resolução', tempo_formatado])
        
        # ===== TABELA DO RESUMO =====
        tabela_resumo = Table(dados_resumo, colWidths=[270, 80])
        tabela_resumo.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#1E40AF')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#F3F4F6')),
        ]))
        
        tabela_alinhada = Table([[tabela_resumo]], colWidths=[400])
        tabela_alinhada.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elementos.append(tabela_alinhada)
        elementos.append(Spacer(1, 20))
                
        # ===== PRIORIDADES =====
        if not prioridades.empty:
            elementos.append(Paragraph("<b><font size=14>⚡ CHAMADOS POR PRIORIDADE</font></b>", styles['Heading3']))
            elementos.append(Spacer(1, 10))
            
            dados_prioridade = [['Prioridade', 'Quantidade']]
            for prioridade, qtd in prioridades.items():
                dados_prioridade.append([f"{prioridade}", str(qtd)])
            
            tabela_prioridade = Table(dados_prioridade, colWidths=[120, 80])
            tabela_prioridade.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            
            tabela_alinhada = Table([[tabela_prioridade]], colWidths=[400])
            tabela_alinhada.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elementos.append(tabela_alinhada)
            elementos.append(Spacer(1, 20))
        
        # ===== LISTA DETALHADA =====
        elementos.append(Paragraph("<b><font size=14>📋 LISTA DETALHADA DE CHAMADOS</font></b>", styles['Heading3']))
        elementos.append(Spacer(1, 5))
        
        df_exibicao = df_mes[['id', 'created_at', 'laboratorio', 'descricao', 'prioridade']].copy()
        df_exibicao['created_at'] = df_exibicao['created_at'].dt.strftime('%d/%m/%Y')
        df_exibicao.columns = ['ID', 'Data', 'Laboratório', 'Descrição', 'Prioridade']
        
        if len(df_exibicao) > 20:
            df_exibicao = df_exibicao.head(20)
            elementos.append(Paragraph("<i>* Mostrando os 20 primeiros chamados</i>", styles['Italic']))
            elementos.append(Spacer(1, 3))
        
        dados_tabela = [df_exibicao.columns.tolist()] + df_exibicao.values.tolist()
        
        col_widths = [40, 70, 60, 200, 60]
        
        tabela_detalhada = Table(dados_tabela, colWidths=col_widths, repeatRows=1)
        tabela_detalhada.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E40AF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elementos.append(tabela_detalhada)
        
        # Rodapé
        elementos.append(Spacer(1, 106))  
        elementos.append(Paragraph("<i>Relatório gerado automaticamente pelo sistema Bithelp - GearTech Solutions</i>", styles['Italic']))
        
        # Gerar PDF
        doc.build(elementos)
        return pdf_path

    def carregar_historico():
        try:
            response = supabase.table("historico").select("*").execute()
            return pd.DataFrame(response.data)
        except:
            return pd.DataFrame()

    df = carregar_dados()

    if df is None or df.empty:
        st.warning("⚠️ Banco de dados vazio ou erro na conexão.")
        st.stop()

    # --- CONFIGURAÇÃO DA PALETA DE CORES DINÂMICA ---
    paletas_config = {
        "Azul Corporativo": {
            "primaria": "#1E40AF", "secundaria": "#60A5FA",
            "filtro_logo": "brightness(0) saturate(100%) invert(18%) sepia(68%) saturate(3724%) hue-rotate(221deg) brightness(87%) contrast(94%)",
            "mapa": {'OK': '#1E40AF', 'Pendente de Manutenção': '#FFC107', 'Inativo': '#6C757D', 'Em Reparo': '#17A2B8', 'Pendente': '#FFC107'}
        },
        "Modo Tech Neon": {
            "primaria": "#00F5D4", "secundaria": "#9B5DE5",
            "filtro_logo": "brightness(0) saturate(100%) invert(74%) sepia(96%) saturate(1518%) hue-rotate(117deg) brightness(101%) contrast(105%)",
            "mapa": {'OK': '#00F5D4', 'Pendente de Manutenção': '#9B5DE5', 'Inativo': '#545454', 'Em Reparo': '#F15BB5', 'Pendente': '#9B5DE5'}
        },
        "Esmeralda Clean": {
            "primaria": "#0F5132", "secundaria": "#25C37D",
            "filtro_logo": "brightness(0) saturate(100%) invert(21%) sepia(35%) saturate(1472%) hue-rotate(107deg) brightness(93%) contrast(92%)",
            "mapa": {'OK': '#198754', 'Pendente de Manutenção': '#FD7E14', 'Inativo': '#ADB5BD', 'Em Reparo': '#0DCAF0', 'Pendente': '#FD7E14'}
        },
        "Vinho Premium": {
            "primaria": "#722F37", "secundaria": "#C5A0A5",
            "filtro_logo": "brightness(0) saturate(100%) invert(21%) sepia(10%) saturate(3015%) hue-rotate(307deg) brightness(86%) contrast(87%)",
            "mapa": {'OK': '#722F37', 'Pendente de Manutenção': '#E65C00', 'Inativo': '#5C5C5C', 'Em Reparo': '#9933FF', 'Pendente': '#E65C00'}
        },
        "Cyberpunk Amber": {
            "primaria": "#FFB300", "secundaria": "#FF3D00",
            "filtro_logo": "brightness(0) saturate(100%) invert(75%) sepia(60%) saturate(3443%) hue-rotate(360deg) brightness(102%) contrast(106%)",
            "mapa": {'OK': '#FFB300', 'Pendente de Manutenção': '#FF3D00', 'Inativo': '#2B2B2B', 'Em Reparo': '#00E5FF', 'Pendente': '#FF3D00'}
        },
        "Roxo Cyber Sec": {
            "primaria": "#6A1B9A", "secundaria": "#E040FB",
            "filtro_logo": "brightness(0) saturate(100%) invert(14%) sepia(74%) saturate(4238%) hue-rotate(272deg) brightness(79%) contrast(110%)",
            "mapa": {'OK': '#6A1B9A', 'Pendente de Manutenção': '#FF1744', 'Inativo': '#424242', 'Em Reparo': '#00E676', 'Pendente': '#FF1744'}
        },
        "Slate Minimalista": {
            "primaria": "#374151", "secundaria": "#9CA3AF",
            "filtro_logo": "brightness(0) saturate(100%) invert(22%) sepia(12%) saturate(996%) hue-rotate(178deg) brightness(93%) contrast(89%)",
            "mapa": {'OK': '#374151', 'Pendente de Manutenção': '#F59E0B', 'Inativo': '#9CA3AF', 'Em Reparo': '#10B981', 'Pendente': '#F59E0B'}
        },
        "Carmesim Autêntico": {
            "primaria": "#990000", "secundaria": "#FF4D4D",
            "filtro_logo": "brightness(0) saturate(100%) invert(10%) sepia(97%) saturate(5833%) hue-rotate(359deg) brightness(83%) contrast(115%)",
            "mapa": {'OK': '#990000', 'Pendente de Manutenção': '#CC6600', 'Inativo': '#555555', 'Em Reparo': '#006699', 'Pendente': '#CC6600'}
        },
        "Café Cappuccino": {
            "primaria": "#4E3629", "secundaria": "#D7CCC8",
            "filtro_logo": "brightness(0) saturate(100%) invert(19%) sepia(17%) saturate(1243%) hue-rotate(339deg) brightness(93%) contrast(91%)",
            "mapa": {'OK': '#4E3629', 'Pendente de Manutenção': '#D7CCC8', 'Inativo': '#8D6E63', 'Em Reparo': '#A1887F', 'Pendente': '#D7CCC8'}
        },
        "Laranja Burnout": {
            "primaria": "#E65100", "secundaria": "#FFB74D",
            "filtro_logo": "brightness(0) saturate(100%) invert(35%) sepia(85%) saturate(3502%) hue-rotate(13deg) brightness(97%) contrast(104%)",
            "mapa": {'OK': '#E65100', 'Pendente de Manutenção': '#311B92', 'Inativo': '#757575', 'Em Reparo': '#00B0FF', 'Pendente': '#311B92'}
        },
        "Deep Ocean": {
            "primaria": "#0A2540", "secundaria": "#00D4B2",
            "filtro_logo": "brightness(0) saturate(100%) invert(9%) sepia(35%) saturate(2283%) hue-rotate(179deg) brightness(91%) contrast(97%)",
            "mapa": {'OK': '#0A2540', 'Pendente de Manutenção': '#FF5A5F', 'Inativo': '#64748B', 'Em Reparo': '#00D4B2', 'Pendente': '#FF5A5F'}
        },
        "Hacker Green": {
            "primaria": "#39FF14", "secundaria": "#00FFCC",
            "filtro_logo": "brightness(0) saturate(100%) invert(77%) sepia(74%) saturate(2644%) hue-rotate(63deg) brightness(109%) contrast(113%)",
            "mapa": {'OK': '#39FF14', 'Pendente de Manutenção': '#D00000', 'Inativo': '#1A1A1A', 'Em Reparo': '#7B2CBF', 'Pendente': '#D00000'}
        },
        "Synthwave Metal": {
            "primaria": "#FF007F", "secundaria": "#4CC9F0",
            "filtro_logo": "brightness(0) saturate(100%) invert(15%) sepia(100%) saturate(6325%) hue-rotate(320deg) brightness(95%) contrast(114%)",
            "mapa": {'OK': '#FF007F', 'Pendente de Manutenção': '#3A0CA3', 'Inativo': '#212529', 'Em Reparo': '#4CC9F0', 'Pendente': '#3A0CA3'}
        },
        "Nordic Cold": {
            "primaria": "#4C6EF5", "secundaria": "#748FFC",
            "filtro_logo": "brightness(0) saturate(100%) invert(39%) sepia(61%) saturate(2311%) hue-rotate(211deg) brightness(101%) contrast(94%)",
            "mapa": {'OK': '#4C6EF5', 'Pendente de Manutenção': '#FAB005', 'Inativo': '#A61E4D', 'Em Reparo': '#15AABF', 'Pendente': '#FAB005'}
        },
        "Imperial Gold": {
            "primaria": "#C5A880", "secundaria": "#E5D4BC",
            "filtro_logo": "brightness(0) saturate(100%) invert(73%) sepia(13%) saturate(1112%) hue-rotate(354deg) brightness(89%) contrast(87%)",
            "mapa": {'OK': '#C5A880', 'Pendente de Manutenção': '#2C3E50', 'Inativo': '#7F8C8D', 'Em Reparo': '#16A085', 'Pendente': '#2C3E50'}
        },
        "Plum Orchid": {
            "primaria": "#522258", "secundaria": "#C63065",
            "filtro_logo": "brightness(0) saturate(100%) invert(11%) sepia(42%) saturate(2250%) hue-rotate(256deg) brightness(89%) contrast(92%)",
            "mapa": {'OK': '#522258', 'Pendente de Manutenção': '#C63065', 'Inativo': '#D8B4F8', 'Em Reparo': '#E07A5F', 'Pendente': '#C63065'}
        },
        "Forest Bio": {
            "primaria": "#2D6A4F", "secundaria": "#52B788",
            "filtro_logo": "brightness(0) saturate(100%) invert(35%) sepia(15%) saturate(2132%) hue-rotate(104deg) brightness(93%) contrast(86%)",
            "mapa": {'OK': '#2D6A4F', 'Pendente de Manutenção': '#D90429', 'Inativo': '#708238', 'Em Reparo': '#52B788', 'Pendente': '#D90429'}
        },
        "Electric Velvet": {
            "primaria": "#E0115F", "secundaria": "#FF5E97",
            "filtro_logo": "brightness(0) saturate(100%) invert(17%) sepia(74%) saturate(5412%) hue-rotate(330deg) brightness(87%) contrast(98%)",
            "mapa": {'OK': '#E0115F', 'Pendente de Manutenção': '#FFCC00', 'Inativo': '#3E2723', 'Em Reparo': '#8E44AD', 'Pendente': '#FFCC00'}
        },
        "Sweet Marshmallow": {
            "primaria": "#F4978E", "secundaria": "#FBC4AB",
            "filtro_logo": "brightness(0) saturate(100%) invert(76%) sepia(19%) saturate(1512%) hue-rotate(313deg) brightness(98%) contrast(97%)",
            "mapa": {'OK': '#F4978E', 'Pendente de Manutenção': '#FBC4AB', 'Inativo': '#90E0EF', 'Em Reparo': '#F08080', 'Pendente': '#FBC4AB'}
        },
        "Carbon Dark": {
            "primaria": "#1C1A27", "secundaria": "#4EA8DE",
            "filtro_logo": "brightness(0) saturate(100%) invert(8%) sepia(9%) saturate(1824%) hue-rotate(211deg) brightness(94%) contrast(94%)",
            "mapa": {'OK': '#1C1A27', 'Pendente de Manutenção': '#E63946', 'Inativo': '#8D99AE', 'Em Reparo': '#4EA8DE', 'Pendente': '#E63946'}
        },
        "Turquesa Premium": {
            "primaria": "#14B8A6", "secundaria": "#99F6E4",
            "filtro_logo": "brightness(0) saturate(100%) invert(58%) sepia(57%) saturate(548%) hue-rotate(124deg) brightness(94%) contrast(90%)",
            "mapa": {'OK': '#14B8A6', 'Pendente de Manutenção': '#F59E0B', 'Inativo': '#6B7280', 'Em Reparo': '#EC4899', 'Pendente': '#F59E0B'}
        },
        "Solar Radiance": {
            "primaria": "#EAB308", "secundaria": "#FEF08A",
            "filtro_logo": "brightness(0) saturate(100%) invert(74%) sepia(61%) saturate(952%) hue-rotate(1deg) brightness(102%) contrast(93%)",
            "mapa": {'OK': '#EAB308', 'Pendente de Manutenção': '#EF4444', 'Inativo': '#9CA3AF', 'Em Reparo': '#3B82F6', 'Pendente': '#EF4444'}
        },
        "Violeta Intenso": {
            "primaria": "#7C3AED", "secundaria": "#DDD6FE",
            "filtro_logo": "brightness(0) saturate(100%) invert(29%) sepia(91%) saturate(2325%) hue-rotate(251deg) brightness(96%) contrast(94%)",
            "mapa": {'OK': '#7C3AED', 'Pendente de Manutenção': '#F43F5E', 'Inativo': '#4B5563', 'Em Reparo': '#10B981', 'Pendente': '#F43F5E'}
        },
        "Aço Industrial": {
            "primaria": "#475569", "secundaria": "#94A3B8",
            "filtro_logo": "brightness(0) saturate(100%) invert(32%) sepia(13%) saturate(1054%) hue-rotate(174deg) brightness(92%) contrast(87%)",
            "mapa": {'OK': '#475569', 'Pendente de Manutenção': '#EA580C', 'Inativo': '#94A3B8', 'Em Reparo': '#06B6D4', 'Pendente': '#EA580C'}
        },
        "Menta Pastel": {
            "primaria": "#059669", "secundaria": "#A7F3D0",
            "filtro_logo": "brightness(0) saturate(100%) invert(87%) sepia(21%) saturate(601%) hue-rotate(107deg) brightness(101%) contrast(98%)",
            "mapa": {'OK': '#059669', 'Pendente de Manutenção': '#D97706', 'Inativo': '#D1D5DB', 'Em Reparo': '#2563EB', 'Pendente': '#D97706'}
        },
        "Lava Vulcânica": {
            "primaria": "#DC2626", "secundaria": "#FCA5A5",
            "filtro_logo": "brightness(0) saturate(100%) invert(18%) sepia(93%) saturate(4174%) hue-rotate(354deg) brightness(91%) contrast(93%)",
            "mapa": {'OK': '#DC2626', 'Pendente de Manutenção': '#4B5563', 'Inativo': '#1F2937', 'Em Reparo': '#F59E0B', 'Pendente': '#4B5563'}
        },
        "Orquídea Soft": {
            "primaria": "#DB2777", "secundaria": "#F472B6",
            "filtro_logo": "brightness(0) saturate(100%) invert(67%) sepia(20%) saturate(1814%) hue-rotate(299deg) brightness(98%) contrast(95%)",
            "mapa": {'OK': '#DB2777', 'Pendente de Manutenção': '#843DFF', 'Inativo': '#9CA3AF', 'Em Reparo': '#00F5D4', 'Pendente': '#843DFF'}
        },
        "Petróleo Profundo": {
            "primaria": "#155E75", "secundaria": "#22D3EE",
            "filtro_logo": "brightness(0) saturate(100%) invert(33%) sepia(17%) saturate(3015%) hue-rotate(152deg) brightness(88%) contrast(89%)",
            "mapa": {'OK': '#155E75', 'Pendente de Manutenção': '#BE123C', 'Inativo': '#64748B', 'Em Reparo': '#10B981', 'Pendente': '#BE123C'}
        },
        "Glow Cyber": {
            "primaria": "#ADFF2F", "secundaria": "#00FFFF",
            "filtro_logo": "brightness(0) saturate(100%) invert(86%) sepia(35%) saturate(3211%) hue-rotate(44deg) brightness(103%) contrast(104%)",
            "mapa": {'OK': '#7FFF00', 'Pendente de Manutenção': '#FF0055', 'Inativo': '#222222', 'Em Reparo': '#00FFFF', 'Pendente': '#FF0055'}
        },
        "Bronze Classic": {
            "primaria": "#CD7F32", "secundaria": "#E6C29E",
            "filtro_logo": "brightness(0) saturate(100%) invert(56%) sepia(21%) saturate(1215%) hue-rotate(345deg) brightness(91%) contrast(86%)",
            "mapa": {'OK': '#A0522D', 'Pendente de Manutenção': '#8B0000', 'Inativo': '#708090', 'Em Reparo': '#2E8B57', 'Pendente': '#8B0000'}
        },
        "Midnight Blue": {
            "primaria": "#1E3A8A", "secundaria": "#93C5FD",
            "filtro_logo": "brightness(0) saturate(100%) invert(16%) sepia(42%) saturate(4915%) hue-rotate(219deg) brightness(92%) contrast(101%)",
            "mapa": {'OK': '#1E3A8A', 'Pendente de Manutenção': '#F59E0B', 'Inativo': '#475569', 'Em Reparo': '#10B981', 'Pendente': '#F59E0B'}
        },
        "Oásis Deserto": {
            "primaria": "#ED8936", "secundaria": "#FBD38D",
            "filtro_logo": "brightness(0) saturate(100%) invert(64%) sepia(34%) saturate(2311%) hue-rotate(345deg) brightness(97%) contrast(92%)",
            "mapa": {'OK': '#DD6B20', 'Pendente de Manutenção': '#E53E3E', 'Inativo': '#A0AEC0', 'Em Reparo': '#319795', 'Pendente': '#E53E3E'}
        },
        "Neon Violet": {
            "primaria": "#9F7AEA", "secundaria": "#E9D8FD",
            "filtro_logo": "brightness(0) saturate(100%) invert(58%) sepia(32%) saturate(2300%) hue-rotate(222deg) brightness(96%) contrast(93%)",
            "mapa": {'OK': '#805AD5', 'Pendente de Manutenção': '#ED64A6', 'Inativo': '#4A5568', 'Em Reparo': '#319795', 'Pendente': '#ED64A6'}
        },
        "Iceberg Antártica": {
            "primaria": "#63B3ED", "secundaria": "#BEE3F8",
            "filtro_logo": "brightness(0) saturate(100%) invert(72%) sepia(25%) saturate(1412%) hue-rotate(187deg) brightness(97%) contrast(94%)",
            "mapa": {'OK': '#3182CE', 'Pendente de Manutenção': '#DD6B20', 'Inativo': '#A0AEC0', 'Em Reparo': '#319795', 'Pendente': '#DD6B20'}
        },
        "Canyon Rust": {
            "primaria": "#C53030", "secundaria": "#FEB2B2",
            "filtro_logo": "brightness(0) saturate(100%) invert(24%) sepia(61%) saturate(3501%) hue-rotate(345deg) brightness(88%) contrast(92%)",
            "mapa": {'OK': '#9B2C2C', 'Pendente de Manutenção': '#DD6B20', 'Inativo': '#718096', 'Em Reparo': '#2B6CB0', 'Pendente': '#DD6B20'}
        },
        "Malva Real": {
            "primaria": "#D53F8C", "secundaria": "#FED7E2",
            "filtro_logo": "brightness(0) saturate(100%) invert(43%) sepia(45%) saturate(2314%) hue-rotate(301deg) brightness(91%) contrast(92%)",
            "mapa": {'OK': '#9B2C2C', 'Pendente de Manutenção': '#805AD5', 'Inativo': '#718096', 'Em Reparo': '#319795', 'Pendente': '#805AD5'}
        },
        "Açaí Fresh": {
            "primaria": "#44337A", "secundaria": "#B794F4",
            "filtro_logo": "brightness(0) saturate(100%) invert(21%) sepia(34%) saturate(2102%) hue-rotate(244deg) brightness(91%) contrast(93%)",
            "mapa": {'OK': '#553C9A', 'Pendente de Manutenção': '#E53E3E', 'Inativo': '#718096', 'Em Reparo': '#38A169', 'Pendente': '#E53E3E'}
        },
        "Militar Ops": {
            "primaria": "#2F855A", "secundaria": "#9AE6B4",
            "filtro_logo": "brightness(0) saturate(100%) invert(41%) sepia(25%) saturate(1402%) hue-rotate(105deg) brightness(91%) contrast(88%)",
            "mapa": {'OK': '#276749', 'Pendente de Manutenção': '#C53030', 'Inativo': '#A0AEC0', 'Em Reparo': '#2B6CB0', 'Pendente': '#C53030'}
        },
        "Electric Tangerine": {
            "primaria": "#FF6B6B", "secundaria": "#FFD2D2",
            "filtro_logo": "brightness(0) saturate(100%) invert(54%) sepia(42%) saturate(2154%) hue-rotate(325deg) brightness(101%) contrast(102%)",
            "mapa": {'OK': '#FF4757', 'Pendente de Manutenção': '#2F3542', 'Inativo': '#747D8C', 'Em Reparo': '#1E90FF', 'Pendente': '#2F3542'}
        },
        "Vaporwave Sun": {
            "primaria": "#FFCC00", "secundaria": "#FF007F",
            "filtro_logo": "brightness(0) saturate(100%) invert(81%) sepia(65%) saturate(2104%) hue-rotate(5deg) brightness(102%) contrast(101%)",
            "mapa": {'OK': '#FF007F', 'Pendente de Manutenção': '#7B2CBF', 'Inativo': '#1A1A1A', 'Em Reparo': '#00F5D4', 'Pendente': '#7B2CBF'}
        }
    }
    
    if "paleta_cor" not in st.session_state:
        try:
            config_resp = supabase.table("configuracoes").select("valor").eq("chave", "paleta_padrao").execute()
            if config_resp.data:
                st.session_state.paleta_cor = config_resp.data[0]["valor"]
            else:
                st.session_state.paleta_cor = "Azul Corporativo"
        except:
            st.session_state.paleta_cor = "Azul Corporativo"

    def atualizar_paleta_instantaneo():
        st.session_state.paleta_cor = st.session_state.nova_paleta_selecionada
        registrar_historico("ALTERAR APARÊNCIA", f"Paleta alterada temporariamente para {st.session_state.paleta_cor}")

    cor_atual = paletas_config[st.session_state.paleta_cor]["primaria"]
    cor_secundaria = paletas_config[st.session_state.paleta_cor]["secundaria"]
    filtro_atual = paletas_config[st.session_state.paleta_cor]["filtro_logo"]
    mapa_cores_plotly = paletas_config[st.session_state.paleta_cor]["mapa"]

    # --- 4. ESTILO CSS REFINADO ---
    st.markdown(f"""
        <style>
        html, body, [data-testid="stWidgetLabel"] p, .stSelectbox label, .stMultiSelect label {{ 
            font-size: 1.05rem !important;
            font-weight: 600 !important;
        }}
        [data-testid="stDataFrame"] {{
            font-size: 1.0rem !important;
        }}
        [data-testid="stSidebar"] label {{ 
            font-size: 1.05rem !important;
            font-weight: 700 !important; 
            color: {cor_atual} !important; 
        }}
        span[data-baseweb="tag"] {{ 
            background-color: {cor_atual} !important;
            color: white !important; 
            font-size: 0.95rem !important;
        }}
        
        div[data-testid="stForm"] {{
            border: 3px solid {cor_atual} !important;
        }}
        
        .st-key-painel_bi_container {{
            border: 5px solid {cor_atual} !important;
            border-radius: 12px !important;
            padding: 25px !important;
            background-color: transparent !important;
            margin-bottom: 20px !important;
        }}
        
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border: none !important;
        }}
        
        .metric-card {{
            background-color: rgba(128, 128, 128, 0.12);
            backdrop-filter: blur(4px);
            padding: 0.8rem; 
            border-radius: 10px; 
            text-align: center; 
            box-shadow: 0px 3px 8px rgba(0, 0, 0, 0.08); 
            border: 3px solid {cor_secundaria};
            display: flex; 
            flex-direction: column; 
            justify-content: center; 
            align-items: center; 
            height: 110px; 
            margin-bottom: 8px;
        }}
        .metric-title {{ 
            font-size: 1.0rem;
            font-weight: 800; 
            text-transform: uppercase; 
            margin-bottom: 3px; 
            color: {cor_atual}; 
        }}
        .metric-value {{ 
            font-size: 1.8rem;
            font-weight: 900; 
        }}
        
        .stTabs [data-baseweb="tab-list"] {{
            background-color: transparent !important;
            border-style: none !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            font-size: 3.0rem !important;
            font-weight: 700 !important;
            padding: 18px 36px !important;
            background-color: transparent !important;
            border-style: none !important;
        }}
        .stTabs [aria-selected="true"] p {{
            color: {cor_atual} !important;
        }}
        .stTabs [data-baseweb="tab-highlight-line"] {{
            background-color: {cor_atual} !important;
        }}
        
        button[kind="primary"], [data-testid="stDownloadButton"] button {{ 
            background-color: {cor_atual} !important;
            border-color: {cor_atual} !important; 
            color: white !important;
            font-size: 1.1rem !important;
            font-weight: 700 !important;
            transition: background-color 0.2s ease-in-out;
        }}
        button[kind="primary"]:hover, [data-testid="stDownloadButton"] button:hover {{
            background-color: {cor_secundaria} !important; 
            border-color: {cor_secundaria} !important;
            color: white !important;
        }}
        
        button[kind="secondary"] {{ 
            background-color: transparent !important;
            border: 2px solid {cor_secundaria} !important; 
            color: {cor_atual} !important;
            font-size: 1.1rem !important;
            font-weight: 700 !important;
        }}
        button[kind="secondary"]:hover {{
            background-color: {cor_secundaria} !important;
            color: white !important;
        }}

        div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, div[data-baseweb="textarea"] > div, div[data-testid="stMultiSelect"] div[role="combobox"] {{
            box-shadow: none !important; outline: none !important;
        }}

        div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within, div[data-baseweb="textarea"]:focus-within, div[data-testid="stMultiSelect"] div[role="combobox"]:focus-within {{
            border-color: {cor_atual} !important; box-shadow: none !important; outline: none !important;
        }}
        
        [data-testid="stImage"] img {{
            filter: {filtro_atual} !important;
            transition: filter 0.2s ease-in-out;
        }}
        
        .main .block-container {{ max-width: 1700px; padding-top: 1.5rem; }}
        </style>
        """, unsafe_allow_html=True)

    # --- HEADER DINÂMICO ---
    col_header_logo, col_header_tit = st.columns([1, 5], vertical_alignment="center") 
    with col_header_logo:
        if os.path.exists("bithelplogo.png"): 
            st.image("bithelplogo.png", use_container_width=True)
    with col_header_tit:
        st.markdown(f"<h1 style='margin: 0; color: {cor_atual}; font-weight: 700; font-size: 2.8rem;'>Bithelp - GearTech Soluções em BI e Help Desk</h1>", unsafe_allow_html=True)
   
    st.markdown("---")

    # --- 5. BARRA LATERAL ---
    st.sidebar.markdown(f"<h3 style='text-align: center; color: {cor_atual}; margin-top:0;'>🔎 CONFIGURAÇÕES</h3>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='text-align: center; font-size: 0.95rem;'>Usuário: {st.session_state.usuario_nome}<br>Acesso: {st.session_state.perfil}</p>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    lista_opcoes_paleta = list(paletas_config.keys())
    indice_atual = lista_opcoes_paleta.index(st.session_state.paleta_cor)
    
    st.sidebar.selectbox(
        "🎨 Personalizar Minha Aparência", 
        options=lista_opcoes_paleta,
        index=indice_atual,
        key="nova_paleta_selecionada",
        on_change=atualizar_paleta_instantaneo
    )

    if st.session_state.perfil == "Administrador":
        st.sidebar.markdown("<p style='text-align: center; font-weight: bold; margin-bottom: 2px;'>Padrão Geral do Sistema</p>", unsafe_allow_html=True)
        col_fixar, col_limpar = st.sidebar.columns(2)
        
        with col_fixar:
            if st.button("📌 Fixar", use_container_width=True, type="primary"):
                try:
                    payload_config = {"id": 1, "chave": "paleta_padrao", "valor": st.session_state.paleta_cor}
                    supabase.table("configuracoes").upsert(payload_config).execute()
                    registrar_historico("FIXAR PALETA", f"Fixou a paleta global '{st.session_state.paleta_cor}'")
                    st.toast("Paleta fixada como padrão geral!", icon='📌')
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Erro ao salvar: {e}")
                    
        with col_limpar:
            if st.button("❌ Desfixar", use_container_width=True, type="secondary"):
                try:
                    supabase.table("configuracoes").delete().eq("id", 1).execute()
                    registrar_historico("DESFIXAR PALETA", "Resetou a paleta global para o padrão de fábrica")
                    st.session_state.paleta_cor = "Azul Corporativo"
                    st.toast("Padrão do sistema resetado!", icon='🔄')
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Erro ao limpar: {e}")

        # --- FILTROS DO DASHBOARD (APENAS PARA ADMINISTRADOR) ---
    if st.session_state.perfil == "Administrador":
        st.sidebar.markdown("---")
        st.sidebar.markdown("<p style='text-align: center; font-weight: bold; margin-bottom: 5px;'>Filtros do Inventário</p>", unsafe_allow_html=True)
        def criar_filtro(label, column_name):
            if column_name in df.columns:
                opcoes = sorted([str(x) for x in df[column_name].dropna().unique() if str(x).strip() != ""])
                return st.sidebar.multiselect(label, options=opcoes, default=opcoes)
            return []

        f_lab = criar_filtro("Laboratório", "laboratorio")
        # Cria uma lista fixa com apenas as duas opções
        opcoes_status = ["OK", "Pendente de Manutenção"]
        f_status = st.sidebar.multiselect("Status da Máquina", options=opcoes_status, default=opcoes_status)
        f_so = criar_filtro("Sistema Operacional", "sistema_operacional")
        f_familia = criar_filtro("Família CPU", "familia_cpu")
    else:
        # Usuários não-admin não têm filtros (valores vazios)
        f_lab = []
        f_status = []
        f_so = []
        f_familia = []
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair / Logout", use_container_width=True):
        registrar_historico("LOGOUT", "Usuário encerrou a sessão")
        st.session_state.autenticado = False
        st.session_state.perfil = None
        st.session_state.usuario_nome = None
        st.rerun()

    # --- 6. NAVEGAÇÃO DINÂMICA POR ABAS ---
    if st.session_state.perfil == "Administrador":
        abas_labels = ["📊 Dashboard", "🛠️ Central de Chamados", "📋 Gestão de Chamados", "⚙️ Painel Administrativo"]
        tabs = st.tabs(abas_labels)
        aba_dash, aba_chamado, aba_gestao, aba_admin = tabs[0], tabs[1], tabs[2], tabs[3]
    elif st.session_state.perfil == "Assistente":
        abas_labels = ["🛠️ Central de Chamados", "📋 Gestão de Chamados"]
        tabs = st.tabs(abas_labels)
        aba_dash, aba_chamado, aba_gestao, aba_admin = None, tabs[0], tabs[1], None
    else: 
        abas_labels = ["🛠️ Central de Chamados"]
        tabs = st.tabs(abas_labels)
        aba_dash, aba_chamado, aba_gestao, aba_admin = None, tabs[0], None, None

    # --- DEFINE MODAIS ---
    @st.dialog("🛠️ Registrar Novo Chamado Técnico", width="large")
    def modal_abrir_chamado(dataframe_maquinas):
        mapa_maquinas_id = {str(row['identificacao']): row['id'] for _, row in dataframe_maquinas.iterrows() if str(row['identificacao']).strip() != ""}
        opcoes_select = ["Clique para selecionar..."] + list(mapa_maquinas_id.keys())
        with st.form("form_abrir_chamado", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                m_sel = st.selectbox("Selecione a Máquina", options=opcoes_select)
                prioridade_input = st.selectbox("Prioridade", ["Baixa", "Média", "Alta"])
            with col_f2:
                desc_input = st.text_area("Descrição do Problema", placeholder="Descreva o defeito aqui...")
            
            if st.form_submit_button("REGISTRAR CHAMADO AGORA", use_container_width=True, type="primary"):
                if m_sel != "Clique para selecionar..." and desc_input:
                    maquina_info = dataframe_maquinas[dataframe_maquinas['identificacao'] == m_sel]
                    lab_ref = maquina_info['laboratorio'].iloc[0] if not maquina_info.empty else "N/A"
                    try:
                        supabase.table("chamados").insert({"maquina_id": int(mapa_maquinas_id[m_sel]), "laboratorio": str(lab_ref), "descricao": desc_input, "prioridade": prioridade_input}).execute()
                        supabase.table("maquinas").update({"status": "Pendente de Manutenção"}).eq("id", int(mapa_maquinas_id[m_sel])).execute()
                        registrar_historico("ABERTURA DE CHAMADO", f"Chamado aberto para computador {m_sel} ({prioridade_input}). Desc: {desc_input}")
                        st.toast(f"✅ Chamado registrado para {m_sel}!", icon='🛠️')
                        st.rerun() 
                    except Exception as e: 
                        st.error(f"Erro ao salvar no banco: {e}")
                else: 
                    st.error("⚠️ Preencha todos os campos antes de registrar!")

    @st.dialog("📋 Tabela Completa de Dados", width="large")
    def modal_tabela_dados(dados):
        st.dataframe(dados[["identificacao", "laboratorio", "status", "sistema_operacional", "familia_cpu", "qtde_memoria_ram_gb", "armazenamento_tipo"]], use_container_width=True, hide_index=True)

    @st.dialog("👥 Gestão de Usuários", width="large")
    def modal_gestao_usuarios():
        col_usr_cad, col_usr_exc = st.columns([3, 1])
        with col_usr_cad:
            st.markdown("**Cadastrar Novo Usuário**")
            with st.form("form_cadastro_usuario", clear_on_submit=True):
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    u_nome = st.text_input("Nome/Login de Usuário*")
                    u_email = st.text_input("E-mail corporativo*")
                with col_u2:
                    u_senha = st.text_input("Senha de Acesso*", type="password")
                    u_perfil = st.selectbox("Nível de Acesso (Perfil)*", ["Usuário", "Assistente", "Administrador"])
                
                if st.form_submit_button("CADASTRAR NOVO USUÁRIO", use_container_width=True, type="primary"):
                    if u_nome and u_email and u_senha:
                        try:
                            user_payload = {"nome": u_nome.strip(), "email": u_email.strip(), "senha": u_senha.strip(), "perfil": u_perfil}
                            supabase.table("usuarios").insert(user_payload).execute()
                            registrar_historico("CADASTRAR USUÁRIO", f"Criado usuário {u_nome} com nível {u_perfil}")
                            st.success(f"✅ Usuário '{u_nome}' registrado.")
                            st.rerun()
                        except Exception as e: 
                            st.error(f"Erro: {e}")
                    else: 
                        st.warning("Preencha todos os campos.")
        
        with col_usr_exc:
            st.markdown("**Remover Usuário**")
            try:
                resp_usr = supabase.table("usuarios").select("id, nome").execute()
                mapa_usuarios = {user["nome"]: user["id"] for user in resp_usr.data} if resp_usr.data else {}
                if mapa_usuarios:
                    usr_exc_sel = st.selectbox("Selecione:", options=list(mapa_usuarios.keys()), key="del_usr_box")
                    if usr_exc_sel.lower() == st.session_state.usuario_nome.lower():
                        st.warning("Você não pode se excluir.")
                    else:
                        if st.button("EXCLUIR USUÁRIO", use_container_width=True):
                            supabase.table("usuarios").delete().eq("id", mapa_usuarios[usr_exc_sel]).execute()
                            registrar_historico("REMOVER USUÁRIO", f"Deletou o usuário {usr_exc_sel}")
                            st.success(f"Usuário '{usr_exc_sel}' removido!")
                            st.rerun()
            except Exception as e: 
                st.error(f"Erro: {e}")

    @st.dialog("⚡ Atualização de Status Expressa")
    def modal_status_expresso():
        mapa_maquinas_geral = {str(row['identificacao']): row['id'] for _, row in df.iterrows() if str(row['identificacao']).strip() != ""}
        maq_status_sel = st.selectbox("Selecione a Máquina:", options=list(mapa_maquinas_geral.keys()), key="quick_maq")
        novo_status_sel = st.selectbox("Novo Status:", ["OK", "Pendente de Manutenção", "Inativo", "Em Reparo"], key="quick_status")
        if st.button("ATUALIZAR STATUS", use_container_width=True, type="primary"):
            try:
                supabase.table("maquinas").update({"status": novo_status_sel}).eq("id", mapa_maquinas_geral[maq_status_sel]).execute()
                registrar_historico("STATUS EXPRESSO", f"Mudou status da máquina {maq_status_sel} para {novo_status_sel}")
                st.toast("Status alterado!", icon='⚙️')
                st.rerun()
            except Exception as e: 
                st.error(f"Erro: {e}")

    @st.dialog("📥 Importar e Exportar Planilhas (CSV)")
    def modal_planilhas():
        col_csv_in, col_csv_out = st.columns(2)
        with col_csv_in:
            st.markdown("**Importar Inventário (CSV)**")
            with st.form("import_csv_form"):
                arquivo_csv = st.file_uploader("Selecione o arquivo CSV", type="csv")
                if st.form_submit_button("Confirmar Importação", use_container_width=True, type="primary"):
                    if arquivo_csv:
                        # 👇 DETECTA O SEPARADOR AUTOMATICAMENTE
                        import csv
                        try:
                            # Lê o arquivo como texto para detectar o separador
                            file_content = arquivo_csv.getvalue().decode('utf-8-sig')
                            sniffer = csv.Sniffer()
                            delimiter = sniffer.sniff(file_content).delimiter
                        except:
                            # Se não conseguir detectar, usa vírgula como padrão
                            delimiter = ','
                        
                        # Lê o CSV com o separador detectado
                        df_importado = pd.read_csv(arquivo_csv, sep=delimiter, encoding='utf-8-sig')
                        
                        # Remove a coluna 'id' se existir
                        if 'id' in df_importado.columns:
                            df_importado = df_importado.drop(columns=['id'])
                        
                        # Substitui NaN por None
                        df_importado = df_importado.replace({pd.NA: None, float('nan'): None})
                        
                        # Converte colunas para o tipo correto
                        for col in df_importado.columns:
                            if df_importado[col].dtype in ['float64', 'int64']:
                                df_importado[col] = df_importado[col].fillna(0)
                            else:
                                df_importado[col] = df_importado[col].fillna('')
                        
                        # Garante que não haja NaN
                        df_importado = df_importado.where(pd.notnull(df_importado), None)
                        
                        # Converte para lista de dicionários
                        dados_para_inserir = df_importado.to_dict(orient='records')
                        
                        # Remove qualquer NaN residual
                        for linha in dados_para_inserir:
                            for chave, valor in linha.items():
                                if pd.isna(valor):
                                    linha[chave] = None
                        
                        # Insere no Supabase
                        supabase.table("maquinas").insert(dados_para_inserir).execute()
                        registrar_historico("IMPORTAR CSV", f"Importou lote de {len(df_importado)} máquinas via planilha")
                        st.success(f"✅ Importação concluída! {len(df_importado)} máquinas adicionadas.")
                        st.rerun()
        with col_csv_out:
            st.markdown("**Exportar Dados Atuais**")
            st.markdown("<br><br>", unsafe_allow_html=True)
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="BAIXAR PLANILHA CSV COMPLETA", data=csv_data, file_name='inventario_bithelp.csv', use_container_width=True)

    @st.dialog("➕ Cadastro e Edição Detalhada", width="large")
    def modal_formulario_completo():
        col_cad, col_exc = st.columns([3, 1])
        with col_cad:
            mapa_maquinas = {str(row['identificacao']): row for _, row in df.iterrows() if str(row['identificacao']).strip() != ""}
            modo = st.radio("Ação:", ["Novo Cadastro", "Editar Existente"], horizontal=True)
             
            lista_campos = ["identificacao", "mac", "laboratorio", "familia_cpu", "modelo_cpu", "fabricante", "geracao", "qtde_memoria_ram_gb", "armazenamento_tipo", "qtde_ssd_gb", "qtde_hd_gb", "sistema_operacional", "status", "anomalia", "observacao"]
            vals = {k: "" for k in lista_campos}
            vals["status"] = "OK"
            vals["sistema_operacional"] = "Windows 11"
            maquina_selecionada = None
             
            if modo == "Editar Existente" and mapa_maquinas:
                escolha = st.selectbox("Selecione a Máquina para editar:", options=list(mapa_maquinas.keys()))
                maquina_selecionada = mapa_maquinas[escolha]
                for k in lista_campos: vals[k] = maquina_selecionada.get(k, "") if pd.notna(maquina_selecionada.get(k, "")) else ""

            # 👇 FUNÇÃO PARA GARANTIR STRING
            def garantir_string(valor):
                if valor is None:
                    return ""
                if pd.isna(valor):
                    return ""
                if str(valor).lower() in ["nan", "none", "null", ""]:
                    return ""
                return str(valor)

            with st.form("form_cadastro_full", clear_on_submit=(modo == "Novo Cadastro")):
                c1, c2, c3 = st.columns(3)
                with c1: new_id = st.text_input("Identificação (ID/TAG)*", value=garantir_string(vals["identificacao"]))
                with c2: new_mac = st.text_input("Endereço MAC", value=garantir_string(vals["mac"]))
                with c3: new_lab = st.text_input("Laboratório*", value=garantir_string(vals["laboratorio"]))

                c4, c5, c6, c7 = st.columns(4)
                with c4: new_fam = st.text_input("Família CPU*", value=garantir_string(vals["familia_cpu"]))
                with c5: new_mod = st.text_input("Modelo CPU", value=garantir_string(vals["modelo_cpu"]))
                with c6: new_fab = st.text_input("Fabricante", value=garantir_string(vals["fabricante"]))
                with c7: new_ger = st.text_input("Geração", value=garantir_string(vals["geracao"]))
                
                c8, c9, col_d1, col_d2 = st.columns(4)
                with c8:
                    new_ram = st.text_input("RAM (GB)", value=garantir_string(vals.get("qtde_memoria_ram_gb", "")))
                with c9:
                    opcoes_disco = ["SSD", "HD", "SSD + HD", "SSD NVMe M.2", "SSD / HD", "SSD "]
                    val_atual_disco = garantir_string(vals.get("armazenamento_tipo", ""))
                    
                    if val_atual_disco not in opcoes_disco and val_atual_disco.strip() != "":
                        opcoes_disco.append(val_atual_disco)
                    
                    try:
                        index_disco = opcoes_disco.index(val_atual_disco) if val_atual_disco in opcoes_disco else 0
                    except ValueError:
                        index_disco = 0
                    
                    new_tipo_arm = st.selectbox("Tipo Disco", opcoes_disco, index=index_disco)
                with col_d1:
                    new_ssd = st.text_input("SSD (GB)", value=garantir_string(vals.get("qtde_ssd_gb", "")))
                with col_d2:
                    new_hd = st.text_input("HD (GB)", value=garantir_string(vals.get("qtde_hd_gb", "")))

                c12, c13, c14 = st.columns(3)
                with c12:
                    opcoes_so = ["Windows 11", "Windows 10", "Windows 7", "Linux", "MacOS"]
                    val_so_atual = str(vals["sistema_operacional"]).strip()
                    if val_so_atual not in opcoes_so:
                        opcoes_so.append(val_so_atual) if val_so_atual != "" else None
                    new_so = st.selectbox("Sistema Operacional*", opcoes_so, index=opcoes_so.index(val_so_atual) if val_so_atual in opcoes_so else 0)
                with c13:
                    opcoes_status = ["OK", "Pendente de Manutenção", "Inativo", "Em Reparo", "Pendente"]
                    val_st_atual = str(vals["status"]).strip()
                    if val_st_atual not in opcoes_status:
                        opcoes_status.append(val_st_atual) if val_st_atual != "" else None
                    new_status = st.selectbox("Status*", opcoes_status, index=opcoes_status.index(val_st_atual) if val_st_atual in opcoes_status else 0)
                with c14:
                    new_anomalia = st.text_input("Anomalia Atual", value=garantir_string(vals.get("anomalia", "")))

                new_obs = st.text_area("Observações Adicionais", value=garantir_string(vals["observacao"]))


                st.markdown("---")
                txt_btn = "SALVAR ALTERAÇÕES TÉCNICAS" if modo == "Editar Existente" else "CADASTRAR NOVO ATIVO"
                if st.form_submit_button(txt_btn, use_container_width=True, type="primary"):
                    if new_id and new_lab and new_fam:
                        try:
                            ram_val = int(new_ram.split('.')[0]) if str(new_ram).strip().replace('.0','').isdigit() else None
                            ssd_val = int(new_ssd.split('.')[0]) if str(new_ssd).strip().replace('.0','').isdigit() else None
                            hd_val = int(new_hd.split('.')[0]) if str(new_hd).strip().replace('.0','').isdigit() else None

                            payload = {
                                "identificacao": new_id, "mac": new_mac, "laboratorio": new_lab,
                                "familia_cpu": new_fam, "modelo_cpu": new_mod, "fabricante": new_fab,
                                "geracao": new_ger, "qtde_memoria_ram_gb": ram_val, 
                                "armazenamento_tipo": new_tipo_arm, "qtde_ssd_gb": ssd_val, 
                                "qtde_hd_gb": hd_val, "sistema_operacional": new_so,
                                "status": new_status, "anomalia": new_anomalia, "observacao": new_obs
                            }
                            
                            if modo == "Editar Existente":
                                supabase.table("maquinas").update(payload).eq("id", maquina_selecionada['id']).execute()
                                registrar_historico("EDIÇÃO DE ATIVO", f"Editou propriedades do computador {new_id}")
                                st.toast("Dados alterados!", icon='💾')
                            else:
                                supabase.table("maquinas").insert(payload).execute()
                                registrar_historico("CADASTRO DE ATIVO", f"Cadastrou novo computador {new_id} no Lab {new_lab}")
                                st.cache_data.clear()
                            st.rerun()
                        except Exception as e: 
                            st.error(f"Erro: {e}")
                    else: 
                        st.warning("Preencha os campos obrigatórios (*)")

        with col_exc:
            st.markdown("**Remover Ativo**")
            if mapa_maquinas:
                maq_exc = st.selectbox("Escolha:", options=list(mapa_maquinas.keys()), key="del_box")
                st.error("⚠️ Apaga também os chamados!")
                if st.button("EXCLUIR MÁQUINA", use_container_width=True):
                    supabase.table("maquinas").delete().eq("id", mapa_maquinas[maq_exc]['id']).execute()
                    registrar_historico("REMOVER ATIVO", f"Deletou a máquina {maq_exc} permanentemente")
                    st.toast("Removido!", icon='🗑️')
                    st.cache_data.clear()
                    st.rerun()

    # Central de Relatórios e Histórico de Auditoria (Modal)
    @st.dialog("📋 Central de Relatórios & Histórico de Auditoria", width="large")
    def modal_central_relatorios():
        st.markdown("Acompanhe o registro de auditoria em tempo real.")
        
        # Adicionar seletor de ordenação
        col_ord1, col_ord2 = st.columns([1, 3])
        with col_ord1:
            ordem = st.radio(
                "Ordenar por Data",
                options=["Mais Recente", "Mais Antigo"],
                index=0,
                horizontal=True
            )
        
        df_hist = carregar_historico()
        if not df_hist.empty:
            # CORREÇÃO DO HORÁRIO (MANTER COMO DATETIME PARA ORDENAR)
            df_hist['created_at'] = pd.to_datetime(df_hist['created_at'])
            if df_hist['created_at'].dt.tz is None:
                df_hist['created_at'] = df_hist['created_at'].dt.tz_localize('UTC')
            df_hist['created_at'] = df_hist['created_at'].dt.tz_convert('America/Sao_Paulo')
            
            # 👇 ORDENAR ANTES DE CONVERTER PARA STRING
            if ordem == "Mais Recente":
                df_hist = df_hist.sort_values(by='created_at', ascending=False)
            else:
                df_hist = df_hist.sort_values(by='created_at', ascending=True)
            
            # 👇 AGORA CONVERTER PARA STRING (DEPOIS DE ORDENAR)
            df_hist['created_at'] = df_hist['created_at'].dt.strftime('%d/%m/%Y - %H:%M:%S')
            
            df_hist_exibir = df_hist[['created_at', 'usuario', 'perfil', 'acao', 'detalhes']].copy()
            df_hist_exibir.columns = ['Data/Hora', 'Operador', 'Nível de Acesso', 'Ação Executada', 'Detalhes Complementares']
            
            st.dataframe(df_hist_exibir, use_container_width=True, hide_index=True)
            
            csv_hist_data = df_hist_exibir.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 EMITIR E BAIXAR RELATÓRIO DE HISTÓRICO COMPLETO (CSV)",
                data=csv_hist_data,
                file_name='relatorio_auditoria_bithelp.csv',
                use_container_width=True,
                type="primary"
            )
        else:
            st.info("Nenhuma ação gravada no histórico ainda.")
            
    @st.dialog("📊 Gerar Relatório Gerencial", width="large")
    def modal_relatorio_pdf():
        st.markdown("### Selecione o período para o relatório")
        
        meses_pt = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
            5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
            9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
        }
        
        col_mes, col_ano = st.columns(2)
        with col_mes:
            from datetime import datetime
            mes_selecionado = st.selectbox(
                "Mês", 
                options=list(range(1, 13)),
                format_func=lambda x: meses_pt[x],
                index=datetime.now().month - 1
            )
        with col_ano:
            ano_selecionado = st.number_input("Ano", min_value=2024, max_value=2030, value=datetime.now().year)
        
        st.markdown("---")
        
        if st.button("✅ GERAR RELATÓRIO PDF", use_container_width=True, type="primary"):
            with st.spinner("Gerando relatório... Isso pode levar alguns segundos."):
                try:
                    pdf_path = gerar_relatorio_pdf(ano_selecionado, mes_selecionado)
                    
                    if pdf_path:
                        with open(pdf_path, "rb") as f:
                            pdf_data = f.read()
                        
                        import os
                        os.unlink(pdf_path)
                        
                        nome_mes = meses_pt[mes_selecionado].lower()
                        nome_arquivo = f"relatorio_chamados_{nome_mes}_{ano_selecionado}.pdf"
                        
                        st.success(f"✅ Relatório gerado com sucesso!")
                        st.download_button(
                            label="📥 BAIXAR RELATÓRIO PDF",
                            data=pdf_data,
                            file_name=nome_arquivo,
                            mime="application/pdf",
                            use_container_width=True
                        )
                    else:
                        st.warning(f"ℹ️ Nenhum chamado foi aberto em {meses_pt[mes_selecionado]} de {ano_selecionado}.")
                except Exception as e:
                    st.error(f"❌ Erro ao gerar relatório: {e}")

    # --- ABA 1: DASHBOARD OTIMIZADA ---
    if aba_dash:
        with aba_dash:
            df_filtrado = df.copy()
            df_filtrado["laboratorio"] = df_filtrado["laboratorio"].astype(str).str.strip()
            df_filtrado["status"] = df_filtrado["status"].astype(str).str.strip().replace('Pendente', 'Pendente de Manutenção')
            df_filtrado["sistema_operacional"] = df_filtrado["sistema_operacional"].astype(str).str.strip()
            df_filtrado["familia_cpu"] = df_filtrado["familia_cpu"].astype(str).str.strip()
            df_filtrado["geracao"] = df_filtrado["geracao"].astype(str).str.strip()
            df_filtrado["armazenamento_tipo"] = df_filtrado["armazenamento_tipo"].astype(str).str.strip()
            df_filtrado["anomalia"] = df_filtrado["anomalia"].astype(str).str.strip()
            
            df_filtrado["qtde_memoria_ram_gb"] = pd.to_numeric(df_filtrado["qtde_memoria_ram_gb"], errors='coerce').fillna(0)
            df_filtrado["qtde_ssd_gb"] = pd.to_numeric(df_filtrado["qtde_ssd_gb"], errors='coerce').fillna(0)
            df_filtrado["qtde_hd_gb"] = pd.to_numeric(df_filtrado["qtde_hd_gb"], errors='coerce').fillna(0)

            if f_lab: df_filtrado = df_filtrado[df_filtrado["laboratorio"].isin(f_lab)]
            if f_status: df_filtrado = df_filtrado[df_filtrado["status"].isin(f_status)]
            if f_so: df_filtrado = df_filtrado[df_filtrado["sistema_operacional"].isin(f_so)]
            if f_familia: df_filtrado = df_filtrado[df_filtrado["familia_cpu"].isin(f_familia)]
            
            

            with st.container(key="painel_bi_container"):
                st.markdown(f"""
                    <p style='color: {cor_atual}; font-weight: 800; margin-top: -5px; margin-bottom: 20px; font-size:1.2rem; text-transform: uppercase;'>
                        📊 PAINEL DE GESTÃO E INTELIGÊNCIA DE INFRAESTRUTURA DE TI
                    </p>
                """, unsafe_allow_html=True)
                
                # --- CARDS DE INFRAESTRUTURA ---
                col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
                total_ativos = len(df_filtrado)
                
                with col_kpi1:
                    ativos_operacionais = len(df_filtrado[df_filtrado["status"] == "OK"])
                    pct_operacionais = (ativos_operacionais / total_ativos * 100) if total_ativos > 0 else 0
                    st.markdown(f'<div class="metric-card"><div class="metric-title">Ativos Saudáveis (OK)</div><div class="metric-value" style="color: #198754;">{ativos_operacionais} <span style="font-size:1.0rem; font-weight:normal;">({pct_operacionais:.1f}%)</span></div></div>', unsafe_allow_html=True)
                
                with col_kpi2:
                    ativos_parados = len(df_filtrado[df_filtrado["status"] != "OK"])
                    pct_parados = (ativos_parados / total_ativos * 100) if total_ativos > 0 else 0
                    st.markdown(f'<div class="metric-card"><div class="metric-title">Fora de Conformidade</div><div class="metric-value" style="color: #DC2626;">{ativos_parados} <span style="font-size:1.0rem; font-weight:normal;">({pct_parados:.1f}%)</span></div></div>', unsafe_allow_html=True)
                
                with col_kpi3:
                    legado_count = len(df_filtrado[df_filtrado["geracao"].isin(["1ª", "2ª"])])
                    st.markdown(f'<div class="metric-card"><div class="metric-title">Máquinas Obsoletas</div><div class="metric-value" style="color: {cor_atual};">{legado_count} un</div></div>', unsafe_allow_html=True)
                
                with col_kpi4:
                    # Contar chamados em aberto (não finalizados)
                    df_chamados_total = carregar_chamados()
                    if not df_chamados_total.empty:
                        chamados_abertos = len(df_chamados_total)
                        st.markdown(f'<div class="metric-card"><div class="metric-title">Chamados em Aberto</div><div class="metric-value" style="color: #FF6B6B;">{chamados_abertos}</div></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="metric-card"><div class="metric-title">Chamados em Aberto</div><div class="metric-value" style="color: #FF6B6B;">0</div></div>', unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # --- MIX DE GRÁFICOS EM 3 COLUNAS ---
                col_g_esquerda, col_g_centro, col_g_direita = st.columns([1.3, 1.3, 1.4])
               
               # GRÁFICO DE GERAÇÃO CPU 
                with col_g_esquerda:
                    if not df_filtrado.empty:
                        geracao_counts = df_filtrado[df_filtrado["geracao"] != ""].value_counts("geracao").reset_index(name="qtd")
                        fig_ger = px.bar(geracao_counts, x="geracao", y="qtd", title="<b>MATRIZ DE OBSOLESCÊNCIA DE CPU</b>")
                        fig_ger.update_traces(
                            marker_color=cor_atual, 
                            texttemplate='%{y}', 
                            textposition='inside',  # 👈 MUDOU para inside
                            textfont=dict(size=15, color="white")  # 👈 Fonte branca para contraste
                        )
                        fig_ger.update_layout(
                            showlegend=False, 
                            height=270, 
                            margin=dict(t=35, b=5, l=5, r=5),
                            title={'x': 0.45, 'xanchor': 'center'},
                            paper_bgcolor='rgba(0,0,0,0)', 
                            plot_bgcolor='rgba(0,0,0,0)',
                            yaxis=dict(visible=False),  # 👈 Remove eixo Y
                            xaxis=dict(title="Geração")
                        )
                        fig_ger.update_xaxes(showgrid=False)
                        fig_ger.update_yaxes(showgrid=False, visible=False)
                        st.plotly_chart(fig_ger, use_container_width=True)

                # GRÁFICO DE STATUS OPERACIONAL (DONUT) - Gráfico de Rosca
                with col_g_centro:
                    if not df_filtrado.empty:
                        status_counts = df_filtrado["status"].value_counts().reset_index(name="qtd")
                        fig_st_donut = px.pie(status_counts, values='qtd', names='status', hole=0.5, title="<b>STATUS OPERACIONAL GERAL</b>", color='status', color_discrete_map=mapa_cores_plotly)
                        fig_st_donut.update_traces(textfont=dict(size=15, color="white"), textinfo='percent', hovertemplate='<b>Status: %{label}</b><br>Quantidade: %{value}<br>Percentual: %{percent:.1f}%<extra></extra>')
                        fig_st_donut.update_layout(
                            showlegend=True, 
                            height=270,  # 👈 IGUAL aos outros
                            margin=dict(t=35, b=5, l=5, r=5),  # 👈 IGUAL aos outros
                            title={'x': 0.5, 'xanchor': 'center'},  # 👈 SEM 'y' para ficar igual
                            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5, font=dict(size=14)),
                            paper_bgcolor='rgba(0,0,0,0)', 
                            plot_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_st_donut, use_container_width=True)
                        
               # GRÁFICO DE CONVÊNIO DE SISTEMAS OPERACIONAIS - Gráfico de Barras        
                with col_g_direita:
                    if not df_filtrado.empty:
                        so_data = df_filtrado["sistema_operacional"].value_counts().reset_index(name="qtd")
                        fig_so = px.bar(so_data, x='qtd', y='sistema_operacional', orientation='h', text_auto=True, title="<b>DISTRIBUIÇÃO SO</b>")
                        fig_so.update_traces(
                            marker_color=cor_atual,  # 👈 MUDOU de cor_secundaria para cor_atual
                            textposition="inside",
                            textfont=dict(size=15, color="white"),
                            hovertemplate='<b>SO: %{y}</b><br>Quantidade: %{x}<extra></extra>'
                        )
                        fig_so.update_layout(
                            title_x=0.33, 
                            height=270, 
                            bargap=0.35,
                            margin=dict(t=35, b=5, l=5, r=5), 
                            paper_bgcolor='rgba(0,0,0,0)', 
                            plot_bgcolor='rgba(0,0,0,0)',
                            xaxis=dict(visible=False),  # 👈 REMOVE OS NÚMEROS 0,10,20
                            yaxis=dict(title="")
                        ) 
                        fig_so.update_xaxes(showgrid=False, title="")
                        fig_so.update_yaxes(showgrid=False, title="")
                        st.plotly_chart(fig_so, use_container_width=True)

                # --- SEÇÃO INFERIOR COMPLEMENTAR DE MANUTENÇÃO ---
                st.markdown("<hr style='margin: 15px 0; border-color: rgba(128,128,128,0.2);'>", unsafe_allow_html=True)
                col_g_infra, col_g_anomalias = st.columns([2.1, 1.9])
                
                # GRÁFICO DE CHAMADOS POR MÊS (LINHA DO TEMPO) - Gráfico de Colunas
                with col_g_infra:
                    # GRÁFICO DE CHAMADOS POR MÊS
                    df_chamados_total = carregar_chamados()
                    
                    if not df_chamados_total.empty:
                        # Processar dados para gráfico mensal
                        df_mensal = df_chamados_total.copy()
                        df_mensal['created_at'] = pd.to_datetime(df_mensal['created_at'])
                        
                        # Dicionário para converter meses para português
                        meses_pt = {
                            'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr',
                            'May': 'Mai', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
                            'Sep': 'Set', 'Oct': 'Out', 'Nov': 'Nov', 'Dec': 'Dez'
                        }
                        
                        # Criar mês/ano com nome em português
                        df_mensal['mes_num'] = df_mensal['created_at'].dt.month
                        df_mensal['ano'] = df_mensal['created_at'].dt.year
                        df_mensal['mes_ano'] = df_mensal['created_at'].dt.strftime('%b/%Y')
                        
                        # Substituir nome do mês por português
                        for en, pt in meses_pt.items():
                            df_mensal['mes_ano'] = df_mensal['mes_ano'].str.replace(en, pt)
                        
                        df_mensal['data_ref'] = df_mensal['created_at'].dt.to_period('M')
                        
                        # Agrupar por mês
                        df_agrupado = df_mensal.groupby(['mes_ano', 'data_ref']).size().reset_index(name='quantidade')
                        df_agrupado = df_agrupado.sort_values('data_ref')
                        
                        # Criar gráfico de barras
                        fig_chamados_mensal = px.bar(
                            df_agrupado, 
                            x='mes_ano', 
                            y='quantidade',
                            title="<b>CHAMADOS MENSAIS ABERTOS</b>",
                            text='quantidade',
                            color_discrete_sequence=[cor_atual]
                        )
                        
                        fig_chamados_mensal.update_traces(
                            textposition='inside',  # 👈 MUDOU para inside (dentro da barra)
                            marker_line_color=cor_secundaria,
                            marker_line_width=1.5,
                            textfont=dict(size=15, color="white")  # 👈 Fonte branca para contraste
                        )
                        
                        fig_chamados_mensal.update_layout(
                            height=260,
                            margin=dict(t=35, b=25, l=5, r=5),
                            title={'x': 0.5, 'xanchor': 'center'},
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            xaxis_title="",
                            yaxis_title="",
                            xaxis=dict(showgrid=False),
                            yaxis=dict(showgrid=False, visible=False)  # 👈 REMOVE o eixo Y (números 0, 0.5, 1)
                        )
                        
                        fig_chamados_mensal.update_xaxes(showgrid=False)
                        fig_chamados_mensal.update_yaxes(showgrid=False, visible=False)  # 👈 GARANTE REMOÇÃO
                        
                        st.plotly_chart(fig_chamados_mensal, use_container_width=True)
                        
                        # Adicionar métrica rápida de total
                        total_chamados = len(df_chamados_total)
                        st.caption(f"📊 Total acumulado: {total_chamados} chamados registrados")
                        
                    else:
                        # Mensagem quando não há chamados
                        st.markdown(f"""
                            <div style="
                                border: 3px dashed {cor_atual}; 
                                border-radius: 10px; 
                                padding: 40px 20px; 
                                text-align: center; 
                                background-color: {cor_secundaria}15;
                                height: 260px;
                                display: flex;
                                flex-direction: column;
                                justify-content: center;
                                align-items: center;
                            ">
                                <span style="font-size: 2.5rem; margin-bottom: 10px;">📭</span>
                                <p style="margin:0; font-weight:700; font-size:1.1rem; color:{cor_atual}; text-transform: uppercase;">
                                    Nenhum chamado registrado
                                </p>
                                <p style="margin:5px 0 0 0; color:inherit; font-size:0.95rem; opacity: 0.85;">
                                    Abra chamados para ver o histórico mensal
                                </p>
                            </div>
                        """, unsafe_allow_html=True)          
                
                with col_g_anomalias:
                    st.markdown("<p style='margin:0; font-weight:700; font-size:1.05rem; text-align:center;'>ATIVOS CRÍTICOS COM DIAGNÓSTICO DE FALHA</p>", unsafe_allow_html=True)
                    
                    # Filtrar: tem anomalia E status não é OK
                    df_falhas = df_filtrado[
                        df_filtrado["anomalia"].notna() & 
                        (df_filtrado["anomalia"].astype(str).str.strip() != "") & 
                        (df_filtrado["anomalia"].astype(str).str.upper() != "NENHUMA") & 
                        (df_filtrado["anomalia"].astype(str).str.upper() != "NAN") &
                        (df_filtrado["status"].astype(str).str.upper() != "OK")
                    ]
                    
                    if not df_falhas.empty:
                        st.dataframe(
                            df_falhas[["identificacao", "laboratorio", "anomalia", "status"]].rename(columns={
                                "identificacao": "ID Computador", 
                                "laboratorio": "Laboratório", 
                                "anomalia": "Anomalia Detectada", 
                                "status": "Situação"
                            }), 
                            use_container_width=True, 
                            hide_index=True,
                            height=200
                        )
                    else:
                        st.markdown("<p style='text-align:center; color:green; padding-top:40px;'>✅ Nenhuma anomalia ativa em máquinas com problema.</p>", unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            if st.button("📋 Visualizar Tabela Completa de Dados", use_container_width=True):
                modal_tabela_dados(df_filtrado)

    # --- ABA 2: CENTRAL DE CHAMADOS ---
    if aba_chamado:
        with aba_chamado:
            st.markdown(f"<h3 style='text-align: center; color: {cor_atual};'>🛠️ Suporte Técnico</h3>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Encontrou alguma falha de hardware ou software em algum computador? Abra um chamado imediatamente.</p>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            col_btn_chamado, _ = st.columns([2, 2])
            with col_btn_chamado:
                if st.button("➕ REGISTRAR NOVO CHAMADO DE MANUTENÇÃO", use_container_width=True, type="primary"):
                    modal_abrir_chamado(df)

            # --- ABA 3: GESTÃO DE CHAMADOS ---
    if aba_gestao:
        with aba_gestao:
            st.markdown(f"<h3 style='text-align: center; color: {cor_atual};'>📋 Chamados Ativos</h3>", unsafe_allow_html=True)
            df_c = carregar_chamados()
            if not df_c.empty:
                # CORREÇÃO DO HORÁRIO
                df_c['created_at'] = pd.to_datetime(df_c['created_at'])
                if df_c['created_at'].dt.tz is None:
                    df_c['created_at'] = df_c['created_at'].dt.tz_localize('UTC')
                df_c['created_at'] = df_c['created_at'].dt.tz_convert('America/Sao_Paulo')
                df_c['created_at'] = df_c['created_at'].dt.strftime('%d/%m/%Y       %H:%M:%S')
                
                def rotular_prioridade(p): return {"Baixa": "🔵 Baixa", "Média": "🟡 Média", "Alta": "🔴 Alta"}.get(p, p)
                df_c['Máquina'] = df_c['maquinas'].apply(lambda x: x['identificacao'] if isinstance(x, dict) else "N/A")
                df_c['Prioridade Visual'] = df_c['prioridade'].apply(rotular_prioridade)
                exibir = df_c[['id', 'created_at', 'Máquina', 'laboratorio', 'descricao', 'Prioridade Visual']]
                exibir.columns = ['ID', 'Data', 'Computador', 'Lab', 'Descrição', 'Urgência']
                st.dataframe(exibir.sort_values(by='ID', ascending=False), use_container_width=True, hide_index=True)
                
                if st.session_state.perfil in ["Administrador", "Assistente"]:
                    with st.expander("🗑️ Dar Baixa em Chamado Resolvido"):
                        id_excluir = st.selectbox("Selecione o ID do Chamado:", options=exibir['ID'].tolist())
                        if st.button("CONFIRMAR FINALIZAÇÃO", use_container_width=True):
                            info_chamado = exibir[exibir['ID'] == id_excluir]
                            comp_ref = info_chamado['Computador'].iloc[0] if not info_chamado.empty else "N/A"
                            
                            try:
                                # Buscar a máquina vinculada ao chamado
                                chamado = supabase.table("chamados").select("maquina_id").eq("id", id_excluir).execute()
                                if chamado.data and len(chamado.data) > 0:
                                    maquina_id = chamado.data[0]["maquina_id"]
                                    
                                    # Atualizar status da máquina para OK e limpar anomalia
                                    supabase.table("maquinas").update({
                                        "status": "OK",
                                        "anomalia": ""
                                    }).eq("id", maquina_id).execute()
                                    
                                    # Marcar chamado como finalizado
                                    supabase.table("chamados").update({
                                        "finalizado": True,
                                        "status": "finalizado"
                                    }).eq("id", id_excluir).execute()
                                    
                                    # Registrar no histórico a ação automatizada
                                    registrar_historico("FINALIZAR CHAMADO", f"Chamado {id_excluir} finalizado. Máquina {comp_ref} restaurada para OK.")
                                    
                            except Exception as e:
                                st.error(f"Erro ao restaurar máquina: {e}")

                            # Marcar chamado como finalizado e atualizar status
                            supabase.table("chamados").update({
                            "finalizado": True,
                            "status": "finalizado"
                            }).eq("id", id_excluir).execute()
                            st.toast(f"✅ Chamado {id_excluir} finalizado! Máquina restaurada para OK.", icon='✅')
                            st.rerun()
            else: 
                st.markdown(f"<div style='background-color: rgba(128, 128, 128, 0.08); padding: 1rem; border-radius: 8px; text-align: center; border-left: 5px solid {cor_atual};'><p style='color: {cor_atual}; font-weight: 700; margin: 0;'>ℹ️ Nenhum chamado pendente no momento.</p></div>", unsafe_allow_html=True)

    # --- ABA 4: PAINEL ADMINISTRATIVO ---
    if aba_admin and st.session_state.perfil == "Administrador":
        with aba_admin:
            st.markdown(f"<h3 style='text-align: center; color: {cor_atual};'>⚙️ Painel Administrativo</h3>", unsafe_allow_html=True)
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                if st.button("👥 Cadastro de Usuários", use_container_width=True, type="secondary"): 
                    modal_gestao_usuarios()
                
                if st.button("⚡ Atualização de Status de Chamados", use_container_width=True, type="secondary"): 
                    modal_status_expresso()
                
                if st.button("📊 Relatório Gerencial em PDF", use_container_width=True, type="secondary"):
                    modal_relatorio_pdf()
            
            with c_btn2:
                if st.button("📥 Importação e Exportação de Planilhas (CSV)", use_container_width=True, type="secondary"): 
                    modal_planilhas()
                
                if st.button("📋 Registro de Logs", use_container_width=True, type="secondary"): 
                    modal_central_relatorios()
                
                if st.button("➕ Cadastro e Edição de Máquinas", use_container_width=True, type="primary"): 
                    modal_formulario_completo()