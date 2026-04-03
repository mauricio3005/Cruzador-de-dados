import asyncio
import base64
import io
import json
import os
import time
import unicodedata
from functools import lru_cache
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from api.config import OPENAI_CHAT_MODEL, OPENAI_MINI_MODEL, OPENAI_WHISPER_MODEL
from api.dependencies import get_current_user
from api.supabase_client import get_supabase as _get_supabase
from api.logger import get_logger

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}

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
def referencias(_user=Depends(get_current_user)):
    """Retorna obras, etapas, fornecedores e categorias do banco de dados."""
    try:
        return _get_referencias()
    except Exception as e:
        logger.error("referencias: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ---------------------------------------------------------------------------
# Endpoint: extrair NF individual (imagem / PDF)
# ---------------------------------------------------------------------------

@router.post("/extrair")
async def extrair_nota(
    file: UploadFile = File(...),
    fornecedores: str = Form("[]"),
    obras: str        = Form("[]"),
    etapas: str       = Form("[]"),
    categorias: str   = Form("[]"),
    _user=Depends(get_current_user),
):
    """Extrai dados de uma nota fiscal ou comprovante usando GPT-4 Vision."""
    logger.info("extrair_nota: arquivo='%s' tipo='%s'", file.filename, file.content_type)
    file_bytes = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Arquivo maior que 20 MB")
    media_type = file.content_type or "image/jpeg"
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Tipo de arquivo não permitido: {media_type}")

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

        resp = client.chat.completions.create(model=OPENAI_CHAT_MODEL, max_completion_tokens=1024, messages=messages)
        result = _parse_json_response(resp.choices[0].message.content)
        logger.info("extrair_nota: concluído tokens=%s", resp.usage.total_tokens if resp.usage else "?")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("extrair_nota: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ---------------------------------------------------------------------------
# Endpoint: extrair por texto livre
# ---------------------------------------------------------------------------

@router.post("/extrair-texto")
async def extrair_texto(payload: dict, _user=Depends(get_current_user)):
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
            model=OPENAI_CHAT_MODEL,
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
        logger.error("extrair_texto: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


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
    _user=Depends(get_current_user),
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
            model=OPENAI_CHAT_MODEL,
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
        logger.error("extrair_texto_misto: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ---------------------------------------------------------------------------
# Endpoint: transcrição de áudio (Whisper)
# ---------------------------------------------------------------------------

@router.post("/transcrever")
async def transcrever_audio(file: UploadFile = File(...), _user=Depends(get_current_user)):
    """Transcreve áudio usando Whisper."""
    file_bytes = await file.read()
    filename   = file.filename or "audio.webm"
    media_type = file.content_type or "audio/webm"
    logger.info("transcrever: arquivo='%s' size=%d bytes", filename, len(file_bytes))
    client = _get_openai()
    try:
        transcript = client.audio.transcriptions.create(
            model=OPENAI_WHISPER_MODEL,
            file=(filename, file_bytes, media_type),
            language="pt",
        )
        logger.info("transcrever: concluído %d chars", len(transcript.text))
        return {"texto": transcript.text}
    except Exception as e:
        logger.error("transcrever: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ---------------------------------------------------------------------------
# Endpoint: chat de revisão de despesas extraídas
# ---------------------------------------------------------------------------

@router.post("/chat-despesas")
async def chat_despesas(payload: dict, _user=Depends(get_current_user)):
    """Chat contextual para revisar e corrigir despesas extraídas por IA."""
    messages_hist = payload.get("messages", [])
    despesas      = payload.get("despesas", [])
    contexto      = payload.get("contexto", "")

    _CHAT_SYSTEM = (
        "Você é o Jarvis, assistente especializado em revisar despesas de construção civil extraídas por IA. "
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
            model=OPENAI_CHAT_MODEL,
            max_completion_tokens=2000,
            messages=full_messages,
        )
        return _parse_json_response(resp.choices[0].message.content)
    except Exception as e:
        logger.error("chat_despesas: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ---------------------------------------------------------------------------
# Endpoint: extrair PIX (beneficiário + valor)
# ---------------------------------------------------------------------------

@router.post("/extrair-pix")
async def extrair_pix(file: UploadFile = File(...), _user=Depends(get_current_user)):
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

        resp = client.chat.completions.create(model=OPENAI_CHAT_MODEL, max_completion_tokens=100, messages=messages)
        return _parse_json_response(resp.choices[0].message.content)
    except Exception as e:
        logger.error("extrair_pix: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ---------------------------------------------------------------------------
# Endpoint: chat assistente geral (acesso ao banco)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Endpoint: sincronização manual de embeddings
# ---------------------------------------------------------------------------

@router.post("/embeddings/sync")
async def embeddings_sync(_user=Depends(get_current_user)):
    """Gera embeddings para todas as despesas que ainda não possuem um."""
    try:
        from api.embeddings import sync_embeddings
        total = await asyncio.to_thread(sync_embeddings)
        return {"ok": True, "embedados": total}
    except Exception as e:
        logger.error("embeddings_sync: erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


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
            "description": "Planeja criação de uma conta a pagar.",
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
            "description": "Planeja edição de uma conta a pagar existente.",
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
            "description": "Planeja edição de MÚLTIPLAS contas a pagar aplicando os mesmos campos a todas. Forneça pelo menos um campo além de ids.",
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
            "description": "Planeja marcação de uma conta a pagar como paga.",
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
                "Retorna o saldo disponível de cada conta controlada (Kathleen, Diego, etc.) — "
                "remessas recebidas menos despesas lançadas naquela conta. "
                "A conta Maurício é a origem principal e não aparece nos saldos. "
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
                "Planeja o registro de uma nova remessa de caixa (valor enviado de Maurício para uma conta controlada). "
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


def _exec_buscar_despesas(db, fornecedor=None, obra=None, etapa=None, categoria=None, data_inicio=None, data_fim=None):
    # Busca valores reais de fornecedor/obra existentes no banco para fuzzy match
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
    obras  = [r["nome"] for r in (db.table("obras").select("nome").execute().data or [])]
    etapas = [r["nome"] for r in (db.table("etapas").select("nome").execute().data or [])]
    fornecs = [r["nome"] for r in (db.table("fornecedores").select("nome").execute().data or [])]
    cats   = [r["nome"] for r in (db.table("categorias_despesa").select("nome").execute().data or [])]
    return {"obras": obras, "etapas": etapas, "fornecedores": fornecs, "categorias": cats}


_CONTA_PRINCIPAL = "Maurício"  # Origem das remessas — não aparece nos saldos controlados


def _exec_buscar_saldo_bancos(db) -> dict:
    remessas_rows = db.table("remessas_caixa").select("banco_destino, valor").execute().data or []
    despesas_rows = db.table("c_despesas").select("banco, valor_total").not_.is_("banco", "null").execute().data or []

    recebido: dict = {}
    for r in remessas_rows:
        recebido[r["banco_destino"]] = recebido.get(r["banco_destino"], 0) + (r["valor"] or 0)

    gasto: dict = {}
    for d in despesas_rows:
        b = d.get("banco")
        if b and b != _CONTA_PRINCIPAL:
            gasto[b] = gasto.get(b, 0) + (d["valor_total"] or 0)

    # Contas controladas = destinatários de remessas + contas com despesas (sem Maurício)
    contas = set(recebido) | set(gasto)
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
    q = db.table("remessas_caixa").select("*")
    if conta:       q = q.ilike("banco_destino", f"%{conta}%")
    if data_inicio: q = q.gte("data", data_inicio)
    if data_fim:    q = q.lte("data", data_fim)
    rows = q.order("data", desc=True).limit(100).execute().data or []
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


def _exec_planejar(db, tool_name: str, args: dict, refs: dict) -> str:
    """Handler unificado para todos os tools planejar_*. Valida, faz fuzzy match e monta payload — não escreve no banco."""
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
        # Extrai campos diretamente de args (sem wrapper "campos")
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
        dados.setdefault("paga", False)
        return json.dumps({"tabela": "contas_a_pagar", "operacao": "inserir", "dados": dados, "antes": None}, ensure_ascii=False)

    elif tool_name == "planejar_editar_conta_a_pagar":
        id_ = args.get("id")
        if not id_:
            return json.dumps({"erro": "id obrigatório"})
        campos = {k: v for k, v in args.items() if k != "id" and v is not None}
        if "obra" in campos: campos["obra"] = fuzzy(campos["obra"], refs["obras"])
        res = db.table("contas_a_pagar").select("*").eq("id", id_).limit(1).execute()
        antes = res.data[0] if res.data else {}
        return json.dumps({"tabela": "contas_a_pagar", "operacao": "atualizar", "id": id_, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_editar_lote_contas_a_pagar":
        ids = args.get("ids", [])
        if not ids:
            return json.dumps({"erro": "ids[] obrigatório"})
        _CAMPOS_CAP = {"descricao", "valor", "vencimento", "obra", "fornecedor"}
        campos = {k: v for k, v in args.items() if k in _CAMPOS_CAP and v is not None}
        if not campos:
            return json.dumps({"erro": "Nenhum campo para alterar foi fornecido. Informe pelo menos um campo além de ids."})
        if "obra" in campos:       campos["obra"]       = fuzzy(campos["obra"], refs["obras"])
        if "fornecedor" in campos: campos["fornecedor"] = fuzzy(campos["fornecedor"], refs["fornecedores"])
        res = db.table("contas_a_pagar").select("id, descricao, valor, vencimento, obra, fornecedor").in_("id", ids).execute()
        antes = res.data or []
        return json.dumps({"tabela": "contas_a_pagar", "operacao": "atualizar_lote", "ids": ids, "dados": campos, "antes": antes}, ensure_ascii=False)

    elif tool_name == "planejar_marcar_conta_paga":
        id_ = args.get("id")
        if not id_:
            return json.dumps({"erro": "id obrigatório"})
        data_pag = args.get("data_pagamento", hoje)
        res = db.table("contas_a_pagar").select("*").eq("id", id_).limit(1).execute()
        antes = res.data[0] if res.data else {}
        return json.dumps({"tabela": "contas_a_pagar", "operacao": "atualizar", "id": id_, "dados": {"paga": True, "data_pagamento": data_pag}, "antes": antes}, ensure_ascii=False)

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
        if destino == _CONTA_PRINCIPAL:
            return json.dumps({"erro": f"'{_CONTA_PRINCIPAL}' é a conta principal e não pode ser o destino"})
        data_r = (args.get("data") or _date.today().isoformat()).strip()
        dados  = {"banco_destino": destino, "valor": valor, "data": data_r}
        if args.get("descricao"): dados["descricao"] = args["descricao"]
        if args.get("obra"):      dados["obra"]      = args["obra"]
        return json.dumps({"tabela": "remessas_caixa", "operacao": "inserir", "dados": dados, "antes": None}, ensure_ascii=False)

    # ── Folha de pagamento ───────────────────────────────────────────────────

    elif tool_name == "planejar_criar_folha":
        obra = (args.get("obra") or "").strip()
        quinzena = (args.get("quinzena") or "").strip()
        if not obra:
            return json.dumps({"erro": "Campo 'obra' obrigatório"})
        if not quinzena:
            return json.dumps({"erro": "Campo 'quinzena' obrigatório (YYYY-MM-DD)"})
        # Valida que a obra existe
        obra_match = fuzzy(obra, refs.get("obras", []))
        obras_existentes = [o["nome"] for o in (db.table("obras").select("nome").execute().data or [])]
        if obra_match not in obras_existentes:
            return json.dumps({"erro": f"Obra '{obra}' não encontrada. Obras disponíveis: {obras_existentes[:10]}"})
        dados = {"obra": obra_match, "quinzena": quinzena, "status": "rascunho"}
        return json.dumps({
            "tabela": "folhas", "operacao": "inserir", "dados": dados,
            "antes": None,
            "depois": dados,
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
        # Valida que a folha existe e está em rascunho
        folha_rows = db.table("folhas").select("id, obra, status").eq("id", folha_id).execute().data
        if not folha_rows:
            return json.dumps({"erro": f"Folha id={folha_id} não encontrada"})
        folha_rec = folha_rows[0]
        if folha_rec["status"] == "fechada":
            return json.dumps({"erro": "Não é possível adicionar funcionários a uma folha fechada"})
        # Calcula valor: valor_fixo tem prioridade sobre cálculo por diárias
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
            "antes": None,
            "depois": dados,
        }, ensure_ascii=False)

    elif tool_name == "planejar_editar_funcionario":
        id_ = args.get("id")
        if not id_:
            return json.dumps({"erro": "Campo 'id' obrigatório"})
        # Valida que o registro existe e a folha não está fechada
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
        # valor_fixo aceita None explícito (reverter para automático) ou número
        if "valor_fixo" in args:
            campos["valor_fixo"] = round(float(args["valor_fixo"]), 2) if args["valor_fixo"] is not None else None
        if not campos:
            return json.dumps({"erro": "Nenhum campo informado para edição"})
        # Recalcula valor efetivo
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
            "antes": antes,
            "depois": campos,
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
            "antes": {"nome": nome_real},
            "depois": None,
        }, ensure_ascii=False)

    return json.dumps({"erro": f"tool '{tool_name}' não reconhecido"})


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

    _SYSTEM = (
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
        "O sistema controla remessas de caixa enviadas pela conta principal (Maurício) para as contas controladas (ex: Kathleen, Diego). "
        "A conta Maurício é apenas a origem — não aparece nos saldos. "
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
                b64 = base64.b64encode(file_bytes).decode()
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
                    _PLANEJAR_TOOLS = {
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
                    elif tc.function.name in _PLANEJAR_TOOLS:
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
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")


# ---------------------------------------------------------------------------
# Endpoint: executar operação confirmada pelo usuário
# ---------------------------------------------------------------------------

_TABELAS_PERMITIDAS = {
    "c_despesas", "recebimentos", "contas_a_pagar", "fornecedores",
    "obras", "etapas", "empresas", "orcamentos", "taxa_conclusao",
    "categorias_despesa", "formas_pagamento", "obra_etapas", "despesas_recorrentes",
    "remessas_caixa", "folhas", "folha_funcionarios",
}
# Tabelas onde a operação 'deletar' é permitida (apenas registros de rascunho/linha)
_TABELAS_DELETAR_PERMITIDAS = {"folha_funcionarios"}
_PK_TEXTO = {"fornecedores", "obras", "etapas", "categorias_despesa", "formas_pagamento"}


@router.post("/executar")
async def executar_operacao(body: dict, _user=Depends(get_current_user)):
    """Executa operação de escrita no banco após confirmação do usuário no frontend."""
    tabela   = body.get("tabela")
    operacao = body.get("operacao")
    dados    = dict(body.get("dados", {}))

    if tabela not in _TABELAS_PERMITIDAS:
        raise HTTPException(400, f"Tabela '{tabela}' não permitida")
    if operacao not in {"inserir", "atualizar", "atualizar_lote", "deletar"}:
        raise HTTPException(400, "Operação inválida")
    if operacao == "deletar" and tabela not in _TABELAS_DELETAR_PERMITIDAS:
        raise HTTPException(400, f"Operação 'deletar' não permitida para '{tabela}'")

    sb = _get_supabase()

    try:
        if operacao == "inserir":
            res = sb.table(tabela).insert(dados).execute()

        elif operacao == "atualizar":
            id_ = body.get("id")
            if not id_:
                raise HTTPException(400, "id obrigatório para atualizar")
            pk  = "nome" if tabela in _PK_TEXTO else "id"
            res = sb.table(tabela).update(dados).eq(pk, id_).execute()

        elif operacao == "atualizar_lote":
            ids = body.get("ids", [])
            if not ids:
                raise HTTPException(400, "ids[] obrigatório para atualizar_lote")
            res = sb.table(tabela).update(dados).in_("id", ids).execute()

        elif operacao == "deletar":
            id_ = body.get("id")
            if not id_:
                raise HTTPException(400, "id obrigatório para deletar")
            res = sb.table(tabela).delete().eq("id", id_).execute()

        afetados = len(res.data) if res.data else 0
        logger.info("[AI-EXEC] %s em %s | afetados=%d | dados=%s", operacao, tabela, afetados, dados)
        return {"sucesso": True, "afetados": afetados}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[AI-EXEC] erro — %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno. Consulte os logs.")
