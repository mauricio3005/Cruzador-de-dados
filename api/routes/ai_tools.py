"""Definições de tools e funções executoras para o chat assistente de IA."""

import json

from api.logger import get_logger

from .ai_helpers import _get_referencias, _melhor_match, _normalizar

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Tool definitions para OpenAI function calling
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_despesas",
            "description": (
                "Busca despesas no banco de dados com filtros opcionais. "
                "Use SEMPRE que o usuário perguntar sobre despesas de um fornecedor, obra, "
                "período ou categoria específicos. Nomes podem ter variação de acento — passe como escrito."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fornecedor": {"type": "string", "description": "Nome do fornecedor (parcial ou com variação de acento)"},
                    "obra":       {"type": "string", "description": "Nome da obra"},
                    "etapa":      {"type": "string", "description": "Nome da etapa"},
                    "categoria":  {"type": "string", "description": "Categoria da despesa"},
                    "data_inicio":{"type": "string", "description": "Data inicial YYYY-MM-DD"},
                    "data_fim":   {"type": "string", "description": "Data final YYYY-MM-DD"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_totais",
            "description": "Retorna totais financeiros: despesas, orçamento, recebimentos, contas a pagar e top fornecedores. Use para perguntas de resumo financeiro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "obra": {"type": "string", "description": "Filtrar por obra (opcional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_referencias",
            "description": "Lista todos os fornecedores, obras, etapas e categorias cadastradas. Use para encontrar o nome exato antes de outras buscas.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # ── Tools de planejamento (não escrevem — apenas validam e montam payload) ──
    {
        "type": "function",
        "function": {
            "name": "planejar_criar_despesa",
            "description": "Planeja criação de uma despesa em c_despesas. Retorna payload validado para confirmação — NÃO escreve no banco.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao":       {"type": "string"},
                    "valor_total":     {"type": "number"},
                    "obra":            {"type": "string"},
                    "etapa":           {"type": "string"},
                    "tipo":            {"type": "string", "description": "Mão de Obra | Materiais | Geral"},
                    "fornecedor":      {"type": "string"},
                    "despesa":         {"type": "string", "description": "Categoria da despesa"},
                    "forma":           {"type": "string", "description": "PIX | Boleto | Cartão | Dinheiro | Transferência"},
                    "banco":           {"type": "string"},
                    "data":            {"type": "string", "description": "YYYY-MM-DD (default: hoje)"},
                },
                "required": ["descricao", "valor_total", "obra"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_editar_despesa",
            "description": "Planeja edição de UMA despesa existente. Requer id (UUID obtido via buscar_despesas). Informe apenas os campos a alterar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id":              {"type": "string", "description": "UUID da despesa"},
                    "descricao":       {"type": "string"},
                    "valor_total":     {"type": "number"},
                    "obra":            {"type": "string"},
                    "etapa":           {"type": "string"},
                    "tipo":            {"type": "string"},
                    "fornecedor":      {"type": "string"},
                    "despesa":         {"type": "string"},
                    "forma":           {"type": "string"},
                    "banco":           {"type": "string"},
                    "data":            {"type": "string"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_editar_lote_despesas",
            "description": "Planeja edição de MÚLTIPLAS despesas aplicando os mesmos campos a todas. Use após buscar_despesas para obter os ids[]. Forneça pelo menos um campo além de ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ids":         {"type": "array", "items": {"type": "string"}, "description": "Lista de UUIDs das despesas a editar"},
                    "fornecedor":  {"type": "string", "description": "Novo fornecedor (fuzzy match automático)"},
                    "obra":        {"type": "string", "description": "Nova obra"},
                    "etapa":       {"type": "string", "description": "Nova etapa"},
                    "tipo":        {"type": "string", "enum": ["Mão de Obra", "Materiais", "Geral"]},
                    "despesa":     {"type": "string", "description": "Nova categoria de despesa"},
                    "descricao":   {"type": "string"},
                    "valor_total": {"type": "number"},
                    "data":        {"type": "string", "description": "YYYY-MM-DD"},
                    "forma":       {"type": "string", "description": "Forma de pagamento"},
                    "banco":       {"type": "string"},
                    "paga":        {"type": "boolean"},
                    "vencimento":  {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_criar_recebimento",
            "description": "Planeja criação de um recebimento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao":  {"type": "string"},
                    "valor":      {"type": "number"},
                    "obra":       {"type": "string"},
                    "data":       {"type": "string", "description": "YYYY-MM-DD"},
                    "fornecedor": {"type": "string"},
                    "forma":      {"type": "string"},
                },
                "required": ["descricao", "valor", "obra"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_editar_recebimento",
            "description": "Planeja edição de um recebimento existente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id":         {"type": "string"},
                    "descricao":  {"type": "string"},
                    "valor":      {"type": "number"},
                    "obra":       {"type": "string"},
                    "data":       {"type": "string"},
                    "fornecedor": {"type": "string"},
                    "forma":      {"type": "string"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_editar_lote_recebimentos",
            "description": "Planeja edição de MÚLTIPLOS recebimentos aplicando os mesmos campos a todos. Forneça pelo menos um campo além de ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ids":        {"type": "array", "items": {"type": "string"}, "description": "Lista de UUIDs dos recebimentos a editar"},
                    "descricao":  {"type": "string"},
                    "valor":      {"type": "number"},
                    "obra":       {"type": "string"},
                    "data":       {"type": "string"},
                    "fornecedor": {"type": "string"},
                    "forma":      {"type": "string"},
                },
                "required": ["ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_criar_conta_a_pagar",
            "description": "Planeja criação de uma conta a pagar (despesa com vencimento em c_despesas).",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao":  {"type": "string"},
                    "valor":      {"type": "number"},
                    "vencimento": {"type": "string", "description": "YYYY-MM-DD"},
                    "obra":       {"type": "string"},
                    "fornecedor": {"type": "string"},
                },
                "required": ["descricao", "valor", "vencimento", "obra"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_editar_conta_a_pagar",
            "description": "Planeja edição de uma conta a pagar existente (despesa com vencimento em c_despesas).",
            "parameters": {
                "type": "object",
                "properties": {
                    "id":         {"type": "string"},
                    "descricao":  {"type": "string"},
                    "valor":      {"type": "number"},
                    "vencimento": {"type": "string"},
                    "obra":       {"type": "string"},
                    "fornecedor": {"type": "string"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_editar_lote_contas_a_pagar",
            "description": "Planeja edição de MÚLTIPLAS contas a pagar (despesas com vencimento em c_despesas) aplicando os mesmos campos a todas. Forneça pelo menos um campo além de ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ids":        {"type": "array", "items": {"type": "string"}, "description": "Lista de UUIDs das contas a editar"},
                    "descricao":  {"type": "string"},
                    "valor":      {"type": "number"},
                    "vencimento": {"type": "string"},
                    "obra":       {"type": "string"},
                    "fornecedor": {"type": "string"},
                },
                "required": ["ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_marcar_conta_paga",
            "description": "Planeja marcação de uma conta a pagar como paga (atualiza c_despesas.paga e data_pagamento).",
            "parameters": {
                "type": "object",
                "properties": {
                    "id":              {"type": "string", "description": "UUID da conta"},
                    "data_pagamento":  {"type": "string", "description": "YYYY-MM-DD (default: hoje)"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_criar_fornecedor",
            "description": "Planeja criação de um novo fornecedor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                },
                "required": ["nome"],
            },
        },
    },
    # ── Remessas de caixa ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "buscar_saldo_bancos",
            "description": (
                "Retorna o saldo disponível de cada conta controlada (bancos filhos, ex: Kathleen Thais, Diego estagiário) — "
                "remessas recebidas menos despesas lançadas naquela conta. "
                "Bancos principais (ex: Maurício, Marcos Cabelinho) são fontes e não aparecem nos saldos. "
                "Use quando o usuário perguntar sobre saldo, caixa disponível ou posição de uma conta."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_remessas",
            "description": (
                "Lista o histórico de remessas enviadas para as contas controladas, com filtros opcionais. "
                "Use quando o usuário perguntar sobre remessas enviadas, histórico de transferências ou valores enviados para uma conta."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conta":       {"type": "string", "description": "Filtrar por nome da conta destino (ex: Kathleen, Diego)"},
                    "data_inicio": {"type": "string", "description": "Data inicial YYYY-MM-DD"},
                    "data_fim":    {"type": "string", "description": "Data final YYYY-MM-DD"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_criar_remessa",
            "description": (
                "Planeja o registro de uma nova remessa de caixa (valor enviado de um banco principal para uma conta controlada). "
                "Não executa — apenas prepara o payload para confirmação do usuário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "banco_destino": {"type": "string", "description": "Conta que recebe (ex: Kathleen, Diego)"},
                    "valor":         {"type": "number",  "description": "Valor da remessa em R$"},
                    "data":          {"type": "string",  "description": "Data YYYY-MM-DD (padrão: hoje)"},
                    "descricao":     {"type": "string",  "description": "Descrição opcional"},
                    "obra":          {"type": "string",  "description": "Obra relacionada (opcional)"},
                },
                "required": ["banco_destino", "valor"],
            },
        },
    },
    # ── Folha de pagamento ───────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "buscar_folhas",
            "description": (
                "Lista folhas de pagamento cadastradas, com filtro opcional por obra. "
                "Use para localizar o id de uma folha antes de adicionar ou editar funcionários."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "obra":   {"type": "string", "description": "Filtrar por obra (opcional)"},
                    "status": {"type": "string", "description": "Filtrar por status: rascunho | enviada | fechada (opcional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_funcionarios_folha",
            "description": (
                "Lista os funcionários de uma folha específica pelo id da folha. "
                "Use para consultar ou obter os ids dos registros antes de editar ou remover."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folha_id": {"type": "integer", "description": "ID numérico da folha"},
                },
                "required": ["folha_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_criar_folha",
            "description": (
                "Planeja a criação de um novo rascunho de folha de pagamento. "
                "Não executa — apenas prepara o payload para confirmação do usuário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "obra":     {"type": "string", "description": "Nome da obra"},
                    "quinzena": {"type": "string", "description": "Data da quinzena YYYY-MM-DD (ex: primeiro ou décimo sexto dia do mês)"},
                },
                "required": ["obra", "quinzena"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_adicionar_funcionario",
            "description": (
                "Planeja a adição de um funcionário a uma folha em rascunho. "
                "Para diaristas: informe servico e diarias — o valor é calculado pelas regras da obra. "
                "Para CLT ou salário fixo: informe valor_fixo diretamente (ignora diarias no cálculo). "
                "Não executa — apenas prepara o payload para confirmação do usuário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folha_id":   {"type": "integer", "description": "ID numérico da folha (obter via buscar_folhas)"},
                    "nome":       {"type": "string",  "description": "Nome do funcionário"},
                    "servico":    {"type": "string",  "description": "Serviço/função exercido"},
                    "etapa":      {"type": "string",  "description": "Etapa da obra"},
                    "diarias":    {"type": "number",  "description": "Quantidade de diárias (para diaristas)"},
                    "valor_fixo": {"type": "number",  "description": "Valor fixo em R$ (CLT/salário fixo — sobrepõe cálculo por diárias)"},
                    "pix":        {"type": "string",  "description": "Chave PIX (opcional)"},
                    "nome_conta": {"type": "string",  "description": "Nome da conta bancária (opcional)"},
                },
                "required": ["folha_id", "nome", "servico", "etapa"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_editar_funcionario",
            "description": (
                "Planeja a edição de um funcionário já lançado em uma folha. "
                "Informe apenas os campos a alterar. Use buscar_funcionarios_folha para obter o id. "
                "Para remover valor fixo e voltar ao cálculo automático, passe valor_fixo=null explicitamente. "
                "Não executa — apenas prepara o payload para confirmação do usuário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id":         {"type": "integer", "description": "ID do registro em folha_funcionarios"},
                    "nome":       {"type": "string"},
                    "servico":    {"type": "string"},
                    "etapa":      {"type": "string"},
                    "diarias":    {"type": "number"},
                    "valor_fixo": {"type": ["number", "null"], "description": "Valor fixo em R$ (CLT). Passe null para reverter para cálculo automático por diárias."},
                    "pix":        {"type": "string"},
                    "nome_conta": {"type": "string"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_remover_funcionario",
            "description": (
                "Planeja a remoção de um funcionário de uma folha em rascunho. "
                "Use buscar_funcionarios_folha para confirmar o id antes de remover. "
                "Não executa — apenas prepara o payload para confirmação do usuário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id":   {"type": "integer", "description": "ID do registro em folha_funcionarios"},
                    "nome": {"type": "string",  "description": "Nome do funcionário (para exibição no card de confirmação)"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_editar_lote_funcionarios",
            "description": (
                "Planeja edição de MÚLTIPLOS funcionários de uma folha aplicando os mesmos campos a todos. "
                "Use após buscar_funcionarios_folha para obter os ids[]. "
                "Ideal para trocar etapa ou serviço de todos os funcionários de uma vez. "
                "Não executa — apenas prepara o payload para confirmação do usuário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ids":        {"type": "array", "items": {"type": "integer"}, "description": "Lista de IDs dos registros em folha_funcionarios"},
                    "etapa":      {"type": "string"},
                    "servico":    {"type": "string"},
                    "diarias":    {"type": "number"},
                    "valor_fixo": {"type": "number"},
                    "pix":        {"type": "string"},
                    "nome_conta": {"type": "string"},
                },
                "required": ["ids"],
            },
        },
    },
]

# Conjunto de nomes de tools planejar_* (usado no chat loop)
PLANEJAR_TOOLS = {
    "planejar_criar_despesa", "planejar_editar_despesa",
    "planejar_editar_lote_despesas", "planejar_criar_recebimento",
    "planejar_editar_recebimento", "planejar_editar_lote_recebimentos",
    "planejar_criar_conta_a_pagar",
    "planejar_editar_conta_a_pagar", "planejar_editar_lote_contas_a_pagar",
    "planejar_marcar_conta_paga",
    "planejar_criar_fornecedor",
    "planejar_criar_remessa",
    "planejar_criar_folha", "planejar_adicionar_funcionario",
    "planejar_editar_funcionario", "planejar_editar_lote_funcionarios",
    "planejar_remover_funcionario",
}


# ---------------------------------------------------------------------------
# Funções executoras (consultas read-only)
# ---------------------------------------------------------------------------

def _exec_buscar_despesas(db, fornecedor=None, obra=None, etapa=None, categoria=None, data_inicio=None, data_fim=None):
    existentes = db.table("c_despesas").select("fornecedor, obra").execute().data or []
    fornecs_reais = list({r.get("fornecedor") for r in existentes if r.get("fornecedor")})
    obras_reais   = list({r.get("obra")       for r in existentes if r.get("obra")})

    q = db.table("c_despesas").select("id, obra, etapa, fornecedor, despesa, tipo, data, valor_total, descricao")
    if fornecedor:
        match = _melhor_match(fornecs_reais, _normalizar(fornecedor))
        if match: q = q.eq("fornecedor", match)
    if obra:
        match = _melhor_match(obras_reais, _normalizar(obra))
        if match: q = q.eq("obra", match)
    if etapa:      q = q.eq("etapa", etapa)
    if categoria:  q = q.eq("despesa", categoria)
    if data_inicio: q = q.gte("data", data_inicio)
    if data_fim:    q = q.lte("data", data_fim)

    rows = q.order("data", desc=True).limit(200).execute().data or []
    total = sum(r.get("valor_total") or 0 for r in rows)
    linhas = [
        f"[id:{r.get('id','')}] [{r.get('data','')}] obra={r.get('obra','N/D')} | etapa={r.get('etapa','N/D')} | "
        f"fornecedor={r.get('fornecedor','N/D')} | categoria={r.get('despesa','N/D')} | "
        f"R$ {r.get('valor_total',0):,.2f}" + (f" | {r.get('descricao','')}" if r.get('descricao') else "")
        for r in rows
    ]
    return {"registros": len(rows), "total": total, "despesas": linhas}


def _exec_buscar_totais(db, obra=None):
    q_desp = db.table("c_despesas").select("obra, valor_total, fornecedor, despesa")
    q_orc  = db.table("orcamentos").select("obra, valor_estimado")
    q_rec  = db.table("recebimentos").select("obra, valor")
    q_cp   = db.table("c_despesas").select("valor_total, paga, obra").not_.is_("vencimento", None)
    if obra:
        q_desp = q_desp.eq("obra", obra)
        q_orc  = q_orc.eq("obra", obra)
        q_rec  = q_rec.eq("obra", obra)
        q_cp   = q_cp.eq("obra", obra)

    desp_rows = q_desp.execute().data or []
    orc_rows  = q_orc.execute().data or []
    rec_rows  = q_rec.execute().data or []
    cp_rows   = q_cp.execute().data or []

    total_desp = sum(r.get("valor_total") or 0 for r in desp_rows)
    total_orc  = sum(r.get("valor_estimado") or 0 for r in orc_rows)
    total_rec  = sum(r.get("valor") or 0 for r in rec_rows)
    total_cp   = sum(r.get("valor_total") or 0 for r in cp_rows if not r.get("paga"))

    forn_totais: dict = {}
    for r in desp_rows:
        f = r.get("fornecedor") or "N/D"
        forn_totais[f] = forn_totais.get(f, 0) + (r.get("valor_total") or 0)
    top_forn = sorted(forn_totais.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_despesas":      total_desp,
        "total_orcamento":     total_orc,
        "saldo_orcamentario":  total_orc - total_desp,
        "total_recebido":      total_rec,
        "total_a_pagar":       total_cp,
        "top_fornecedores":    [{"fornecedor": f, "total": v} for f, v in top_forn],
    }


def _exec_listar_referencias(db):
    obras   = [r["nome"] for r in (db.table("obras").select("nome").execute().data or [])]
    etapas  = [r["nome"] for r in (db.table("etapas").select("nome").execute().data or [])]
    fornecs = [r["nome"] for r in (db.table("fornecedores").select("nome").execute().data or [])]
    cats    = [r["nome"] for r in (db.table("categorias_despesa").select("nome").execute().data or [])]
    bancos_raw     = db.table("bancos").select("id, nome, tipo").order("tipo").order("nome").execute().data or []
    banco_obras_raw = db.table("banco_obras").select("banco_id, obra").execute().data or []
    obras_por_banco: dict = {}
    for bo in banco_obras_raw:
        obras_por_banco.setdefault(bo["banco_id"], []).append(bo["obra"])
    bancos = [
        {"nome": b["nome"], "tipo": b["tipo"], "obras": obras_por_banco.get(b["id"], [])}
        for b in bancos_raw
    ]
    return {"obras": obras, "etapas": etapas, "fornecedores": fornecs, "categorias": cats, "bancos": bancos}


def _get_bancos_principais(db) -> set:
    """Retorna nomes dos bancos classificados como 'principal' na tabela bancos."""
    rows = db.table("bancos").select("nome").eq("tipo", "principal").execute().data or []
    return {r["nome"] for r in rows}


def _exec_buscar_saldo_bancos(db) -> dict:
    remessas_rows = db.table("remessas_caixa").select("valor, banco_destino:bancos!banco_destino_id(id,nome)").execute().data or []
    despesas_rows = db.table("c_despesas").select("banco, valor_total").not_.is_("banco", "null").execute().data or []
    principais    = _get_bancos_principais(db)

    recebido: dict = {}
    for r in remessas_rows:
        destino = (r.get("banco_destino") or {}).get("nome")
        if destino:
            recebido[destino] = recebido.get(destino, 0) + (r.get("valor") or 0)

    gasto: dict = {}
    for d in despesas_rows:
        b = d.get("banco")
        if b and b not in principais:
            gasto[b] = gasto.get(b, 0) + (d["valor_total"] or 0)

    contas = (set(recebido) | set(gasto)) - principais
    saldos = [
        {
            "conta":              nome,
            "remessas_recebidas": recebido.get(nome, 0),
            "despesas":           gasto.get(nome, 0),
            "saldo":              recebido.get(nome, 0) - gasto.get(nome, 0),
        }
        for nome in sorted(contas)
    ]
    total_recebido = sum(s["remessas_recebidas"] for s in saldos)
    total_gasto    = sum(s["despesas"] for s in saldos)
    return {
        "total_contas":    len(saldos),
        "total_enviado":   total_recebido,
        "total_gasto":     total_gasto,
        "saldo_geral":     total_recebido - total_gasto,
        "saldos":          saldos,
    }


def _exec_buscar_remessas(db, conta=None, data_inicio=None, data_fim=None) -> dict:
    q = db.table("remessas_caixa").select("id, valor, data, descricao, obra, comprovante_url, banco_destino:bancos!banco_destino_id(id,nome)")
    if data_inicio: q = q.gte("data", data_inicio)
    if data_fim:    q = q.lte("data", data_fim)
    rows = q.order("data", desc=True).limit(100).execute().data or []
    if conta:
        conta_lower = conta.lower()
        rows = [r for r in rows if conta_lower in ((r.get("banco_destino") or {}).get("nome") or "").lower()]
    for r in rows:
        destino = r.pop("banco_destino", None) or {}
        r["banco_destino_nome"] = destino.get("nome", "—")
    total = sum(r.get("valor") or 0 for r in rows)
    return {"registros": len(rows), "total_valor": total, "remessas": rows[:50]}


def _exec_buscar_folhas(db, obra=None, status=None) -> dict:
    q = db.table("folhas").select("id, obra, quinzena, status")
    if obra:   q = q.ilike("obra", f"%{obra}%")
    if status: q = q.eq("status", status)
    rows = q.order("quinzena", desc=True).limit(50).execute().data or []
    return {"registros": len(rows), "folhas": rows}


def _exec_buscar_funcionarios_folha(db, folha_id: int) -> dict:
    folha = db.table("folhas").select("id, obra, quinzena, status").eq("id", folha_id).execute().data
    if not folha:
        return {"erro": f"Folha id={folha_id} não encontrada"}
    funcs = db.table("folha_funcionarios").select("*").eq("folha_id", folha_id).order("id").execute().data or []
    return {"folha": folha[0], "funcionarios": funcs}


# ---------------------------------------------------------------------------
# Handler unificado para todos os tools planejar_*
# ---------------------------------------------------------------------------

def _exec_planejar(db, tool_name: str, args: dict, refs: dict) -> str:
    """Valida, faz fuzzy match e monta payload — não escreve no banco."""
    from datetime import date

    hoje = date.today().isoformat()

    def fuzzy(valor, lista):
        if not valor or not lista:
            return valor
        return _melhor_match(lista, _normalizar(str(valor))) or valor

    if tool_name == "planejar_criar_despesa":
        dados = {k: v for k, v in args.items() if v is not None}
        dados["obra"]      = fuzzy(dados.get("obra"), refs["obras"])
        dados["etapa"]     = fuzzy(dados.get("etapa"), refs["etapas"])
        dados["fornecedor"]= fuzzy(dados.get("fornecedor"), refs["fornecedores"])
        dados["despesa"]   = fuzzy(dados.get("despesa"), refs["categorias"])
        dados.setdefault("data", hoje)
        return json.dumps({"tabela": "c_despesas", "operacao": "inserir", "dados": dados, "antes": None}, ensure_ascii=False)

    elif tool_name == "planejar_editar_despesa":
        id_ = args.get("id")
        if not id_:
            return json.dumps({"erro": "id obrigatório para edição"})
        campos = {k: v for k, v in args.items() if k != "id" and v is not None}
        if "obra" in campos:      campos["obra"]      = fuzzy(campos["obra"], refs["obras"])
        if "etapa" in campos:     campos["etapa"]     = fuzzy(campos["etapa"], refs["etapas"])
        if "fornecedor" in campos:campos["fornecedor"]= fuzzy(campos["fornecedor"], refs["fornecedores"])
        if "despesa" in campos:   campos["despesa"]   = fuzzy(campos["despesa"], refs["categorias"])
        res = db.table("c_despesas").select("*").eq("id", id_).limit(1).execute()
        antes = res.data[0] if res.data else {}
        return json.dumps({"tabela": "c_despesas", "operacao": "atualizar", "id": id_, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_editar_lote_despesas":
        ids = args.get("ids", [])
        if not ids:
            return json.dumps({"erro": "ids[] obrigatório"})
        _CAMPOS_DESPESA = {"fornecedor", "obra", "etapa", "tipo", "despesa", "descricao",
                           "valor_total", "data", "forma", "banco", "paga", "vencimento"}
        campos = {k: v for k, v in args.items() if k in _CAMPOS_DESPESA and v is not None}
        if not campos:
            return json.dumps({"erro": "Nenhum campo para alterar foi fornecido. Informe pelo menos um campo além de ids."})
        if "obra" in campos:       campos["obra"]       = fuzzy(campos["obra"], refs["obras"])
        if "etapa" in campos:      campos["etapa"]      = fuzzy(campos["etapa"], refs["etapas"])
        if "fornecedor" in campos: campos["fornecedor"] = fuzzy(campos["fornecedor"], refs["fornecedores"])
        if "despesa" in campos:    campos["despesa"]    = fuzzy(campos["despesa"], refs["categorias"])
        res = db.table("c_despesas").select("id, data, fornecedor, descricao, despesa, valor_total").in_("id", ids).execute()
        antes = res.data or []
        return json.dumps({"tabela": "c_despesas", "operacao": "atualizar_lote", "ids": ids, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_criar_recebimento":
        dados = {k: v for k, v in args.items() if v is not None}
        dados["obra"]      = fuzzy(dados.get("obra"), refs["obras"])
        dados["fornecedor"]= fuzzy(dados.get("fornecedor"), refs["fornecedores"])
        dados.setdefault("data", hoje)
        return json.dumps({"tabela": "recebimentos", "operacao": "inserir", "dados": dados, "antes": None}, ensure_ascii=False)

    elif tool_name == "planejar_editar_recebimento":
        id_ = args.get("id")
        if not id_:
            return json.dumps({"erro": "id obrigatório"})
        campos = {k: v for k, v in args.items() if k != "id" and v is not None}
        if "obra" in campos:      campos["obra"]      = fuzzy(campos["obra"], refs["obras"])
        if "fornecedor" in campos:campos["fornecedor"]= fuzzy(campos["fornecedor"], refs["fornecedores"])
        res = db.table("recebimentos").select("*").eq("id", id_).limit(1).execute()
        antes = res.data[0] if res.data else {}
        return json.dumps({"tabela": "recebimentos", "operacao": "atualizar", "id": id_, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_editar_lote_recebimentos":
        ids = args.get("ids", [])
        if not ids:
            return json.dumps({"erro": "ids[] obrigatório"})
        _CAMPOS_REC = {"descricao", "valor", "obra", "data", "fornecedor", "forma"}
        campos = {k: v for k, v in args.items() if k in _CAMPOS_REC and v is not None}
        if not campos:
            return json.dumps({"erro": "Nenhum campo para alterar foi fornecido. Informe pelo menos um campo além de ids."})
        if "obra" in campos:       campos["obra"]       = fuzzy(campos["obra"], refs["obras"])
        if "fornecedor" in campos: campos["fornecedor"] = fuzzy(campos["fornecedor"], refs["fornecedores"])
        res = db.table("recebimentos").select("id, data, descricao, valor, obra, fornecedor").in_("id", ids).execute()
        antes = res.data or []
        return json.dumps({"tabela": "recebimentos", "operacao": "atualizar_lote", "ids": ids, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_criar_conta_a_pagar":
        dados = {k: v for k, v in args.items() if v is not None}
        dados["obra"]      = fuzzy(dados.get("obra"), refs["obras"])
        dados["fornecedor"]= fuzzy(dados.get("fornecedor"), refs["fornecedores"])
        dados["despesa"]   = fuzzy(dados.get("despesa"), refs["categorias"])
        dados.setdefault("paga", False)
        dados.setdefault("data", dados.get("vencimento", hoje))
        dados.setdefault("tipo", "Geral")
        if "valor" in dados and "valor_total" not in dados:
            dados["valor_total"] = dados.pop("valor")
        return json.dumps({"tabela": "c_despesas", "operacao": "inserir", "dados": dados, "antes": None}, ensure_ascii=False)

    elif tool_name == "planejar_editar_conta_a_pagar":
        id_ = args.get("id")
        if not id_:
            return json.dumps({"erro": "id obrigatório"})
        campos = {k: v for k, v in args.items() if k != "id" and v is not None}
        if "obra" in campos: campos["obra"] = fuzzy(campos["obra"], refs["obras"])
        if "fornecedor" in campos: campos["fornecedor"] = fuzzy(campos["fornecedor"], refs["fornecedores"])
        if "valor" in campos and "valor_total" not in campos:
            campos["valor_total"] = campos.pop("valor")
        res = db.table("c_despesas").select("*").eq("id", id_).limit(1).execute()
        antes = res.data[0] if res.data else {}
        return json.dumps({"tabela": "c_despesas", "operacao": "atualizar", "id": id_, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_editar_lote_contas_a_pagar":
        ids = args.get("ids", [])
        if not ids:
            return json.dumps({"erro": "ids[] obrigatório"})
        _CAMPOS_CAP = {"descricao", "valor", "valor_total", "vencimento", "obra", "fornecedor"}
        campos = {k: v for k, v in args.items() if k in _CAMPOS_CAP and v is not None}
        if not campos:
            return json.dumps({"erro": "Nenhum campo para alterar foi fornecido. Informe pelo menos um campo além de ids."})
        if "obra" in campos:       campos["obra"]       = fuzzy(campos["obra"], refs["obras"])
        if "fornecedor" in campos: campos["fornecedor"] = fuzzy(campos["fornecedor"], refs["fornecedores"])
        if "valor" in campos and "valor_total" not in campos:
            campos["valor_total"] = campos.pop("valor")
        res = db.table("c_despesas").select("id, descricao, valor_total, vencimento, obra, fornecedor").in_("id", ids).execute()
        antes = res.data or []
        return json.dumps({"tabela": "c_despesas", "operacao": "atualizar_lote", "ids": ids, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_marcar_conta_paga":
        id_ = args.get("id")
        if not id_:
            return json.dumps({"erro": "id obrigatório"})
        data_pag = args.get("data_pagamento", hoje)
        res = db.table("c_despesas").select("*").eq("id", id_).limit(1).execute()
        antes = res.data[0] if res.data else {}
        return json.dumps({"tabela": "c_despesas", "operacao": "atualizar", "id": id_, "dados": {"paga": True, "data_pagamento": data_pag}, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_criar_fornecedor":
        nome = (args.get("nome") or "").strip()
        if not nome:
            return json.dumps({"erro": "nome obrigatório"})
        return json.dumps({"tabela": "fornecedores", "operacao": "inserir", "dados": {"nome": nome}, "antes": None}, ensure_ascii=False)

    elif tool_name == "planejar_criar_remessa":
        from datetime import date as _date
        destino = (args.get("banco_destino") or "").strip()
        valor   = args.get("valor")
        if not destino or not valor:
            return json.dumps({"erro": "banco_destino e valor são obrigatórios"})
        principais = _get_bancos_principais(db)
        if destino in principais:
            return json.dumps({"erro": f"'{destino}' é um banco principal (fonte) e não pode ser o destino de uma remessa"})
        filhos_row = db.table("bancos").select("id, nome").eq("tipo", "filho").execute().data or []
        filhos_map = {r["nome"]: r["id"] for r in filhos_row}
        if destino not in filhos_map:
            return json.dumps({"erro": f"'{destino}' não está cadastrado como banco filho. Bancos disponíveis: {sorted(filhos_map.keys())}"})
        destino_id = filhos_map[destino]
        origem_row = db.table("bancos").select("nome").eq("tipo", "principal").limit(1).execute().data or []
        origem = origem_row[0]["nome"] if origem_row else "Maurício"
        data_r = (args.get("data") or _date.today().isoformat()).strip()
        dados  = {"banco_destino_id": destino_id, "valor": valor, "data": data_r}
        if args.get("descricao"): dados["descricao"] = args["descricao"]
        if args.get("obra"):      dados["obra"]      = args["obra"]
        return json.dumps({"tabela": "remessas_caixa", "operacao": "inserir", "dados": dados, "antes": None,
                           "_display": {"banco_origem": origem, "banco_destino": destino}}, ensure_ascii=False)

    # ── Folha de pagamento ───────────────────────────────────────────────────

    elif tool_name == "planejar_criar_folha":
        obra = (args.get("obra") or "").strip()
        quinzena = (args.get("quinzena") or "").strip()
        if not obra:
            return json.dumps({"erro": "Campo 'obra' obrigatório"})
        if not quinzena:
            return json.dumps({"erro": "Campo 'quinzena' obrigatório (YYYY-MM-DD)"})
        obra_match = fuzzy(obra, refs.get("obras", []))
        obras_existentes = [o["nome"] for o in (db.table("obras").select("nome").execute().data or [])]
        if obra_match not in obras_existentes:
            return json.dumps({"erro": f"Obra '{obra}' não encontrada. Obras disponíveis: {obras_existentes[:10]}"})
        dados = {"obra": obra_match, "quinzena": quinzena, "status": "rascunho"}
        return json.dumps({
            "tabela": "folhas", "operacao": "inserir", "dados": dados,
            "antes": None, "depois": dados,
        }, ensure_ascii=False)

    elif tool_name == "planejar_adicionar_funcionario":
        folha_id = args.get("folha_id")
        nome     = (args.get("nome") or "").strip()
        servico  = (args.get("servico") or "").strip()
        etapa    = (args.get("etapa") or "").strip()
        diarias  = float(args.get("diarias") or 0)
        if not folha_id:
            return json.dumps({"erro": "Campo 'folha_id' obrigatório"})
        if not nome:
            return json.dumps({"erro": "Campo 'nome' obrigatório"})
        if not servico:
            return json.dumps({"erro": "Campo 'servico' obrigatório"})
        if not etapa:
            return json.dumps({"erro": "Campo 'etapa' obrigatório"})
        folha_rows = db.table("folhas").select("id, obra, status").eq("id", folha_id).execute().data
        if not folha_rows:
            return json.dumps({"erro": f"Folha id={folha_id} não encontrada"})
        folha_rec = folha_rows[0]
        if folha_rec["status"] == "fechada":
            return json.dumps({"erro": "Não é possível adicionar funcionários a uma folha fechada"})
        valor_fixo = args.get("valor_fixo")
        if valor_fixo is not None:
            valor = round(float(valor_fixo), 2)
        else:
            regras = db.table("folha_regras").select("servico, tipo, valor").eq("obra", folha_rec["obra"]).execute().data or []
            regras_map = {r["servico"]: float(r.get("valor") or 0) for r in regras}
            valor = round(regras_map.get(servico, 0) * diarias, 2)
        dados = {
            "folha_id":  folha_id,
            "nome":      nome,
            "servico":   servico,
            "etapa":     etapa,
            "diarias":   diarias,
            "valor":     valor,
            "valor_fixo": round(float(valor_fixo), 2) if valor_fixo is not None else None,
            "pix":        args.get("pix") or None,
            "nome_conta": args.get("nome_conta") or None,
        }
        return json.dumps({
            "tabela": "folha_funcionarios", "operacao": "inserir", "dados": dados,
            "antes": None, "depois": dados,
        }, ensure_ascii=False)

    elif tool_name == "planejar_editar_funcionario":
        id_ = args.get("id")
        if not id_:
            return json.dumps({"erro": "Campo 'id' obrigatório"})
        func_rows = db.table("folha_funcionarios").select("*, folhas(status)").eq("id", id_).execute().data
        if not func_rows:
            return json.dumps({"erro": f"Funcionário id={id_} não encontrado"})
        func_rec = func_rows[0]
        folha_status = (func_rec.get("folhas") or {}).get("status")
        if folha_status == "fechada":
            return json.dumps({"erro": "Não é possível editar funcionários de uma folha fechada"})
        campos = {k: v for k, v in {
            "nome":       args.get("nome"),
            "servico":    args.get("servico"),
            "etapa":      args.get("etapa"),
            "diarias":    args.get("diarias"),
            "pix":        args.get("pix"),
            "nome_conta": args.get("nome_conta"),
        }.items() if v is not None}
        if "valor_fixo" in args:
            campos["valor_fixo"] = round(float(args["valor_fixo"]), 2) if args["valor_fixo"] is not None else None
        if not campos:
            return json.dumps({"erro": "Nenhum campo informado para edição"})
        folha_rows = db.table("folhas").select("obra").eq("id", func_rec["folha_id"]).execute().data
        valor_fixo_final = campos.get("valor_fixo") if "valor_fixo" in campos else func_rec.get("valor_fixo")
        if valor_fixo_final is not None:
            campos["valor"] = round(float(valor_fixo_final), 2)
        elif folha_rows and ("servico" in campos or "diarias" in campos or "valor_fixo" in campos):
            servico_final = campos.get("servico") or func_rec.get("servico")
            diarias_final = float(campos.get("diarias") if campos.get("diarias") is not None else func_rec.get("diarias") or 0)
            regras = db.table("folha_regras").select("servico, valor").eq("obra", folha_rows[0]["obra"]).execute().data or []
            regras_map = {r["servico"]: float(r.get("valor") or 0) for r in regras}
            campos["valor"] = round(regras_map.get(servico_final, 0) * diarias_final, 2)
        antes = {k: func_rec.get(k) for k in campos}
        return json.dumps({
            "tabela": "folha_funcionarios", "operacao": "atualizar", "id": id_, "dados": campos,
            "antes": antes, "depois": campos,
        }, ensure_ascii=False)

    elif tool_name == "planejar_editar_lote_funcionarios":
        ids = args.get("ids", [])
        if not ids:
            return json.dumps({"erro": "ids[] obrigatório"})
        _CAMPOS_FUNC = {"etapa", "servico", "diarias", "valor_fixo", "pix", "nome_conta"}
        campos = {k: v for k, v in args.items() if k in _CAMPOS_FUNC and v is not None}
        if not campos:
            return json.dumps({"erro": "Nenhum campo para alterar foi fornecido. Informe pelo menos um campo além de ids."})
        func_rows = db.table("folha_funcionarios").select("id, nome, etapa, servico, folha_id, folhas(status)").in_("id", ids).execute().data or []
        fechadas = [r["folha_id"] for r in func_rows if (r.get("folhas") or {}).get("status") == "fechada"]
        if fechadas:
            return json.dumps({"erro": f"Alguns funcionários pertencem a folhas fechadas (folha_id={fechadas}) — edição não permitida"})
        antes = [{"id": r["id"], "nome": r["nome"], "etapa": r.get("etapa"), "servico": r.get("servico")} for r in func_rows]
        return json.dumps({"tabela": "folha_funcionarios", "operacao": "atualizar_lote", "ids": ids, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_remover_funcionario":
        id_ = args.get("id")
        nome = args.get("nome") or f"Funcionário id={id_}"
        if not id_:
            return json.dumps({"erro": "Campo 'id' obrigatório"})
        func_rows = db.table("folha_funcionarios").select("id, nome, folha_id, folhas(status)").eq("id", id_).execute().data
        if not func_rows:
            return json.dumps({"erro": f"Funcionário id={id_} não encontrado"})
        func_rec = func_rows[0]
        folha_status = (func_rec.get("folhas") or {}).get("status")
        if folha_status == "fechada":
            return json.dumps({"erro": "Não é possível remover funcionários de uma folha fechada"})
        nome_real = func_rec.get("nome") or nome
        return json.dumps({
            "tabela": "folha_funcionarios", "operacao": "deletar", "id": id_,
            "antes": {"nome": nome_real}, "depois": None,
        }, ensure_ascii=False)

    return json.dumps({"erro": f"tool '{tool_name}' não reconhecido"})
