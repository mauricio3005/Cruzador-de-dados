from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd
import io
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Variáveis de ambiente do Supabase não configuradas no .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# Nome da tabela no Supabase que será sobreescrita. 
# Importante: Como não sei o nome da tabela que você criou, coloquei 'relatorios'. 
# Lembre-se de mudar aqui caso o nome seja diferente lá no Supabase.
TABELA_SUPABASE = "relatorios"

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "API de Relatórios de Obra está Online"}

@app.post("/gerar-relatorio")
async def gerar_relatorio(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        arquivo_virtual = io.BytesIO(contents)

        
        try:
            df_etapas = pd.read_excel(arquivo_virtual, sheet_name="Etapas", header=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Aba 'Etapas' não encontrada no Excel.")
            
        df_etapas.columns = df_etapas.columns.str.strip()

        creche_budget = df_etapas[['Nome da Etapa', 'TOTAL ESTIMADO']].copy()
        creche_budget['OBRA'] = 'Creche apuarema'
        creche_budget.rename(columns={'TOTAL ESTIMADO': 'ORÇAMENTO_ESTIMADO', 'Nome da Etapa': 'ETAPA'}, inplace=True)

        casa_budget = df_etapas[['Nome da Etapa', 'ESTIMATIVA']].copy()
        casa_budget['OBRA'] = 'Casa Busca Vida'
        casa_budget.rename(columns={'ESTIMATIVA': 'ORÇAMENTO_ESTIMADO', 'Nome da Etapa': 'ETAPA'}, inplace=True)

        df_budget = pd.concat([creche_budget, casa_budget], ignore_index=True)
        df_budget['ORÇAMENTO_ESTIMADO'] = pd.to_numeric(df_budget['ORÇAMENTO_ESTIMADO'], errors='coerce').fillna(0)
        df_budget.dropna(subset=['ETAPA'], inplace=True)

        df_despesas = pd.read_excel(arquivo_virtual, sheet_name="C Despesas")
        df_despesas['VALOR TOTAL'] = pd.to_numeric(df_despesas['VALOR TOTAL'], errors='coerce').fillna(0)
        
        # Obter o nome da coluna que contém 'tipo' para mapear como TIPO
        colunas_tipo = [c for c in df_despesas.columns if 'tipo' in str(c).lower()]
        nome_coluna_tipo = colunas_tipo[0] if colunas_tipo else None
        
        if nome_coluna_tipo:
            df_despesas.rename(columns={nome_coluna_tipo: 'TIPO'}, inplace=True)
        else:
            df_despesas['TIPO'] = 'Geral'

        expenses_agg = df_despesas.groupby(['OBRA', 'ETAPA', 'TIPO'])['VALOR TOTAL'].sum().reset_index()
        expenses_agg.rename(columns={'VALOR TOTAL': 'GASTO_REALIZADO', 'TIPO': 'TIPO_CUSTO'}, inplace=True)

        full_report = pd.merge(df_budget, expenses_agg, on=['OBRA', 'ETAPA'], how='outer')
        full_report[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO']] = full_report[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO']].fillna(0)
        full_report['TIPO_CUSTO'] = full_report['TIPO_CUSTO'].fillna('Geral')
        
        # Evitar duplicar orçamento se houver vários TIPOS_CUSTO para a mesma ETAPA
        full_report = full_report.sort_values(by=['OBRA', 'ETAPA', 'TIPO_CUSTO'])
        mask_duplicados = full_report.duplicated(subset=['OBRA', 'ETAPA'], keep='first')
        full_report.loc[mask_duplicados, 'ORÇAMENTO_ESTIMADO'] = 0
        
        full_report['SALDO_ETAPA'] = full_report['ORÇAMENTO_ESTIMADO'] - full_report['GASTO_REALIZADO']

        cols = ['OBRA', 'ETAPA', 'TIPO_CUSTO', 'ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']
        full_report = full_report[cols]
        
        # ------------------- INTEGRAÇÃO SUPABASE -------------------
        # Convertemos o DataFrame para uma lista de dicionários para inserir no Supabase
        dados_para_inserir = full_report.to_dict(orient="records")

        # 1. Apagar todos os dados antigos da tabela.
        # A API do Supabase requer um filtro para deletar.
        # 'neq' (not equal) com um valor que nunca existirá garante que todas as linhas sejam deletadas.
        supabase.table(TABELA_SUPABASE).delete().neq("OBRA", "VALOR_INEXISTENTE_PARA_DELETAR_TUDO").execute()

        # 2. Inserir os novos dados
        if dados_para_inserir:
             supabase.table(TABELA_SUPABASE).insert(dados_para_inserir).execute()
        # -----------------------------------------------------------

        output_buffer = io.BytesIO()
        with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
            full_report.to_excel(writer, index=False)
        output_buffer.seek(0)

        return StreamingResponse(
            output_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=Relatorio_Completo.xlsx"}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao processar arquivo: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
