from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime
import pandas as pd
import os

# --- CONFIGURAÇÕES ---
# Série 21082: Inadimplência da carteira de crédito - Pessoas Físicas
URL_INADIMPLENCIA = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.21082/dados?formato=csv"
# Série 20742: Taxa média de juros - Pessoas Físicas
URL_JUROS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.20742/dados?formato=csv"

# Caminhos locais dentro do Docker
PATH_INADIMPLENCIA = "/opt/airflow/data/inadimplencia.csv"
PATH_JUROS = "/opt/airflow/data/juros.csv"
PATH_FINAL = "/opt/airflow/data/credito_consolidado.csv"

TABLE_NAME = "indicadores_credito_bcb"

def extract_data():
    """Baixa os dois datasets do Banco Central"""
    print("Iniciando extração...")
    
    # Baixando Inadimplência
    print(f"Baixando: {URL_INADIMPLENCIA}")
    df_inad = pd.read_csv(URL_INADIMPLENCIA, sep=';', decimal=',')
    df_inad.to_csv(PATH_INADIMPLENCIA, index=False)
    
    # Baixando Juros
    print(f"Baixando: {URL_JUROS}")
    df_juros = pd.read_csv(URL_JUROS, sep=';', decimal=',')
    df_juros.to_csv(PATH_JUROS, index=False)
    
    print("Arquivos extraídos com sucesso.")

def transform_data():
    """Lê, limpa, renomeia e une (JOIN) os dados em uma tabela analítica"""
    print("Iniciando transformação...")
    
    # 1. Leitura
    df_inad = pd.read_csv(PATH_INADIMPLENCIA)
    df_juros = pd.read_csv(PATH_JUROS)
    
    # 2. Renomear colunas para ficar profissional (Business Naming)
    df_inad.rename(columns={'data': 'data_ref', 'valor': 'taxa_inadimplencia'}, inplace=True)
    df_juros.rename(columns={'data': 'data_ref', 'valor': 'taxa_juros_media'}, inplace=True)
    
    # 3. Tratamento de Tipos (Data)
    # O BCB manda data como DD/MM/AAAA, o Banco de Dados prefere AAAA-MM-DD
    df_inad['data_ref'] = pd.to_datetime(df_inad['data_ref'], format='%d/%m/%Y')
    df_juros['data_ref'] = pd.to_datetime(df_juros['data_ref'], format='%d/%m/%Y')
    
    # 4. Merge (JOIN) das tabelas pela data
    # Vamos criar um "Dataset Master" com tudo junto
    df_final = pd.merge(df_inad, df_juros, on='data_ref', how='inner')
    
    # 5. Salvar resultado
    df_final.to_csv(PATH_FINAL, index=False)
    print(f"Transformação concluída! Amostra:\n{df_final.head()}")

def load_to_postgres():
    """Carrega a tabela consolidada no PostgreSQL"""
    print("Iniciando carga no Banco...")
    df = pd.read_csv(PATH_FINAL)
    
    hook = PostgresHook(postgres_conn_id='postgres_default')
    engine = hook.get_sqlalchemy_engine()
    
    df.to_sql(TABLE_NAME, engine, if_exists='replace', index=False)
    print(f"Carga finalizada na tabela '{TABLE_NAME}'. Total de registros: {len(df)}")

# --- DAG ---
default_args = {
    'owner': 'alexandre',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
}

with DAG(
    'bcb_credit_indicators_pipeline',
    default_args=default_args,
    schedule_interval='@monthly', # Dados do BCB costumam ser mensais
    catchup=False,
    description='Pipeline de Indicadores de Risco de Crédito (BCB)'
) as dag:

    t1 = PythonOperator(task_id='extract_bcb_data', python_callable=extract_data)
    t2 = PythonOperator(task_id='transform_merge', python_callable=transform_data)
    t3 = PythonOperator(task_id='load_postgres', python_callable=load_to_postgres)

    t1 >> t2 >> t3