import io
import os
import tempfile
import urllib.request
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

# ── Paleta alinhada ao design system "Industrial Architect" ───────────────────
C_PRIMARY    = colors.HexColor('#101b30')  # cabeçalhos / fundo principal
C_SECONDARY  = colors.HexColor('#47607e')  # acentos secundários
C_SUCCESS    = colors.HexColor('#2e7d32')  # positivo / dentro do orçamento
C_ERROR      = colors.HexColor('#ba1a1a')  # negativo / acima do orçamento
C_ON_SURFACE = colors.HexColor('#191c1e')  # texto principal
C_ON_VAR     = colors.HexColor('#44474e')  # texto secundário / labels
C_SURFACE    = colors.HexColor('#f8f9fb')  # fundo da página / linha par
C_SURFACE_HI = colors.HexColor('#e7e8ea')  # fundo alternado / seções
C_OUTLINE    = colors.HexColor('#c4c6cc')  # ghost borders (15% nos docs)
C_BRANCO     = colors.white

MARGEM       = 1.5 * cm
LARGURA_PAG, ALTURA_PAG = landscape(A4)
LARGURA_UTIL = LARGURA_PAG - 2 * MARGEM

LOGO_PATH = os.path.join(os.path.dirname(__file__), 'logo.png')


def _fmt(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _estilos():
    base = getSampleStyleSheet()
    return {
        'timbrado_obra': ParagraphStyle(
            'TimbradoObra', parent=base['Normal'],
            fontSize=13, textColor=C_ON_SURFACE,
            fontName='Helvetica-Bold', alignment=TA_LEFT,
        ),
        'timbrado_subtitulo': ParagraphStyle(
            'TimbradoSub', parent=base['Normal'],
            fontSize=9, textColor=C_ON_VAR,
            fontName='Helvetica', alignment=TA_LEFT,
        ),
        'timbrado_data': ParagraphStyle(
            'TimbradoData', parent=base['Normal'],
            fontSize=8, textColor=C_ON_VAR,
            fontName='Helvetica', alignment=TA_RIGHT,
        ),
        'etapa_titulo': ParagraphStyle(
            'EtapaTitulo', parent=base['Normal'],
            fontSize=13, textColor=C_SECONDARY,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'secao_titulo': ParagraphStyle(
            'SecaoTitulo', parent=base['Normal'],
            fontSize=9, textColor=C_ON_SURFACE,
            fontName='Helvetica-Bold',
        ),
        'kpi_label_c': ParagraphStyle(
            'KpiLabelC', parent=base['Normal'],
            fontSize=7, textColor=C_ON_VAR,
            fontName='Helvetica', spaceAfter=3, alignment=TA_CENTER,
        ),
        'kpi_valor_c': ParagraphStyle(
            'KpiValorC', parent=base['Normal'],
            fontSize=13, textColor=C_ON_SURFACE,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'kpi_verde_c': ParagraphStyle(
            'KpiVerdeC', parent=base['Normal'],
            fontSize=13, textColor=C_SUCCESS,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'kpi_vermelho_c': ParagraphStyle(
            'KpiVermelhoC', parent=base['Normal'],
            fontSize=13, textColor=C_ERROR,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'pct_label': ParagraphStyle(
            'PctLabel', parent=base['Normal'],
            fontSize=7, textColor=C_ON_VAR,
            fontName='Helvetica', spaceAfter=4, alignment=TA_CENTER,
        ),
        'pct_valor': ParagraphStyle(
            'PctValor', parent=base['Normal'],
            fontSize=20, textColor=C_ON_SURFACE,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'pct_vermelho': ParagraphStyle(
            'PctVermelho', parent=base['Normal'],
            fontSize=20, textColor=C_ERROR,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'tab_header': ParagraphStyle(
            'TabHeader', parent=base['Normal'],
            fontSize=7.5, textColor=C_BRANCO,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'tab_label': ParagraphStyle(
            'TabLabel', parent=base['Normal'],
            fontSize=9, textColor=C_ON_SURFACE,
            fontName='Helvetica',
        ),
        'tab_valor': ParagraphStyle(
            'TabValor', parent=base['Normal'],
            fontSize=9, textColor=C_ON_SURFACE,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'tab_verde': ParagraphStyle(
            'TabVerde', parent=base['Normal'],
            fontSize=9, textColor=C_SUCCESS,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'tab_vermelho': ParagraphStyle(
            'TabVermelho', parent=base['Normal'],
            fontSize=9, textColor=C_ERROR,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        # Simples
        'simples_titulo': ParagraphStyle(
            'SimplesT', parent=base['Normal'],
            fontSize=11, textColor=C_ON_SURFACE,
            fontName='Helvetica-Bold', spaceAfter=0,
        ),
        'simples_header': ParagraphStyle(
            'SimplesH', parent=base['Normal'],
            fontSize=8, textColor=C_BRANCO,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'simples_etapa': ParagraphStyle(
            'SimplesE', parent=base['Normal'],
            fontSize=10, textColor=C_ON_SURFACE,
            fontName='Helvetica-Bold',
        ),
        'simples_valor': ParagraphStyle(
            'SimplesV', parent=base['Normal'],
            fontSize=10, textColor=C_ON_SURFACE,
            fontName='Helvetica', alignment=TA_CENTER,
        ),
        'simples_verde': ParagraphStyle(
            'SimplesVd', parent=base['Normal'],
            fontSize=10, textColor=C_SUCCESS,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
        'simples_vermelho': ParagraphStyle(
            'SimplesVm', parent=base['Normal'],
            fontSize=10, textColor=C_ERROR,
            fontName='Helvetica-Bold', alignment=TA_CENTER,
        ),
    }


def _linha_separadora(largura: float) -> Table:
    t = Table([['']], colWidths=[largura], rowHeights=[1])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_PRIMARY),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def _timbrado_simples(obra_nome: str, largura: float, obra_info: dict = None) -> Table:
    info          = obra_info or {}
    descricao     = info.get('descricao')    or obra_nome
    contrato      = info.get('contrato')     or '—'
    art           = info.get('art')          or '—'
    empresa_nome  = info.get('empresa_nome') or ''
    empresa_logo  = info.get('empresa_logo') or ''

    st_label = ParagraphStyle('TimLabel', fontSize=7.5, textColor=C_ON_VAR,     fontName='Helvetica')
    st_valor = ParagraphStyle('TimValor', fontSize=9,   textColor=C_ON_SURFACE, fontName='Helvetica-Bold')
    st_data  = ParagraphStyle('TimData',  fontSize=7.5, textColor=C_ON_VAR,     fontName='Helvetica', alignment=TA_RIGHT)

    col_logo = largura * 0.20
    col_info = largura * 0.60
    col_data = largura * 0.20

    logo_cel = None

    # 1) Logo da empresa no banco (URL do Supabase Storage)
    if empresa_logo:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                urllib.request.urlretrieve(empresa_logo, tmp.name)
                logo_cel = Image(tmp.name, width=col_logo * 0.85, height=2.2 * cm, kind='proportional')
        except Exception:
            logo_cel = None

    # 2) Fallback: logo local
    if logo_cel is None and os.path.exists(LOGO_PATH):
        logo_cel = Image(LOGO_PATH, width=col_logo * 0.85, height=2.2 * cm, kind='proportional')

    # 3) Fallback: nome da empresa em texto
    if logo_cel is None:
        logo_cel = Paragraph(empresa_nome or '—', st_valor)

    rows = [
        [Paragraph("OBRA:",      st_label), Paragraph(descricao,    st_valor)],
        [Paragraph("CONTRATO:",  st_label), Paragraph(contrato,     st_valor)],
        [Paragraph("ART:",       st_label), Paragraph(art,          st_valor)],
    ]

    info_interna = Table(rows, colWidths=[col_info * 0.22, col_info * 0.78])
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
        ('BACKGROUND',     (0, 0), (-1, -1), C_SURFACE),
        ('LINEBELOW',      (0, 0), (-1, 0),  0.3, C_OUTLINE),
        ('LINEBEFORE',     (1, 0), (1, -1),  0.3, C_OUTLINE),
        ('LINEBEFORE',     (2, 0), (2, -1),  0.3, C_OUTLINE),
        ('TOPPADDING',     (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 10),
        ('LEFTPADDING',    (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_SURFACE, C_BRANCO]),
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
        ('LINEBEFORE',    (1, 0), (1, -1),  0.3, C_OUTLINE),
        ('TOPPADDING',    (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
    ]))
    return t


def _tabela_dados_complementares(df_etapa, estilos, largura):
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
        ('BACKGROUND',     (0, 0), (-1, 0),  C_PRIMARY),
        ('LINEBELOW',      (0, 0), (-1, 0),  0.3, C_OUTLINE),
        ('TOPPADDING',     (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 7),
        ('LEFTPADDING',    (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_BRANCO, C_SURFACE]),
    ]

    for tipo_chave, tipo_label in TIPOS:
        sub        = df_etapa[df_etapa['TIPO_CUSTO'].str.strip() == tipo_chave]
        orc_tipo   = float(sub['ORÇAMENTO_ESTIMADO'].sum())
        gasto_tipo = float(sub['GASTO_REALIZADO'].sum())

        if orc_tipo > 0:
            pct_tipo = gasto_tipo / orc_tipo * 100
            cor_pct  = '#ba1a1a' if pct_tipo > 100 else '#44474e'
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


def _tabela_despesas(df_desp: pd.DataFrame, estilos, largura, mostrar_etapa: bool = False) -> Table:
    """Tabela de despesas — usada tanto para 'última semana' quanto para histórico completo."""
    col_widths = (
        [largura * 0.09, largura * 0.17, largura * 0.11, largura * 0.17, largura * 0.34, largura * 0.12]
        if mostrar_etapa else
        [largura * 0.09, largura * 0.14, largura * 0.20, largura * 0.43, largura * 0.14]
    )

    if mostrar_etapa:
        header = ['Data', 'Etapa', 'Tipo', 'Fornecedor', 'Descrição', 'Valor']
    else:
        header = ['Data', 'Tipo', 'Fornecedor', 'Descrição', 'Valor']

    rows = [[Paragraph(h, estilos['tab_header']) for h in header]]
    total = 0.0

    for _, r in df_desp.sort_values('DATA').iterrows():
        data_str = pd.to_datetime(r['DATA']).strftime('%d/%m/%Y') if pd.notna(r.get('DATA')) else ''
        forn     = str(r.get('FORNECEDOR', '') or '')
        desc     = str(r.get('DESCRICAO',  '') or '')
        tipo     = str(r.get('TIPO_CUSTO', '') or '')
        etapa    = str(r.get('ETAPA',      '') or '')
        valor    = float(r.get('VALOR_TOTAL', 0) or 0)
        total   += valor

        if mostrar_etapa:
            row = [
                Paragraph(data_str, estilos['tab_valor']),
                Paragraph(etapa,    estilos['tab_label']),
                Paragraph(tipo,     estilos['tab_label']),
                Paragraph(forn,     estilos['tab_label']),
                Paragraph(desc,     estilos['tab_label']),
                Paragraph(_fmt(valor), estilos['tab_valor']),
            ]
        else:
            row = [
                Paragraph(data_str, estilos['tab_valor']),
                Paragraph(tipo,     estilos['tab_label']),
                Paragraph(forn,     estilos['tab_label']),
                Paragraph(desc,     estilos['tab_label']),
                Paragraph(_fmt(valor), estilos['tab_valor']),
            ]
        rows.append(row)

    # Linha de total
    empty = [Paragraph('', estilos['tab_valor'])] * (len(header) - 2)
    rows.append(empty + [
        Paragraph('Total', estilos['tab_header']),
        Paragraph(_fmt(total), estilos['tab_header']),
    ])

    style_cmds = [
        ('BACKGROUND',    (0, 0),  (-1, 0),  C_PRIMARY),
        ('BACKGROUND',    (0, -1), (-1, -1), C_SURFACE_HI),
        ('LINEBELOW',     (0, 0),  (-1, 0),  0.3, C_OUTLINE),
        ('VALIGN',        (0, 0),  (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0),  (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0),  (-1, -1), 6),
        ('LEFTPADDING',   (0, 0),  (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0),  (-1, -1), 8),
        ('ROWBACKGROUNDS',(0, 1),  (-1, -2), [C_BRANCO, C_SURFACE]),
    ]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle(style_cmds))
    return t


def _tabela_recebimentos(df_receb: pd.DataFrame, estilos, largura) -> Table:
    """Tabela de recebimentos."""
    col_widths = [largura * 0.10, largura * 0.22, largura * 0.30, largura * 0.14, largura * 0.12, largura * 0.12]
    header = ['Data', 'Fornecedor', 'Descrição', 'Forma', 'Parcela', 'Valor']
    rows = [[Paragraph(h, estilos['tab_header']) for h in header]]
    total = 0.0

    for _, r in df_receb.sort_values('DATA').iterrows():
        data_str = pd.to_datetime(r['DATA']).strftime('%d/%m/%Y') if pd.notna(r.get('DATA')) else ''
        forn     = str(r.get('FORNECEDOR', '') or '')
        desc     = str(r.get('DESCRICAO',  '') or '')
        forma    = str(r.get('FORMA',      '') or '')
        parcela_num = int(r.get('PARCELA_NUM', 1) or 1)
        total_parc  = int(r.get('TOTAL_PARCELAS', 1) or 1)
        parcela_str = f"{parcela_num}/{total_parc}" if total_parc > 1 else "—"
        valor    = float(r.get('VALOR', 0) or 0)
        total   += valor

        rows.append([
            Paragraph(data_str,      estilos['tab_valor']),
            Paragraph(forn,          estilos['tab_label']),
            Paragraph(desc,          estilos['tab_label']),
            Paragraph(forma,         estilos['tab_label']),
            Paragraph(parcela_str,   estilos['tab_valor']),
            Paragraph(_fmt(valor),   estilos['tab_verde']),
        ])

    # Linha de total
    rows.append([
        Paragraph('', estilos['tab_valor'])] * 4 + [
        Paragraph('Total', estilos['tab_header']),
        Paragraph(_fmt(total), estilos['tab_header']),
    ])

    style_cmds = [
        ('BACKGROUND',    (0, 0),  (-1, 0),  C_PRIMARY),
        ('BACKGROUND',    (0, -1), (-1, -1), C_SURFACE_HI),
        ('LINEBELOW',     (0, 0),  (-1, 0),  0.3, C_OUTLINE),
        ('VALIGN',        (0, 0),  (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0),  (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0),  (-1, -1), 6),
        ('LEFTPADDING',   (0, 0),  (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0),  (-1, -1), 8),
        ('ROWBACKGROUNDS',(0, 1),  (-1, -2), [C_BRANCO, C_SURFACE]),
    ]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle(style_cmds))
    return t


def _tabela_fluxo_caixa(total_receitas: float, total_despesas: float, estilos, largura) -> Table:
    """KPI cards: Receitas | Despesas | Saldo (fluxo de caixa)."""
    saldo = total_receitas - total_despesas
    est_saldo = estilos['kpi_verde_c'] if saldo >= 0 else estilos['kpi_vermelho_c']
    col_w = largura / 3
    data = [
        [
            Paragraph("TOTAL RECEBIMENTOS", estilos['kpi_label_c']),
            Paragraph("TOTAL DESPESAS",     estilos['kpi_label_c']),
            Paragraph("FLUXO DE CAIXA",     estilos['kpi_label_c']),
        ],
        [
            Paragraph(_fmt(total_receitas), estilos['kpi_verde_c']),
            Paragraph(_fmt(total_despesas), estilos['kpi_valor_c']),
            Paragraph(_fmt(saldo),          est_saldo),
        ],
    ]
    t = Table(data, colWidths=[col_w] * 3)
    t.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, -1), C_SURFACE),
        ('LINEBELOW',      (0, 0), (-1, 0),  0.3, C_OUTLINE),
        ('LINEBEFORE',     (1, 0), (1, -1),  0.3, C_OUTLINE),
        ('LINEBEFORE',     (2, 0), (2, -1),  0.3, C_OUTLINE),
        ('TOPPADDING',     (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 10),
        ('LEFTPADDING',    (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_SURFACE, C_BRANCO]),
    ]))
    return t


def _kpis_fluxo_caixa(df_receb, total_despesas, estilos, largura, story):
    """Adiciona KPIs de fluxo de caixa ao story (para a página de dados principais)."""
    total_receitas = float(df_receb['VALOR'].sum())
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Fluxo de caixa", estilos['secao_titulo']))
    story.append(Spacer(1, 0.15 * cm))
    story.append(_tabela_fluxo_caixa(total_receitas, total_despesas, estilos, largura))


def _tabela_recebimentos_secao(df_receb, estilos, largura, story):
    """Adiciona seção de recebimentos ao story (junto das tabelas completas)."""
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Recebimentos", estilos['secao_titulo']))
    story.append(Spacer(1, 0.15 * cm))
    story.append(_tabela_recebimentos(df_receb, estilos, largura))


def _tabela_resumo_etapas(df_despesas: pd.DataFrame, estilos, largura) -> Table:
    """Resumo de gastos agrupados por etapa — para relatório administrativo por etapa."""
    agrup = (
        df_despesas.groupby('ETAPA')['VALOR_TOTAL']
        .sum()
        .reset_index()
        .sort_values('VALOR_TOTAL', ascending=False)
    )

    col_widths = [largura * 0.60, largura * 0.40]
    rows = [[
        Paragraph("ETAPA",  estilos['tab_header']),
        Paragraph("TOTAL",  estilos['tab_header']),
    ]]

    for _, r in agrup.iterrows():
        rows.append([
            Paragraph(str(r['ETAPA'] or '—'), estilos['tab_label']),
            Paragraph(_fmt(float(r['VALOR_TOTAL'])), estilos['tab_valor']),
        ])

    # Linha de total
    total = float(agrup['VALOR_TOTAL'].sum())
    rows.append([
        Paragraph('Total', estilos['tab_header']),
        Paragraph(_fmt(total), estilos['tab_header']),
    ])

    style_cmds = [
        ('BACKGROUND',    (0, 0),  (-1, 0),  C_PRIMARY),
        ('BACKGROUND',    (0, -1), (-1, -1), C_SURFACE_HI),
        ('LINEBELOW',     (0, 0),  (-1, 0),  0.3, C_OUTLINE),
        ('TOPPADDING',    (0, 0),  (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0),  (-1, -1), 7),
        ('LEFTPADDING',   (0, 0),  (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0),  (-1, -1), 10),
        ('ROWBACKGROUNDS',(0, 1),  (-1, -2), [C_BRANCO, C_SURFACE]),
    ]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle(style_cmds))
    return t


# ─────────────────────────────────────────────────────────────────────────────
# RELATÓRIO DETALHADO — uma página por etapa (ou resumo geral)
# ─────────────────────────────────────────────────────────────────────────────

def gerar_relatorio_detalhado(
    df_raw: pd.DataFrame,
    obra_nome: str,
    df_despesas_semana: pd.DataFrame = None,
    obra_info: dict = None,
    por_etapa: bool = True,
    df_despesas_todas: pd.DataFrame = None,
    df_recebimentos: pd.DataFrame = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=MARGEM, leftMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM,
    )

    estilos = _estilos()
    story   = []

    df_obra = df_raw[df_raw['OBRA'] == obra_nome].copy()

    if not por_etapa:
        # ── Modo: informações gerais + histórico completo ─────────────────────
        orc   = float(df_obra['ORÇAMENTO_ESTIMADO'].sum())
        gasto = float(df_obra['GASTO_REALIZADO'].sum())
        saldo = orc - gasto
        pct_consumo = (gasto / orc * 100) if orc > 0 else 0.0

        story.append(_timbrado_simples(obra_nome, LARGURA_UTIL, obra_info))
        story.append(_linha_separadora(LARGURA_UTIL))
        story.append(Spacer(1, 0.35 * cm))

        story.append(_tabela_kpis_principais(orc, gasto, saldo, estilos, LARGURA_UTIL))
        story.append(Spacer(1, 0.3 * cm))

        story.append(_tabela_percentuais(pct_consumo, 0.0, estilos, LARGURA_UTIL))

        # KPIs de fluxo de caixa na mesma página
        if df_recebimentos is not None and not df_recebimentos.empty:
            _kpis_fluxo_caixa(df_recebimentos, gasto, estilos, LARGURA_UTIL, story)

        # ── Página seguinte: tabelas completas ───────────────────────────────
        df_hist = df_despesas_todas if df_despesas_todas is not None and not df_despesas_todas.empty else df_despesas_semana
        has_hist = df_hist is not None and not df_hist.empty
        has_receb = df_recebimentos is not None and not df_recebimentos.empty

        if has_hist or has_receb:
            story.append(PageBreak())
            story.append(_timbrado_simples(obra_nome, LARGURA_UTIL, obra_info))
            story.append(_linha_separadora(LARGURA_UTIL))
            story.append(Spacer(1, 0.4 * cm))

            if has_hist:
                story.append(Paragraph("Histórico de despesas", estilos['secao_titulo']))
                story.append(Spacer(1, 0.15 * cm))
                story.append(_tabela_despesas(df_hist, estilos, LARGURA_UTIL, mostrar_etapa=True))

            if has_receb:
                _tabela_recebimentos_secao(df_recebimentos, estilos, LARGURA_UTIL, story)

    else:
        # ── Modo: por etapa — uma página por etapa ───────────────────────────
        # Incluir etapas que tenham orçamento OU gasto realizado
        orc_por_etapa   = df_obra.groupby('ETAPA')['ORÇAMENTO_ESTIMADO'].sum()
        gasto_por_etapa = df_obra.groupby('ETAPA')['GASTO_REALIZADO'].sum()
        etapas_com_dados = orc_por_etapa.index[
            (orc_por_etapa > 0) | (gasto_por_etapa.reindex(orc_por_etapa.index, fill_value=0) > 0)
        ]

        if 'ORDEM_ETAPA' in df_obra.columns:
            ordem = df_obra.groupby('ETAPA')['ORDEM_ETAPA'].min().sort_values()
            etapas_ativas = [e for e in ordem.index if e in etapas_com_dados]
        else:
            etapas_ativas = etapas_com_dados.tolist()

        for idx, etapa_nome in enumerate(etapas_ativas):
            df_etapa = df_obra[df_obra['ETAPA'] == etapa_nome]
            is_adm_local = etapa_nome.strip().upper() == 'ADM LOCAL'

            orc   = float(df_etapa['ORÇAMENTO_ESTIMADO'].sum())
            gasto = float(df_etapa['GASTO_REALIZADO'].sum())
            saldo = orc - gasto
            pct_consumo    = (gasto / orc * 100) if orc > 0 else 0.0
            pct_realizacao = float(df_etapa['TAXA_CONCLUSAO'].iloc[0]) if 'TAXA_CONCLUSAO' in df_etapa.columns and not df_etapa.empty else 0.0

            story.append(_timbrado_simples(obra_nome, LARGURA_UTIL, obra_info))
            story.append(_linha_separadora(LARGURA_UTIL))
            story.append(Spacer(1, 0.2 * cm))

            st_etapa = ParagraphStyle('EtNome', fontSize=11, textColor=C_SECONDARY,
                                      fontName='Helvetica-Bold', alignment=TA_CENTER)
            story.append(Paragraph(etapa_nome, st_etapa))
            story.append(Spacer(1, 0.25 * cm))

            story.append(_tabela_kpis_principais(orc, gasto, saldo, estilos, LARGURA_UTIL))
            story.append(Spacer(1, 0.3 * cm))

            if not is_adm_local:
                story.append(_tabela_percentuais(pct_consumo, pct_realizacao, estilos, LARGURA_UTIL))
                story.append(Spacer(1, 0.3 * cm))

                story.append(Paragraph("Dados complementares", estilos['secao_titulo']))
                story.append(Spacer(1, 0.15 * cm))
                story.append(_tabela_dados_complementares(df_etapa, estilos, LARGURA_UTIL))

            if df_despesas_semana is not None and not df_despesas_semana.empty:
                df_etapa_desp = df_despesas_semana[df_despesas_semana['ETAPA'] == etapa_nome]
                if not df_etapa_desp.empty:
                    story.append(Spacer(1, 0.3 * cm))
                    story.append(Paragraph("Despesas da última semana", estilos['secao_titulo']))
                    story.append(Spacer(1, 0.15 * cm))
                    story.append(_tabela_despesas(df_etapa_desp, estilos, LARGURA_UTIL, mostrar_etapa=False))

            if idx < len(etapas_ativas) - 1:
                story.append(PageBreak())

        # ── Fluxo de caixa — página final (modo por etapa) ───────────────
        if df_recebimentos is not None and not df_recebimentos.empty:
            total_gasto = float(df_obra['GASTO_REALIZADO'].sum())
            story.append(PageBreak())
            story.append(_timbrado_simples(obra_nome, LARGURA_UTIL, obra_info))
            story.append(_linha_separadora(LARGURA_UTIL))
            story.append(Spacer(1, 0.2 * cm))
            _kpis_fluxo_caixa(df_recebimentos, total_gasto, estilos, LARGURA_UTIL, story)
            _tabela_recebimentos_secao(df_recebimentos, estilos, LARGURA_UTIL, story)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# RELATÓRIO SIMPLES — resumo por etapas + histórico da última semana
# ─────────────────────────────────────────────────────────────────────────────

def gerar_relatorio_simples(
    df_raw: pd.DataFrame,
    obra_nome: str,
    df_despesas_semana: pd.DataFrame = None,
    obra_info: dict = None,
    df_recebimentos: pd.DataFrame = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=MARGEM, leftMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM,
    )

    estilos = _estilos()
    story   = []

    df_obra = df_raw[df_raw['OBRA'] == obra_nome].copy()
    # Incluir etapas que tenham orçamento OU gasto realizado
    orc_por_etapa   = df_obra.groupby('ETAPA')['ORÇAMENTO_ESTIMADO'].sum()
    gasto_por_etapa = df_obra.groupby('ETAPA')['GASTO_REALIZADO'].sum()
    etapas_com_dados = orc_por_etapa.index[
        (orc_por_etapa > 0) | (gasto_por_etapa.reindex(orc_por_etapa.index, fill_value=0) > 0)
    ]

    if 'ORDEM_ETAPA' in df_obra.columns:
        ordem = df_obra.groupby('ETAPA')['ORDEM_ETAPA'].min().sort_values()
        etapas_ativas = [e for e in ordem.index if e in etapas_com_dados]
    else:
        etapas_ativas = etapas_com_dados.tolist()

    # ── Timbrado ─────────────────────────────────────────────────────────────
    story.append(_timbrado_simples(obra_nome, LARGURA_UTIL, obra_info))
    story.append(_linha_separadora(LARGURA_UTIL))
    story.append(Spacer(1, 0.4 * cm))

    # ── Tabela resumo por etapa ───────────────────────────────────────────────
    col_etapa  = LARGURA_UTIL * 0.22
    col_dados  = (LARGURA_UTIL - col_etapa) / 5
    col_widths = [col_etapa] + [col_dados] * 5

    HEADERS = ["ETAPA", "ORÇAMENTO\nESTIMADO", "CUSTO\nREALIZADO", "SALDO\nFINANCEIRO", "% DE\nCONSUMO", "% DE\nREALIZAÇÃO"]
    header_row = [Paragraph(h, estilos['simples_header']) for h in HEADERS]
    rows = [header_row]

    style_cmds = [
        ('BACKGROUND',     (0, 0), (-1, 0),  C_PRIMARY),
        ('LINEBELOW',      (0, 0), (-1, 0),  0.3, C_OUTLINE),
        ('TOPPADDING',     (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 10),
        ('LEFTPADDING',    (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 10),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_BRANCO, C_SURFACE]),
    ]

    for i, etapa_nome in enumerate(etapas_ativas):
        df_etapa = df_obra[df_obra['ETAPA'] == etapa_nome]
        is_adm_local = etapa_nome.strip().upper() == 'ADM LOCAL'

        orc   = float(df_etapa['ORÇAMENTO_ESTIMADO'].sum())
        gasto = float(df_etapa['GASTO_REALIZADO'].sum())
        saldo = orc - gasto
        pct_consumo = (gasto / orc * 100) if orc > 0 else 0.0

        est_saldo   = estilos['simples_verde']   if saldo >= 0        else estilos['simples_vermelho']
        est_consumo = estilos['simples_vermelho'] if pct_consumo > 100 else estilos['simples_valor']

        pct_real_str = "—" if is_adm_local else "0.0%"
        rows.append([
            Paragraph(etapa_nome,            estilos['simples_etapa']),
            Paragraph(_fmt(orc),             estilos['simples_valor']),
            Paragraph(_fmt(gasto),           estilos['simples_valor']),
            Paragraph(_fmt(saldo),           est_saldo),
            Paragraph(f"{pct_consumo:.1f}%", est_consumo),
            Paragraph(pct_real_str,          estilos['simples_valor']),
        ])

    tabela = Table(rows, colWidths=col_widths)
    tabela.setStyle(TableStyle(style_cmds))
    story.append(tabela)

    # KPIs de fluxo de caixa na mesma página
    if df_recebimentos is not None and not df_recebimentos.empty:
        total_gasto = float(df_obra['GASTO_REALIZADO'].sum())
        _kpis_fluxo_caixa(df_recebimentos, total_gasto, estilos, LARGURA_UTIL, story)

    # ── Página seguinte: tabelas completas ────────────────────────────────────
    has_desp = df_despesas_semana is not None and not df_despesas_semana.empty
    has_receb = df_recebimentos is not None and not df_recebimentos.empty

    if has_desp or has_receb:
        story.append(PageBreak())
        story.append(_timbrado_simples(obra_nome, LARGURA_UTIL, obra_info))
        story.append(_linha_separadora(LARGURA_UTIL))
        story.append(Spacer(1, 0.4 * cm))

        if has_desp:
            story.append(Paragraph("Despesas da última semana", estilos['secao_titulo']))
            story.append(Spacer(1, 0.15 * cm))
            story.append(_tabela_despesas(df_despesas_semana, estilos, LARGURA_UTIL, mostrar_etapa=True))

        if has_receb:
            _tabela_recebimentos_secao(df_recebimentos, estilos, LARGURA_UTIL, story)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# RELATÓRIO ADMINISTRATIVO — centro de custos com filtro de período
# ─────────────────────────────────────────────────────────────────────────────

def gerar_relatorio_administrativo(
    df_despesas: pd.DataFrame,
    obra_nome: str,
    data_inicio,
    data_fim,
    obra_info: dict = None,
    por_etapa: bool = False,
    df_recebimentos: pd.DataFrame = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=MARGEM, leftMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM,
    )

    estilos = _estilos()
    story   = []

    df = df_despesas.copy()
    if not df.empty:
        df['DATA'] = pd.to_datetime(df['DATA'], errors='coerce')
        ini = pd.Timestamp(data_inicio)
        fim = pd.Timestamp(data_fim)
        df  = df[(df['DATA'] >= ini) & (df['DATA'] <= fim)]

    # Timbrado
    story.append(_timbrado_simples(obra_nome, LARGURA_UTIL, obra_info))
    story.append(_linha_separadora(LARGURA_UTIL))
    story.append(Spacer(1, 0.4 * cm))

    # Subtítulo de período
    st_periodo = ParagraphStyle(
        'Periodo', fontSize=9, textColor=C_ON_VAR,
        fontName='Helvetica', alignment=TA_CENTER,
    )
    story.append(Paragraph(
        f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}",
        st_periodo,
    ))
    story.append(Spacer(1, 0.35 * cm))

    # KPI: custo total do período
    total = float(df['VALOR_TOTAL'].sum()) if not df.empty else 0.0
    col_w = LARGURA_UTIL / 3
    kpi_data = [
        [Paragraph("CUSTO TOTAL DO PERÍODO", estilos['kpi_label_c'])],
        [Paragraph(_fmt(total), estilos['kpi_valor_c'])],
    ]
    kpi_table = Table(kpi_data, colWidths=[col_w])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_SURFACE),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)

    # Filtrar recebimentos pelo mesmo período
    df_receb_periodo = None
    if df_recebimentos is not None and not df_recebimentos.empty:
        df_receb_periodo = df_recebimentos.copy()
        df_receb_periodo['DATA'] = pd.to_datetime(df_receb_periodo['DATA'], errors='coerce')
        _ini = pd.Timestamp(data_inicio)
        _fim = pd.Timestamp(data_fim)
        df_receb_periodo = df_receb_periodo[(df_receb_periodo['DATA'] >= _ini) & (df_receb_periodo['DATA'] <= _fim)]
        if df_receb_periodo.empty:
            df_receb_periodo = None

    # KPIs de fluxo de caixa na mesma página
    if df_receb_periodo is not None:
        _kpis_fluxo_caixa(df_receb_periodo, total, estilos, LARGURA_UTIL, story)

    story.append(Spacer(1, 0.4 * cm))

    # Resumo por etapa (opcional)
    if por_etapa and not df.empty:
        story.append(Paragraph("Resumo por etapa", estilos['secao_titulo']))
        story.append(Spacer(1, 0.15 * cm))
        story.append(_tabela_resumo_etapas(df, estilos, LARGURA_UTIL * 0.5))
        story.append(Spacer(1, 0.4 * cm))

    # ── Página seguinte: tabelas completas ────────────────────────────────────
    has_desp = not df.empty
    has_receb = df_receb_periodo is not None

    if has_desp or has_receb:
        story.append(PageBreak())
        story.append(_timbrado_simples(obra_nome, LARGURA_UTIL, obra_info))
        story.append(_linha_separadora(LARGURA_UTIL))
        story.append(Spacer(1, 0.4 * cm))

        if has_desp:
            story.append(Paragraph("Despesas do período", estilos['secao_titulo']))
            story.append(Spacer(1, 0.15 * cm))
            story.append(_tabela_despesas(df, estilos, LARGURA_UTIL, mostrar_etapa=True))

        if has_receb:
            _tabela_recebimentos_secao(df_receb_periodo, estilos, LARGURA_UTIL, story)
    elif df.empty:
        story.append(Paragraph("Nenhuma despesa encontrada para o período selecionado.", estilos['secao_titulo']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
