import pandas as pd
import os
from supabase import create_client, Client
from dotenv import load_dotenv

def processar_planilha():
    load_dotenv()

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Variáveis de ambiente do Supabase não configuradas no .env")

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    TABELA_SUPABASE = "relatorios"

    caminho_planilha = r"C:\Users\mauri\OneDrive\Controle de obra\Controle de obras.xlsx"
    
    if not os.path.exists(caminho_planilha):
        print(f"Erro: Arquivo não encontrado em {caminho_planilha}")
        return

    print(f"Lendo planilha de: {caminho_planilha}")
    try:
        df_etapas = pd.read_excel(caminho_planilha, sheet_name="Etapas", header=1)
    except ValueError:
        print("Aba 'Etapas' não encontrada no Excel.")
        return
        
    df_etapas.columns = df_etapas.columns.str.strip()
    df_etapas.dropna(subset=['Nome da Etapa'], inplace=True)

    # ── Orçamento por tipo, direto da planilha ────────────────────────────────
    # Cada etapa gera 2 linhas de orçamento (Mão de Obra e Materiais) por obra.
    # O merge com despesas é feito em OBRA + ETAPA + TIPO_CUSTO — sem deduplicação.
    budget_rows = []
    for _, row in df_etapas.iterrows():
        etapa = str(row['Nome da Etapa']).strip()
        for obra, col_mo, col_mat in [
            ('Creche apuarema',   'ESTIM MÃO DE OBRA APUA', 'ESTIM MATERIAL APUA'),
            ('Creche Teoflandia', 'ESTIM MÃO DE OBRA TEOF', 'ESTIM MATERIAL TEOF'),
        ]:
            budget_rows.append({'OBRA': obra, 'ETAPA': etapa,
                                 'TIPO_CUSTO': 'Mão de Obra',
                                 'ORÇAMENTO_ESTIMADO': pd.to_numeric(row.get(col_mo, 0), errors='coerce') or 0})
            budget_rows.append({'OBRA': obra, 'ETAPA': etapa,
                                 'TIPO_CUSTO': 'Materiais',
                                 'ORÇAMENTO_ESTIMADO': pd.to_numeric(row.get(col_mat, 0), errors='coerce') or 0})

    df_budget = pd.DataFrame(budget_rows)

    print("Processando despesas...")
    df_despesas = pd.read_excel(caminho_planilha, sheet_name="C Despesas")
    df_despesas['VALOR TOTAL'] = pd.to_numeric(df_despesas['VALOR TOTAL'], errors='coerce').fillna(0)

    colunas_tipo = [c for c in df_despesas.columns if 'tipo' in str(c).lower()]
    nome_coluna_tipo = colunas_tipo[0] if colunas_tipo else None
    if nome_coluna_tipo:
        df_despesas.rename(columns={nome_coluna_tipo: 'TIPO'}, inplace=True)
    else:
        df_despesas['TIPO'] = 'Geral'

    # Normaliza valores de TIPO e OBRA
    NORMALIZAR_TIPOS = {
        'MATERIAL':     'Materiais',
        'MÃO DE OBRA':  'Mão de Obra',
        'MAO DE OBRA':  'Mão de Obra',
        'Mao de Obra':  'Mão de Obra',
    }
    df_despesas['TIPO'] = df_despesas['TIPO'].fillna('Geral').str.strip().replace(NORMALIZAR_TIPOS)
    NORMALIZAR_OBRAS = {
        'Creche de Teoflandia': 'Creche Teoflandia',
        'Creche De Teoflandia': 'Creche Teoflandia',
    }
    df_despesas['OBRA'] = df_despesas['OBRA'].replace(NORMALIZAR_OBRAS)

    expenses_agg = df_despesas.groupby(['OBRA', 'ETAPA', 'TIPO'])['VALOR TOTAL'].sum().reset_index()
    expenses_agg.rename(columns={'VALOR TOTAL': 'GASTO_REALIZADO', 'TIPO': 'TIPO_CUSTO'}, inplace=True)

    # Merge em OBRA + ETAPA + TIPO_CUSTO — orçamento já está por tipo, sem deduplicação
    full_report = pd.merge(df_budget, expenses_agg, on=['OBRA', 'ETAPA', 'TIPO_CUSTO'], how='outer')
    full_report[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO']] = (
        full_report[['ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO']].fillna(0)
    )
    full_report['TIPO_CUSTO'] = full_report['TIPO_CUSTO'].fillna('Geral').str.strip()

    full_report['SALDO_ETAPA'] = full_report['ORÇAMENTO_ESTIMADO'] - full_report['GASTO_REALIZADO']

    cols = ['OBRA', 'ETAPA', 'TIPO_CUSTO', 'ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA']
    full_report = full_report[cols]
    
    # ------------------- INTEGRAÇÃO SUPABASE -------------------
    dados_para_inserir = full_report.to_dict(orient="records")

    print("Apagando dados antigos do Supabase...")
    supabase.table(TABELA_SUPABASE).delete().neq("OBRA", "VALOR_INEXISTENTE_PARA_DELETAR_TUDO").execute()

    print("Inserindo novos dados no Supabase...")
    if dados_para_inserir:
         supabase.table(TABELA_SUPABASE).insert(dados_para_inserir).execute()
         print("Sincronização concluída com sucesso!")
    else:
         print("Nenhum dado para inserir.")

if __name__ == "__main__":
    processar_planilha()
