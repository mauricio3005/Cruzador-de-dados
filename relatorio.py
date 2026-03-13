import io
import os
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Cores ─────────────────────────────────────────────────────────────────────
C_AZUL      = colors.HexColor('#2563EB')
C_VERDE     = colors.HexColor('#10B981')
C_VERMELHO  = colors.HexColor('#EF4444')
C_CINZA_ESC = colors.HexColor('#1F2937')
C_CINZA_MED = colors.HexColor('#6B7280')
C_CINZA_CLA = colors.HexColor('#E5E7EB')
C_FUNDO     = colors.HexColor('#F9FAFB')
C_BRANCO    = colors.white

MARGEM       = 1.5 * cm
LARGURA_PAG, ALTURA_PAG = landscape(A4)
LARGURA_UTIL = LARGURA_PAG - 2 * MARGEM

LOGO_PATH = os.path.join(os.path.dirname(__file__), 'logo.png')

# Metadados fixos por obra para o timbrado do relatório simples
OBRAS_METADATA = {
    'Creche Teoflandia': {
        'descricao': 'Creche proinfância tipo 01 no município de Teofilândia',
        'contrato':  '0252/2025',
        'art':       'BA20240905989',
    },
    # Adicione outras obras aqui conforme necessário
}


def _fmt(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _estilos():
    base = getSampleStyleSheet()
    return {
        'timbrado_obra': ParagraphStyle(
            'TimbradoObra', parent=base['Normal'],
            fontSize=13, textColor=C_CINZA_ESC,
            fontName='Helvetica-Bold', alignment=TA_LEFT,
        ),
        'timbrado_subtitulo': ParagraphStyle(
            'TimbradoSub', parent=base['Normal'],
            fontSize=9, textColor=C_CINZA_MED,
            fontName='Helvetica', alignment=TA_LEFT,
        ),
        'timbrado_data': ParagraphStyle(
            'TimbradoData', parent=base['Normal'],
            fontSize=8, textColor=C_CINZA_MED,
            fontName='Helvetica', alignment=TA_RIGHT,
        ),
        'etapa_titulo': ParagraphStyle(
            'EtapaTitulo', parent=base['Normal'],
            fontSize=13, textColor=C_AZUL,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'secao_titulo': ParagraphStyle(
            'SecaoTitulo', parent=base['Normal'],
            fontSize=9, textColor=C_CINZA_ESC,
            fontName='Helvetica-Bold',
        ),
        'kpi_label_c': ParagraphStyle(
            'KpiLabelC', parent=base['Normal'],
            fontSize=7, textColor=C_CINZA_MED,
            fontName='Helvetica', spaceAfter=3, alignment=TA_CENTER,
        ),
        'kpi_valor_c': ParagraphStyle(
            'KpiValorC', parent=base['Normal'],
            fontSize=13, textColor=C_CINZA_ESC,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'kpi_verde_c': ParagraphStyle(
            'KpiVerdeC', parent=base['Normal'],
            fontSize=13, textColor=C_VERDE,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'kpi_vermelho_c': ParagraphStyle(
            'KpiVermelhoC', parent=base['Normal'],
            fontSize=13, textColor=C_VERMELHO,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'pct_label': ParagraphStyle(
            'PctLabel', parent=base['Normal'],
            fontSize=7, textColor=C_CINZA_MED,
            fontName='Helvetica', spaceAfter=4, alignment=TA_CENTER,
        ),
        'pct_valor': ParagraphStyle(
            'PctValor', parent=base['Normal'],
            fontSize=20, textColor=C_CINZA_ESC,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'pct_vermelho': ParagraphStyle(
            'PctVermelho', parent=base['Normal'],
            fontSize=20, textColor=C_VERMELHO,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'tab_header': ParagraphStyle(
            'TabHeader', parent=base['Normal'],
            fontSize=7.5, textColor=C_CINZA_MED,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'tab_label': ParagraphStyle(
            'TabLabel', parent=base['Normal'],
            fontSize=9, textColor=C_CINZA_ESC,
            fontName='Helvetica',
        ),
        'tab_valor': ParagraphStyle(
            'TabValor', parent=base['Normal'],
            fontSize=9, textColor=C_CINZA_ESC,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'tab_verde': ParagraphStyle(
            'TabVerde', parent=base['Normal'],
            fontSize=9, textColor=C_VERDE,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'tab_vermelho': ParagraphStyle(
            'TabVermelho', parent=base['Normal'],
            fontSize=9, textColor=C_VERMELHO,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        # Simples
        'simples_titulo': ParagraphStyle(
            'SimplesT', parent=base['Normal'],
            fontSize=11, textColor=C_CINZA_ESC,
            fontName='Helvetica-Bold', spaceAfter=0,
        ),
        'simples_header': ParagraphStyle(
            'SimplesH', parent=base['Normal'],
            fontSize=8, textColor=C_CINZA_MED,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'simples_etapa': ParagraphStyle(
            'SimplesE', parent=base['Normal'],
            fontSize=10, textColor=C_CINZA_ESC,
            fontName='Helvetica-Bold',
        ),
        'simples_valor': ParagraphStyle(
            'SimplesV', parent=base['Normal'],
            fontSize=10, textColor=C_CINZA_ESC,
            fontName='Helvetica', alignment=TA_CENTER,
        ),
        'simples_verde': ParagraphStyle(
            'SimplesVd', parent=base['Normal'],
            fontSize=10, textColor=C_VERDE,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'simples_vermelho': ParagraphStyle(
            'SimplesVm', parent=base['Normal'],
            fontSize=10, textColor=C_VERMELHO,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
    }


def _linha_separadora(largura: float) -> Table:
    t = Table([['']], colWidths=[largura], rowHeights=[1])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_CINZA_CLA),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def _timbrado(obra_nome: str, etapa_nome: str, subtitulo: str, estilos: dict, largura: float) -> Table:
    data = [[
        [
            Paragraph(obra_nome, estilos['timbrado_obra']),
            Paragraph(subtitulo, estilos['timbrado_subtitulo']),
        ],
        Paragraph(etapa_nome, estilos['etapa_titulo']),
        Paragraph(
            f"Gerado em<br/>{datetime.now().strftime('%d/%m/%Y  %H:%M')}",
            estilos['timbrado_data'],
        ),
    ]]
    t = Table(data, colWidths=[largura * 0.35, largura * 0.35, largura * 0.30])
    t.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    return t


def _timbrado_simples(obra_nome: str, largura: float) -> Table:
    """Timbrado completo para o relatório simples: logo + dados da obra."""
    meta = OBRAS_METADATA.get(obra_nome, {})
    descricao = meta.get('descricao', obra_nome)
    contrato  = meta.get('contrato',  '—')
    art       = meta.get('art',       '—')

    st_label = ParagraphStyle('TimLabel', fontSize=7.5, textColor=C_CINZA_MED, fontName='Helvetica')
    st_valor = ParagraphStyle('TimValor', fontSize=9,   textColor=C_CINZA_ESC, fontName='Helvetica-Bold')
    st_data  = ParagraphStyle('TimData',  fontSize=7.5, textColor=C_CINZA_MED, fontName='Helvetica', alignment=TA_RIGHT)

    # Coluna esquerda: logo (se existir) ou nome da empresa
    col_logo = largura * 0.20
    col_info = largura * 0.60
    col_data = largura * 0.20

    if os.path.exists(LOGO_PATH):
        logo_cel = Image(LOGO_PATH, width=col_logo * 0.85, height=2.2 * cm, kind='proportional')
    else:
        logo_cel = Paragraph("MM Reformas<br/>&amp; Serviços", st_valor)

    # Tabela interna com os dados da obra
    info_interna = Table(
        [
            [Paragraph("OBRA:",      st_label), Paragraph(descricao, st_valor)],
            [Paragraph("CONTRATO:",  st_label), Paragraph(contrato,  st_valor)],
            [Paragraph("ART:",       st_label), Paragraph(art,       st_valor)],
        ],
        colWidths=[col_info * 0.22, col_info * 0.78],
    )
    info_interna.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ]))

    data_cel = Paragraph(
        f"Gerado em<br/>{datetime.now().strftime('%d/%m/%Y  %H:%M')}",
        st_data,
    )

    outer = Table(
        [[logo_cel, info_interna, data_cel]],
        colWidths=[col_logo, col_info, col_data],
    )
    outer.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    return outer


def _tabela_kpis_principais(orc, gasto, saldo, estilos, largura):
    est_saldo = estilos['kpi_verde_c'] if saldo >= 0 else estilos['kpi_vermelho_c']
    col_w = largura / 3
    data = [
        [
            Paragraph("ORÇAMENTO ESTIMADO", estilos['kpi_label_c']),
            Paragraph("CUSTO REALIZADO",    estilos['kpi_label_c']),
            Paragraph("SALDO FINANCEIRO",   estilos['kpi_label_c']),
        ],
        [
            Paragraph(_fmt(orc),   estilos['kpi_valor_c']),
            Paragraph(_fmt(gasto), estilos['kpi_valor_c']),
            Paragraph(_fmt(saldo), est_saldo),
        ],
    ]
    t = Table(data, colWidths=[col_w] * 3)
    t.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, -1), C_FUNDO),
        ('BOX',            (0, 0), (-1, -1), 0.5, C_CINZA_CLA),
        ('INNERGRID',      (0, 0), (-1, -1), 0.5, C_CINZA_CLA),
        ('TOPPADDING',     (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 10),
        ('LEFTPADDING',    (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_FUNDO, C_BRANCO]),
    ]))
    return t


def _tabela_percentuais(pct_consumo, pct_realizacao, estilos, largura):
    est_consumo = estilos['pct_vermelho'] if pct_consumo > 100 else estilos['pct_valor']
    col_w = largura / 2
    data = [
        [
            Paragraph("% DE CONSUMO",    estilos['pct_label']),
            Paragraph("% DE REALIZAÇÃO", estilos['pct_label']),
        ],
        [
            Paragraph(f"{pct_consumo:.1f}%",    est_consumo),
            Paragraph(f"{pct_realizacao:.1f}%", estilos['pct_valor']),
        ],
    ]
    t = Table(data, colWidths=[col_w] * 2)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_BRANCO),
        ('BOX',           (0, 0), (-1, -1), 0.5, C_CINZA_CLA),
        ('LINEAFTER',     (0, 0), (0, -1),  0.5, C_CINZA_CLA),
        ('TOPPADDING',    (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
    ]))
    return t


def _tabela_dados_complementares(df_etapa, estilos, largura):
    """Mão de Obra / Materiais / Geral — Previsto (total etapa) | Realizado por tipo."""
    TIPOS = [
        ('Mão de Obra', 'Mão de Obra'),
        ('Materiais',   'Materiais'),
        ('Geral',       'Geral (sem tipo definido)'),
    ]

    col_widths = [largura * 0.45, largura * 0.275, largura * 0.275]

    rows = [[
        Paragraph("CATEGORIA",  estilos['tab_header']),
        Paragraph("PREVISTO",   estilos['tab_header']),
        Paragraph("REALIZADO",  estilos['tab_header']),
    ]]

    style_cmds = [
        ('BACKGROUND',     (0, 0), (-1, 0),  C_FUNDO),
        ('BOX',            (0, 0), (-1, -1), 0.5, C_CINZA_CLA),
        ('INNERGRID',      (0, 0), (-1, -1), 0.5, C_CINZA_CLA),
        ('TOPPADDING',     (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 7),
        ('LEFTPADDING',    (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_BRANCO, C_FUNDO]),
    ]

    for tipo_chave, tipo_label in TIPOS:
        sub        = df_etapa[df_etapa['TIPO_CUSTO'].str.strip() == tipo_chave]
        orc_tipo   = float(sub['ORÇAMENTO_ESTIMADO'].sum())
        gasto_tipo = float(sub['GASTO_REALIZADO'].sum())

        if orc_tipo > 0:
            pct_tipo = gasto_tipo / orc_tipo * 100
            cor_pct  = '#EF4444' if pct_tipo > 100 else '#6B7280'
            pct_txt  = f'<br/><font size="7" color="{cor_pct}">({pct_tipo:.1f}% consumido)</font>'
        else:
            pct_txt = ''

        est_gasto = estilos['tab_vermelho'] if gasto_tipo > orc_tipo and orc_tipo > 0 else estilos['tab_verde']

        rows.append([
            Paragraph(tipo_label, estilos['tab_label']),
            Paragraph(_fmt(orc_tipo),  estilos['tab_valor']),
            Paragraph(f"{_fmt(gasto_tipo)}{pct_txt}", est_gasto),
        ])

    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle(style_cmds))
    return t


# ─────────────────────────────────────────────────────────────────────────────
# RELATÓRIO DETALHADO — uma página por etapa
# ─────────────────────────────────────────────────────────────────────────────

def gerar_relatorio_detalhado(df_raw: pd.DataFrame, obra_nome: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=MARGEM, leftMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM,
    )

    estilos = _estilos()
    story   = []

    df_obra          = df_raw[df_raw['OBRA'] == obra_nome].copy()
    gastos_por_etapa = df_obra.groupby('ETAPA')['GASTO_REALIZADO'].sum()
    etapas_ativas    = gastos_por_etapa[gastos_por_etapa > 0].index.tolist()

    for idx, etapa_nome in enumerate(etapas_ativas):
        df_etapa = df_obra[df_obra['ETAPA'] == etapa_nome]

        orc   = float(df_etapa['ORÇAMENTO_ESTIMADO'].sum())
        gasto = float(df_etapa['GASTO_REALIZADO'].sum())
        saldo = orc - gasto
        pct_consumo    = (gasto / orc * 100) if orc > 0 else 0.0
        pct_realizacao = 0.0  # campo futuro no Supabase

        story.append(_timbrado(obra_nome, etapa_nome, "Relatório Detalhado", estilos, LARGURA_UTIL))
        story.append(_linha_separadora(LARGURA_UTIL))
        story.append(Spacer(1, 0.35 * cm))

        story.append(_tabela_kpis_principais(orc, gasto, saldo, estilos, LARGURA_UTIL))
        story.append(Spacer(1, 0.3 * cm))

        story.append(_tabela_percentuais(pct_consumo, pct_realizacao, estilos, LARGURA_UTIL))
        story.append(Spacer(1, 0.3 * cm))

        story.append(Paragraph("Dados complementares", estilos['secao_titulo']))
        story.append(Spacer(1, 0.15 * cm))
        story.append(_tabela_dados_complementares(df_etapa, estilos, LARGURA_UTIL))

        if idx < len(etapas_ativas) - 1:
            story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# RELATÓRIO SIMPLES — todas as etapas em uma única página
# ─────────────────────────────────────────────────────────────────────────────

def gerar_relatorio_simples(df_raw: pd.DataFrame, obra_nome: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=MARGEM, leftMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM,
    )

    estilos = _estilos()
    story   = []

    df_obra           = df_raw[df_raw['OBRA'] == obra_nome].copy()
    orcamentos_etapa  = df_obra.groupby('ETAPA')['ORÇAMENTO_ESTIMADO'].sum()
    etapas_ativas     = orcamentos_etapa[orcamentos_etapa > 0].index.tolist()

    # ── Timbrado ─────────────────────────────────────────────────────────────
    story.append(_timbrado_simples(obra_nome, LARGURA_UTIL))
    story.append(_linha_separadora(LARGURA_UTIL))
    story.append(Spacer(1, 0.4 * cm))

    # ── Tabela resumo: uma linha por etapa, 6 colunas ────────────────────────
    # Larguras: etapa (maior) + 5 colunas de dados distribuídas igualmente
    col_etapa  = LARGURA_UTIL * 0.22
    col_dados  = (LARGURA_UTIL - col_etapa) / 5
    col_widths = [col_etapa] + [col_dados] * 5

    HEADERS = ["ETAPA", "ORÇAMENTO\nESTIMADO", "CUSTO\nREALIZADO", "SALDO\nFINANCEIRO", "% DE\nCONSUMO", "% DE\nREALIZAÇÃO"]
    header_row = [Paragraph(h, estilos['simples_header']) for h in HEADERS]
    rows = [header_row]

    style_cmds = [
        ('BACKGROUND',     (0, 0), (-1, 0),  C_FUNDO),
        ('BOX',            (0, 0), (-1, -1), 0.5, C_CINZA_CLA),
        ('INNERGRID',      (0, 0), (-1, -1), 0.5, C_CINZA_CLA),
        ('TOPPADDING',     (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 10),
        ('LEFTPADDING',    (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 10),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_BRANCO, C_FUNDO]),
    ]

    for i, etapa_nome in enumerate(etapas_ativas):
        df_etapa = df_obra[df_obra['ETAPA'] == etapa_nome]

        orc   = float(df_etapa['ORÇAMENTO_ESTIMADO'].sum())
        gasto = float(df_etapa['GASTO_REALIZADO'].sum())
        saldo = orc - gasto
        pct_consumo    = (gasto / orc * 100) if orc > 0 else 0.0
        pct_realizacao = 0.0

        est_saldo   = estilos['simples_verde']   if saldo >= 0       else estilos['simples_vermelho']
        est_consumo = estilos['simples_vermelho'] if pct_consumo > 100 else estilos['simples_valor']

        row_idx = i + 1  # linha 0 é o header
        # Destaque visual na coluna de saldo
        if saldo < 0:
            style_cmds.append(('TEXTCOLOR', (3, row_idx), (3, row_idx), C_VERMELHO))
        else:
            style_cmds.append(('TEXTCOLOR', (3, row_idx), (3, row_idx), C_VERDE))

        rows.append([
            Paragraph(etapa_nome,                    estilos['simples_etapa']),
            Paragraph(_fmt(orc),                     estilos['simples_valor']),
            Paragraph(_fmt(gasto),                   estilos['simples_valor']),
            Paragraph(_fmt(saldo),                   est_saldo),
            Paragraph(f"{pct_consumo:.1f}%",         est_consumo),
            Paragraph(f"{pct_realizacao:.1f}%",      estilos['simples_valor']),
        ])

    tabela = Table(rows, colWidths=col_widths)
    tabela.setStyle(TableStyle(style_cmds))
    story.append(tabela)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
