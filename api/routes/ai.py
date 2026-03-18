import base64
import io
import json
import os

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
            messages = [{"role": "user", "content": f"{prompt}\n\nConteúdo:\n{texto}"}]
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            messages = [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ]}]

        resp = client.chat.completions.create(model="gpt-4.1-mini", max_tokens=1024, messages=messages)
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
            messages = [{"role": "user", "content": f"{prompt}\n\nTexto:\n{texto}"}]
        else:
            b64 = base64.standard_b64encode(file_bytes).decode()
            messages = [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ]}]

        resp = client.chat.completions.create(model="gpt-4.1-mini", max_tokens=100, messages=messages)
        return _parse_json_response(resp.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
