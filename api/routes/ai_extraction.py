"""Endpoints de extração de IA: NF, texto, PIX, transcrição, chat-despesas, embeddings."""

import asyncio
import base64
import datetime
import io
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.config import OPENAI_CHAT_MODEL, OPENAI_WHISPER_MODEL
from api.dependencies import get_current_user
from api.logger import get_logger

from .ai_helpers import (
    ALLOWED_CONTENT_TYPES,
    MAX_UPLOAD_SIZE,
    _get_openai,
    _get_referencias,
    _get_system_extracao,
    _normalizar_fornecedor,
    _parse_json_response,
)

router = APIRouter()
logger = get_logger(__name__)


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
        system_extracao = _get_system_extracao()
        if media_type == "application/pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            texto = "\n".join(p.extract_text() or "" for p in reader.pages)
            messages = [
                {"role": "system", "content": system_extracao},
                {"role": "user", "content": f"{prompt}\n\nConteúdo:\n{texto}"},
            ]
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            messages = [
                {"role": "system", "content": system_extracao},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ]},
            ]

        resp = client.chat.completions.create(model=OPENAI_CHAT_MODEL, max_completion_tokens=1024, messages=messages)
        result = _parse_json_response(resp.choices[0].message.content)
        # Post-processing: garante que FORNECEDOR seja da lista cadastrada
        if isinstance(result, list):
            for item in result:
                item["FORNECEDOR"] = _normalizar_fornecedor(item.get("FORNECEDOR"), forn_list)
        elif isinstance(result, dict):
            result["FORNECEDOR"] = _normalizar_fornecedor(result.get("FORNECEDOR"), forn_list)
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
                {"role": "system", "content": _get_system_extracao()},
                {"role": "user", "content": prompt},
            ],
        )
        resultado = _parse_json_response(resp.choices[0].message.content)
        if isinstance(resultado, dict):
            resultado = [resultado]
        # Post-processing: garante que FORNECEDOR seja da lista cadastrada
        for item in resultado:
            item["FORNECEDOR"] = _normalizar_fornecedor(item.get("FORNECEDOR"), forn_list)
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
                {"role": "system", "content": _get_system_extracao()},
                {"role": "user", "content": content},
            ],
        )
        resultado = _parse_json_response(resp.choices[0].message.content)
        if isinstance(resultado, dict):
            resultado = [resultado]
        # Post-processing: garante que FORNECEDOR seja da lista cadastrada
        for item in resultado:
            item["FORNECEDOR"] = _normalizar_fornecedor(item.get("FORNECEDOR"), forn_list)
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
    ref_etapas    = payload.get("etapas", [])
    ref_obras     = payload.get("obras", [])
    ref_fornecs   = payload.get("fornecedores", [])

    hoje = datetime.date.today()
    chat_system = (
        f"Data de hoje: {hoje.isoformat()} (ano {hoje.year}).\n\n"
        "Você é o Jarvis, assistente especializado em revisar despesas de construção civil extraídas por IA. "
        "O usuário pode pedir explicações sobre o raciocínio da extração ou solicitar correções na tabela.\n\n"
        "Responda SEMPRE em JSON válido, sem texto fora do JSON, no formato:\n"
        '{"mensagem": "sua resposta em texto para o usuário", "despesas": null}\n\n'
        "Se o usuário pedir qualquer alteração nas despesas (corrigir, juntar, separar, remover, adicionar), "
        "retorne o array COMPLETO e atualizado no campo despesas:\n"
        '{"mensagem": "explique o que foi alterado", "despesas": [...]}\n\n'
        "Campos de cada despesa: FORNECEDOR, DESCRICAO, TIPO, ETAPA, DESPESA, VALOR_TOTAL (float), DATA (YYYY-MM-DD), FORMA, OBRA.\n"
        "Mantenha os campos não alterados exatamente como estão. Nunca invente valores.\n"
        "Ao alterar ETAPA ou OBRA, use apenas valores da lista de referência abaixo.\n"
        "Ao alterar FORNECEDOR, use apenas nomes da lista de fornecedores cadastrados — nunca invente um novo."
    )
    if ref_etapas:
        chat_system += f"\n\nEtapas válidas: {', '.join(ref_etapas)}"
    if ref_obras:
        chat_system += f"\nObras válidas: {', '.join(ref_obras)}"
    if ref_fornecs:
        chat_system += f"\nFornecedores cadastrados: {', '.join(ref_fornecs)}"

    context_block = (
        f"=== TEXTO/DOCUMENTO ORIGINAL ===\n{contexto}\n\n"
        f"=== DESPESAS ATUALMENTE NA TABELA ===\n{json.dumps(despesas, ensure_ascii=False, indent=2)}"
    )

    full_messages = [
        {"role": "system",    "content": chat_system},
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
        system_pix = _get_system_extracao()
        if media_type == "application/pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            texto = "\n".join(p.extract_text() or "" for p in reader.pages)
            messages = [
                {"role": "system", "content": system_pix},
                {"role": "user", "content": f"{prompt}\n\nTexto:\n{texto}"},
            ]
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            messages = [
                {"role": "system", "content": system_pix},
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
