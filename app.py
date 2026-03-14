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
    for idx, (_, row) in enumerate(df_etapas.iterrows()):
        etapa = str(row['Nome da Etapa']).strip()
        for obra, col_mo, col_mat in [
            ('Creche apuarema',   'ESTIM MÃO DE OBRA APUA', 'ESTIM MATERIAL APUA'),
            ('Creche Teoflandia', 'ESTIM MÃO DE OBRA TEOF', 'ESTIM MATERIAL TEOF'),
        ]:
            budget_rows.append({'OBRA': obra, 'ETAPA': etapa,
                                 'TIPO_CUSTO': 'Mão de Obra',
                                 'ORÇAMENTO_ESTIMADO': pd.to_numeric(row.get(col_mo, 0), errors='coerce') or 0,
                                 'ORDEM_ETAPA': idx})
            budget_rows.append({'OBRA': obra, 'ETAPA': etapa,
                                 'TIPO_CUSTO': 'Materiais',
                                 'ORÇAMENTO_ESTIMADO': pd.to_numeric(row.get(col_mat, 0), errors='coerce') or 0,
                                 'ORDEM_ETAPA': idx})

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

    # Preenche ORDEM_ETAPA para linhas de despesa sem orçamento correspondente
    etapa_ordem = df_budget[['ETAPA', 'ORDEM_ETAPA']].drop_duplicates().set_index('ETAPA')['ORDEM_ETAPA']
    full_report['ORDEM_ETAPA'] = full_report['ORDEM_ETAPA'].fillna(
        full_report['ETAPA'].map(etapa_ordem)
    ).fillna(999).astype(int)

    full_report['SALDO_ETAPA'] = full_report['ORÇAMENTO_ESTIMADO'] - full_report['GASTO_REALIZADO']

    # ── Taxa de conclusão por OBRA + ETAPA, da planilha Taxa_Conc ────────────
    df_taxa = pd.read_excel(caminho_planilha, sheet_name="Taxa_Conc", header=0)
    df_taxa.columns = df_taxa.columns.str.strip()
    df_taxa['Nome da Etapa'] = df_taxa['Nome da Etapa'].str.strip()
    df_taxa_melted = pd.melt(
        df_taxa,
        id_vars=['Nome da Etapa'],
        value_vars=['Conc_Apua', 'Conc_Teof'],
        var_name='COL',
        value_name='TAXA_CONCLUSAO',
    )
    df_taxa_melted['OBRA'] = df_taxa_melted['COL'].map({
        'Conc_Apua': 'Creche apuarema',
        'Conc_Teof': 'Creche Teoflandia',
    })
    df_taxa_melted = df_taxa_melted.rename(columns={'Nome da Etapa': 'ETAPA'})[['OBRA', 'ETAPA', 'TAXA_CONCLUSAO']]
    df_taxa_melted['TAXA_CONCLUSAO'] = pd.to_numeric(df_taxa_melted['TAXA_CONCLUSAO'], errors='coerce').fillna(0)

    full_report = pd.merge(full_report, df_taxa_melted, on=['OBRA', 'ETAPA'], how='left')
    full_report['TAXA_CONCLUSAO'] = full_report['TAXA_CONCLUSAO'].fillna(0)

    cols = ['OBRA', 'ETAPA', 'TIPO_CUSTO', 'ORÇAMENTO_ESTIMADO', 'GASTO_REALIZADO', 'SALDO_ETAPA', 'ORDEM_ETAPA', 'TAXA_CONCLUSAO']
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

    # ── Upload de despesas individuais ───────────────────────────────────────
    print("Sincronizando despesas individuais...")
    supabase.table("despesas").delete().neq("OBRA", "VALOR_INEXISTENTE_PARA_DELETAR_TUDO").execute()

    col_desc = next((c for c in df_despesas.columns if 'descri' in str(c).lower()), None)
    desp_col_map = {'OBRA': 'OBRA', 'ETAPA': 'ETAPA', 'TIPO': 'TIPO',
                    'FORNECEDOR': 'FORNECEDOR', 'VALOR TOTAL': 'VALOR_TOTAL', 'DATA': 'DATA'}
    if col_desc:
        desp_col_map[col_desc] = 'DESCRICAO'

    df_desp_upload = df_despesas[list(desp_col_map.keys())].rename(columns=desp_col_map).copy()
    df_desp_upload['DATA'] = pd.to_datetime(df_desp_upload['DATA'], errors='coerce')
    df_desp_upload = df_desp_upload.dropna(subset=['DATA'])
    df_desp_upload['DATA'] = df_desp_upload['DATA'].dt.strftime('%Y-%m-%d')
    df_desp_upload['VALOR_TOTAL'] = pd.to_numeric(df_desp_upload['VALOR_TOTAL'], errors='coerce').fillna(0)

    desp_records = df_desp_upload.where(df_desp_upload.notna(), other=None).to_dict(orient='records')
    if desp_records:
        BATCH = 200
        for i in range(0, len(desp_records), BATCH):
            supabase.table("despesas").insert(desp_records[i:i + BATCH]).execute()
        print(f"Despesas sincronizadas: {len(desp_records)} registros.")

if __name__ == "__main__":
    processar_planilha()
