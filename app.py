from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd
import io

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
        expenses_agg = df_despesas.groupby(['OBRA', 'ETAPA'])['VALOR TOTAL'].sum().reset_index()
        expenses_agg.rename(columns={'VALOR TOTAL': 'GASTO_REALIZADO'}, inplace=True)

        df_recebimentos = pd.read_excel(arquivo_virtual, sheet_name="C Recebimentos")
        df_recebimentos['VALOR'] = pd.to_numeric(df_recebimentos['VALOR'], errors='coerce').fillna(0)
        receipts_agg = df_recebimentos.groupby('OBRA')['VALOR'].sum().reset_index()
        receipts_agg.rename(columns={'VALOR': 'RECEBIMENTOS_TOTAIS'}, inplace=True)

        full_report = pd.merge(df_budget, expenses_agg, on=['OBRA', 'ETAPA'], how='outer')
        full_report[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO']] = full_report[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO']].fillna(0)
        full_report['SALDO_ETAPA'] = full_report['ORÇAMENTO_ESTIMADO'] - full_report['GASTO_REALIZADO']

        full_report = pd.merge(full_report, receipts_agg, on='OBRA', how='left')
        full_report['RECEBIMENTOS_TOTAIS'] = full_report['RECEBIMENTOS_TOTAIS'].fillna(0)
        full_report['GASTO_TOTAL_OBRA'] = full_report.groupby('OBRA')['GASTO_REALIZADO'].transform('sum')
        full_report['SALDO_GLOBAL_OBRA'] = full_report['RECEBIMENTOS_TOTAIS'] - full_report['GASTO_TOTAL_OBRA']

        cols = ['OBRA', 'ETAPA', 'ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA', 'RECEBIMENTOS_TOTAIS', 'SALDO_GLOBAL_OBRA']
        full_report = full_report[cols].sort_values(by=['OBRA', 'ETAPA'])

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
        raise HTTPException(status_code=500, detail=f"Erro ao processar arquivo: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
