import asyncio
import base64
import io
import json
import os
import time
import unicodedata
from functools import lru_cache
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.supabase_client import get_supabase as _get_supabase
from api.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers de normalização (usados em tool calling e busca híbrida)
# ---------------------------------------------------------------------------

def _normalizar(s: str) -> str:
    """Remove acentos e converte para minúsculas."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def _melhor_match(candidatos: list, query: str) -> str | None:
    """Retorna o candidato com mais palavras (>3 letras) presentes na query."""
    best, best_score = None, 0
    for c in candidatos:
        palavras = [p for p in _normalizar(c).split() if len(p) > 3]
        score = sum(1 for p in palavras if p in query)
        if score > best_score:
            best_score, best = score, c
    return best if best_score > 0 else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_openai():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY não configurada")
    return OpenAI(api_key=api_key)


def _parse_json_response(text: str):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


_refs_cache: dict = {}
_refs_cache_ts: float = 0.0
_REFS_TTL = 120  # segundos


def _get_referencias() -> dict:
    """Busca obras, etapas, fornecedores e categorias do Supabase (cache de 2 min)."""
    global _refs_cache, _refs_cache_ts
    if _refs_cache and (time.monotonic() - _refs_cache_ts) < _REFS_TTL:
        return _refs_cache
    db = _get_supabase()
    obras      = [r["nome"] for r in (db.table("obras").select("nome").order("nome").execute().data or [])]
    etapas     = [r["nome"] for r in (db.table("etapas").select("nome").order("nome").execute().data or [])]
    fornecs    = [r["nome"] for r in (db.table("fornecedores").select("nome").order("nome").execute().data or [])]
    categorias = [r["nome"] for r in (db.table("categorias_despesa").select("nome").order("nome").execute().data or [])]
    _refs_cache = {"obras": obras, "etapas": etapas, "fornecedores": fornecs, "categorias": categorias}
    _refs_cache_ts = time.monotonic()
    logger.debug("_get_referencias: cache atualizado (%d fornecs, %d obras)", len(fornecs), len(obras))
    return _refs_cache


# ---------------------------------------------------------------------------
# System prompt base (extração)
# ---------------------------------------------------------------------------

_SYSTEM_EXTRACAO = (
    "Você é um assistente especializado em gestão de obras e despesas da construção civil brasileira. "
    "Sua única função é extrair dados estruturados de documentos fiscais, comprovantes e textos, "
    "retornando SEMPRE JSON válido — nunca texto livre, nunca markdown, nunca explicações.\n\n"
    "REGRAS INVIOLÁVEIS:\n"
    "1. Retorne SOMENTE o JSON solicitado. Nenhum texto antes ou depois. Nenhum bloco ```json```.\n"
    "2. OBRA, ETAPA, FORNECEDOR são campos próprios — JAMAIS os coloque em DESCRICAO.\n"
    "   DESCRICAO deve conter apenas o material/serviço em si (ex: 'cimento CP-II', 'reboco externo').\n"
    "3. Quando receber listas de referência (fornecedores, obras, etapas, categorias), "
    "   use SEMPRE o nome mais próximo da lista — nunca invente nomes. "
    "   Aplique correspondência flexível: ignore acentos, maiúsculas e abreviações comuns.\n"
    "4. DESPESA deve ser exatamente um dos valores da lista de categorias, ou null. "
    "   Nunca use sinônimos nem variações.\n"
    "5. TIPO deve ser exatamente 'Mão de Obra', 'Materiais' ou 'Geral'. "
    "   Use 'Mão de Obra' para serviços/empreiteiros; 'Materiais' para insumos físicos; "
    "   'Geral' para despesas administrativas/operacionais.\n"
    "6. FORMA deve ser exatamente 'PIX', 'Boleto', 'Cartão', 'Dinheiro' ou 'Transferência', ou null.\n"
    "7. DATA deve estar no formato YYYY-MM-DD, ou null se não encontrada.\n"
    "8. VALOR_TOTAL deve ser um número float, sem símbolo de moeda, ou null.\n"
    "9. Quando houver múltiplas despesas no mesmo conteúdo, retorne um array com todas elas. "
    "   Nunca agrupe despesas distintas em uma só entrada.\n"
    "10. Campos não encontrados devem ser null — nunca string vazia, nunca 'N/A'.\n"
    "11. Quando um único comprovante ou documento cobrir mais de uma despesa (ex: uma NF com itens "
    "    de categorias ou etapas diferentes, ou um PIX que paga duas notas distintas), gere uma "
    "    entrada separada para cada despesa E atribua a todas elas o mesmo valor no campo _grupo "
    "    (string curta, ex: 'A', 'B'). Despesas de documentos distintos que não compartilham "
    "    comprovante NÃO devem ter _grupo. Nunca coloque nada sobre comprovante na DESCRICAO.\n"
)

# ---------------------------------------------------------------------------
# Endpoints de referência
# ---------------------------------------------------------------------------

@router.get("/referencias")
def referencias():
    """Retorna obras, etapas, fornecedores e categorias do banco de dados."""
    try:
        return _get_referencias()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoint: extrair NF individual (imagem / PDF)
# ---------------------------------------------------------------------------

@router.post("/extrair")
async def extrair_nota(
    file: UploadFile = File(...),
    fornecedores: str = Form("[]"),
    obras: str       = Form("[]"),
    etapas: str      = Form("[]"),
    categorias: str  = Form("[]"),
):
    """Extrai dados de uma nota fiscal ou comprovante usando GPT-4 Vision."""
    logger.info("extrair_nota: arquivo='%s' tipo='%s'", file.filename, file.content_type)
    file_bytes = await file.read()
    media_type = file.content_type or "image/jpeg"

    # Resolve referências: usa as enviadas pelo frontend; se vazias, busca no banco
    forn_list = json.loads(fornecedores) if fornecedores else []
    obra_list = json.loads(obras)        if obras        else []
    etap_list = json.loads(etapas)       if etapas       else []
    cat_list  = json.loads(categorias)   if categorias   else []

    if not forn_list or not obra_list or not cat_list:
        try:
            refs     = _get_referencias()
            forn_list = forn_list or refs["fornecedores"]
            obra_list = obra_list or refs["obras"]
            etap_list = etap_list or refs["etapas"]
            cat_list  = cat_list  or refs["categorias"]
        except Exception:
            pass  # continua sem listas se o banco falhar

    lista_forn  = ", ".join(forn_list) if forn_list else "qualquer nome"
    lista_obras = ", ".join(obra_list) if obra_list else "qualquer obra"
    lista_etap  = ", ".join(etap_list) if etap_list else "qualquer etapa"
    lista_cat   = ", ".join(cat_list)  if cat_list  else "qualquer categoria"

    client = _get_openai()
    prompt = (
        "Analise o documento anexado — pode ser uma nota fiscal ou comprovante de pagamento.\n\n"
        "REGRA: Se for comprovante de pagamento (PIX, recibo, transferência), preencha APENAS "
        "VALOR_TOTAL, DATA e FORMA. Deixe os demais como null.\n\n"
        "Se for nota fiscal completa, extraia todos os campos.\n\n"
        "Retorne SOMENTE JSON válido, sem texto adicional:\n"
        "{\n"
        '  "FORNECEDOR": "nome mais próximo da lista de fornecedores, ou null",\n'
        '  "OBRA": "nome mais próximo da lista de obras, ou null",\n'
        '  "ETAPA": "nome mais próximo da lista de etapas, ou null",\n'
        '  "VALOR_TOTAL": <float obrigatório>,\n'
        '  "DATA": "YYYY-MM-DD",\n'
        '  "DESCRICAO": "descrição do serviço/material (null se comprovante)",\n'
        '  "TIPO": "Mão de Obra" ou "Materiais" ou "Geral" (null se comprovante),\n'
        '  "FORMA": "PIX" ou "Boleto" ou "Cartão" ou "Dinheiro" ou "Transferência" ou null,\n'
        f'  "DESPESA": escolha da lista [{lista_cat}] ou null\n'
        "}\n\n"
        f"Fornecedores cadastrados: {lista_forn}\n"
        f"Obras cadastradas: {lista_obras}\n"
        f"Etapas cadastradas: {lista_etap}\n"
    )

    try:
        if media_type == "application/pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            texto = "\n".join(p.extract_text() or "" for p in reader.pages)
            messages = [
                {"role": "system", "content": _SYSTEM_EXTRACAO},
                {"role": "user", "content": f"{prompt}\n\nConteúdo:\n{texto}"},
            ]
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            messages = [
                {"role": "system", "content": _SYSTEM_EXTRACAO},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ]},
            ]

        resp = client.chat.completions.create(model="gpt-5.4", max_completion_tokens=1024, messages=messages)
        result = _parse_json_response(resp.choices[0].message.content)
        logger.info("extrair_nota: concluído tokens=%s", resp.usage.total_tokens if resp.usage else "?")
        return result
    except Exception as e:
        logger.error("extrair_nota: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoint: extrair por texto livre
# ---------------------------------------------------------------------------

@router.post("/extrair-texto")
async def extrair_texto(payload: dict):
    """Extrai uma ou mais despesas a partir de texto livre, com matching de fornecedor e categoria."""
    texto = (payload.get("texto") or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Campo 'texto' obrigatório")

    forn_list  = payload.get("fornecedores") or []
    cat_list   = payload.get("categorias")   or []
    obra_list  = payload.get("obras")        or []
    etap_list  = payload.get("etapas")       or []

    # Fallback ao banco se listas vieram vazias
    if not forn_list or not obra_list or not cat_list:
        try:
            refs      = _get_referencias()
            forn_list = forn_list or refs["fornecedores"]
            obra_list = obra_list or refs["obras"]
            etap_list = etap_list or refs["etapas"]
            cat_list  = cat_list  or refs["categorias"]
        except Exception:
            pass

    lista_forn  = ", ".join(forn_list)  if forn_list  else "qualquer nome"
    lista_cat   = ", ".join(cat_list)   if cat_list   else "qualquer categoria"
    lista_obras = ", ".join(obra_list)  if obra_list  else "qualquer obra"
    lista_etap  = ", ".join(etap_list)  if etap_list  else "qualquer etapa"

    client = _get_openai()
    prompt = (
        "Você é um assistente de gestão de obras. Analise o texto abaixo e extraia os dados de UMA ou MAIS despesas.\n"
        "Cada campo deve ser preenchido com precisão. Não coloque em DESCRICAO o que já está em outro campo.\n"
        "ATENÇÃO: FORNECEDOR é empresa/pessoa física que forneceu o serviço/material. "
        "BANCO é a instituição financeira usada para o pagamento (ex: Itaú, Bradesco, Nubank, Caixa). "
        "Nunca coloque banco em FORNECEDOR nem fornecedor em BANCO.\n"
        "Retorne SOMENTE um array JSON válido (mesmo que seja 1 item), sem texto adicional:\n"
        "[\n"
        "  {\n"
        '    "FORNECEDOR": "empresa/pessoa que forneceu o serviço ou material — NÃO coloque banco aqui, ou null",\n'
        '    "BANCO": "instituição financeira do pagamento (ex: Itaú, Nubank) — NÃO coloque fornecedor aqui, ou null",\n'
        '    "OBRA": "nome exato ou mais próximo da lista de obras cadastradas, ou null",\n'
        '    "ETAPA": "nome exato ou mais próximo da lista de etapas cadastradas, ou null",\n'
        '    "VALOR_TOTAL": <número float ou null>,\n'
        '    "DATA": "YYYY-MM-DD ou null",\n'
        '    "DESCRICAO": "breve descrição do serviço/material — NÃO repita obra, etapa, fornecedor aqui",\n'
        '    "TIPO": "Mão de Obra" ou "Materiais" ou "Geral" ou null,\n'
        '    "FORMA": "PIX" ou "Boleto" ou "Cartão" ou "Dinheiro" ou "Transferência" ou null,\n'
        '    "DESPESA": "valor exato da lista de categorias ou null"\n'
        "  }\n"
        "]\n\n"
        f"Fornecedores cadastrados:\n{lista_forn}\n\n"
        f"Obras cadastradas:\n{lista_obras}\n\n"
        f"Etapas cadastradas:\n{lista_etap}\n\n"
        f"Categorias de despesa (use exatamente um desses):\n{lista_cat}\n\n"
        f"Texto:\n{texto}"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-5.4",
            max_completion_tokens=1024,
            messages=[
                {"role": "system", "content": _SYSTEM_EXTRACAO},
                {"role": "user", "content": prompt},
            ],
        )
        resultado = _parse_json_response(resp.choices[0].message.content)
        if isinstance(resultado, dict):
            resultado = [resultado]
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoint: extrair texto misto (texto + arquivos)
# ---------------------------------------------------------------------------

@router.post("/extrair-texto-misto")
async def extrair_texto_misto(
    texto: str = Form(""),
    files: Optional[List[UploadFile]] = File(default=None),
    fornecedores: str = Form("[]"),
    categorias: str   = Form("[]"),
    obras: str        = Form("[]"),
    etapas: str       = Form("[]"),
):
    """Extrai despesas combinando texto livre + imagens/PDFs de NFs em uma única chamada."""
    forn_list  = json.loads(fornecedores) if fornecedores else []
    cat_list   = json.loads(categorias)  if categorias  else []
    obra_list  = json.loads(obras)       if obras       else []
    etap_list  = json.loads(etapas)      if etapas      else []

    # Fallback ao banco se listas vieram vazias
    if not forn_list or not obra_list or not cat_list:
        try:
            refs      = _get_referencias()
            forn_list = forn_list or refs["fornecedores"]
            obra_list = obra_list or refs["obras"]
            etap_list = etap_list or refs["etapas"]
            cat_list  = cat_list  or refs["categorias"]
        except Exception:
            pass

    lista_forn  = ", ".join(forn_list)  if forn_list  else "qualquer nome"
    lista_cat   = ", ".join(cat_list)   if cat_list   else "qualquer categoria"
    lista_obras = ", ".join(obra_list)  if obra_list  else "qualquer obra"
    lista_etap  = ", ".join(etap_list)  if etap_list  else "qualquer etapa"

    prompt = (
        "Você é um assistente de gestão de obras. Analise TODO o conteúdo abaixo "
        "(texto informado + documentos/imagens anexados) e extraia os dados de UMA ou MAIS despesas.\n"
        "Cada campo deve ser preenchido com precisão. Não coloque em DESCRICAO o que já está em outro campo.\n"
        "ATENÇÃO: FORNECEDOR é empresa/pessoa física que forneceu o serviço/material. "
        "BANCO é a instituição financeira usada para o pagamento (ex: Itaú, Bradesco, Nubank, Caixa). "
        "Nunca coloque banco em FORNECEDOR nem fornecedor em BANCO.\n"
        "Retorne SOMENTE um array JSON válido (mesmo que seja 1 item), sem texto adicional:\n"
        "[\n"
        "  {\n"
        '    "FORNECEDOR": "empresa/pessoa que forneceu o serviço ou material — NÃO coloque banco aqui, ou null",\n'
        '    "BANCO": "instituição financeira do pagamento (ex: Itaú, Nubank) — NÃO coloque fornecedor aqui, ou null",\n'
        '    "OBRA": "nome exato ou mais próximo da lista de obras cadastradas, ou null",\n'
        '    "ETAPA": "nome exato ou mais próximo da lista de etapas cadastradas, ou null",\n'
        '    "VALOR_TOTAL": <número float ou null>,\n'
        '    "DATA": "YYYY-MM-DD ou null",\n'
        '    "DESCRICAO": "breve descrição do serviço/material — NÃO repita obra, etapa, fornecedor aqui",\n'
        '    "TIPO": "Mão de Obra" ou "Materiais" ou "Geral" ou null,\n'
        '    "FORMA": "PIX" ou "Boleto" ou "Cartão" ou "Dinheiro" ou "Transferência" ou null,\n'
        '    "DESPESA": "valor exato da lista de categorias ou null"\n'
        "  }\n"
        "]\n\n"
        f"Fornecedores cadastrados:\n{lista_forn}\n\n"
        f"Obras cadastradas:\n{lista_obras}\n\n"
        f"Etapas cadastradas:\n{lista_etap}\n\n"
        f"Categorias de despesa (use exatamente um desses):\n{lista_cat}"
    )

    client = _get_openai()

    content: list = []
    if texto.strip():
        content.append({"type": "text", "text": f"Texto informado:\n{texto.strip()}\n\n"})

    for f in (files or []):
        file_bytes = await f.read()
        media_type = f.content_type or "image/jpeg"
        if media_type == "application/pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pdf_text = "\n".join(p.extract_text() or "" for p in reader.pages)
            content.append({"type": "text", "text": f"Conteúdo do arquivo {f.filename}:\n{pdf_text}\n\n"})
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}})

    content.append({"type": "text", "text": prompt})

    if not content:
        raise HTTPException(status_code=400, detail="Informe texto ou arquivos")

    try:
        resp = client.chat.completions.create(
            model="gpt-5.4",
            max_completion_tokens=2048,
            messages=[
                {"role": "system", "content": _SYSTEM_EXTRACAO},
                {"role": "user", "content": content},
            ],
        )
        resultado = _parse_json_response(resp.choices[0].message.content)
        if isinstance(resultado, dict):
            resultado = [resultado]
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoint: transcrição de áudio (Whisper)
# ---------------------------------------------------------------------------

@router.post("/transcrever")
async def transcrever_audio(file: UploadFile = File(...)):
    """Transcreve áudio usando Whisper."""
    file_bytes = await file.read()
    filename   = file.filename or "audio.webm"
    media_type = file.content_type or "audio/webm"
    logger.info("transcrever: arquivo='%s' size=%d bytes", filename, len(file_bytes))
    client = _get_openai()
    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, file_bytes, media_type),
            language="pt",
        )
        logger.info("transcrever: concluído %d chars", len(transcript.text))
        return {"texto": transcript.text}
    except Exception as e:
        logger.error("transcrever: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoint: chat de revisão de despesas extraídas
# ---------------------------------------------------------------------------

@router.post("/chat-despesas")
async def chat_despesas(payload: dict):
    """Chat contextual para revisar e corrigir despesas extraídas por IA."""
    messages_hist = payload.get("messages", [])
    despesas      = payload.get("despesas", [])
    contexto      = payload.get("contexto", "")

    _CHAT_SYSTEM = (
        "Você é um assistente especializado em revisar despesas de construção civil extraídas por IA. "
        "O usuário pode pedir explicações sobre o raciocínio da extração ou solicitar correções na tabela.\n\n"
        "Responda SEMPRE em JSON válido, sem texto fora do JSON, no formato:\n"
        '{"mensagem": "sua resposta em texto para o usuário", "despesas": null}\n\n'
        "Se o usuário pedir qualquer alteração nas despesas (corrigir, juntar, separar, remover, adicionar), "
        "retorne o array COMPLETO e atualizado no campo despesas:\n"
        '{"mensagem": "explique o que foi alterado", "despesas": [...]}\n\n'
        "Campos de cada despesa: FORNECEDOR, DESCRICAO, TIPO, ETAPA, DESPESA, VALOR_TOTAL (float), DATA (YYYY-MM-DD), FORMA, OBRA.\n"
        "Mantenha os campos não alterados exatamente como estão. Nunca invente valores."
    )

    context_block = (
        f"=== TEXTO/DOCUMENTO ORIGINAL ===\n{contexto}\n\n"
        f"=== DESPESAS ATUALMENTE NA TABELA ===\n{json.dumps(despesas, ensure_ascii=False, indent=2)}"
    )

    full_messages = [
        {"role": "system",    "content": _CHAT_SYSTEM},
        {"role": "user",      "content": context_block},
        {"role": "assistant", "content": '{"mensagem": "Entendido. Estou pronto para ajudar a revisar essas despesas.", "despesas": null}'},
        *messages_hist,
    ]

    client = _get_openai()
    try:
        resp = client.chat.completions.create(
            model="gpt-5.4",
            max_completion_tokens=2000,
            messages=full_messages,
        )
        return _parse_json_response(resp.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoint: extrair PIX (beneficiário + valor)
# ---------------------------------------------------------------------------

@router.post("/extrair-pix")
async def extrair_pix(file: UploadFile = File(...)):
    """Extrai nome do beneficiário e valor de um comprovante PIX."""
    file_bytes = await file.read()
    media_type = file.content_type or "image/jpeg"

    client = _get_openai()
    prompt = (
        "Analise este comprovante de pagamento PIX. "
        "Retorne SOMENTE JSON com exatamente dois campos:\n"
        '{"nome": "nome completo do beneficiário", "valor": "valor numérico ex: 150.00"}\n'
        "Se não encontrar, use null."
    )

    try:
        if media_type == "application/pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            texto = "\n".join(p.extract_text() or "" for p in reader.pages)
            messages = [
                {"role": "system", "content": _SYSTEM_EXTRACAO},
                {"role": "user", "content": f"{prompt}\n\nTexto:\n{texto}"},
            ]
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            messages = [
                {"role": "system", "content": _SYSTEM_EXTRACAO},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ]},
            ]

        resp = client.chat.completions.create(model="gpt-5.4", max_completion_tokens=100, messages=messages)
        return _parse_json_response(resp.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoint: chat assistente geral (acesso ao banco)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Endpoint: sincronização manual de embeddings
# ---------------------------------------------------------------------------

@router.post("/embeddings/sync")
async def embeddings_sync():
    """Gera embeddings para todas as despesas que ainda não possuem um."""
    try:
        from api.embeddings import sync_embeddings
        total = await asyncio.to_thread(sync_embeddings)
        return {"ok": True, "embedados": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Tool definitions e executores para o chat assistente
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
]


def _exec_buscar_despesas(db, fornecedor=None, obra=None, etapa=None, categoria=None, data_inicio=None, data_fim=None):
    # Busca valores reais de fornecedor/obra existentes no banco para fuzzy match
    existentes = db.table("c_despesas").select("fornecedor, obra").execute().data or []
    fornecs_reais = list({r.get("fornecedor") for r in existentes if r.get("fornecedor")})
    obras_reais   = list({r.get("obra")       for r in existentes if r.get("obra")})

    q = db.table("c_despesas").select("obra, etapa, fornecedor, despesa, tipo, data, valor_total, descricao")
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
        f"[{r.get('data','')}] obra={r.get('obra','N/D')} | etapa={r.get('etapa','N/D')} | "
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
    obras  = [r["nome"] for r in (db.table("obras").select("nome").execute().data or [])]
    etapas = [r["nome"] for r in (db.table("etapas").select("nome").execute().data or [])]
    fornecs = [r["nome"] for r in (db.table("fornecedores").select("nome").execute().data or [])]
    cats   = [r["nome"] for r in (db.table("categorias_despesa").select("nome").execute().data or [])]
    return {"obras": obras, "etapas": etapas, "fornecedores": fornecs, "categorias": cats}


# ---------------------------------------------------------------------------
# Endpoint: chat assistente geral — tool calling + reasoning effort
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat_assistente(payload: dict):
    """
    Assistente de IA com tool calling + reasoning effort high.
    O modelo decide quais queries executar — nunca erra por falta de dados.
    """
    mensagem      = (payload.get("mensagem") or "").strip()
    historico     = payload.get("historico") or []
    obra_contexto = payload.get("obra") or None
    pagina        = payload.get("pagina") or "dashboard"

    if not mensagem:
        raise HTTPException(status_code=400, detail="Campo 'mensagem' obrigatório")

    logger.info("chat: mensagem='%.80s' obra='%s' pagina='%s'", mensagem, obra_contexto, pagina)

    try:
        db = _get_supabase()
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Erro no banco: {type(err).__name__}: {str(err)}")

    _SYSTEM = (
        "Você é o assistente financeiro do sistema Industrial Architect Finance Suite, "
        "especializado em gestão de obras de construção civil brasileira.\n\n"
        "REGRAS:\n"
        "1. Para qualquer pergunta sobre despesas específicas (por fornecedor, obra, período ou categoria), "
        "   chame 'buscar_despesas'. NUNCA afirme que não há dados sem antes buscar.\n"
        "2. Para totais e resumos financeiros, chame 'buscar_totais'.\n"
        "3. Nomes com variação de acento são aceitos ('antonio luiz' encontra 'Antônio Luiz ...').\n"
        "4. Seja objetivo. Sem introduções, sem frases de cortesia. Vá direto ao dado.\n"
        "5. Formate valores como 'R$ 1.234,56'.\n"
        "6. Para cadastrar despesa: retorne JSON {\"acao\": \"cadastrar_despesa\", \"mensagem\": \"...\", \"despesa\": {\"FORNECEDOR\": ..., \"DESCRICAO\": ..., \"VALOR_TOTAL\": ..., \"DATA\": \"YYYY-MM-DD\", \"OBRA\": ..., \"ETAPA\": ..., \"TIPO\": ..., \"DESPESA\": ..., \"FORMA\": ..., \"BANCO\": ...}}. Inclua BANCO sempre que o usuário mencionar banco, conta ou instituição financeira.\n"
        f"7. Página atual: {pagina}." + (f" Obra selecionada: {obra_contexto}." if obra_contexto else "")
    )

    messages: list = [
        {"role": "system", "content": _SYSTEM},
        *historico,
        {"role": "user", "content": mensagem},
    ]

    client = _get_openai()

    try:
        # Tool calling loop — até 5 rodadas
        for _ in range(5):
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-5.4",
                max_completion_tokens=2000,
                tools=_TOOLS,
                tool_choice="auto",
                messages=messages,
            )
            choice = resp.choices[0]

            if choice.finish_reason == "tool_calls":
                # Adiciona resposta do assistente com as tool_calls
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

                # Executa cada ferramenta e devolve o resultado
                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    logger.debug("chat: tool_call '%s' args=%s", tc.function.name, args)
                    if tc.function.name == "buscar_despesas":
                        result = _exec_buscar_despesas(db, **args)
                    elif tc.function.name == "buscar_totais":
                        result = _exec_buscar_totais(db, **args)
                    elif tc.function.name == "listar_referencias":
                        result = _exec_listar_referencias(db)
                    else:
                        result = {"error": "ferramenta desconhecida"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
            else:
                # Resposta final
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
        raise HTTPException(status_code=500, detail=str(e))
