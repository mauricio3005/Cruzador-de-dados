import base64
import io
import json
import os

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()

_OPCOES_DESPESA = (
    "AREIA COLCHÃO, BLOCO INTERTRAVADO, CALCETEIRO, ESTACAS, MEIO-FIO, PARALELEPÍPEDO, "
    "PEDRA CORTADA, PÓ DE PEDRA, SOLO-BRITA, AÇO / VERGALHÃO, ADITIVOS, AREIA LAVADA, "
    "ARGAMASSA, BLOCO CERÂMICO, BLOCO DE CIMENTO, BRITA GRAVILHÃO, CIMENTO, COMBOGÓ, "
    "FERRO, MADERITE, PREGO, TÁBUA, BLOCO CALHA, MADEIRA P/ TELHADO, TELHA CERÂMICA, "
    "TELHA FIBROCIMENTO, BOMBA, CABOS, CAIXA D'ÁGUA, DISJUNTORES, ELETRODUTO E CONEXÕES, "
    "EMPREITEIRO ELETRICISTA, EMPREITEIRO ENCANADOR, TUBO ÁGUA E CONEXÕES, "
    "TUBO ESGOTO E CONEXÕES, ESQUADRIA DE FERRO, ESQUADRIA DE MADEIRA, GESSO ACARTONADO, "
    "LOUÇAS, LUMINÁRIAS, SOLDA, COMPRA EQUIPAMENTOS, DIVERSOS, EMPREITEIRO, ENTULHO, "
    "EQUIPAMENTOS URBANOS, FARDAS E EPIS, LOCAÇÃO EQUIPAMENTOS, MADEIRA LOCAÇÃO OBRA, "
    "MADEIRA TRATADA, PAISAGISMO, PROJETOS, ÁGUA, ALUGUEL, CONDOMÍNIO, CONTABILIDADE, "
    "ENERGIA, IMPRESSÃO / GRÁFICA, INTERNET / TI, MANUTENÇÃO, MATERIAL PARA ESCRITÓRIO, "
    "TELEFONIA FIXA, TELEFONIA MÓVEL, ALIMENTAÇÃO, COMBUSTÍVEL, DIÁRIA, "
    "FERRYBOAT / BALSA, HOSPEDAGEM, PEDÁGIO, SALÁRIO PESSOAL, TRANSPORTE, "
    "IMPOSTOS, JUROS, RECEITA, REPOSIÇÃO DE CAIXA"
)


_SYSTEM_MSG = (
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


def _get_openai():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY não configurada")
    return OpenAI(api_key=api_key)


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


@router.post("/extrair")
async def extrair_nota(file: UploadFile = File(...)):
    """Extrai dados de uma nota fiscal ou comprovante usando GPT-4 Vision."""
    file_bytes = await file.read()
    media_type = file.content_type or "image/jpeg"

    client = _get_openai()
    prompt = (
        "Analise o documento anexado — pode ser uma nota fiscal ou comprovante de pagamento.\n\n"
        "REGRA: Se for comprovante de pagamento (PIX, recibo, transferência), preencha APENAS "
        "VALOR_TOTAL, DATA e FORMA. Deixe os demais como null.\n\n"
        "Se for nota fiscal completa, extraia todos os campos.\n\n"
        "Retorne SOMENTE JSON válido, sem texto adicional:\n"
        "{\n"
        '  "FORNECEDOR": "nome do fornecedor (null se comprovante)",\n'
        '  "VALOR_TOTAL": <float obrigatório>,\n'
        '  "DATA": "YYYY-MM-DD",\n'
        '  "DESCRICAO": "descrição do serviço/material (null se comprovante)",\n'
        '  "TIPO": "Mão de Obra" ou "Materiais" ou "Geral" (null se comprovante),\n'
        '  "FORMA": "PIX" ou "Boleto" ou "Cartão" ou "Dinheiro" ou "Transferência" ou "",\n'
        f'  "DESPESA": escolha da lista [{_OPCOES_DESPESA}] ou null\n'
        "}"
    )

    try:
        if media_type == "application/pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            texto = "\n".join(p.extract_text() or "" for p in reader.pages)
            messages = [
                {"role": "system", "content": _SYSTEM_MSG},
                {"role": "user", "content": f"{prompt}\n\nConteúdo:\n{texto}"},
            ]
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            messages = [
                {"role": "system", "content": _SYSTEM_MSG},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ]},
            ]

        resp = client.chat.completions.create(model="gpt-5.4", max_completion_tokens=1024, messages=messages)
        return _parse_json_response(resp.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extrair-texto")
async def extrair_texto(payload: dict):
    """Extrai uma ou mais despesas a partir de texto livre, com matching de fornecedor e categoria."""
    texto = (payload.get("texto") or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Campo 'texto' obrigatório")

    fornecedores = payload.get("fornecedores") or []
    categorias   = payload.get("categorias")   or []
    obras        = payload.get("obras")        or []
    etapas       = payload.get("etapas")       or []

    lista_forn  = ", ".join(fornecedores) if fornecedores else "qualquer nome"
    lista_cat   = ", ".join(categorias)   if categorias   else _OPCOES_DESPESA
    lista_obras = ", ".join(obras)        if obras        else "qualquer obra"
    lista_etap  = ", ".join(etapas)       if etapas       else "qualquer etapa"

    client = _get_openai()
    prompt = (
        "Você é um assistente de gestão de obras. Analise o texto abaixo e extraia os dados de UMA ou MAIS despesas.\n"
        "Cada campo deve ser preenchido com precisão. Não coloque em DESCRICAO o que já está em outro campo.\n"
        "Retorne SOMENTE um array JSON válido (mesmo que seja 1 item), sem texto adicional:\n"
        "[\n"
        "  {\n"
        '    "FORNECEDOR": "nome exato ou mais próximo da lista de fornecedores cadastrados, ou null",\n'
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
                {"role": "system", "content": _SYSTEM_MSG},
                {"role": "user", "content": prompt},
            ],
        )
        resultado = _parse_json_response(resp.choices[0].message.content)
        # Garante que sempre retorna lista
        if isinstance(resultado, dict):
            resultado = [resultado]
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extrair-texto-misto")
async def extrair_texto_misto(
    texto: str = Form(""),
    files: Optional[List[UploadFile]] = File(default=None),
    fornecedores: str = Form("[]"),
    categorias: str = Form("[]"),
    obras: str = Form("[]"),
    etapas: str = Form("[]"),
):
    """Extrai despesas combinando texto livre + imagens/PDFs de NFs em uma única chamada."""
    forn_list  = json.loads(fornecedores) if fornecedores else []
    cat_list   = json.loads(categorias)  if categorias  else []
    obra_list  = json.loads(obras)       if obras       else []
    etap_list  = json.loads(etapas)      if etapas      else []

    lista_forn  = ", ".join(forn_list)  if forn_list  else "qualquer nome"
    lista_cat   = ", ".join(cat_list)   if cat_list   else _OPCOES_DESPESA
    lista_obras = ", ".join(obra_list)  if obra_list  else "qualquer obra"
    lista_etap  = ", ".join(etap_list)  if etap_list  else "qualquer etapa"

    prompt = (
        "Você é um assistente de gestão de obras. Analise TODO o conteúdo abaixo "
        "(texto informado + documentos/imagens anexados) e extraia os dados de UMA ou MAIS despesas.\n"
        "Cada campo deve ser preenchido com precisão. Não coloque em DESCRICAO o que já está em outro campo.\n"
        "Retorne SOMENTE um array JSON válido (mesmo que seja 1 item), sem texto adicional:\n"
        "[\n"
        "  {\n"
        '    "FORNECEDOR": "nome exato ou mais próximo da lista de fornecedores cadastrados, ou null",\n'
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

    # Monta conteúdo multimodal: texto + arquivos
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
                {"role": "system", "content": _SYSTEM_MSG},
                {"role": "user", "content": content},
            ],
        )
        resultado = _parse_json_response(resp.choices[0].message.content)
        if isinstance(resultado, dict):
            resultado = [resultado]
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcrever")
async def transcrever_audio(file: UploadFile = File(...)):
    """Transcreve áudio usando Whisper."""
    file_bytes = await file.read()
    filename   = file.filename or "audio.webm"
    media_type = file.content_type or "audio/webm"
    client = _get_openai()
    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, file_bytes, media_type),
            language="pt",
        )
        return {"texto": transcript.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat-despesas")
async def chat_despesas(payload: dict):
    """Chat contextual para revisar e corrigir despesas extraídas por IA."""
    messages_hist = payload.get("messages", [])      # histórico [{role, content}]
    despesas      = payload.get("despesas", [])       # estado atual da tabela
    contexto      = payload.get("contexto", "")       # texto original da extração

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
                {"role": "system", "content": _SYSTEM_MSG},
                {"role": "user", "content": f"{prompt}\n\nTexto:\n{texto}"},
            ]
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            messages = [
                {"role": "system", "content": _SYSTEM_MSG},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ]},
            ]

        resp = client.chat.completions.create(model="gpt-5.4", max_completion_tokens=100, messages=messages)
        return _parse_json_response(resp.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
