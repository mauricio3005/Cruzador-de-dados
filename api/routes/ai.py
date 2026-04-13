"""Router principal de IA: chat assistente com tool calling e execução de operações.

Módulos auxiliares:
  - ai_helpers.py    — normalização, OpenAI client, cache de referências
  - ai_extraction.py — endpoints de extração (NF, texto, PIX, Whisper, embeddings)
  - ai_tools.py      — definições de tools e funções executoras
"""

import asyncio
import base64
import datetime
import json

from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, model_validator

from api.config import OPENAI_CHAT_MODEL
from api.dependencies import get_current_user
from api.logger import get_logger
from api.supabase_client import get_supabase as _get_supabase

from .ai_helpers import _get_openai, _get_referencias, _parse_json_response
from .ai_extraction import router as _extraction_router
from .ai_tools import (
    PLANEJAR_TOOLS,
    _TOOLS,
    _exec_buscar_despesas,
    _exec_buscar_folhas,
    _exec_buscar_funcionarios_folha,
    _exec_buscar_remessas,
    _exec_buscar_saldo_bancos,
    _exec_buscar_totais,
    _exec_listar_referencias,
    _exec_planejar,
)

router = APIRouter()
logger = get_logger(__name__)

# Inclui endpoints de extração no mesmo router (mesmas URLs)
router.include_router(_extraction_router)


# ---------------------------------------------------------------------------
# Endpoint: chat assistente geral — tool calling + reasoning effort
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat_assistente(request: Request, _user=Depends(get_current_user)):
    """
    Assistente de IA com tool calling.
    Aceita JSON (application/json) ou multipart/form-data (com arquivos opcionais).
    """
    content_type = request.headers.get("content-type", "")
    arquivos: list = []

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        mensagem      = (form.get("mensagem") or "").strip()
        historico_raw = form.get("historico") or "[]"
        try:
            historico = json.loads(historico_raw)
        except Exception:
            historico = []
        obra_contexto = form.get("obra") or None
        pagina        = form.get("pagina") or "dashboard"
        folha_id_ctx  = form.get("folha_id") or None
        quinzena_ctx  = form.get("quinzena") or None
        arquivos      = form.getlist("arquivos")
    else:
        body = await request.json()
        mensagem      = (body.get("mensagem") or "").strip()
        historico     = body.get("historico") or []
        obra_contexto = body.get("obra") or None
        pagina        = body.get("pagina") or "dashboard"
        folha_id_ctx  = body.get("folha_id") or None
        quinzena_ctx  = body.get("quinzena") or None

    if not mensagem and not arquivos:
        raise HTTPException(status_code=400, detail="Campo 'mensagem' obrigatório")
    if not mensagem:
        mensagem = "Analise o(s) arquivo(s) em anexo."

    logger.info("chat: mensagem='%.80s' obra='%s' pagina='%s'", mensagem, obra_contexto, pagina)

    try:
        db = _get_supabase()
    except Exception as err:
        logger.error("chat: erro ao conectar ao banco — %s", err, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")

    _hoje = datetime.date.today()
    _SYSTEM = (
        f"Data de hoje: {_hoje.isoformat()} (ano {_hoje.year}). Toda data informada pelo usuário deve ser interpretada neste contexto.\n\n"
        "Você é a IA de bordo de um sistema de gestão de obras. Você tem acesso a ferramentas de leitura e planejamento de operações no banco de dados. Seu comportamento segue regras rígidas descritas abaixo.\n\n"
        "---\n\n"
        "## IDENTIDADE E ESCOPO\n\n"
        "Você auxilia gestores e equipes de obra a consultar, registrar e alterar dados financeiros e operacionais — despesas, recebimentos, contas a pagar e fornecedores. Você é direto, eficiente e nunca inventa dados.\n\n"
        "---\n\n"
        "## REGRAS DE OURO (invioláveis)\n\n"
        "1. **Nunca escreva no banco de dados diretamente.** Para qualquer operação de criação ou edição, use exclusivamente os tools `planejar_*`. Esses tools apenas validam e montam o payload — não executam nada.\n\n"
        "2. **Toda operação de escrita exige confirmação explícita do usuário.** Após usar um tool `planejar_*`, retorne sempre um JSON com `\"acao\": \"confirmar_operacao\"` para o frontend exibir o card de confirmação. Nunca simule que a operação foi executada antes da confirmação.\n\n"
        "3. **Nunca delete registros.** Operações de exclusão não estão disponíveis e não devem ser sugeridas.\n\n"
        "4. **Nunca invente IDs, UUIDs ou dados que você não buscou.** Para edições, use primeiro `buscar_despesas` para obter os IDs reais antes de chamar qualquer tool `planejar_editar_*`.\n\n"
        "5. **Se faltar um campo obrigatório, pergunte antes de planejar.** Não tente prosseguir com dados incompletos.\n\n"
        "6. **Para edições em lote, sempre busque os registros antes.** Despesas: `buscar_despesas` → `planejar_editar_lote_despesas(ids, campos)`. Recebimentos: `buscar_totais` ou consulta direta → `planejar_editar_lote_recebimentos(ids, campos)`. Contas a pagar: consulta → `planejar_editar_lote_contas_a_pagar(ids, campos)`. Funcionários de folha: `buscar_funcionarios_folha(folha_id)` → `planejar_editar_lote_funcionarios(ids, campos)`.\n\n"
        "7. **Aplique fuzzy match ao interpretar nomes.** Obras, etapas, fornecedores e categorias podem vir com grafia aproximada. Use correspondência aproximada — mas confirme se ambíguo.\n\n"
        "8. **Seja conciso.** Sem introduções nem frases de cortesia. Formate valores como 'R$ 1.234,56'.\n\n"
        "---\n\n"
        "## FORMATO DE RETORNO PARA CONFIRMAÇÃO\n\n"
        "Sempre que um tool `planejar_*` retornar sucesso, sua resposta deve ser **exclusivamente** o seguinte JSON (sem texto antes ou depois):\n"
        "```json\n"
        "{\"acao\": \"confirmar_operacao\", \"tipo\": \"<tipo>\", \"resumo\": \"<descrição curta>\", "
        "\"registros\": [{\"id\": \"...\", \"descricao\": \"...\", \"antes\": {}, \"depois\": {}}], "
        "\"payload\": {\"tabela\": \"...\", \"operacao\": \"...\", \"dados\": {}}}\n"
        "```\n"
        "Para criações, `\"antes\"` é null e `\"depois\"` contém os campos do novo registro.\n"
        "O campo `\"payload\"` deve conter exatamente o que o tool `planejar_*` retornou (tabela, operacao, id/ids, dados).\n\n"
        "---\n\n"
        "## FLUXO DE CONSULTA\n\n"
        "Para perguntas como 'quais despesas da Obra Norte em março?' use os tools de leitura e responda em linguagem natural. Não exiba cards de confirmação para consultas.\n\n"
        "## REMESSAS E SALDO DAS CONTAS\n\n"
        "O sistema controla remessas de caixa enviadas por bancos principais (ex: Maurício, Marcos Cabelinho) para contas controladas/filhas (ex: Kathleen Thais, Diego estagiário). "
        "Bancos principais são fontes de recursos e não aparecem nos saldos controlados. "
        "Use `buscar_saldo_bancos` para saldo disponível de cada conta controlada. "
        "Use `buscar_remessas` para histórico de remessas enviadas (filtre por `conta` se necessário). "
        "Para registrar nova remessa, use `planejar_criar_remessa` com `banco_destino` e `valor` (requer confirmação). "
        "Saldo de uma conta = total recebido em remessas − total de despesas lançadas naquela conta em c_despesas.\n\n"
        "## FOLHA DE PAGAMENTO\n\n"
        "Você pode criar rascunhos de folha e editar folhas existentes que ainda não foram fechadas. "
        "Fluxo para criar nova folha: `planejar_criar_folha(obra, quinzena)` → confirmação → folha criada com status 'rascunho'. "
        "Fluxo para adicionar funcionário: `buscar_folhas` para obter o id → `planejar_adicionar_funcionario(folha_id, nome, servico, etapa, diarias)` → confirmação. O valor é calculado automaticamente pelas regras da obra. "
        "Fluxo para editar funcionário único: `buscar_funcionarios_folha(folha_id)` para obter o id → `planejar_editar_funcionario(id, campos...)` → confirmação. "
        "Fluxo para editar todos ou múltiplos funcionários: `buscar_funcionarios_folha(folha_id)` → colete os ids → `planejar_editar_lote_funcionarios(ids, campos...)` → confirmação. "
        "Fluxo para remover funcionário: `buscar_funcionarios_folha(folha_id)` para confirmar o id → `planejar_remover_funcionario(id)` → confirmação. "
        "**Restrições:** não é possível criar, editar ou remover funcionários de folhas com status 'fechada'. O fechamento definitivo (que gera despesas e faz upload de comprovantes) deve ser feito pela interface da folha de pagamento.\n\n"
        f"Página atual: {pagina}."
        + (f" Obra selecionada: {obra_contexto}." if obra_contexto else "")
        + (f" Folha ativa: id={folha_id_ctx}, quinzena={quinzena_ctx}. Use este folha_id diretamente ao chamar buscar_funcionarios_folha ou planejar_*_funcionario." if folha_id_ctx else "")
    )

    # Monta conteúdo da mensagem do usuário (text + arquivos opcionais)
    user_content: list = [{"type": "text", "text": mensagem}]
    for arq in (arquivos or []):
        file_bytes = await arq.read()
        media_type = arq.content_type or "image/jpeg"
        if media_type == "application/pdf":
            try:
                import pypdf, io as _io
                reader = pypdf.PdfReader(_io.BytesIO(file_bytes))
                texto_pdf = "\n".join(p.extract_text() or "" for p in reader.pages).strip()
                if texto_pdf:
                    user_content.append({"type": "text", "text": f"[PDF: {arq.filename}]\n{texto_pdf}"})
            except Exception:
                user_content.append({"type": "text", "text": f"[PDF não legível: {arq.filename}]"})
        elif media_type.startswith("image/"):
            b64 = base64.b64encode(file_bytes).decode()
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{b64}", "detail": "high"},
            })
        else:
            try:
                texto_arq = file_bytes.decode("utf-8", errors="replace")
                user_content.append({"type": "text", "text": f"[{arq.filename}]\n{texto_arq}"})
            except Exception:
                pass

    messages: list = [
        {"role": "system", "content": _SYSTEM},
        *historico,
        {"role": "user", "content": user_content if len(user_content) > 1 else mensagem},
    ]

    client = _get_openai()

    try:
        # Tool calling loop — até 5 rodadas
        for _ in range(5):
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=OPENAI_CHAT_MODEL,
                max_completion_tokens=2000,
                tools=_TOOLS,
                tool_choice="auto",
                messages=messages,
            )
            choice = resp.choices[0]

            if choice.finish_reason == "tool_calls":
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in choice.message.tool_calls
                    ],
                })

                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    logger.debug("chat: tool_call '%s' args=%s", tc.function.name, args)

                    if tc.function.name == "buscar_despesas":
                        result = _exec_buscar_despesas(db, **args)
                    elif tc.function.name == "buscar_totais":
                        result = _exec_buscar_totais(db, **args)
                    elif tc.function.name == "listar_referencias":
                        result = _exec_listar_referencias(db)
                    elif tc.function.name == "buscar_saldo_bancos":
                        result = _exec_buscar_saldo_bancos(db)
                    elif tc.function.name == "buscar_remessas":
                        result = _exec_buscar_remessas(db, **args)
                    elif tc.function.name == "buscar_folhas":
                        result = _exec_buscar_folhas(db, **args)
                    elif tc.function.name == "buscar_funcionarios_folha":
                        result = _exec_buscar_funcionarios_folha(db, **args)
                    elif tc.function.name in PLANEJAR_TOOLS:
                        refs = _get_referencias()
                        result = _exec_planejar(db, tc.function.name, args, refs)
                    else:
                        result = {"error": "ferramenta desconhecida"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result if isinstance(result, str) else json.dumps(result, ensure_ascii=False),
                    })
            else:
                conteudo = (choice.message.content or "").strip()
                try:
                    parsed = _parse_json_response(conteudo)
                    if isinstance(parsed, dict) and "acao" in parsed:
                        return parsed
                except Exception:
                    pass
                return {"resposta": conteudo}

        logger.warning("chat: loop de tool_calls esgotado sem resposta final")
        return {"resposta": "Não foi possível completar a consulta."}
    except Exception as e:
        logger.error("chat: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ---------------------------------------------------------------------------
# Endpoint: executar operação confirmada pelo usuário
# ---------------------------------------------------------------------------

_TABELAS_PERMITIDAS = {
    "c_despesas", "recebimentos", "fornecedores",
    "obras", "etapas", "empresas", "orcamentos", "taxa_conclusao",
    "categorias_despesa", "formas_pagamento", "obra_etapas", "despesas_recorrentes",
    "remessas_caixa", "folhas", "folha_funcionarios",
}
_TABELAS_DELETAR_PERMITIDAS = {"folha_funcionarios"}
_PK_TEXTO = {"fornecedores", "obras", "etapas", "categorias_despesa", "formas_pagamento"}

# Colunas permitidas por tabela — impede injeção de campos arbitrários
_COLUNAS_PERMITIDAS: Dict[str, set] = {
    "c_despesas": {
        "obra", "etapa", "fornecedor", "despesa", "tipo", "forma",
        "valor_total", "data", "descricao", "banco", "vencimento",
        "paga", "data_pagamento", "tem_nota_fiscal", "folha_id",
    },
    "recebimentos": {
        "obra", "fornecedor", "descricao", "valor", "data", "forma",
        "banco", "observacao", "recebido", "data_recebimento",
        "comprovante_url", "parcela_num", "total_parcelas", "grupo_id",
        "tem_comprovante",
    },
    "fornecedores": {"nome", "categoria", "contato"},
    "obras": {
        "nome", "cliente", "status", "data_inicio", "data_fim",
        "valor_contrato", "orcamento_total", "descricao", "contrato",
        "art", "empresa_id",
    },
    "etapas": {"nome", "ordem"},
    "empresas": {"nome", "cnpj", "logo_url", "endereco", "telefone"},
    "orcamentos": {"obra", "etapa", "tipo_custo", "valor_estimado"},
    "taxa_conclusao": {"obra", "etapa", "taxa"},
    "categorias_despesa": {"nome", "grupo"},
    "formas_pagamento": {"nome"},
    "obra_etapas": {"obra", "etapa"},
    "despesas_recorrentes": {
        "obra", "etapa", "tipo", "fornecedor", "despesa", "valor_total",
        "descricao", "banco", "forma", "frequencia", "proxima_data",
        "data_fim", "ativa",
    },
    "remessas_caixa": {
        "valor", "data", "descricao", "obra", "banco_destino_id",
        "comprovante_url",
    },
    "folhas": {"obra", "quinzena", "status"},
    "folha_funcionarios": {
        "folha_id", "nome", "pix", "nome_conta", "servico", "etapa",
        "diarias", "valor", "valor_fixo",
    },
}


class ExecutarRequest(BaseModel):
    tabela: str
    operacao: Literal["inserir", "atualizar", "atualizar_lote", "deletar"]
    dados: Dict[str, Any] = {}
    id: Optional[Union[int, str]] = None
    ids: Optional[List[Union[int, str]]] = None
    antes: Optional[Any] = None  # usado pelo frontend para exibir diff, ignorado aqui

    @model_validator(mode="after")
    def validar_campos(self):
        if self.tabela not in _TABELAS_PERMITIDAS:
            raise ValueError(f"Tabela '{self.tabela}' não permitida")
        if self.operacao == "deletar" and self.tabela not in _TABELAS_DELETAR_PERMITIDAS:
            raise ValueError(f"Operação 'deletar' não permitida para '{self.tabela}'")
        if self.operacao in ("atualizar", "deletar") and not self.id:
            raise ValueError("id obrigatório para " + self.operacao)
        if self.operacao == "atualizar_lote" and not self.ids:
            raise ValueError("ids[] obrigatório para atualizar_lote")
        # Filtrar colunas não permitidas
        permitidas = _COLUNAS_PERMITIDAS.get(self.tabela, set())
        rejeitadas = set(self.dados.keys()) - permitidas
        if rejeitadas:
            raise ValueError(f"Campos não permitidos para '{self.tabela}': {rejeitadas}")
        return self


@router.post("/executar")
async def executar_operacao(body: ExecutarRequest, _user=Depends(get_current_user)):
    """Executa operação de escrita no banco após confirmação do usuário no frontend."""
    sb = _get_supabase()

    try:
        if body.operacao == "inserir":
            res = sb.table(body.tabela).insert(body.dados).execute()

        elif body.operacao == "atualizar":
            pk  = "nome" if body.tabela in _PK_TEXTO else "id"
            res = sb.table(body.tabela).update(body.dados).eq(pk, body.id).execute()

        elif body.operacao == "atualizar_lote":
            res = sb.table(body.tabela).update(body.dados).in_("id", body.ids).execute()

        elif body.operacao == "deletar":
            res = sb.table(body.tabela).delete().eq("id", body.id).execute()

        afetados = len(res.data) if res.data else 0
        logger.info("[AI-EXEC] %s em %s | afetados=%d | dados=%s",
                    body.operacao, body.tabela, afetados, body.dados)
        return {"sucesso": True, "afetados": afetados}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[AI-EXEC] erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")
