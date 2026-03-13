import pandas as pd
import os
from supabase import create_client, Client
from dotenv import load_dotenv

def processar_planilha():
    load_dotenv()

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Variáveis de ambiente do Supabase não configuradas no .env")

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    TABELA_SUPABASE = "relatorios"

    caminho_planilha = r"C:\Users\mauri\OneDrive\Controle de obra\CONTROLE MATERIAIS.xlsx"
    
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

    # Custos planejados: Creche apuarema
    creche_budget = df_etapas[['Nome da Etapa', 'TOTAL ESTIMADO']].copy()
    creche_budget['OBRA'] = 'Creche apuarema'
    creche_budget.rename(columns={'TOTAL ESTIMADO': 'ORÇAMENTO_ESTIMADO', 'Nome da Etapa': 'ETAPA'}, inplace=True)

    # Custos planejados: Teoflandia (idênticos aos de apuarema)
    teoflandia_budget = creche_budget.copy()
    teoflandia_budget['OBRA'] = 'Teoflandia'

    # Custos planejados: Casa Busca Vida
    if 'ESTIMATIVA' in df_etapas.columns:
        casa_budget = df_etapas[['Nome da Etapa', 'ESTIMATIVA']].copy()
        casa_budget.rename(columns={'ESTIMATIVA': 'ORÇAMENTO_ESTIMADO', 'Nome da Etapa': 'ETAPA'}, inplace=True)
    else:
        casa_budget = pd.DataFrame(columns=['ETAPA', 'ORÇAMENTO_ESTIMADO'])
    
    casa_budget['OBRA'] = 'Casa Busca Vida'

    df_budget = pd.concat([creche_budget, teoflandia_budget, casa_budget], ignore_index=True)
    df_budget['ORÇAMENTO_ESTIMADO'] = pd.to_numeric(df_budget['ORÇAMENTO_ESTIMADO'], errors='coerce').fillna(0)
    df_budget.dropna(subset=['ETAPA'], inplace=True)

    print("Processando despesas...")
    df_despesas = pd.read_excel(caminho_planilha, sheet_name="C Despesas")
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
